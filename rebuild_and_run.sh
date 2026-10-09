#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

CREATE_DEFAULT_ADMIN="${CREATE_DEFAULT_ADMIN:-true}"
if [[ "${1:-}" == "--no-admin" ]]; then
  CREATE_DEFAULT_ADMIN="false"
  shift
fi

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi

DB_URL="postgresql://meal_user:meal_password@localhost:5432/meal_db"
DB_CONTAINER_NAME="meal_planner-db-1"

printf '\n==> Rebuilding containers...\n'
docker compose down --remove-orphans

docker compose up --build -d

printf '\n==> Waiting for PostgreSQL health check...\n'
for _ in $(seq 1 30); do
  status="$(docker inspect -f '{{.State.Health.Status}}' "$DB_CONTAINER_NAME" 2>/dev/null || echo 'starting')"
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 2
done

if [[ "$(docker inspect -f '{{.State.Health.Status}}' "$DB_CONTAINER_NAME" 2>/dev/null || echo 'starting')" != "healthy" ]]; then
  echo "PostgreSQL did not become healthy in time." >&2
  docker compose logs --tail 200 db >&2 || true
  exit 1
fi

printf '\n==> Default admin creation flag: %s\n' "$CREATE_DEFAULT_ADMIN"
if [[ "$CREATE_DEFAULT_ADMIN" == "true" ]]; then
  printf '\n==> Ensuring default admin user exists...\n'
  if [[ -n "$PYTHON_BIN" ]]; then
    "$PYTHON_BIN" "$ROOT_DIR/scripts/create_user.py" \
      --database-url "$DB_URL" \
      --username admin \
      --password admin \
      --email admin@example.com \
      --create-table || \
      echo "Admin user already exists or creation was skipped." >&2
  else
    echo "Python interpreter not found; cannot create the admin user." >&2
    exit 1
  fi
else
  printf '\n==> Skipping default admin creation because CREATE_DEFAULT_ADMIN=%s\n' "$CREATE_DEFAULT_ADMIN"
fi

printf '\n==> Containers are up.\n'
printf 'Login: admin / admin\n'
printf 'Frontend: http://localhost:8000\n'
printf 'DB: postgresql://meal_user:meal_password@localhost:5432/meal_db\n'
