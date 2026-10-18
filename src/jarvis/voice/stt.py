from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from jarvis.config import STTSettings

logger = logging.getLogger(__name__)


class WhisperSTT:
    def __init__(self, settings: STTSettings) -> None:
        self._settings = settings
        self._model: WhisperModel | None = None

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            logger.info("Loading Whisper model %s", self._settings.model)
            self._model = WhisperModel(
                self._settings.model,
                device=self._settings.device,
                compute_type=self._settings.compute_type,
            )
        return self._model

    def transcribe(self, samples: np.ndarray, sample_rate: int) -> str:
        if samples.size == 0:
            return ""
        model = self._ensure_model()
        audio = samples.astype(np.float32)
        if sample_rate != 16000:
            # faster-whisper expects 16k; simple decimation if needed
            factor = sample_rate // 16000
            if factor > 1:
                audio = audio[::factor]
        segments, _ = model.transcribe(
            audio,
            language=self._settings.language or None,
            vad_filter=True,
        )
        return " ".join(s.text.strip() for s in segments).strip()

    def transcribe_file(self, path: str | Path) -> str:
        model = self._ensure_model()
        segments, _ = model.transcribe(
            str(path),
            language=self._settings.language or None,
            vad_filter=True,
        )
        return " ".join(s.text.strip() for s in segments).strip()
