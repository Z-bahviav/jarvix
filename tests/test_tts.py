from __future__ import annotations

import threading
import time

from jarvis.config import TTSSettings
from jarvis.voice.tts import InterruptibleTTS, PrintTTS


class SlowTTS(PrintTTS):
    def speak(self, text: str) -> None:
        time.sleep(0.3)
        super().speak(text)


def test_stop_speech_interrupts() -> None:
    settings = TTSSettings(interrupt_on_new_message=True)
    tts = InterruptibleTTS(SlowTTS(), settings)
    tts.speak("first")
    time.sleep(0.05)
    tts.stop()
    tts.speak("second")
    tts.stop()
