from __future__ import annotations

import logging
import platform
import subprocess
import threading
from abc import ABC, abstractmethod

from jarvis.config import TTSSettings

logger = logging.getLogger(__name__)


class TTSEngine(ABC):
    @abstractmethod
    def speak(self, text: str) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        pass


class Pyttsx3TTS(TTSEngine):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engine = None

    def _get_engine(self):
        import pyttsx3

        if self._engine is None:
            self._engine = pyttsx3.init()
        return self._engine

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        with self._lock:
            engine = self._get_engine()
            engine.stop()
            engine.say(text)
            engine.runAndWait()

    def stop(self) -> None:
        with self._lock:
            if self._engine:
                self._engine.stop()


class PrintTTS(TTSEngine):
    def speak(self, text: str) -> None:
        print(f"[Jarvis TTS] {text}")


class InterruptibleTTS(TTSEngine):
    def __init__(self, inner: TTSEngine, settings: TTSSettings) -> None:
        self._inner = inner
        self._settings = settings
        self._thread: threading.Thread | None = None

    def speak(self, text: str) -> None:
        if self._settings.interrupt_on_new_message:
            self.stop()
        if len(text) > self._settings.max_chars:
            text = text[: self._settings.max_chars] + "…"
        self._thread = threading.Thread(target=self._inner.speak, args=(text,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._inner.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def wait_until_done(self, timeout: float | None = None) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)


def build_tts(settings: TTSSettings) -> TTSEngine:
    engine = settings.engine.lower()
    inner: TTSEngine
    if engine == "none":
        inner = PrintTTS()
    elif engine == "pyttsx3":
        try:
            inner = Pyttsx3TTS()
        except Exception:
            inner = PrintTTS()
    else:
        try:
            import pyttsx3  # noqa: F401

            inner = Pyttsx3TTS()
        except Exception:
            if platform.system() == "Darwin":
                inner = _MacSayTTS()
            else:
                inner = PrintTTS()
    return InterruptibleTTS(inner, settings)


class _MacSayTTS(TTSEngine):
    def speak(self, text: str) -> None:
        if not text.strip():
            return
        subprocess.run(["say", text[:4000]], check=False)

    def stop(self) -> None:
        subprocess.run(["killall", "say"], check=False)
