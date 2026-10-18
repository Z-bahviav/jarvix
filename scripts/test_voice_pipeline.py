#!/usr/bin/env python3
"""Quick STT smoke test (requires microphone). Run from repo root with venv active."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.config import Settings
from jarvis.voice.capture import MicrophoneRecorder
from jarvis.voice.stt import WhisperSTT


def main() -> None:
    settings = Settings()
    settings.config_dir = ROOT / "config"
    app = settings.load_app_settings()
    rec = MicrophoneRecorder(app.audio)
    stt = WhisperSTT(app.stt)
    print("Recording 2 seconds… speak now.")
    rec.start()
    import time

    time.sleep(2)
    recording = rec.stop()
    text = stt.transcribe(recording.samples, recording.sample_rate)
    print(f"Transcript: {text or '(empty)'}")


if __name__ == "__main__":
    main()
