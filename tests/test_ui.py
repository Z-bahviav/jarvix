import os
import subprocess
import sys
import time
from urllib.request import urlopen

from jarvis.ui.app import _should_open_browser


def test_should_open_browser_env() -> None:
    os.environ["JARVIS_UI_SHOW"] = "0"
    assert _should_open_browser() is False
    os.environ["JARVIS_UI_SHOW"] = "1"
    assert _should_open_browser() is True
    del os.environ["JARVIS_UI_SHOW"]


def test_ui_serves_homepage(tmp_path) -> None:
    port = 18765
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("PYTEST_") and k != "NICEGUI_SCREEN_TEST_PORT"
    }
    env["JARVIS_UI_SHOW"] = "0"
    env["JARVIS_UI_PORT"] = str(port)
    log_path = tmp_path / "jarvis-ui.log"
    jarvis_bin = os.path.join(os.path.dirname(sys.executable), "jarvis")
    with log_path.open("w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            [jarvis_bin, "ui"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    try:
        url = f"http://127.0.0.1:{port}/"
        deadline = time.time() + 30
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                with urlopen(url, timeout=2) as resp:
                    assert resp.status == 200
                    body = resp.read(500)
                assert b"nicegui" in body.lower() or b"Jarvis" in body or len(body) > 50
                return
            except OSError:
                time.sleep(0.5)
        log = log_path.read_text(encoding="utf-8", errors="replace")
        raise AssertionError(
            f"UI did not become reachable on {url} (exit={proc.poll()})\n{log[-2000:]}"
        )
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, 15)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, 9)
