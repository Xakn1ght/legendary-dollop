#!/usr/bin/env bash
# Install optional git hooks (snapshot after commit — off unless you export ASTROBOT_SNAPSHOT_ON_COMMIT=1).
# Usage: ./scripts/setup_git_hooks.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GIT_DIR="$(git -C "$ROOT" rev-parse --absolute-git-dir)"
HOOKDIR="$GIT_DIR/hooks"
mkdir -p "$HOOKDIR"
POST_COMMIT="$HOOKDIR/post-commit"

cat > "$POST_COMMIT" <<'EOF'
#!/usr/bin/env bash
# Optional full-tree snapshot after each commit (large tar — opt-in only).
if [[ "${ASTROBOT_SNAPSHOT_ON_COMMIT:-}" == "1" ]]; then
  ROOT="$(git rev-parse --show-toplevel)"
  exec "$ROOT/scripts/backup_snapshot.sh" "git-commit-$(git rev-parse --short HEAD)"
fi
exit 0
EOF
chmod +x "$POST_COMMIT"
echo "Installed: $POST_COMMIT"
echo "Enable with: export ASTROBOT_SNAPSHOT_ON_COMMIT=1  (add to ~/.bashrc if you want it always)"
