from __future__ import annotations

import subprocess
from pathlib import Path

from jarvis.config import CursorSettings
from jarvis.cursor.resolve import resolve_cursor_binary


def run_cursor_agent(
    settings: CursorSettings,
    repo: str,
    brief: str,
    dry_run: bool = False,
) -> tuple[int, str]:
    repo_path = Path(repo).expanduser()
    if not repo_path.is_dir():
        return 1, f"Repo path does not exist: {repo_path}"

    resolved = resolve_cursor_binary(settings.binary)
    if not resolved:
        return 127, (
            f"{settings.binary} not found. Install Cursor CLI or set cursor.binary to "
            f"~/.local/bin/agent in config/settings.yaml"
        )
    binary = str(resolved)
    cmd = [binary, "-p", brief]
    if dry_run:
        return 0, f"[dry-run] would run in {repo_path}: {binary} -p <brief>"

    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=settings.default_timeout_seconds,
        )
    except FileNotFoundError:
        return 127, f"{binary} not found on PATH. Install Cursor Agent CLI."
    except subprocess.TimeoutExpired:
        return 124, "cursor-agent timed out"

    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output[-12000:]
