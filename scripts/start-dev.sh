#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# AgriVision AI - start the backend and the frontend together (macOS / Linux).
#
#   ./scripts/start-dev.sh
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "The virtual environment was not found at $VENV_PYTHON." >&2
  echo "Create it first: python3.10 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

cleanup() {
  echo ""
  echo "Stopping AgriVision AI..."
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "${WEB_PID:-}" ]] && kill "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Starting the FastAPI backend on http://localhost:8000"
(
  cd "$ROOT/backend"
  "$VENV_PYTHON" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
API_PID=$!

echo "==> Starting the Vite dev server on http://localhost:5173"
(
  cd "$ROOT/frontend"
  npm run dev
) &
WEB_PID=$!

echo ""
echo "Backend docs: http://localhost:8000/docs"
echo "Frontend:     http://localhost:5173"
echo "Press Ctrl+C to stop both."

wait
