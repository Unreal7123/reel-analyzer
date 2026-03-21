#!/usr/bin/env bash
# setup.sh — First-time local setup for ReelScan
# Usage: bash setup.sh

set -e

echo ""
echo "┌─────────────────────────────────────────┐"
echo "│  ReelScan — Local Setup                 │"
echo "└─────────────────────────────────────────┘"
echo ""

# ── Check Python version ──────────────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python || echo "")
if [ -z "$PYTHON" ]; then
  echo "❌  Python 3.11+ is required. Install from https://python.org"
  exit 1
fi
PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓  Python $PY_VER found"

# ── Check Node version ────────────────────────────────────────────────────────
NODE=$(command -v node || echo "")
if [ -z "$NODE" ]; then
  echo "❌  Node 18+ is required. Install from https://nodejs.org"
  exit 1
fi
NODE_VER=$(node -v)
echo "✓  Node $NODE_VER found"

# ── Backend setup ─────────────────────────────────────────────────────────────
echo ""
echo "── Setting up backend ───────────────────────"
cd backend
$PYTHON -m venv .venv
source .venv/bin/activate 2>/dev/null || . .venv/Scripts/activate 2>/dev/null || true
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
playwright install chromium
echo "✓  Backend dependencies installed"

# Optional spaCy
echo ""
read -p "Install spaCy NLP model? (improves detection accuracy) [y/N]: " install_spacy
if [[ "$install_spacy" =~ ^[Yy]$ ]]; then
  python -m spacy download en_core_web_sm
  echo "✓  spaCy model installed"
fi

cd ..

# ── Frontend setup ────────────────────────────────────────────────────────────
echo ""
echo "── Setting up frontend ──────────────────────"
cd frontend
npm install --silent
echo "✓  Frontend dependencies installed"
cd ..

# ── Copy env file ─────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✓  .env file created from .env.example"
fi

echo ""
echo "┌─────────────────────────────────────────┐"
echo "│  Setup complete!                        │"
echo "│                                         │"
echo "│  Start backend:                         │"
echo "│    cd backend && source .venv/bin/activate│"
echo "│    uvicorn main:app --reload --port 8000│"
echo "│                                         │"
echo "│  Start frontend (new terminal):         │"
echo "│    cd frontend && npm run dev           │"
echo "│                                         │"
echo "│  Or use Docker:                         │"
echo "│    docker compose up --build            │"
echo "└─────────────────────────────────────────┘"
echo ""
