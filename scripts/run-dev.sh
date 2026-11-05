#!/usr/bin/env bash
# Evolve — local development launcher
# Usage: ./scripts/run-dev.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

docker compose up -d db

cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -e ".[dev]"
else
  . .venv/bin/activate
fi

echo "==> API: http://localhost:8000/docs"
echo "==> UI:  cd frontend && npm install && npm run dev"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
