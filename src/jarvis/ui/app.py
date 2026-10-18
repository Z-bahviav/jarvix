from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from nicegui import core as nicegui_core
from nicegui import ui

from jarvis.config import Settings
from jarvis.conversation.service import ConversationService, DelegateRequest
from jarvis.jobs.store import JobStore
from jarvis.jobs.worker import JobWorker
from jarvis.llm.factory import build_llm_provider
from jarvis.ui.browser_mic import BROWSER_MIC_JS, parse_mic_event, transcribe_browser_audio
from jarvis.ui.live_voice import (
    LIVE_VOICE_TOGGLE_JS,
    parse_live_voice_event,
    speech_api_language,
)
from jarvis.ui.voice_hud import VOICE_HUD_CSS
from jarvis.voice.capture import MicrophoneRecorder, audio_input_available
from jarvis.voice.stt import WhisperSTT
from jarvis.voice.tts import build_tts

logger = logging.getLogger(__name__)


class JarvisApp:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._app_settings = settings.load_app_settings()
        self._projects = settings.load_projects()
        db_path = settings.resolve_path(self._app_settings.jobs.database_path, self._app_settings)
        self._jobs = JobStore(db_path)
        self._llm = build_llm_provider(settings, self._app_settings.llm)
        self._tts = build_tts(self._app_settings.tts)
        self._stt = WhisperSTT(self._app_settings.stt)
        self._use_server_mic = os.environ.get("JARVIS_VOICE_SERVER_MIC", "").lower() in (
            "1",
            "true",
            "yes",
        )
        self._recorder = (
            MicrophoneRecorder(self._app_settings.audio)
            if self._use_server_mic and audio_input_available()
            else None
        )
        self._pending_delegate: DelegateRequest | None = None
        self._state = "idle"
        self._mic_button: Any = None
        self._browser_mic_active = False
        self._voice_mode_active = False
        self._voice_busy = False
        self._voice_client: Any = None
        self._live_transcript: Any = None
        self._live_transcript_panel: Any = None
        self._last_final_sent: str = ""
        self._voice_pending_text: str = ""
        self._voice_pause_task: asyncio.Task[None] | None = None
        self._voice_pause_seconds = float(self._app_settings.conversation.voice_pause_seconds)
        self._voice_last_speech_at: float = 0.0
        self._hud_phase: str = "idle"
        self._level_decay: float = 0.0
        self._voice_orb_wrap: Any = None
        self._hud_state_label: Any = None
        self._hud_detail_label: Any = None
        self._level_bars: list[Any] = []
        self._chat_container: ui.column | None = None
        self._status_label: ui.label | None = None
        self._input: ui.textarea | None = None
        self._job_panel: ui.column | None = None

        self._conversation = ConversationService(
            self._llm,
            self._app_settings,
            self._projects,
            self._jobs,
            on_job_enqueued=self._on_job_enqueued,
        )
        self._worker = JobWorker(
            settings,
            self._app_settings,
            self._jobs,
            on_complete=self._on_job_complete,
        )

    def _set_state(self, state: str) -> None:
        self._state = state
        if self._status_label:
            self._status_label.set_text(state)

    def _set_voice_phase(self, phase: str, detail: str | None = None, *, force: bool = False) -> None:
        rank = {"idle": 0, "reconnecting": 1, "listening": 2, "thinking": 3, "speaking": 4}
        if not force and rank.get(phase, 0) < rank.get(self._hud_phase, 0):
            if detail is not None and self._hud_detail_label and phase == "listening":
                self._hud_detail_label.set_text(detail)
            return
        self._hud_phase = phase
        titles = {
            "idle": "○ STANDBY",
            "listening": "● LISTENING",
            "thinking": "◐ THINKING",
            "speaking": "◉ SPEAKING",
            "reconnecting": "↻ RECONNECTING",
        }
        default_detail = {
            "idle": "Tap the orb to start a live conversation",
            "listening": "Speak naturally — words appear live below",
            "thinking": "Jarvis is thinking…",
            "speaking": "Jarvis is speaking…",
            "reconnecting": "Reconnecting microphone…",
        }
        if self._hud_state_label:
            self._hud_state_label.set_text(titles.get(phase, phase.upper()))
        if self._hud_detail_label:
            self._hud_detail_label.set_text(detail if detail is not None else default_detail.get(phase, ""))
        if self._voice_orb_wrap:
            self._voice_orb_wrap.classes(
                remove="idle listening thinking speaking reconnecting",
            )
            self._voice_orb_wrap.classes(add=phase if phase in titles else "idle")
        self._set_state(titles.get(phase, phase))

    def _update_level_bars(self, level: float) -> None:
        level = max(0.0, min(1.0, level))
        for i, bar in enumerate(self._level_bars):
            threshold = (i + 1) / max(len(self._level_bars), 1)
            on = level >= threshold * 0.45
            scale = 0.25 + level * 0.9 if on else 0.2
            bar.classes(remove="on", add="on" if on else "")
            bar.style(f"transform: scaleY({scale})")

    def _tick_voice_hud(self) -> None:
        if self._level_decay > 0:
            self._level_decay = max(0.0, self._level_decay - 0.08)
            self._update_level_bars(self._level_decay)
        if not self._voice_mode_active or self._voice_busy:
            return
        if self._hud_phase != "listening":
            return
        if not self._voice_pending_text or self._voice_last_speech_at <= 0:
            return
        remaining = self._voice_pause_seconds - (time.monotonic() - self._voice_last_speech_at)
        if remaining > 0 and self._hud_detail_label:
            secs = int(remaining + 0.99)
            self._hud_detail_label.set_text(f"Pause {secs}s to send · then Jarvis thinks & speaks")

    def _append_message(self, role: str, content: str) -> None:
        if not self._chat_container:
            return
        align = "items-end" if role == "user" else "items-start"
        bg = "bg-blue-100" if role == "user" else "bg-gray-100"
        label = "You" if role == "user" else "Jarvis"
        with self._chat_container:
            with ui.card().classes(f"w-full max-w-2xl {align}"):
                ui.label(label).classes("text-xs text-gray-500")
                ui.markdown(content).classes(f"p-2 rounded {bg}")

    def _on_job_enqueued(self, job_id: int, project: str) -> None:
        self._refresh_jobs()
        self._set_state(f"cursor job {job_id} running ({project})")

    def _on_job_complete(self, job_id: int, status: str, _result: str) -> None:
        asyncio.create_task(self._async_job_complete(job_id, status))

    async def _async_job_complete(self, job_id: int, status: str) -> None:
        self._refresh_jobs()
        line = f"Cursor job {job_id} {status}. Check Cursor for the full answer."
        self._append_message("assistant", line)
        self._set_state("idle")
        self._tts.speak(line)

    def _refresh_jobs(self) -> None:
        if not self._job_panel:
            return
        self._job_panel.clear()
        with self._job_panel:
            ui.label("Cursor jobs").classes("font-bold")
            for job in self._jobs.list_recent(5):
                ui.label(f"#{job.id} {job.status} — {job.payload.get('project', '?')}").classes(
                    "text-sm"
                )

    def _set_voice_busy(self, busy: bool) -> None:
        self._voice_busy = busy
        if self._voice_client:
            self._voice_client.run_javascript(f"window.jarvisSetVoiceBusy && jarvisSetVoiceBusy({str(busy).lower()})")

    def _cancel_voice_pause_timer(self) -> None:
        if self._voice_pause_task and not self._voice_pause_task.done():
            self._voice_pause_task.cancel()
        self._voice_pause_task = None

    def _clear_voice_utterance(self) -> None:
        self._voice_pending_text = ""
        if self._voice_client:
            self._voice_client.run_javascript("window.jarvisClearUtterance && jarvisClearUtterance()")

    def _schedule_voice_send_after_pause(self) -> None:
        self._cancel_voice_pause_timer()
        self._voice_pause_task = asyncio.create_task(self._voice_send_after_pause())

    async def _voice_send_after_pause(self) -> None:
        try:
            await asyncio.sleep(self._voice_pause_seconds)
        except asyncio.CancelledError:
            return
        text = self._voice_pending_text.strip()
        if (
            not text
            or not self._voice_mode_active
            or self._voice_busy
            or text == self._last_final_sent
        ):
            return
        self._last_final_sent = text
        self._voice_pending_text = ""
        self._update_live_transcript("")
        self._clear_voice_utterance()
        await self._send_text(text, auto_confirm=True)

    async def _voice_on_speech(self, text: str) -> None:
        text = text.strip()
        if not text or self._voice_busy or not self._voice_mode_active:
            return
        self._voice_pending_text = text
        self._voice_last_speech_at = time.monotonic()
        self._update_live_transcript(text, listening=True)
        self._set_voice_phase("listening", "Hearing you…", force=True)
        self._level_decay = max(self._level_decay, 0.35)
        self._schedule_voice_send_after_pause()

    def _update_live_transcript(self, text: str, listening: bool = True) -> None:
        if not self._live_transcript:
            return
        if not text.strip():
            self._live_transcript.set_text("")
            if self._live_transcript_panel:
                self._live_transcript_panel.set_visibility(False)
            return
        self._live_transcript.set_text(text)
        if self._live_transcript_panel:
            self._live_transcript_panel.set_visibility(True)

    def _set_voice_mode_visual(self, active: bool) -> None:
        if self._voice_orb_wrap:
            if active:
                self._voice_orb_wrap.classes(add="active-session")
                self._set_voice_phase("listening", "Speak now — live captions below")
            else:
                self._voice_orb_wrap.classes(remove="active-session")
                self._set_voice_phase("idle")
                self._update_live_transcript("")

    async def _send_text(self, text: str, auto_confirm: bool = False) -> None:
        text = text.strip()
        if not text:
            return
        self._cancel_voice_pause_timer()
        self._append_message("user", text)
        self._update_live_transcript("")
        if self._voice_mode_active:
            self._set_voice_phase("thinking", "Sending to Gemini…", force=True)
            self._set_voice_busy(True)
        else:
            self._set_state("thinking")
        try:
            result = await asyncio.to_thread(
                self._conversation.handle_user_text,
                text,
                auto_confirm_delegate=auto_confirm,
            )
            self._append_message("assistant", result.assistant_text)
            self._pending_delegate = result.delegate if result.job_id is None else None
            if result.job_id:
                self._refresh_jobs()
            elif result.assistant_text:
                if self._voice_mode_active:
                    self._set_voice_phase("speaking", "Playing reply…", force=True)
                    self._set_voice_busy(True)
                self._tts.speak(result.assistant_text)
                if self._voice_mode_active:
                    await asyncio.to_thread(self._tts.wait_until_done, 120.0)
            if self._voice_mode_active:
                self._set_voice_phase("listening", "Your turn — speak when ready", force=True)
            else:
                self._set_state("idle")
        except Exception as exc:
            logger.exception("Chat error")
            self._append_message("assistant", f"Error: {exc}")
            self._set_state("listening" if self._voice_mode_active else "error")
        finally:
            if self._voice_mode_active:
                self._set_voice_busy(False)
                self._last_final_sent = ""

    async def _confirm_delegate(self) -> None:
        if not self._pending_delegate:
            return
        req = self._pending_delegate
        self._pending_delegate = None
        self._set_state("thinking")
        result = await asyncio.to_thread(self._conversation.confirm_delegate, req)
        self._append_message("assistant", result.assistant_text)
        self._refresh_jobs()
        self._tts.speak("Sent to Cursor.")
        self._set_state("idle")

    def _set_mic_visual(self, recording: bool) -> None:
        if not self._mic_button:
            return
        if recording:
            self._mic_button.props("color=red icon=mic")
        else:
            self._mic_button.props("color=primary icon=mic")

    def _start_server_recording(self) -> None:
        if not self._recorder:
            self._append_message(
                "assistant",
                "Server microphone unavailable. Use the in-browser mic (default), or install "
                "PortAudio and set JARVIS_VOICE_SERVER_MIC=1.",
            )
            return
        try:
            self._recorder.start()
        except Exception as exc:
            logger.exception("Microphone start failed")
            self._append_message("assistant", f"Microphone error: {exc}")
            self._set_state("error")
            return
        self._set_mic_visual(True)
        self._set_state("listening")

    async def _stop_server_recording_and_transcribe(self) -> None:
        if not self._recorder:
            return
        self._set_mic_visual(False)
        self._set_state("transcribing")
        recording = self._recorder.stop()
        try:
            text = await asyncio.to_thread(
                self._stt.transcribe, recording.samples, recording.sample_rate
            )
        except Exception as exc:
            self._append_message("assistant", f"Transcription failed: {exc}")
            self._set_state("error")
            return
        await self._apply_transcript(text)

    async def _apply_transcript(self, text: str) -> None:
        if not text:
            self._append_message("assistant", "I didn't catch that.")
            self._set_state("idle")
            return
        if self._input:
            self._input.set_value(text)
        if self._app_settings.conversation.require_stt_confirm:
            self._set_state("idle — edit and send")
            self._tts.speak("Review the text and press send.")
        else:
            await self._send_text(text)

    async def _handle_browser_mic(self, event) -> None:
        payload = parse_mic_event(event.args)
        action = payload.get("action")
        if action == "start":
            self._browser_mic_active = True
            self._set_mic_visual(True)
            self._set_state("listening")
            return
        if action == "error":
            self._browser_mic_active = False
            self._set_mic_visual(False)
            message = payload.get("message") or "Microphone permission denied or unavailable."
            self._append_message("assistant", f"Microphone: {message}")
            self._set_state("error")
            return
        if action != "stop":
            return
        self._browser_mic_active = False
        self._set_mic_visual(False)
        self._set_state("transcribing")
        try:
            text = await asyncio.to_thread(transcribe_browser_audio, self._stt, payload)
        except Exception as exc:
            logger.exception("Browser audio transcription failed")
            self._append_message("assistant", f"Transcription failed: {exc}")
            self._set_state("error")
            return
        await self._apply_transcript(text)

    async def _handle_live_voice(self, event) -> None:
        self._voice_client = event.client
        payload = parse_live_voice_event(event.args)
        action = payload.get("action")

        if action == "mode":
            enabled = bool(payload.get("enabled"))
            self._voice_mode_active = enabled
            self._set_voice_mode_visual(enabled)
            if enabled:
                lang = speech_api_language(self._app_settings.stt.language)
                event.client.run_javascript(f"window.__jarvisVoiceLang = '{lang}';")
                pause = int(self._voice_pause_seconds)
                self._set_voice_phase("listening", f"Live mode · {pause}s pause sends your turn")
                self._append_message(
                    "assistant",
                    f"Live conversation on — talk like ChatGPT voice. "
                    f"**{pause}s** of silence sends your line; Jarvis replies and listens again. "
                    "Tap the orb to stop.",
                )
            else:
                self._set_voice_phase("idle", force=True)
                self._set_voice_busy(False)
                self._cancel_voice_pause_timer()
                self._voice_pending_text = ""
                self._update_live_transcript("")
            return

        if not self._voice_mode_active:
            return

        if action == "level":
            if self._voice_mode_active and not self._voice_busy:
                try:
                    self._level_decay = max(self._level_decay, float(payload.get("value", 0)))
                except (TypeError, ValueError):
                    pass
            return

        if action == "error":
            message = payload.get("message") or "Voice recognition error."
            self._append_message(
                "assistant",
                f"Voice mode stopped: {message}. "
                "Check microphone permission and use Chrome/Edge on localhost or HTTPS.",
            )
            self._voice_mode_active = False
            self._set_voice_mode_visual(False)
            event.client.run_javascript(
                "if (window.__jarvisVoice) { window.__jarvisVoice.active = false; }"
            )
            self._set_state("error")
            return

        if action in ("interim", "final", "speech"):
            await self._voice_on_speech(str(payload.get("text") or ""))
            return

    def build(self) -> None:
        ui.add_css(VOICE_HUD_CSS)
        ui.page_title("Jarvis")
        with ui.header().classes("items-center justify-between bg-slate-900 text-cyan-100"):
            ui.label("Jarvis").classes("text-h5")
            self._status_label = ui.label("○ STANDBY")

        with ui.row().classes("w-full gap-4 p-4"):
            with ui.column().classes("flex-grow"):
                if not self._use_server_mic:
                    with ui.card().classes("jarvis-hud w-full p-4 mb-3"):
                        with ui.row().classes("w-full items-center gap-6 flex-wrap"):
                            with ui.element("div").classes("voice-orb-wrap idle") as orb_wrap:
                                self._voice_orb_wrap = orb_wrap
                                ui.element("div").classes("voice-ring r1")
                                ui.element("div").classes("voice-ring r2")
                                ui.element("div").classes("voice-ring r3")
                                ui.element("div").classes("voice-orb-core")
                                orb_wrap.on(
                                    "click",
                                    self._handle_live_voice,
                                    js_handler=LIVE_VOICE_TOGGLE_JS,
                                )
                            with ui.column().classes("flex-grow gap-2 min-w-[200px]"):
                                self._hud_state_label = ui.label("○ STANDBY").classes(
                                    "hud-state-title"
                                )
                                self._hud_detail_label = ui.label(
                                    "Tap the orb to start a live conversation"
                                ).classes("hud-state-detail")
                                with ui.row().classes("gap-1 items-end h-8"):
                                    self._level_bars = [
                                        ui.element("div").classes("level-bar") for _ in range(14)
                                    ]
                self._chat_container = ui.column().classes("w-full gap-2 overflow-auto h-80")
                with ui.card().classes("w-full live-transcript-panel p-3 mb-2") as panel:
                    self._live_transcript_panel = panel
                    panel.set_visibility(False)
                    ui.label("Live caption").classes(
                        "text-xs font-bold uppercase tracking-wide text-cyan-300"
                    )
                    self._live_transcript = ui.label("").classes("text-lg italic text-cyan-50")
                with ui.row().classes("w-full gap-2 items-end"):
                    self._input = (
                        ui.textarea("Message")
                        .classes("flex-grow")
                        .props("outlined autogrow")
                    )

                    async def send_click() -> None:
                        if self._input:
                            await self._send_text(self._input.value or "")
                            self._input.set_value("")

                    ui.button("Send", on_click=send_click).props("color=primary")

                    self._mic_button = ui.button(icon="mic").props("flat round dense")
                    self._mic_button.tooltip("Dictation (record then transcribe)")
                    if self._use_server_mic:
                        async def server_mic_hold() -> None:
                            if self._state == "listening":
                                await self._stop_server_recording_and_transcribe()
                            else:
                                self._start_server_recording()

                        self._mic_button.on("click", server_mic_hold)
                        ui.label("Server mic: click to start/stop").classes("text-xs text-gray-500")
                    else:
                        self._mic_button.on(
                            "click",
                            self._handle_browser_mic,
                            js_handler=BROWSER_MIC_JS,
                        )
                with ui.row().classes("gap-2 items-center"):
                    ui.button("Stop speech", on_click=lambda: self._tts.stop())
                    ui.button("Confirm Cursor task", on_click=self._confirm_delegate)
                    ui.button("New chat", on_click=self._new_chat)

            with ui.column().classes("w-64"):
                ui.label("Settings").classes("font-bold")
                ui.label(f"Model: {self._app_settings.llm.model}").classes("text-sm")
                ui.label(f"Provider: {self._app_settings.llm.provider}").classes("text-sm")
                self._job_panel = ui.column().classes("gap-1")
                self._refresh_jobs()

        self._append_message(
            "assistant",
            "Hello. I'm Jarvis. **Tap the orb** for hands-free voice chat (live captions, "
            "auto-reply). Or type below. Coding tasks can be sent to Cursor when you confirm.",
        )

        ui.timer(0.25, self._tick_voice_hud)

    def _new_chat(self) -> None:
        self._conversation.new_session()
        if self._chat_container:
            self._chat_container.clear()
        self._pending_delegate = None
        self._last_final_sent = ""
        self._voice_pending_text = ""
        self._cancel_voice_pause_timer()
        self._voice_mode_active = False
        self._set_voice_mode_visual(False)
        self._set_voice_busy(False)
        self._append_message("assistant", "Started a new conversation.")
        self._set_state("idle")

    def run(self) -> None:
        self._worker.start()

        def main_page() -> None:
            self.build()

        # Console entry (`jarvis ui`) enables NiceGUI "script mode", which re-runs sys.argv[0]
        # on 404 and crashes with SystemExit. Use an explicit root page instead.
        nicegui_core.script_mode = False

        port = int(os.environ.get("JARVIS_UI_PORT", self._app_settings.ui.port))
        ui.run(
            root=main_page,
            host=self._app_settings.ui.host,
            port=port,
            title="Jarvis",
            reload=False,
            show=_should_open_browser(),
            favicon="🤖",
        )


def _should_open_browser() -> bool:
    explicit = os.environ.get("JARVIS_UI_SHOW", "").strip().lower()
    if explicit in ("1", "true", "yes"):
        return True
    if explicit in ("0", "false", "no"):
        return False
    return bool(os.environ.get("DISPLAY"))


def run_ui(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    JarvisApp(settings).run()
