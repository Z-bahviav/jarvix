#!/usr/bin/env bash
# End-to-end test: browser-style WebM blob -> decode -> Whisper (same path as jarvis ui mic).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=/dev/null
source .venv/bin/activate

SAMPLE="$ROOT/data/test-voice/jfk.flac"
WEBM="$ROOT/data/test-voice/jfk.webm"
mkdir -p "$ROOT/data/test-voice"

if [[ ! -f "$SAMPLE" ]]; then
  echo "Downloading Whisper JFK sample..."
  curl -fsSL -o "$SAMPLE" \
    "https://github.com/openai/whisper/raw/main/tests/jfk.flac"
fi

echo "Encoding sample as WebM (browser MediaRecorder format)..."
ffmpeg -y -loglevel error -i "$SAMPLE" -c:a libopus "$WEBM"

python <<'PY'
import base64
import sys
from pathlib import Path

from jarvis.config import Settings
from jarvis.ui.browser_mic import parse_mic_event, transcribe_browser_audio
from jarvis.voice.decode import decode_audio_file
from jarvis.voice.stt import WhisperSTT

webm = Path("data/test-voice/jfk.webm")

raw = webm.read_bytes()
print(f"1) WebM size: {len(raw)} bytes")

samples = decode_audio_file(webm, sampling_rate=16000)
print(f"2) Decoded samples: {len(samples)} @ 16kHz ({len(samples)/16000:.2f}s)")

settings = Settings()
stt = WhisperSTT(settings.load_app_settings().stt)
payload = {
    "action": "stop",
    "mime": "audio/webm",
    "audio": base64.b64encode(raw).decode("ascii"),
}
text = transcribe_browser_audio(stt, payload)
print(f"3) Transcript: {text!r}")

if not text or len(text) < 10:
    print("FAIL: transcript too short", file=sys.stderr)
    sys.exit(1)

# Mic event parsing (UI wire format)
ev = parse_mic_event({"action": "stop", "mime": "audio/webm", "audio": payload["audio"]})
assert ev["action"] == "stop"
print("4) parse_mic_event OK")
print("PASS voice flow (WebM -> decode -> Whisper)")
PY
