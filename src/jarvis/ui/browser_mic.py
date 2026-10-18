from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path

from jarvis.voice.stt import WhisperSTT

logger = logging.getLogger(__name__)

# Toggle recording in the browser; emits a dict to the server on start/stop/error.
BROWSER_MIC_JS = """
async () => {
  const state = window.__jarvisMic ?? (window.__jarvisMic = { recorder: null, chunks: [], stream: null });
  try {
    if (!state.recorder || state.recorder.state === 'inactive') {
      if (!navigator.mediaDevices?.getUserMedia) {
        emit({ action: 'error', message: 'This browser does not expose microphone APIs.' });
        return;
      }
      state.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      state.chunks = [];
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';
      state.recorder = new MediaRecorder(state.stream, { mimeType: mime });
      state.recorder.ondataavailable = (e) => {
        if (e.data?.size) state.chunks.push(e.data);
      };
      state.recorder.start();
      emit({ action: 'start' });
      return;
    }
    await new Promise((resolve) => {
      state.recorder.onstop = async () => {
        try {
          const blob = new Blob(state.chunks, { type: state.recorder.mimeType || 'audio/webm' });
          const buffer = await blob.arrayBuffer();
          const bytes = new Uint8Array(buffer);
          let binary = '';
          const chunk = 0x8000;
          for (let i = 0; i < bytes.length; i += chunk) {
            binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
          }
          const b64 = btoa(binary);
          emit({ action: 'stop', mime: blob.type || 'audio/webm', audio: b64 });
        } catch (err) {
          emit({ action: 'error', message: String(err?.message || err) });
        } finally {
          state.stream?.getTracks().forEach((t) => t.stop());
          state.stream = null;
          state.recorder = null;
          state.chunks = [];
          resolve();
        }
      };
      state.recorder.stop();
    });
  } catch (err) {
    emit({ action: 'error', message: String(err?.message || err) });
  }
}
"""


def parse_mic_event(args: object) -> dict:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        return {"action": "error", "message": args}
    if isinstance(args, (list, tuple)) and args:
        return parse_mic_event(args[0])
    return {"action": "error", "message": "Unexpected microphone event payload."}


def transcribe_browser_audio(stt: WhisperSTT, payload: dict) -> str:
    audio_b64 = payload.get("audio")
    if not audio_b64:
        return ""
    mime = str(payload.get("mime") or "audio/webm")
    suffix = ".webm" if "webm" in mime else ".ogg" if "ogg" in mime else ".bin"
    raw = base64.b64decode(audio_b64)
    if not raw:
        return ""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        path = Path(tmp.name)
        tmp.write(raw)
    try:
        logger.info("Transcribing browser audio (%d bytes, %s)", len(raw), mime)
        return stt.transcribe_file(path)
    finally:
        path.unlink(missing_ok=True)
