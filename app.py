"""Web app: type a handle, get the audit.

  .venv/bin/python app.py            -> http://localhost:8000

Env vars:
  ANTHROPIC_API_KEY   Claude key for the written audit (without it you get metrics only)
  IG_SESSIONID        sessionid cookie of a logged-in burner Instagram account
  IG_CSRFTOKEN        csrftoken cookie of the same session
  IG_DS_USER_ID       ds_user_id cookie of the same session
  ACCESS_CODE         if set, people must enter this code to run a new audit
  DATA_DIR            where reports are stored (default: output)
  IG_COOKIES_FROM     local alternative: firefox|chrome|safari, reuse that browser's instagram.com login
  IG_SESSION_USER     local alternative: username saved with `instaloader --login`
  MAX_POSTS           posts to read per account (default: 80)
  VIDEO_ANALYSIS      1 = download reels, transcribe audio, send frames to Claude (slower; for laptops)

For personal use put these in a .env file next to this script (see .env.example).
"""
import json
import os
import queue
import re
import threading
import time
import traceback
import uuid
from pathlib import Path


def _load_dotenv(path=Path(__file__).with_name(".env")):
    """Read KEY=value lines from .env (local/personal use); real env vars win."""
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

import hashlib
import hmac

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from iga import pipeline
from iga.report import STYLE, compact

DATA = Path(os.environ.get("DATA_DIR", "output"))
MAX_POSTS = int(os.environ.get("MAX_POSTS", "80"))
HANDLE_RE = re.compile(r"^[a-z0-9._]{1,30}$")
STEPS = [("fetch", "Reading posts"), ("media", "Analysing reels"), ("metrics", "Calculating metrics"),
         ("ai", "Writing the audit"), ("report", "Building report")]

app = FastAPI(title="Content Audit")
COOKIE = "ca_team"
OPEN_PATHS = {"/login", "/healthz"}


def _token(code):
    return hmac.new(code.encode(), b"content-audit-team", hashlib.sha256).hexdigest()


