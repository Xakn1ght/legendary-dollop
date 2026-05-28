#!/usr/bin/env bash
# Run user + admin bots in background with timestamped stdout/stderr capture.
# Structured logs still go to logs/bot.log and logs/admin_bot.log (see setup_logging).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs/runs
STAMP="$(date +%Y%m%d_%H%M%S)"
export PYTHONPATH="${ROOT}/src"

USER_LOG="logs/runs/user_${STAMP}.log"
ADMIN_LOG="logs/runs/admin_${STAMP}.log"

nohup python -u -m app.main >>"$USER_LOG" 2>&1 &
echo $! >"logs/runs/user_${STAMP}.pid"

nohup python -u -m app.admin_main >>"$ADMIN_LOG" 2>&1 &
echo $! >"logs/runs/admin_${STAMP}.pid"

cat >logs/runs/LATEST_RUN.txt <<EOF
run_id=${STAMP}
user_pid=$(cat "logs/runs/user_${STAMP}.pid")
admin_pid=$(cat "logs/runs/admin_${STAMP}.pid")
user_capture=${USER_LOG}
admin_capture=${ADMIN_LOG}
user_structured=logs/bot.log
admin_structured=logs/admin_bot.log
error_files=logs/bot_error.log logs/admin_bot_error.log
EOF

echo "Started. See logs/runs/LATEST_RUN.txt"
cat logs/runs/LATEST_RUN.txt
