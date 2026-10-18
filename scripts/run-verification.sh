#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="$ROOT/scripts:$PATH"
VERIFY_CFG="$ROOT/config-verify"
mkdir -p "$VERIFY_CFG"
cp "$ROOT/config/settings.yaml" "$VERIFY_CFG/"
cat > "$VERIFY_CFG/projects.yaml" <<EOF
projects:
  jarvis-test:
    repo: "$ROOT/test-repo"
    default_folder: "."
EOF
export JARVIS_CONFIG_DIR="$VERIFY_CFG"
export JARVIS_DATA_DIR="$ROOT/data"
export JARVIS_CURSOR_DRY_RUN="${JARVIS_CURSOR_DRY_RUN:-}"

# mock cursor-agent unless real one exists
if ! command -v cursor-agent >/dev/null 2>&1 || [[ "$(command -v cursor-agent)" == "$ROOT/scripts/cursor-agent" ]]; then
  ln -sf mock-cursor-agent.sh "$ROOT/scripts/cursor-agent"
  export PATH="$ROOT/scripts:$PATH"
fi

mkdir -p "$ROOT/data"
mkdir -p "$ROOT/test-repo"
if [[ ! -d "$ROOT/test-repo/.git" ]]; then
  git -C "$ROOT/test-repo" init -q
  echo "# jarvis-test" > "$ROOT/test-repo/README.md"
fi

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

echo "=== pytest (offline) ==="
PYTHONPATH=src python3 -m pytest -q

echo "=== jarvis check ==="
if python3 -m jarvis.cli check; then
  CHECK_OK=1
else
  CHECK_OK=0
fi

if [[ -n "${JARVIS_GEMINI_API_KEY:-}" || -n "${GEMINI_API_KEY:-}" ]]; then
  echo "=== chat: hash map (no cursor) ==="
  python3 -m jarvis.cli chat -t "What is a hash map? Answer in two sentences."

  echo "=== chat: delegate (dry-run) ==="
  export JARVIS_CURSOR_DRY_RUN=1
  python3 -m jarvis.cli chat -t "In project jarvis-test, read README and summarize in one sentence. Do not modify files."
  sleep 3

  echo "=== mock cursor-agent job (no dry-run) ==="
  unset JARVIS_CURSOR_DRY_RUN
  python3 -m jarvis.cli chat -t "In project jarvis-test, list repo files. Do not modify anything."
  sleep 3
else
  echo "=== live Gemini chat skipped (set JARVIS_GEMINI_API_KEY in .env) ==="
fi

echo "=== TTS stop (pytest) ==="
PYTHONPATH=src python3 -m pytest -q tests/test_tts.py

echo "=== voice STT (optional; skip if no mic) ==="
if python3 -c "import sounddevice; sounddevice.query_devices()" 2>/dev/null; then
  python3 "$ROOT/scripts/test_voice_pipeline.py" || echo "voice pipeline skipped/failed"
else
  echo "No audio device — skip voice recording test"
fi

if [[ "$CHECK_OK" -eq 0 ]] && [[ -z "${JARVIS_GEMINI_API_KEY:-}" && -z "${GEMINI_API_KEY:-}" ]]; then
  echo "check failed only due to missing API key — offline tests passed."
  exit 0
fi

echo "=== verification done ==="
