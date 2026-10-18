from __future__ import annotations

from pathlib import Path

import yaml

from jarvis.config import Settings
from jarvis.cursor.resolve import resolve_cursor_binary


def run_doctor(settings: Settings | None = None, write_local: bool = True) -> int:
    """Discover Cursor CLI and optional local overrides. Returns 0 if ready enough for check."""
    settings = settings or Settings()
    config_dir = settings.config_dir
    config_dir.mkdir(parents=True, exist_ok=True)

    issues = 0

    cursor_path = resolve_cursor_binary("agent")
    if cursor_path:
        print(f"✓ Cursor CLI: {cursor_path}")
        if write_local:
            local_path = config_dir / "settings.local.yaml"
            payload = {"cursor": {"binary": str(cursor_path)}}
            local_path.write_text(yaml.safe_dump(payload, default_flow_style=False))
            print(f"  Wrote {local_path}")
    else:
        print("✗ Cursor CLI not found under ~/.local/bin or ~/.local/share/cursor-agent")
        print("  Run: curl https://cursor.com/install -fsS | bash")
        print("  Then: jarvis doctor")
        issues += 1

    key = Settings.gemini_api_key()
    env_path = _find_env_file(settings)
    if key:
        print("✓ Gemini API key: set in environment")
    else:
        print("✗ Gemini API key missing")
        if env_path and not env_path.is_file():
            env_path.write_text("JARVIS_GEMINI_API_KEY=\n")
            print(f"  Created {env_path} — add your key after the =")
        elif env_path:
            print(f"  Add JARVIS_GEMINI_API_KEY to {env_path}")
        issues += 1

    venv = Path(settings.config_dir).parent / ".venv" / "bin" / "activate"
    if not venv.is_file():
        venv = Path.cwd() / ".venv" / "bin" / "activate"
    if venv.is_file():
        print(f"✓ venv: {venv.parent.parent}")
    else:
        print("✗ No .venv — run: ./scripts/setup.sh")
        issues += 1

    return issues


def _find_env_file(settings: Settings) -> Path | None:
    for candidate in (
        Path.cwd() / ".env",
        settings.config_dir.parent / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ):
        if candidate.parent.is_dir():
            return candidate
    return Path.cwd() / ".env"
