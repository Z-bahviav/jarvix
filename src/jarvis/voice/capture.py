from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from jarvis.config import AudioSettings


@dataclass
class Recording:
    samples: np.ndarray
    sample_rate: int


def audio_input_available() -> bool:
    try:
        import sounddevice as sd  # noqa: F401
    except OSError:
        return False
    return True


def _import_sounddevice():
    try:
        import sounddevice as sd
    except OSError as exc:
        raise RuntimeError(
            "Microphone support needs PortAudio. "
            "Ubuntu/Debian: sudo apt install libportaudio2 portaudio19-dev"
        ) from exc
    return sd


class MicrophoneRecorder:
    def __init__(self, settings: AudioSettings) -> None:
        self._settings = settings
        self._stream = None
        self._chunks: list[np.ndarray] = []

    def start(self) -> None:
        sd = _import_sounddevice()
        self._chunks = []
        sr = self._settings.sample_rate

        def callback(indata, frames, time_info, status) -> None:
            if status:
                pass
            self._chunks.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=sr,
            channels=self._settings.channels,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> Recording:
        if self._stream:
            sd = _import_sounddevice()
            self._stream.stop()
            self._stream.close()
            self._stream = None
        sr = self._settings.sample_rate
        if not self._chunks:
            return Recording(samples=np.zeros((0,), dtype=np.float32), sample_rate=sr)
        samples = np.concatenate(self._chunks, axis=0).flatten()
        max_samples = self._settings.max_record_seconds * sr
        if len(samples) > max_samples:
            samples = samples[:max_samples]
        return Recording(samples=samples, sample_rate=sr)
