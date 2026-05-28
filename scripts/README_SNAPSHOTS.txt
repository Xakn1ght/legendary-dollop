Snapshot / rollback (repo root = directory containing src/app/, config/, scripts/)

Application code lives under src/app/ (import name is still "app").

Run bots / tools:
  export PYTHONPATH="$(pwd)/src"
  python -m app.main
  # or: pip install -e .   then   python -m app.main

Alembic:
  PYTHONPATH=src alembic -c config/alembic.ini current

Snapshots:
  ./scripts/backup_snapshot.sh my-label
  ./scripts/list_snapshots.sh
  RESTORE_OK=yes ./scripts/restore_snapshot.sh backups/LATEST.tar.gz

Before tests + backup:
  ./scripts/test_run_with_backup.sh

Optional git snapshot (slow):
  ./scripts/setup_git_hooks.sh
  export ASTROBOT_SNAPSHOT_ON_COMMIT=1

Shell shortcuts: scripts/shell_snippet.sh
