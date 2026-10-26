#!/bin/sh
set -e
PORT="${PORT:-10000}"

# Start a tiny HTTP server so Render sees an open port immediately.
python -m http.server "$PORT" --bind 0.0.0.0 >/dev/null 2>&1 &

# Hand off to the official Hermes entrypoint so s6 supervision still works.
exec /opt/hermes/docker/entrypoint-dispatch.sh "$@"
