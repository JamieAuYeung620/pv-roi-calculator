#!/bin/zsh
set -euo pipefail

PROJECT="/Users/jamie/Desktop/Diss/pv-roi-calculator"
PORT=8501
URL="http://127.0.0.1:${PORT}"
LOG="/tmp/pv_streamlit.log"
PIDFILE="/tmp/pv_streamlit.pid"

cd "$PROJECT"
source .venv/bin/activate

# If already healthy, just open it.
if curl -fsS "${URL}/_stcore/health" >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi

# If pid file exists but process is dead, clean it.
if [[ -f "$PIDFILE" ]]; then
  PID="$(cat "$PIDFILE" || true)"
  if [[ -n "${PID:-}" ]] && ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PIDFILE"
  fi
fi

# Start only if not already listening.
if ! lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  nohup python3 -m streamlit run app.py \
    --server.port "$PORT" \
    --server.address 127.0.0.1 \
    --server.headless true \
    --browser.gatherUsageStats false \
    >"$LOG" 2>&1 &
  echo $! > "$PIDFILE"
fi

# Wait for health endpoint
for i in {1..60}; do
  if curl -fsS "${URL}/_stcore/health" >/dev/null 2>&1; then
    open "$URL"
    exit 0
  fi
  sleep 0.5
done

echo "Streamlit failed to start. Log:"
tail -n 80 "$LOG"
exit 1
