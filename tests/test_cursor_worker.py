from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from jarvis.config import AppSettings, CursorSettings, JobsSettings, Settings
from jarvis.jobs.store import JobStore
from jarvis.jobs.worker import JobWorker


def test_worker_runs_mock_cursor_agent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("hello")

        mock = root / "cursor-agent"
        mock.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "-p" ]; then echo "Title: Mock"; echo ok; exit 0; fi\n'
            "exit 1\n"
        )
        mock.chmod(mock.stat().st_mode | stat.S_IEXEC)

        cfg_dir = root / "config"
        cfg_dir.mkdir()
        data_dir = root / "data"
        os.environ["PATH"] = f"{root}:{os.environ.get('PATH', '')}"

        settings = Settings(config_dir=cfg_dir)
        app = AppSettings(
            cursor=CursorSettings(binary="cursor-agent", default_timeout_seconds=30),
            jobs=JobsSettings(database_path=str(data_dir / "jobs.sqlite")),
        )
        store = JobStore(data_dir / "jobs.sqlite")
        job_id = store.enqueue(
            "cursor",
            {
                "project": "jarvis-test",
                "repo": str(repo),
                "folder": ".",
                "instructions": "read README",
            },
        )
        worker = JobWorker(settings, app, store)
        job = store.get(job_id)
        assert job is not None
        result = worker._run_job(job)  # noqa: SLF001 — integration hook
        assert result.startswith("exit=0")
        assert "ok" in result
