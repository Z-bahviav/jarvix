from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from jarvis.config import AppSettings, ProjectsConfig
from jarvis.conversation.session import Session
from jarvis.jobs.store import JobStore
from jarvis.llm.base import LLMProvider
from jarvis.llm.tools import gemini_tools_schema

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Jarvis, a helpful conversational assistant on the user's Mac.

Answer general questions, explanations, and brainstorming directly in chat.

Use the delegate_cursor_task tool ONLY when the user clearly wants coding work done in a repository
(implementation, debugging, tests, RCA that requires the codebase, refactors). Do not delegate for
purely conceptual questions (e.g. "what is a hash map?").

If the project name is missing, ask which project from their registry before delegating.
Keep replies clear; the user may hear them via text-to-speech, but full text appears in the chat UI.
"""


@dataclass
class DelegateRequest:
    project: str
    folder: str
    ticket: str | None
    instructions: str


@dataclass
class TurnResult:
    assistant_text: str
    delegate: DelegateRequest | None = None
    job_id: int | None = None


class ConversationService:
    def __init__(
        self,
        llm: LLMProvider,
        app: AppSettings,
        projects: ProjectsConfig,
        jobs: JobStore,
        session: Session | None = None,
        on_job_enqueued: Callable[[int, str], None] | None = None,
    ) -> None:
        self._llm = llm
        self._app = app
        self._projects = projects
        self._jobs = jobs
        self._session = session or Session()
        self._on_job_enqueued = on_job_enqueued

    @property
    def session(self) -> Session:
        return self._session

    def new_session(self) -> Session:
        self._session = Session()
        return self._session

    def handle_user_text(
        self,
        text: str,
        *,
        auto_confirm_delegate: bool = False,
    ) -> TurnResult:
        text = text.strip()
        if not text:
            return TurnResult(assistant_text="I didn't receive any text.")

        self._session.add("user", text)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self._session.to_llm_messages(self._app.conversation.max_messages),
        ]

        completion = self._llm.complete(messages, tools=gemini_tools_schema())

        if completion.tool_calls:
            call = completion.tool_calls[0]
            if call.name == "delegate_cursor_task":
                return self._handle_delegate(call.arguments, auto_confirm_delegate)

        reply = completion.text or "I don't have a response right now."
        self._session.add("assistant", reply)
        return TurnResult(assistant_text=reply)

    def confirm_delegate(self, request: DelegateRequest) -> TurnResult:
        return self._enqueue_delegate(request)

    def _handle_delegate(
        self, args: dict[str, Any], auto_confirm: bool
    ) -> TurnResult:
        project = str(args.get("project", "")).strip()
        instructions = str(args.get("instructions", "")).strip()
        folder = str(args.get("folder") or "").strip()
        ticket = args.get("ticket")
        ticket_str = str(ticket).strip() if ticket else None

        entry = self._projects.projects.get(project)
        if not entry:
            names = ", ".join(self._projects.projects.keys()) or "(none configured)"
            msg = f"I don't know project '{project}'. Configured projects: {names}."
            self._session.add("assistant", msg)
            return TurnResult(assistant_text=msg)

        if not instructions:
            msg = "I need clearer instructions before sending work to Cursor."
            self._session.add("assistant", msg)
            return TurnResult(assistant_text=msg)

        req = DelegateRequest(
            project=project,
            folder=folder or entry.default_folder,
            ticket=ticket_str,
            instructions=instructions,
        )

        if self._app.cursor.require_confirmation and not auto_confirm:
            msg = (
                f"I can send this to Cursor on project **{project}** "
                f"({entry.repo}). Confirm in the UI to proceed."
            )
            self._session.add("assistant", msg)
            return TurnResult(assistant_text=msg, delegate=req)

        return self._enqueue_delegate(req)

    def _enqueue_delegate(self, req: DelegateRequest) -> TurnResult:
        entry = self._projects.projects[req.project]
        job_id = self._jobs.enqueue(
            "cursor",
            {
                "project": req.project,
                "repo": str(entry.repo),
                "folder": req.folder,
                "ticket": req.ticket,
                "instructions": req.instructions,
                "session_id": self._session.id,
            },
        )
        msg = (
            f"Delegated to Cursor (job {job_id}) on **{req.project}**. "
            "I'll let you know when it finishes—read the full result in Cursor."
        )
        self._session.add("assistant", msg)
        if self._on_job_enqueued:
            self._on_job_enqueued(job_id, req.project)
        return TurnResult(assistant_text=msg, delegate=req, job_id=job_id)
