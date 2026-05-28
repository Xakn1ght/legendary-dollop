#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ls -lht "$ROOT"/backups/snapshot-*.tar.gz 2>/dev/null | head -30 || echo "No snapshots yet. Run scripts/backup_snapshot.sh"
