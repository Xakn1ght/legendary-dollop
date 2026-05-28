#!/usr/bin/env bash
# Create a full project snapshot (excluding .venv and ./backups) for easy rollback.
# Usage: ./scripts/backup_snapshot.sh [label]
# Example after an edit: ./scripts/backup_snapshot.sh after-payment-fix
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LABEL="${1:-manual}"
STAMP="$(date +%Y%m%d-%H%M%S)"
SAFE_LABEL="$(echo "$LABEL" | tr -cs 'a-zA-Z0-9._-' '_' | sed 's/^_//;s/_$//')"
mkdir -p backups

ARCHIVE="backups/snapshot-${STAMP}-${SAFE_LABEL}.tar.gz"
echo "Creating $ARCHIVE"

tar -czf "$ARCHIVE" \
  --exclude='./.venv' \
  --exclude='./backups' \
  --exclude='__pycache__' \
  --exclude='*/__pycache__' \
  .

ln -sfn "$(basename "$ARCHIVE")" backups/LATEST.tar.gz

# Keep the 25 most recent snapshots (by mtime), delete older
mapfile -t ALL < <(find backups -maxdepth 1 -name 'snapshot-*.tar.gz' -printf '%T@ %p\n' | sort -nr | cut -d' ' -f2-)
if (( ${#ALL[@]} > 25 )); then
  for f in "${ALL[@]:25}"; do
    rm -f "$f"
    echo "Rotated out old backup: $f"
  done
fi

echo "OK: $(ls -lh "$ARCHIVE")"
