#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.11+ from python.org or Homebrew."
  exit 1
fi

PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Using Python $PY_VERSION"

if [[ ! -f .venv/bin/activate ]]; then
  echo "Creating .venv ..."
  rm -rf .venv
  if ! python3 -m venv .venv; then
    echo "venv failed. On Ubuntu: sudo apt install python3-venv"
    echo "On macOS: python3 should include venv; try: python3.12 -m venv .venv"
    exit 1
  fi
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip
pip install -e ".[dev,tts]"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — add JARVIS_GEMINI_API_KEY before running jarvis ui"
fi

echo ""
echo "Done. Activate with:"
echo "  source .venv/bin/activate"
echo "Then:"
echo "  jarvis check"
echo "  jarvis ui"
