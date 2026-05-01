#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-5174}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

port_free() {
  ! lsof -ti "tcp:$1" >/dev/null 2>&1
}

need python3
need npm
need lsof

if ! port_free "$API_PORT"; then
  echo "API port $API_PORT is already in use. Set API_PORT to another value." >&2
  exit 1
fi

if ! port_free "$WEB_PORT"; then
  echo "Web port $WEB_PORT is already in use. Set WEB_PORT to another value." >&2
  exit 1
fi

if [ ! -d "$ROOT_DIR/web/node_modules" ]; then
  echo "Installing web dependencies..."
  (cd "$ROOT_DIR/web" && npm install)
fi

cleanup() {
  local pids
  pids="$(jobs -pr)"
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting AeroSim 6DOF API on http://$API_HOST:$API_PORT"
(cd "$ROOT_DIR" && python3 -m aerosim6dof.web.serve --host "$API_HOST" --port "$API_PORT") &

echo "Starting AeroSim 6DOF web UI on http://$WEB_HOST:$WEB_PORT"
(cd "$ROOT_DIR/web" && npm run dev -- --host "$WEB_HOST" --port "$WEB_PORT") &

echo
echo "Open http://$WEB_HOST:$WEB_PORT"
wait
