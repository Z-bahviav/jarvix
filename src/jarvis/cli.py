from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

from jarvis.config import Settings


def _load_env() -> None:
    for candidate in (
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ):
        if candidate.is_file():
            load_dotenv(candidate)
            return
    load_dotenv()
from jarvis.conversation.service import ConversationService
from jarvis.jobs.store import JobStore
from jarvis.llm.factory import LLMConfigurationError, build_llm_provider


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(description="Jarvis voice assistant")
    parser.add_argument(
        "command",
        choices=["ui", "chat", "check", "doctor"],
        help="ui: desktop chat; chat: REPL; check: verify; doctor: auto-config Cursor path",
    )
    parser.add_argument("--text", "-t", help="Single message for chat mode")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = Settings()

    if args.command == "doctor":
        from jarvis.doctor import run_doctor

        issues = run_doctor(settings)
        sys.exit(0 if issues == 0 else 1)

    if args.command == "check":
        _check(settings)
        return

    if args.command == "ui":
        from jarvis.ui.app import run_ui

        run_ui(settings)
        return

    if args.command == "chat":
        _chat_repl(settings, args.text)
        return


def _check(settings: Settings) -> None:
    app = settings.load_app_settings()
    print(f"config_dir: {settings.config_dir}")
    key = Settings.gemini_api_key()
    print(f"gemini_api_key: {'set' if key else 'MISSING'}")
    print(f"llm: {app.llm.provider} / {app.llm.model}")
    print(f"whisper: {app.stt.model}")
    from jarvis.cursor.resolve import resolve_cursor_binary

    cursor_path = resolve_cursor_binary(app.cursor.binary)
    if cursor_path:
        print(f"cursor CLI: found ({cursor_path})")
    else:
        print(
            f"cursor CLI: missing (configured: {app.cursor.binary}; "
            "try binary: agent or ~/.local/bin/agent)"
        )
    try:
        llm = build_llm_provider(settings, app.llm)
        print(f"llm provider: ok ({type(llm).__name__})")
    except LLMConfigurationError as exc:
        print(f"llm provider: FAIL — {exc}")
        sys.exit(1)


def _chat_repl(settings: Settings, single: str | None) -> None:
    app = settings.load_app_settings()
    projects = settings.load_projects()
    db_path = settings.resolve_path(app.jobs.database_path, app)
    jobs = JobStore(db_path)
    llm = build_llm_provider(settings, app.llm)
    conv = ConversationService(llm, app, projects, jobs)
    from jarvis.jobs.worker import JobWorker

    worker = JobWorker(settings, app, jobs)
    worker.start()

    if single:
        result = conv.handle_user_text(single, auto_confirm_delegate=True)
        print(result.assistant_text)
        return

    print("Jarvis REPL (Ctrl+C to exit). Type messages; 'new' for new session.")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line.lower() == "new":
            conv.new_session()
            print("New session.")
            continue
        result = conv.handle_user_text(line, auto_confirm_delegate=True)
        print(f"jarvis> {result.assistant_text}")


if __name__ == "__main__":
    main()
