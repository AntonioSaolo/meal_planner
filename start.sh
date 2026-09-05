#!/usr/bin/env bash
set -euo pipefail

# Simple local start script for development:
# - starts postgres via docker-compose (service: db)
# - creates/uses Python venv at .venv, installs backend deps
# - runs `flask init-db` (safe to run repeatedly)
# - starts backend (Flask) and frontend (Vite) and tails logs

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "[start] Root: $ROOT"

echo "[start] Starting PostgreSQL (docker compose service: db)..."
docker compose up -d db

# ensure .env exists
if [ ! -f "$ROOT/.env" ]; then
  if [ -f "$ROOT/src/brackend/.env.example" ]; then
    cp "$ROOT/src/brackend/.env.example" "$ROOT/.env"
    echo "[start] Copied src/brackend/.env.example -> .env (edit if needed)"
  else
    echo "[start] Warning: .env not found and no example present"
  fi
fi

# create virtualenv if missing
if [ ! -d "$ROOT/.venv" ]; then
  echo "[start] Creating Python virtualenv at .venv..."
  (python3 -m venv "$ROOT/.venv")
fi

PYTHON="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"
FLASK_CMD="$ROOT/.venv/bin/flask"

echo "[start] Installing backend Python dependencies..."
"$PIP" install -r src/brackend/requirements.txt

echo "[start] Initializing database (flask init-db)..."
export FLASK_APP=src.brackend.main
"$FLASK_CMD" init-db || true

mkdir -p tmp/log

echo "[start] Starting backend (Flask) on :8000..."
"$FLASK_CMD" run --host 0.0.0.0 --port 8000 > tmp/log/backend.log 2>&1 &
BACKEND_PID=$!

echo "[start] Starting frontend (Vite dev server) on default port..."
cd src/frontend
# Check Node version and warn if it's older than recommended (Node >=18)
NODE_VERSION_STR=$(node -v 2>/dev/null || true)
if [ -n "$NODE_VERSION_STR" ]; then
  NODE_MAJOR=$(echo "$NODE_VERSION_STR" | sed 's/^v//' | cut -d. -f1)
else
  NODE_MAJOR=0
fi
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "[start] Warning: Node $NODE_VERSION_STR detected. Vite requires Node >=18. Using a small polyfill, but please upgrade Node for best results."
fi
if [ ! -d node_modules ]; then
  npm install
fi
npm run dev > "$ROOT/tmp/log/frontend.log" 2>&1 &
FRONTEND_PID=$!
cd "$ROOT"

echo "[start] Backend PID: $BACKEND_PID"
echo "[start] Frontend PID: $FRONTEND_PID"
echo "[start] Tailing logs (backend/frontend). Press Ctrl-C to stop and kill both processes."

trap 'echo "[start] Stopping..."; kill $BACKEND_PID $FRONTEND_PID || true; exit 0' INT TERM

tail -n +1 -f tmp/log/backend.log tmp/log/frontend.log &
TAIL_PID=$!

wait $TAIL_PID
