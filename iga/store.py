"""Keep reports across restarts on free hosting by committing each audit's small JSON files to GitHub.

Needs GITHUB_TOKEN (fine-grained, Contents: read & write on this repo only) and GITHUB_REPO (owner/name).
The server re-renders every output/<handle>/raw.json on boot, so a saved audit comes back after a restart.
"""
import base64
import os
from pathlib import Path

import requests

FILES = ("raw.json", "ai_profile.json")


def enabled():
    return bool(os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPO"))


def save(handle, out_dir: Path):
    if not enabled():
        return False
    repo, token = os.environ["GITHUB_REPO"], os.environ["GITHUB_TOKEN"]
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    for name in FILES:
        f = out_dir / name
        if not f.exists():
            continue
        url = f"https://api.github.com/repos/{repo}/contents/output/{handle}/{name}"
        current = requests.get(url, headers=headers, timeout=20)
        body = {"message": f"Save audit for @{handle}", "content": base64.b64encode(f.read_bytes()).decode(),
                "branch": os.environ.get("GITHUB_BRANCH", "main")}
        if current.status_code == 200:
            body["sha"] = current.json()["sha"]
        r = requests.put(url, headers=headers, json=body, timeout=30)
        r.raise_for_status()
    return True
