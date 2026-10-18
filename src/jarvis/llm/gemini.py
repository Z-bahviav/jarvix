from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from jarvis.config import LLMSettings
from jarvis.llm.base import CompletionResult, LLMProvider, ToolCall
from jarvis.llm.tools import DELEGATE_CURSOR_TOOL

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 503, 504}
_NO_RETRY = types.HttpRetryOptions(attempts=1)


def _api_error_code(exc: genai_errors.APIError) -> int | None:
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return None


class GeminiProvider(LLMProvider):
    def __init__(self, settings: LLMSettings, api_key: str) -> None:
        self._settings = settings
        attempt_ms = max(3, settings.per_attempt_timeout_seconds) * 1000
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=attempt_ms,
                retry_options=_NO_RETRY,
            ),
        )

    def health(self) -> bool:
        return bool(self._client)

    def _models_to_try(self) -> list[str]:
        models = [self._settings.model]
        for name in self._settings.fallback_models:
            if name and name not in models:
                models.append(name)
        return models

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> CompletionResult:
        models = self._models_to_try()
        last_error: Exception | None = None
        for model in models:
            try:
                logger.info("Gemini request → model=%s", model)
                return self._complete_model(model, messages, tools=tools)
            except genai_errors.APIError as exc:
                last_error = exc
                code = _api_error_code(exc)
                if code in _RETRYABLE_STATUS:
                    logger.warning("Gemini %s returned %s, trying next model", model, code)
                    continue
                logger.exception("Gemini API error on model %s", model)
                raise RuntimeError(f"Gemini request failed: {exc}") from exc
            except FuturesTimeoutError as exc:
                last_error = exc
                logger.warning("Gemini %s timed out, trying next model", model)
                continue
        raise RuntimeError(f"Gemini unavailable (tried {models}): {last_error}")

    def _complete_model(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None,
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
        attempt_timeout = max(3, self._settings.per_attempt_timeout_seconds)

        def _call() -> Any:
            return self._client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_call)
            try:
                response = future.result(timeout=attempt_timeout)
            except FuturesTimeoutError:
                future.cancel()
                raise

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

        logger.info("Gemini OK model=%s chars=%d", model, len("".join(text_parts)))
        return CompletionResult(
            text="\n".join(text_parts).strip() or None,
            tool_calls=tool_calls,
            finish_reason=None,
        )
