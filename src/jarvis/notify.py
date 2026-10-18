from __future__ import annotations

import platform
import shutil
import subprocess


def notify(title: str, body: str) -> None:
    system = platform.system()
    if system == "Darwin":
        safe_title = title.replace('"', '\\"')
        safe_body = body.replace('"', '\\"')[:200]
        script = f'display notification "{safe_body}" with title "{safe_title}"'
        try:
            subprocess.run(["osascript", "-e", script], check=False)
            return
        except OSError:
            pass
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, body[:200]], check=False)
        return
    print(f"[notify] {title}: {body}")
