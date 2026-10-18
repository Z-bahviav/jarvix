from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from nicegui import core as nicegui_core
from nicegui import ui

from jarvis.config import Settings
from jarvis.conversation.service import ConversationService, DelegateRequest
from jarvis.jobs.store import JobStore
from jarvis.jobs.worker import JobWorker
from jarvis.llm.factory import build_llm_provider
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
        self._recorder = (
            MicrophoneRecorder(self._app_settings.audio) if audio_input_available() else None
        )
        self._pending_delegate: DelegateRequest | None = None
        self._state = "idle"
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
            self._status_label.set_text(f"Status: {state}")

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

    async def _send_text(self, text: str, auto_confirm: bool = False) -> None:
        text = text.strip()
        if not text:
            return
        self._append_message("user", text)
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
            else:
                self._tts.speak(result.assistant_text)
            self._set_state("idle")
        except Exception as exc:
            logger.exception("Chat error")
            self._append_message("assistant", f"Error: {exc}")
            self._set_state("error")

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

    def _start_recording(self) -> None:
        if not self._recorder:
            self._append_message(
                "assistant",
                "Microphone unavailable (install PortAudio: "
                "`sudo apt install libportaudio2` on Linux). Text chat still works.",
            )
            return
        self._recorder.start()
        self._set_state("listening")

    async def _stop_recording_and_transcribe(self) -> None:
        if not self._recorder:
            return
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

    def build(self) -> None:
        ui.page_title("Jarvis")
        with ui.header().classes("items-center justify-between"):
            ui.label("Jarvis").classes("text-h5")
            self._status_label = ui.label("Status: idle")

        with ui.row().classes("w-full gap-4 p-4"):
            with ui.column().classes("flex-grow"):
                self._chat_container = ui.column().classes("w-full gap-2 overflow-auto h-96")
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

                    mic = ui.button(icon="mic")

                    async def mic_down() -> None:
                        self._start_recording()

                    async def mic_up() -> None:
                        await self._stop_recording_and_transcribe()

                    mic.on("mousedown", mic_down)
                    mic.on("mouseup", mic_up)
                    mic.on("mouseleave", mic_up)

                with ui.row().classes("gap-2"):
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
            "Hello. I'm Jarvis. Type or hold the mic button to talk. "
            "Coding tasks can be sent to Cursor when you confirm.",
        )

    def _new_chat(self) -> None:
        self._conversation.new_session()
        if self._chat_container:
            self._chat_container.clear()
        self._pending_delegate = None
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
