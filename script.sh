#!/usr/bin/env bash
#
# Run the RAY frontend locally.
#
# Usage:
#   bash script.sh
#
# Starts the Next.js dev server on http://localhost:3000 and stops it
# cleanly (kills the server process) whenever this script exits — whether
# you press Ctrl+C, close the terminal, or it exits any other way.

set -euo pipefail

PORT=3000
WEB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/apps/web"

cleanup() {
  echo ""
  echo "Stopping RAY dev server..."
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  # Catch any stray process still bound to the port (e.g. a child the
  # PID above didn't cover).
  local stray
  stray=$(lsof -ti:"$PORT" 2>/dev/null || true)
  if [[ -n "$stray" ]]; then
    kill -9 $stray 2>/dev/null || true
  fi
  echo "Stopped."
}
trap cleanup EXIT INT TERM

# Free the port if something is already listening on it.
existing=$(lsof -ti:"$PORT" 2>/dev/null || true)
if [[ -n "$existing" ]]; then
  echo "Port $PORT is in use — stopping the existing process first..."
  kill -9 $existing 2>/dev/null || true
  sleep 1
fi

cd "$WEB_DIR"

if [[ ! -d node_modules ]]; then
  echo "Installing dependencies..."
  npm install
fi

echo "Starting RAY at http://localhost:$PORT (Ctrl+C to stop)"
npm run dev -- -p "$PORT" &
SERVER_PID=$!

wait "$SERVER_PID"
