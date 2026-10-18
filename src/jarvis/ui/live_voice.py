"""Browser live voice mode (Web Speech API) — interim + final transcripts."""

from __future__ import annotations

LIVE_VOICE_TOGGLE_JS = """
() => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    emit({ action: 'error', message: 'Live voice needs Chrome or Edge (Web Speech API).' });
    return;
  }
  const voice = window.__jarvisVoice ?? (window.__jarvisVoice = {
    active: false,
    pause: false,
    recognition: null,
    restartTimer: null,
  });

  const clearRestart = () => {
    if (voice.restartTimer) {
      clearTimeout(voice.restartTimer);
      voice.restartTimer = null;
    }
  };

  const scheduleRestart = (delayMs = 400) => {
    clearRestart();
    if (!voice.active || voice.pause || !voice.recognition) return;
    voice.restartTimer = setTimeout(() => {
      voice.restartTimer = null;
      if (!voice.active || voice.pause) return;
      try {
        voice.recognition.start();
      } catch (err) {
        const msg = String(err?.message || err);
        if (msg.includes('already started')) return;
        scheduleRestart(Math.min(delayMs * 2, 3000));
      }
    }, delayMs);
  };

  window.jarvisSetVoiceBusy = (busy) => {
    voice.pause = !!busy;
    if (!voice.recognition) return;
    clearRestart();
    if (busy) {
      try { voice.recognition.stop(); } catch (_) {}
    } else if (voice.active) {
      scheduleRestart(250);
    }
  };

  if (!voice.recognition) {
    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.lang = window.__jarvisVoiceLang || 'en-US';
    rec.onresult = (event) => {
      let interim = '';
      let finals = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const piece = event.results[i][0].transcript;
        if (event.results[i].isFinal) finals += piece;
        else interim += piece;
      }
      const live = (finals + interim).trim();
      if (live) emit({ action: 'interim', text: live });
      if (finals.trim()) emit({ action: 'final', text: finals.trim() });
    };
    rec.onerror = (e) => {
      const code = e.error || 'unknown';
      if (code === 'no-speech' || code === 'aborted') return;
      if (code === 'network') {
        emit({ action: 'warn', message: code });
        scheduleRestart(600);
        return;
      }
      if (code === 'not-allowed' || code === 'service-not-allowed') {
        voice.active = false;
        clearRestart();
        emit({ action: 'error', message: code });
        return;
      }
      emit({ action: 'warn', message: code });
      scheduleRestart(800);
    };
    rec.onend = () => {
      scheduleRestart(300);
    };
    voice.recognition = rec;
  }

  if (!voice.active) {
    voice.active = true;
    voice.pause = false;
    voice.recognition.lang = window.__jarvisVoiceLang || voice.recognition.lang || 'en-US';
    clearRestart();
    try {
      voice.recognition.start();
      emit({ action: 'mode', enabled: true });
    } catch (err) {
      const msg = String(err?.message || err);
      if (msg.includes('already started')) {
        emit({ action: 'mode', enabled: true });
        return;
      }
      voice.active = false;
      emit({ action: 'error', message: msg });
    }
    return;
  }

  voice.active = false;
  voice.pause = false;
  clearRestart();
  try { voice.recognition.stop(); } catch (_) {}
  emit({ action: 'mode', enabled: false });
}
"""


def parse_live_voice_event(args: object) -> dict:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        return {"action": "error", "message": args}
    if isinstance(args, (list, tuple)) and args:
        return parse_live_voice_event(args[0])
    return {"action": "error", "message": "Unexpected live voice event."}


def speech_api_language(stt_language: str) -> str:
    lang = (stt_language or "en").strip()
    if "-" in lang:
        return lang
    return {"en": "en-US", "es": "es-ES", "fr": "fr-FR", "de": "de-DE"}.get(lang, f"{lang}-{lang.upper()}")
