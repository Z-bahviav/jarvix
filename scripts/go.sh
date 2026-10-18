#!/bin/zsh
# Run Jarvis without changing ~/.zshrc (works on managed Macs).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

export PATH="$HOME/.local/bin:$PATH"

# Load .env without editing ~/.zshrc
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
else
  echo "Missing .venv — run: $ROOT/scripts/setup.sh"
  exit 1
fi

if [[ "${1:-}" != "check" && "${1:-}" != "chat" && "${1:-}" != "ui" && "${1:-}" != "doctor" ]]; then
  set -- ui "$@"
fi

jarvis doctor 2>/dev/null || true
exec jarvis "$@"
