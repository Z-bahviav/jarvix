from __future__ import annotations

import platform
import shutil
import subprocess


def focus_cursor() -> bool:
    system = platform.system()
    if system == "Darwin":
        script = 'tell application "Cursor" to activate'
        try:
            subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
            return True
        except OSError:
            return False
    if system == "Linux":
        for cmd, args in (
            (shutil.which("wmctrl"), ["-a", "Cursor"]),
            (shutil.which("xdotool"), ["search", "--name", "Cursor", "windowactivate"]),
        ):
            if cmd:
                subprocess.run([cmd, *args], check=False)
                return True
    return False
