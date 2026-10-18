from __future__ import annotations

from jarvis.config import AppSettings, ConversationSettings, CursorSettings, ProjectEntry, ProjectsConfig
from jarvis.conversation.service import ConversationService
from jarvis.jobs.store import JobStore
from jarvis.llm.base import CompletionResult, LLMProvider, ToolCall
from typing import Any
import tempfile
from pathlib import Path


class MockLLM(LLMProvider):
    def __init__(self, result: CompletionResult) -> None:
        self._result = result

    def complete(
        self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None
    ) -> CompletionResult:
        return self._result


def test_chat_without_cursor() -> None:
    llm = MockLLM(CompletionResult(text="A hash map maps keys to values."))
    app = AppSettings(conversation=ConversationSettings(max_messages=10))
    projects = ProjectsConfig()
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(Path(tmp) / "jobs.sqlite")
        svc = ConversationService(llm, app, projects, store)
        result = svc.handle_user_text("What is a hash map?")
        assert "hash map" in result.assistant_text.lower()
        assert result.job_id is None


def test_delegate_enqueues_job() -> None:
    llm = MockLLM(
        CompletionResult(
            tool_calls=[
                ToolCall(
                    name="delegate_cursor_task",
                    arguments={
                        "project": "demo",
                        "instructions": "fix the tests",
                    },
                )
            ]
        )
    )
    app = AppSettings(
        conversation=ConversationSettings(max_messages=10),
        cursor=CursorSettings(require_confirmation=False),
    )
    projects = ProjectsConfig(
        projects={"demo": ProjectEntry(repo="/tmp", default_folder=".")}
    )
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(Path(tmp) / "jobs.sqlite")
        svc = ConversationService(llm, app, projects, store)
        result = svc.handle_user_text("fix tests in demo", auto_confirm_delegate=True)
        assert result.job_id is not None
        job = store.get(result.job_id)
        assert job is not None
        assert job.status == "pending"
