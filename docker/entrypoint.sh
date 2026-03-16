#!/bin/sh
set -e

PORT="${APP_PORT:-8000}"

if [ "$APP_ENV" = "development" ]; then
  exec uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" --reload
else
  exec uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
fi
