from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

from jarvis.config import AppSettings, CursorSettings, Settings
from jarvis.cursor.brief import build_brief
from jarvis.cursor.runner import run_cursor_agent
from jarvis.jobs.store import JobStore
from jarvis.notify import notify
from jarvis.platform.desktop import focus_cursor

logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(
        self,
        settings: Settings,
        app: AppSettings,
        store: JobStore,
        on_complete: Callable[[int, str, str], None] | None = None,
    ) -> None:
        self._settings = settings
        self._app = app
        self._store = store
        self._on_complete = on_complete
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="jarvis-jobs", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        interval = self._app.jobs.poll_interval_seconds
        while not self._stop.is_set():
            job = self._store.claim_next()
            if not job:
                time.sleep(interval)
                continue
            try:
                result = self._run_job(job)
                ok = result.startswith("exit=0") or result.startswith("[dry-run]")
                status = "succeeded" if ok else "failed"
                self._store.complete(job.id, status, result)
                if self._app.notifications.enabled:
                    notify("Jarvis — Cursor", f"Job {job.id} {status}")
                if ok and self._app.cursor.focus_on_complete:
                    focus_cursor()
                if self._on_complete:
                    self._on_complete(job.id, status, result)
            except Exception as exc:
                logger.exception("Job %s failed", job.id)
                self._store.complete(job.id, "failed", str(exc))
                if self._on_complete:
                    self._on_complete(job.id, "failed", str(exc))

    def _run_job(self, job) -> str:
        if job.kind != "cursor":
            return f"Unsupported job kind: {job.kind}"
        payload = job.payload
        repo = self._resolve_repo(payload.get("repo", ""))
        brief = build_brief(
            project=payload.get("project", ""),
            repo=repo,
            folder=payload.get("folder", "."),
            ticket=payload.get("ticket"),
            instructions=payload.get("instructions", ""),
            session_id=payload.get("session_id"),
        )
        cursor_settings = CursorSettings(**self._app.cursor.model_dump())
        dry = os.environ.get("JARVIS_CURSOR_DRY_RUN") == "1"
        code, output = run_cursor_agent(
            cursor_settings,
            repo,
            brief,
            dry_run=dry,
        )
        return f"exit={code}\n{output}"

    def _resolve_repo(self, repo: str) -> str:
        path = Path(repo).expanduser()
        if not path.is_absolute():
            path = (self._settings.config_dir.parent / path).resolve()
        return str(path)
