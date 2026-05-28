#!/usr/bin/env bash
# Restore project from a snapshot created by backup_snapshot.sh.
# Preserves ./.venv and ./backups (existing backups are not deleted by rsync --delete).
# Usage: RESTORE_OK=yes ./scripts/restore_snapshot.sh [path/to/snapshot.tar.gz]
#        Default: backups/LATEST.tar.gz
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE="${1:-"$ROOT/backups/LATEST.tar.gz"}"

if [[ ! -f "$ARCHIVE" ]]; then
  echo "Snapshot not found: $ARCHIVE" >&2
  echo "Available:" >&2
  ls -1t "$ROOT"/backups/snapshot-*.tar.gz 2>/dev/null | head -15 >&2 || true
  exit 1
fi

if [[ "${RESTORE_OK:-}" != "yes" ]]; then
  echo "This will overwrite files under: $ROOT" >&2
  echo "(Keeps ./.venv and ./backups/ as-is.)" >&2
  echo "Archive: $ARCHIVE" >&2
  echo "Run: RESTORE_OK=yes $0 $*" >&2
  exit 2
fi

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

tar -xzf "$ARCHIVE" -C "$TMP"

echo "Restoring from $(basename "$ARCHIVE") ..."
rsync -a --delete "${TMP}/" "${ROOT}/" \
  --exclude '.venv/' \
  --exclude 'backups/'

echo "Restore complete."
