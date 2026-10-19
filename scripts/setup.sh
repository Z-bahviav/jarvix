#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pick_python() {
  if [[ -n "${JARVIS_PYTHON:-}" ]]; then
    echo "$JARVIS_PYTHON"
    return
  fi
  local c
  for c in python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 13) else 1)' 2>/dev/null; then
        echo "$c"
        return
      fi
    fi
  done
  echo ""
}

PYTHON="$(pick_python)"
if [[ -z "$PYTHON" ]]; then
  echo "Jarvis needs Python 3.11 or 3.12 (faster-whisper/ctranslate2 has no 3.13+ wheels yet)."
  echo "On macOS: brew install python@3.12"
  echo "Then: rm -rf .venv && JARVIS_PYTHON=python3.12 ./scripts/setup.sh"
  exit 1
fi

PY_VERSION="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Using $PYTHON ($PY_VERSION)"

if [[ -d .venv ]]; then
  VENV_PY="$(.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")"
  if [[ "$VENV_PY" != "$PY_VERSION" ]] || ! .venv/bin/python -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 13) else 1)' 2>/dev/null; then
    echo "Removing .venv (was Python ${VENV_PY:-unknown}; need 3.11–3.12) ..."
    rm -rf .venv
  fi
fi

if [[ ! -f .venv/bin/activate ]]; then
  echo "Creating .venv ..."
  if ! "$PYTHON" -m venv .venv; then
    echo "venv failed. On Ubuntu: sudo apt install python3.12-venv"
    echo "On macOS: brew install python@3.12 && python3.12 -m venv .venv"
    exit 1
  fi
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Corporate pip.conf often sets a private index that times off VPN. Override when needed:
#   JARVIS_USE_PUBLIC_PYPI=1 ./scripts/setup.sh
PIP_INSTALL_ARGS=()
if [[ "${JARVIS_USE_PUBLIC_PYPI:-}" == "1" ]]; then
  PIP_INSTALL_ARGS=(-i https://pypi.org/simple)
  echo "Using public PyPI (JARVIS_USE_PUBLIC_PYPI=1)"
fi

pip install "${PIP_INSTALL_ARGS[@]}" --upgrade pip
pip install "${PIP_INSTALL_ARGS[@]}" -e ".[dev,tts]"

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
