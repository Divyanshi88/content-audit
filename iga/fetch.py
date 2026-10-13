"""Step 1: pull profile + every post's metadata (and optionally the reel videos) from Instagram.

Uses instaloader. Instagram blocks anonymous scraping, so a logged-in session is needed:
  - `instaloader --login YOUR_BURNER_ACCOUNT` once in a terminal (creates a session file), or
  - log into instagram.com in Firefox/Chrome and pass --cookies-from firefox|chrome.
Use a secondary/burner account, not the company's main account.
"""
import json
import os
import re
import time
from pathlib import Path

import instaloader


def make_loader(session_user=None, cookies_from=None):
    L = instaloader.Instaloader(
        download_pictures=False, download_videos=False, download_video_thumbnails=False,
        download_geotags=False, download_comments=False, save_metadata=False,
        compress_json=False, quiet=True, max_connection_attempts=3,
    )
    if os.environ.get("IG_SESSIONID"):
        # server mode: cookies copied from a logged-in browser, passed as env vars
        cookies = {"sessionid": os.environ["IG_SESSIONID"],
                   "csrftoken": os.environ.get("IG_CSRFTOKEN", "missing"),
                   "ds_user_id": os.environ.get("IG_DS_USER_ID", "")}
        L.load_session(os.environ.get("IG_USERNAME", "session"), cookies)
    elif session_user:
        L.load_session_from_file(session_user)
    elif cookies_from:
        # instaloader >= 4.12 can import a logged-in browser session
        from instaloader.__main__ import import_session  # type: ignore
        import_session(cookies_from, L, None)
    return L


def _hashtags(text):
    return re.findall(r"#(\w+)", text or "")


def _mentions(text):
    return re.findall(r"@([\w.]+)", text or "")


def fetch_profile(handle, out_dir: Path, max_posts=200, session_user=None, cookies_from=None,
                  download_videos=False, sleep=1.5, progress=None):
    handle = handle.lstrip("@").strip().lower()
    L = make_loader(session_user, cookies_from)
    p = instaloader.Profile.from_username(L.context, handle)

    profile = {
        "username": p.username,
        "full_name": p.full_name,
        "biography": p.biography,
        "external_url": p.external_url,
        "followers": p.followers,
        "following": p.followees,
        "total_posts": p.mediacount,
        "is_verified": p.is_verified,
        "is_business": p.is_business_account,
        "business_category": p.business_category_name,
        "profile_pic_url": p.profile_pic_url,
    }

    videos_dir = out_dir / "videos"
    if download_videos:
        videos_dir.mkdir(parents=True, exist_ok=True)

    posts = []
    for i, post in enumerate(p.get_posts()):
        if i >= max_posts:
            break
        caption = post.caption or ""
        typename = post.typename  # GraphImage / GraphVideo / GraphSidecar
        row = {
            "shortcode": post.shortcode,
            "url": f"https://www.instagram.com/p/{post.shortcode}/",
            "date_utc": post.date_utc.isoformat(),
            "type": {"GraphImage": "image", "GraphVideo": "reel", "GraphSidecar": "carousel"}.get(typename, typename),
            "is_video": post.is_video,
            "likes": post.likes,
            "comments": post.comments,
            "views": post.video_view_count if post.is_video else None,
            "plays": getattr(post, "video_play_count", None) if post.is_video else None,
            "duration_s": post.video_duration if post.is_video else None,
            "caption": caption,
            "hashtags": _hashtags(caption),
            "mentions": _mentions(caption),
            "tagged_users": list(post.tagged_users or []),
            "is_sponsored": post.is_sponsored,
            "is_pinned": getattr(post, "is_pinned", False),
            "location": post.location.name if post.location else None,
            "accessibility_caption": post.accessibility_caption,
            "video_file": None,
        }
        if download_videos and post.is_video:
            target = videos_dir / f"{post.shortcode}.mp4"
            if not target.exists():
                L.context.get_and_write_raw(post.video_url, str(target))
            row["video_file"] = str(target)
        posts.append(row)
        print(f"  [{i + 1}] {row['date_utc'][:10]} {row['type']:8} likes={row['likes']} comments={row['comments']}")
        if progress:
            progress(i + 1, min(max_posts, profile["total_posts"] or max_posts))
        time.sleep(sleep)  # be gentle; aggressive scraping gets the session rate-limited

    data = {"profile": profile, "posts": posts, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data
