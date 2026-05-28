# Source from ~/.bashrc (adjust ASTRO_ROOT to your clone):
#   export ASTRO_ROOT="/root/pasapro/astrobot-worktree"
#   source "$ASTRO_ROOT/scripts/shell_snippet.sh"
#
# Commands: astrobak [label]   astrols   astrorestore (prints instructions)

: "${ASTRO_ROOT:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export PYTHONPATH="$ASTRO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

astrobak() {
  (cd "$ASTRO_ROOT" && ./scripts/backup_snapshot.sh "${1:-cli}")
}

astrols() {
  (cd "$ASTRO_ROOT" && ./scripts/list_snapshots.sh)
}

astrotestbak() {
  (cd "$ASTRO_ROOT" && ./scripts/test_run_with_backup.sh "$@")
}

astrorestore() {
  echo "To restore latest snapshot (overwrites tree; keeps .venv + backups):"
  echo "  cd $ASTRO_ROOT && RESTORE_OK=yes ./scripts/restore_snapshot.sh backups/LATEST.tar.gz"
}
