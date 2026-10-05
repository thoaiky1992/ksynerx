#!/bin/sh
set -e

echo "Starting FastAPI Application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}
