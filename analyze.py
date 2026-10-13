#!/usr/bin/env python3
"""Instagram handle -> full content audit.

  python analyze.py <handle> --cookies-from firefox --videos --transcribe
  python analyze.py <handle> --session-user my_burner_account
  python analyze.py <handle> --offline            # re-run analysis on already-downloaded data

Output: output/<handle>/report.html (+ raw.json, metrics.json, ai_profile.json, videos/, frames/)
For the web version run: python app.py
"""
import argparse

from iga.pipeline import run


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("handle")
    ap.add_argument("--max-posts", type=int, default=150)
    ap.add_argument("--session-user", help="instaloader session (run `instaloader --login USER` once first)")
    ap.add_argument("--cookies-from", choices=["firefox", "chrome", "safari", "edge", "brave"],
                    help="reuse a browser where you're logged into instagram.com")
    ap.add_argument("--videos", action="store_true", help="download reel videos")
    ap.add_argument("--transcribe", action="store_true", help="transcribe reels with Whisper (needs --videos)")
    ap.add_argument("--no-ai", action="store_true", help="skip the Claude bio/audit")
    ap.add_argument("--offline", action="store_true", help="reuse output/<handle>/raw.json, don't hit Instagram")
    ap.add_argument("--tz", default="Asia/Kolkata")
    ap.add_argument("--out", default="output")
    a = ap.parse_args()

    path, m, _ = run(a.handle, a.out, a.max_posts, a.session_user, a.cookies_from, a.videos, a.transcribe,
                     use_ai=not a.no_ai, offline=a.offline, tz=a.tz,
                     step=lambda name, detail=None: print(f"[{name}] {detail or ''}"))
    s = m["summary"]
    print(f"\nDone -> {path}\n  ER {s['avg_engagement_rate_pct']}% ({s['benchmark']}), "
          f"{s['posts_per_week']} posts/week, best {s['best_weekday']} {s['best_hour']}:00")


if __name__ == "__main__":
    main()
