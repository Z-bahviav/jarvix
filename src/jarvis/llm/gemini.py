from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import types

from jarvis.config import LLMSettings
from jarvis.llm.base import CompletionResult, LLMProvider, ToolCall
from jarvis.llm.tools import DELEGATE_CURSOR_TOOL

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(self, settings: LLMSettings, api_key: str) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=api_key)

    def health(self) -> bool:
        return bool(self._client)

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> CompletionResult:
        system_parts: list[str] = []
        contents: list[types.Content] = []
        for msg in messages:
            role = msg.get("role", "user")
            text = msg.get("content") or ""
            if role == "system":
                system_parts.append(text)
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append(
                types.Content(role=gemini_role, parts=[types.Part.from_text(text=text)])
            )

        config_kwargs: dict[str, Any] = {
            "max_output_tokens": self._settings.max_output_tokens,
        }
        if system_parts:
            config_kwargs["system_instruction"] = "\n\n".join(system_parts)

        tool_decls = tools if tools is not None else [DELEGATE_CURSOR_TOOL]
        if tool_decls:
            functions = []
            for t in tool_decls:
                functions.append(
                    types.FunctionDeclaration(
                        name=t["name"],
                        description=t.get("description", ""),
                        parameters=t.get("parameters"),
                    )
                )
            config_kwargs["tools"] = [types.Tool(function_declarations=functions)]

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            response = self._client.models.generate_content(
                model=self._settings.model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            logger.exception("Gemini API error")
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for candidate in response.candidates or []:
            content = candidate.content
            if not content:
                continue
            for part in content.parts or []:
                if part.text:
                    text_parts.append(part.text)
                if part.function_call:
                    fc = part.function_call
                    args = dict(fc.args) if fc.args else {}
                    tool_calls.append(ToolCall(name=fc.name or "", arguments=args))

        return CompletionResult(
            text="\n".join(text_parts).strip() or None,
            tool_calls=tool_calls,
            finish_reason=None,
        )
