#!/usr/bin/env bash
# Start the server and the client together; Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_NAME="justfitting"

cleanup() {
  echo "Stopping JustFitting..."
  [ -n "${SERVER_PID:-}" ] && kill "${SERVER_PID}" 2>/dev/null || true
  [ -n "${CLIENT_PID:-}" ] && kill "${CLIENT_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

conda run -n "${ENV_NAME}" python -m server.src.Server &
SERVER_PID=$!

conda run -n "${ENV_NAME}" python -m client.src.Client &
CLIENT_PID=$!

echo "Server running on http://${JUSTFITTING_SERVER_HOST:-127.0.0.1}:${JUSTFITTING_SERVER_PORT:-5000}"
echo "Client running on http://${JUSTFITTING_CLIENT_HOST:-127.0.0.1}:${JUSTFITTING_CLIENT_PORT:-5500}"
echo "Press Ctrl+C to stop both."

wait
