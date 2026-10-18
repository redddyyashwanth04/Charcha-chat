#!/usr/bin/env bash
# One-command local run (macOS / Linux). Windows: see README, or use WSL / docker compose.
set -e
cd "$(dirname "$0")"
if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; echo "Created backend/.env: add your API key there (or set MOCK_LLM=1)."; fi
[ -d backend/.venv ] || python3 -m venv backend/.venv
backend/.venv/bin/pip install -q -r backend/requirements.txt
[ -d frontend/node_modules ] || (cd frontend && npm install)
(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
BACK=$!
trap "kill $BACK" EXIT
cd frontend && npm run dev
