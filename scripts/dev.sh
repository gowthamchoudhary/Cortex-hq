#!/usr/bin/env bash
# Cortex full-stack dev preview.
#   1. Starts the Flask API server on CORTEX_API_PORT (default 8000).
#   2. Runs the Vite dev server in the foreground (Freebuff injects PORT).
# The Vite dev server proxies /api to the Flask process, so the browser only
# ever talks to one origin.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API_PORT="${CORTEX_API_PORT:-8000}"
HEALTH_URL="http://127.0.0.1:${API_PORT}/api/health"

if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  echo "[cortex] starting API server on :${API_PORT}"
  "$ROOT/.venv/bin/python" "$ROOT/api/server.py" >"$ROOT/.cortex-api.log" 2>&1 &
  API_PID=$!
  for _ in $(seq 1 40); do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
  if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "[cortex] API server failed to start. Last log lines:" >&2
    tail -n 30 "$ROOT/.cortex-api.log" >&2 || true
    kill "$API_PID" >/dev/null 2>&1 || true
    exit 1
  fi
  echo "[cortex] API server healthy (pid ${API_PID})"
fi

export CORTEX_API_URL="http://127.0.0.1:${API_PORT}"
cd "$ROOT/frontend"
echo "[cortex] starting Vite dev server"
exec bun run dev
