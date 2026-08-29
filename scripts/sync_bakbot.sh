#!/usr/bin/env bash
# Pull a fresh read-only copy of the LIVE sales bot into /opt/incoming/bakbot.
# ONE WAY ONLY: that box is live with real customers - never push to it.
# Big runtime junk (backups, logs, exports, media) is skipped.
set -euo pipefail

REMOTE="root@178.105.162.32"
PORT=52217
SRC="/root/5a06b8e65bdb/bakbot/"
DEST="/opt/incoming/bakbot/"

rsync -az --delete --info=stats1 \
  -e "ssh -p $PORT" \
  --exclude 'backups/' \
  --exclude 'user_logs/' \
  --exclude 'result.json' \
  --exclude '*.sqlite3-wal' \
  --exclude '*.sqlite3-shm' \
  --exclude '__pycache__/' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  "$REMOTE:$SRC" "$DEST"

echo
echo "sales_bot.py: $(wc -l < ${DEST}sales_bot.py) lines"
