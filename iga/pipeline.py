"""One function that runs fetch -> media -> metrics -> AI -> report. Used by the CLI and the web app."""
import json
import time
from pathlib import Path

from iga import metrics as M
from iga import report


def run(handle, out_root="output", max_posts=100, session_user=None, cookies_from=None,
        videos=False, transcribe=False, use_ai=True, offline=False, tz="Asia/Kolkata",
        home_url=None, step=lambda name, detail=None: None):
    handle = handle.lstrip("@").strip().lower()
    out = Path(out_root) / handle
    out.mkdir(parents=True, exist_ok=True)

    if offline:
        data = json.loads((out / "raw.json").read_text())
    else:
        from iga.fetch import fetch_profile
        step("fetch", "Reading profile")
        data = fetch_profile(handle, out, max_posts, session_user, cookies_from, download_videos=videos,
                             progress=lambda i, n: step("fetch", f"Post {i} of {n}"))

    if videos or transcribe or any(p.get("video_file") for p in data["posts"]):
        from iga.media import analyze_media
        step("media", "Analysing reels")
        data = analyze_media(data, out, transcribe=transcribe)

    step("metrics", "Calculating metrics")
    m = M.compute(data, tz=tz)
    (out / "metrics.json").write_text(json.dumps(m, indent=2, default=str, ensure_ascii=False))

    ai = None
    ai_path = out / "ai_profile.json"
    if use_ai and not offline:
        from iga.profiler import generate_profile
        step("ai", "Writing the audit")
        ai = generate_profile(data, m)
        if ai:
            ai_path.write_text(json.dumps(ai, indent=2, ensure_ascii=False))
    elif ai_path.exists():
        ai = json.loads(ai_path.read_text())

    step("report", "Building report")
    path = report.render(m, ai, out / "report.html", time.strftime("%d %b %Y"),
                         has_transcripts=any(p.get("transcript") for p in data["posts"]),
                         demo=data.get("fetched_at") == "demo", home_url=home_url)
    s = m["summary"]
    index = {"handle": handle, "full_name": m["profile"].get("full_name"), "followers": m["profile"].get("followers"),
             "er": s.get("avg_engagement_rate_pct"), "benchmark": s.get("benchmark"), "posts": s.get("posts_analyzed"),
             "has_ai": bool(ai), "demo": data.get("fetched_at") == "demo", "generated_at": time.time()}
    (out / "index.json").write_text(json.dumps(index))
    return path, m, ai
