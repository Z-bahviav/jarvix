from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ChatMessage:
    role: str
    content: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[ChatMessage] = field(default_factory=list)

    def add(self, role: str, content: str) -> ChatMessage:
        msg = ChatMessage(role=role, content=content)
        self.messages.append(msg)
        return msg

    def to_llm_messages(self, max_messages: int) -> list[dict[str, Any]]:
        window = self.messages[-max_messages:] if max_messages > 0 else self.messages
        return [{"role": m.role, "content": m.content} for m in window]

    def clear(self) -> None:
        self.messages.clear()