@app.middleware("http")
async def team_only(request: Request, call_next):
    """When ACCESS_CODE is set, every page and API needs the team code (remembered in a cookie)."""
    code = os.environ.get("ACCESS_CODE")
    if not code or request.url.path in OPEN_PATHS:
        return await call_next(request)
    if hmac.compare_digest(request.cookies.get(COOKIE, ""), _token(code)):
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Enter the team code first."}, status_code=401)
    return RedirectResponse(f"/login?next={request.url.path}", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(next: str = "/", error: int = 0):
    nxt = next if next.startswith("/") and not next.startswith("//") else "/"
    return LOGIN.replace("/*STYLE*/", STYLE).replace("__NEXT__", json.dumps(nxt)[1:-1].replace('"', "&quot;")) \
        .replace("__ERR__", "That code isn't right. Ask your team lead for the current code." if error else "")


@app.post("/login")
def login(code: str = Form(""), next: str = Form("/")):
    real = os.environ.get("ACCESS_CODE", "")
    nxt = next if next.startswith("/") and not next.startswith("//") else "/"
    if not real or not hmac.compare_digest(code.strip(), real):
        return RedirectResponse(f"/login?error=1&next={nxt}", status_code=303)
    resp = RedirectResponse(nxt, status_code=303)
    resp.set_cookie(COOKIE, _token(real), max_age=60 * 60 * 24 * 90, httponly=True, samesite="lax",
                    secure=os.environ.get("RENDER") is not None)
    return resp
jobs: dict[str, dict] = {}
work: "queue.Queue[str]" = queue.Queue()


def friendly_error(e):
    name, msg = type(e).__name__, str(e)
    if not any(os.environ.get(k) for k in ("IG_SESSIONID", "IG_SESSION_USER", "IG_COOKIES_FROM")):
        return "Instagram login isn't set up on this server yet. Add IG_SESSIONID (see README)."
    if name == "ProfileNotExistsException":
        return "This account doesn't exist. Check the spelling of the handle."
    if name in ("PrivateProfileNotFollowedException",) or "private" in msg.lower():
        return "This account is private. Only public accounts can be audited."
    if name in ("LoginRequiredException", "LoginException") or "401" in msg or "login" in msg.lower():
        return ("Instagram refused the request. The Instagram session has expired or is rate-limited. "
                "Wait a few minutes, or update IG_SESSIONID with a fresh login.")
    if "429" in msg or "wait a few minutes" in msg.lower():
        return "Instagram is rate-limiting requests. Try again in 10–15 minutes."
    return f"Something went wrong: {msg[:200]}"


def worker():
    while True:
        jid = work.get()
        job = jobs[jid]
        job["status"] = "running"

        def step(name, detail=None):
            job["step"], job["detail"] = name, detail

        try:
            full = os.environ.get("VIDEO_ANALYSIS") == "1"
            pipeline.run(job["handle"], DATA, max_posts=MAX_POSTS, home_url="/", step=step,
                         videos=full, transcribe=full,
                         session_user=os.environ.get("IG_SESSION_USER"), cookies_from=os.environ.get("IG_COOKIES_FROM"))
            job["status"], job["url"] = "done", f"/r/{job['handle']}"
        except Exception as e:  # noqa: BLE001 - surface any failure to the user
            traceback.print_exc()
            job["status"], job["error"] = "error", friendly_error(e)
        finally:
            job["finished"] = time.time()
            work.task_done()


class AuditRequest(BaseModel):
    handle: str


@app.post("/api/audit")
def start_audit(req: AuditRequest):
    handle = req.handle.strip().lstrip("@").lower()
    handle = re.sub(r"^(https?://)?(www\.)?instagram\.com/", "", handle).strip("/").split("/")[0].split("?")[0]
    if not HANDLE_RE.match(handle):
        raise HTTPException(400, "Enter a valid Instagram handle, like @nike.")
    for jid, j in jobs.items():
        if j["handle"] == handle and j["status"] in ("queued", "running"):
            return {"job": jid}
    jid = uuid.uuid4().hex[:10]
    jobs[jid] = {"handle": handle, "status": "queued", "step": None, "detail": None, "created": time.time()}
    work.put(jid)
    return {"job": jid}


@app.get("/api/jobs/{jid}")
def job_status(jid: str):
    if jid not in jobs:
        raise HTTPException(404, "Unknown job")
    j = dict(jobs[jid])
    j["position"] = sum(1 for k, x in jobs.items() if x["status"] == "queued" and x["created"] < j["created"])
    return j


@app.get("/api/reports")
def list_reports():
    rows = []
    for f in DATA.glob("*/index.json"):
        try:
            rows.append(json.loads(f.read_text()))
        except Exception:  # noqa: BLE001
            pass
    rows.sort(key=lambda r: (r.get("demo", False), -r.get("generated_at", 0)))
    return rows


@app.get("/api/config")
def config():
    return {"team_locked": bool(os.environ.get("ACCESS_CODE")),
            "instagram_ready": any(os.environ.get(k) for k in ("IG_SESSIONID", "IG_SESSION_USER", "IG_COOKIES_FROM")),
            "ai_ready": bool(os.environ.get("ANTHROPIC_API_KEY")), "max_posts": MAX_POSTS}


@app.get("/r/{handle}")
def show_report(handle: str):
    path = DATA / handle.lower() / "report.html"
    if not HANDLE_RE.match(handle.lower()) or not path.exists():
        raise HTTPException(404, "No report for this handle yet")
    return FileResponse(path, media_type="text/html")


@app.get("/healthz")
def health():
    return JSONResponse({"ok": True})


@app.get("/", response_class=HTMLResponse)
def home():
    return HOME.replace("/*STYLE*/", STYLE).replace("__STEPS__", json.dumps(STEPS))


HOME = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Content Audit</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<style>/*STYLE*/
.home{max-width:720px}
.intro{padding-block:72px 32px}
.intro h1{font-size:40px;letter-spacing:-.035em;line-height:1.1;text-wrap:balance}
.intro p{color:var(--ink-2);font-size:16px;max-width:34em;margin:14px 0 0}
form{display:grid;gap:10px;margin-top:28px}
.field{display:flex;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding-left:14px;transition:border-color .15s}
.field:focus-within{border-color:var(--ink-3)}
.field span{color:var(--ink-3);font:500 16px var(--mono)}
.field input{flex:1;min-width:0;border:0;background:transparent;color:var(--ink);font:400 16px var(--sans);padding:14px 12px 14px 4px;outline:none}
.row{display:flex;gap:10px;flex-wrap:wrap}.row .field{flex:1 1 260px}
button{font:500 15px var(--sans);background:var(--ink);color:var(--bg);border:0;border-radius:10px;padding:0 22px;min-height:50px;cursor:pointer;flex:0 0 auto}
button:disabled{opacity:.5;cursor:default}button:focus-visible,.field input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.code .field input{font-family:var(--mono)}
.hint{font-size:13px;color:var(--ink-3)}
.err{color:var(--bad);font-size:14px;min-height:1px}
.progress{border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:6px 18px;margin-top:20px}
.progress .head{display:flex;justify-content:space-between;padding-block:12px;border-bottom:1px solid var(--line-2);font-size:14px}
.progress .head b{font-weight:500}.progress .head span{color:var(--ink-3);font:12.5px var(--mono)}
.st{display:grid;grid-template-columns:20px 1fr auto;gap:10px;align-items:center;padding:10px 0;font-size:14px;color:var(--ink-3)}
.st .dot{width:8px;height:8px;border-radius:50%;background:var(--line);justify-self:center}
.st.active{color:var(--ink)}.st.active .dot{background:var(--accent);box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 20%,transparent);animation:pulse 1.2s ease-in-out infinite}
.st.done{color:var(--ink-2)}.st.done .dot{background:var(--good)}
.st small{font:12px var(--mono);color:var(--ink-3)}
@keyframes pulse{50%{opacity:.4}}@media (prefers-reduced-motion:reduce){.st.active .dot{animation:none}}
.setup{margin-top:20px;padding:12px 16px;border:1px solid var(--line);border-radius:10px;background:var(--warn-bg);color:var(--warn);font-size:13.5px}
.recent{padding-block:40px 0}
.recent a.row-link{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:16px;align-items:center;padding:14px 0;border-bottom:1px solid var(--line-2);text-decoration:none}
.recent a.row-link:hover .h{text-decoration:underline;text-decoration-color:var(--ink-3)}
.recent .h{font-weight:500}.recent .sub{font-size:13px;color:var(--ink-3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.recent .f{font:13px var(--mono);color:var(--ink-2);text-align:right}
.empty{color:var(--ink-3);font-size:14px;padding:14px 0}
@media (max-width:560px){.intro{padding-block:44px 24px}.intro h1{font-size:30px}button{width:100%}.recent a.row-link{grid-template-columns:minmax(0,1fr) auto}.recent .f.d{display:none}}
</style></head><body><div class="wrap home">
<nav class="nav"><a class="mark" href="/">Content Audit <span>/ Instagram</span></a><span>Public data only</span></nav>

<div class="intro">
  <h1>Audit any Instagram account</h1>
  <p>Enter a public handle. We read its recent posts and return engagement, posting patterns and a written content audit, usually in two to three minutes.</p>
  <form id="f" autocomplete="off">
    <div class="row">
      <label class="field" for="handle"><span>@</span><input id="handle" name="handle" placeholder="brandname" spellcheck="false" autocapitalize="off" required></label>
      <button id="go" type="submit">Run audit</button>
    </div>
    <div class="err" id="err" role="alert"></div>
  </form>
  <div id="setup"></div>
  <div class="progress" id="prog" hidden aria-live="polite">
    <div class="head"><b id="pTitle">Auditing</b><span id="pTime">0:00</span></div>
    <div id="steps"></div>
  </div>
</div>

<section class="recent">
  <p class="eyebrow">Recent audits</p>
  <div id="list"><div class="empty">Loading…</div></div>
</section>
<p class="foot" style="margin-top:40px">Uses likes, comments, views, post times and captions that anyone can see on Instagram. Shares, saves, reach and audience demographics are private to the account owner and are not part of the audit.</p>
</div>
<script>
const STEPS = __STEPS__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => n == null ? '–' : n >= 1e6 ? (n/1e6).toFixed(1).replace(/\.0$/,'')+'M' : n >= 1e3 ? (n/1e3).toFixed(1).replace(/\.0$/,'')+'K' : String(n);
let cfg = {};

async function loadConfig(){
  cfg = await fetch('/api/config').then(r=>r.json());
  const miss = [];
  if (!cfg.team_locked) miss.push('a team code (ACCESS_CODE), so anyone with the link can use this app');
  if (!cfg.instagram_ready) miss.push('an Instagram session (IG_SESSIONID)');
  if (!cfg.ai_ready) miss.push('a Claude API key (ANTHROPIC_API_KEY), so audits will contain metrics only');
  $('setup').innerHTML = miss.length ? `<div class="setup">Setup needed: ${miss.map(esc).join(' and ')}.</div>` : '';
}
async function loadList(){
  const rows = await fetch('/api/reports').then(r=>r.json());
  $('list').innerHTML = rows.length ? rows.map(r => `<a class="row-link" href="/r/${esc(r.handle)}">
      <div style="min-width:0"><div class="h">@${esc(r.handle)}${r.demo ? ' <span class="pill average" style="vertical-align:1px">Sample</span>' : ''}</div><div class="sub">${esc(r.full_name || '')}</div></div>
      <div class="f">${fmt(r.followers)} followers<br><span class="pill ${esc(r.benchmark)}" style="margin:4px 0 0">${(r.er ?? 0).toFixed(2)}% ER</span></div>
      <div class="f d">${new Date(r.generated_at*1000).toLocaleDateString(undefined,{day:'numeric',month:'short'})}</div></a>`).join('')
    : '<div class="empty">No audits yet. Run the first one above.</div>';
}
function renderSteps(job){
  const idx = STEPS.findIndex(s => s[0] === job.step);
  $('steps').innerHTML = STEPS.filter(s => s[0] !== 'media' || job.step === 'media').map(([k, label]) => {
    const i = STEPS.findIndex(s => s[0] === k);
    const state = job.status === 'done' || i < idx ? 'done' : i === idx ? 'active' : '';
    const detail = state === 'active' && job.detail && job.detail !== label ? job.detail : '';
    return `<div class="st ${state}"><span class="dot"></span><span>${esc(label)}</span><small>${esc(detail)}</small></div>`;
  }).join('');
}
let timer;
async function poll(jid, handle){
  const t0 = Date.now();
  $('prog').hidden = false; $('pTitle').textContent = 'Auditing @' + handle;
  clearInterval(timer);
  timer = setInterval(() => { const s = Math.floor((Date.now()-t0)/1000); $('pTime').textContent = Math.floor(s/60)+':'+String(s%60).padStart(2,'0'); }, 1000);
  while (true){
    const j = await fetch('/api/jobs/'+jid).then(r=>r.json()).catch(()=>null);
    if (j){
      if (j.status === 'queued') { $('steps').innerHTML = `<div class="st active"><span class="dot"></span><span>Waiting in queue</span><small>${j.position} ahead</small></div>`; }
      else renderSteps(j);
      if (j.status === 'done'){ clearInterval(timer); location.href = j.url; return; }
      if (j.status === 'error'){ clearInterval(timer); $('prog').hidden = true; $('err').textContent = j.error; $('go').disabled = false; return; }
    }
    await new Promise(r => setTimeout(r, 2000));
  }
}
$('f').addEventListener('submit', async e => {
  e.preventDefault(); $('err').textContent = '';
  const handle = $('handle').value.trim().replace(/^@/, '');
  if (!handle) return;
  $('go').disabled = true;
  const res = await fetch('/api/audit', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({handle})});
  const body = await res.json().catch(()=>({}));
  if (!res.ok){ $('err').textContent = body.detail || 'Could not start the audit.'; $('go').disabled = false; return; }
  poll(body.job, handle.toLowerCase());
});
loadConfig(); loadList();
</script></body></html>"""


LOGIN = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Content Audit</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<style>/*STYLE*/
.gate{max-width:400px;padding-block:96px 40px}
.gate h1{font-size:26px}.gate p{color:var(--ink-2);margin:10px 0 24px}
.gate form{display:grid;gap:10px}
.gate input{font:16px var(--mono);background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:14px;outline:none}
.gate input:focus{border-color:var(--ink-3)}
.gate button{font:500 15px var(--sans);background:var(--ink);color:var(--bg);border:0;border-radius:10px;min-height:50px;cursor:pointer}
.gate button:focus-visible,.gate input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.gate .err{color:var(--bad);font-size:14px}
</style></head><body><div class="wrap">
<nav class="nav"><span class="mark">Content Audit <span>/ Instagram</span></span><span>Team only</span></nav>
<div class="gate">
  <h1>Enter the team code</h1>
  <p>This tool is for our team. You only need to enter the code once on each device.</p>
  <form method="post" action="/login">
    <input type="hidden" name="next" value="__NEXT__">
    <label for="code" class="eyebrow" style="margin:0">Team code</label>
    <input id="code" name="code" type="password" autocomplete="current-password" autofocus required>
    <button type="submit">Continue</button>
    <div class="err" role="alert">__ERR__</div>
  </form>
</div></div></body></html>"""


def render_bundled_reports():
    """Re-render stored reports on boot so they pick up the current template."""
    for raw in DATA.glob("*/raw.json"):
        try:
            pipeline.run(raw.parent.name, DATA, offline=True, home_url="/")
        except Exception:  # noqa: BLE001
            traceback.print_exc()


render_bundled_reports()
threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
