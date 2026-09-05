#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "[stop] Root: $ROOT"

# Kill local Flask instances started with `flask run`
FLASK_PIDS=$(pgrep -f "flask run" || true)
if [ -n "$FLASK_PIDS" ]; then
  echo "[stop] Killing Flask processes: $FLASK_PIDS"
  kill $FLASK_PIDS || true
fi

# Kill Vite / Node dev server processes
VITE_PIDS=$(pgrep -f "node.*vite" || true)
if [ -z "$VITE_PIDS" ]; then
  VITE_PIDS=$(pgrep -f "vite" || true)
fi
if [ -n "$VITE_PIDS" ]; then
  echo "[stop] Killing Vite/node processes: $VITE_PIDS"
  kill $VITE_PIDS || true
fi

# Kill any tail process streaming the logs from tmp/log
TAIL_PIDS=$(pgrep -f "tail -n +1 -f tmp/log" || true)
if [ -n "$TAIL_PIDS" ]; then
  echo "[stop] Killing tail processes: $TAIL_PIDS"
  kill $TAIL_PIDS || true
fi

# Bring down docker compose services (db). Try plugin first, fall back to legacy.
if command -v docker >/dev/null 2>&1; then
  echo "[stop] Bringing down Docker Compose services..."
  docker compose down || docker-compose down || true
fi

echo "[stop] Done."
