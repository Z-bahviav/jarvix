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
  });

  window.jarvisSetVoiceBusy = (busy) => {
    voice.pause = !!busy;
    if (!voice.recognition) return;
    if (busy) {
      try { voice.recognition.stop(); } catch (_) {}
    } else if (voice.active) {
      try { voice.recognition.start(); } catch (_) {}
    }
  };

  if (!voice.recognition) {
    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
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
      if (e.error === 'no-speech' || e.error === 'aborted') return;
      emit({ action: 'error', message: e.error || 'speech recognition error' });
    };
    rec.onend = () => {
      if (voice.active && !voice.pause) {
        try { rec.start(); } catch (_) {}
      }
    };
    voice.recognition = rec;
  }

  if (!voice.active) {
    voice.active = true;
    voice.pause = false;
    try {
      voice.recognition.start();
      emit({ action: 'mode', enabled: true });
    } catch (err) {
      voice.active = false;
      emit({ action: 'error', message: String(err?.message || err) });
    }
    return;
  }

  voice.active = false;
  voice.pause = false;
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
