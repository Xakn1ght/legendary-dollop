#!/usr/bin/env bash
# Run before risky work: snapshot, then quick import/smoke test.
# Usage: ./scripts/test_run_with_backup.sh [optional pytest args...]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

"$ROOT/scripts/backup_snapshot.sh" "pre-test-run"

if [[ -d .venv ]]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

if [[ -d "$ROOT/src/app" ]]; then
  export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
fi

echo "Smoke: importing app.core.settings ..."
$PY -c "from app.core import settings; print('settings OK')"

if [[ $# -gt 0 ]]; then
  if [[ -x .venv/bin/pytest ]]; then
    .venv/bin/pytest "$@"
  else
    echo "pytest not in .venv; skip (install pytest to use args)" >&2
  fi
fi

echo "Done. Latest snapshot: backups/LATEST.tar.gz -> $(readlink -f backups/LATEST.tar.gz 2>/dev/null || readlink backups/LATEST.tar.gz)"
