#!/usr/bin/env bash
# Nightly DB backup with rotation. Run by astrobyte-backup.timer.
# Output: backups/auto/backup_YYYYMMDD_HHMMSS/ — keeps the newest 14.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/backups/auto"
KEEP=14

mkdir -p "$OUT"
cd "$ROOT"
"$ROOT/.venv/bin/python" scripts/backup_db.py --output-dir "$OUT"

# Rotate: delete oldest beyond $KEEP (dirs sort lexically = chronologically).
mapfile -t dirs < <(ls -1d "$OUT"/backup_* 2>/dev/null | sort)
count=${#dirs[@]}
if (( count > KEEP )); then
  for old in "${dirs[@]:0:count-KEEP}"; do
    rm -rf "$old"
    echo "pruned: $old"
  done
fi

echo "backup complete: $(ls -1d "$OUT"/backup_* | tail -1)"
