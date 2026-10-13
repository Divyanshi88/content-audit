# Instagram Content Analysis Engine

Give it an Instagram handle and you get a full content audit for that account, as a single HTML report you can send to the client.

```
handle ──► fetch (instaloader) ──► reels download ──► Whisper transcripts + frames
                                                        │
          report.html ◄── Claude bio/audit ◄── metrics ◄┘
```

| Step | Module | What it does |
|---|---|---|
| 1 | `iga/fetch.py` | Profile + every post: date/time, type (reel/carousel/image), likes, comments, views, duration, caption, hashtags, mentions, location. Can also download the reel `.mp4` files |
| 2 | `iga/media.py` | Transcribes reel audio locally with faster-whisper (Hindi/Hinglish/English) and grabs hook/mid/end frames with ffmpeg |
| 3 | `iga/metrics.py` | Engagement rate, like/comment rate, comments per 100 likes, reel views as % of followers, posts per week, gaps, consistency score, best weekday/hour, format mix, hashtag performance, 30-day trend, viral posts, top and bottom posts, benchmark band |
| 4 | `iga/profiler.py` | Claude (`claude-opus-5-5`) reads the metrics, captions, transcripts and frames, then writes the bio, content pillars, voice, audience guess, hooks, what works and what doesn't, scores, recommendations, 10 reel ideas and a pitch summary |
| 5 | `iga/report.py` | Self-contained HTML dashboard with charts. Supports dark mode and mobile |

## Web app

```bash
.venv/bin/python app.py        # http://localhost:8000
```
Type a handle, watch the progress, and the report opens at `/r/<handle>`. Recent audits are listed on the home page.
Configuration is through env vars, listed at the top of [app.py](app.py). On a server, set `IG_SESSIONID`, `IG_CSRFTOKEN` and `IG_DS_USER_ID` from a logged-in burner browser session (DevTools → Application → Cookies → instagram.com). Also set `ANTHROPIC_API_KEY`, and set `ACCESS_CODE` so strangers can't run audits on your accounts.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # needed for the AI bio/audit (step 4)
```

**Instagram login is required.** Instagram blocks anonymous scraping (it returns 401). Use a **secondary/burner account**, never a client's or your main account. Pick one:

```bash
# A) log into instagram.com in Firefox/Chrome, then:
.venv/bin/python analyze.py nike --cookies-from firefox
# B) create a session file once (asks for the password in your terminal):
.venv/bin/instaloader --login my_burner_account
.venv/bin/python analyze.py nike --session-user my_burner_account
```

## Usage

```bash
# metrics + AI audit (fast; no video download)
.venv/bin/python analyze.py <handle> --cookies-from firefox --max-posts 100
# full: download reels, transcribe, send frames to Claude
.venv/bin/python analyze.py <handle> --cookies-from firefox --videos --transcribe
# re-analyse already-downloaded data without hitting Instagram again
.venv/bin/python analyze.py <handle> --offline
# try it without Instagram (FAKE demo data)
.venv/bin/python make_demo_data.py && .venv/bin/python analyze.py demo_brand --offline --no-ai
```

Output goes to `output/<handle>/`: `report.html`, `raw.json`, `metrics.json`, `ai_profile.json`, `videos/`, `frames/`, `transcripts.json`.

## Limits (tell clients this up front)
- **Not available from public data:** shares, saves, reach, impressions, follower demographics, story stats. Only the account owner sees these, in Insights or through the Graph API. Engagement rate here means (likes + comments) ÷ followers.
- Some accounts hide like counts. Those posts show −1 or 0 likes.
- Instagram rate-limits heavy scraping. Keep `--max-posts` reasonable (100–200), don't run many handles back-to-back on one account, and expect an occasional "wait a few minutes".
- Scraping goes against Instagram's Terms of Service. Use a burner account and only analyse public business accounts. For clients who sign on, connect their account through the official **Instagram Graph API** to get shares, saves and reach.
