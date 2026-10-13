#!/bin/zsh
# Double-click to start the audit app and open it in your browser. Close this window to stop it.
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
(sleep 3 && open "http://localhost:8000") &
.venv/bin/python app.py
