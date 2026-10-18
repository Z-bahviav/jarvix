from __future__ import annotations

import shutil
from pathlib import Path


def _discover_cursor_agent_in_share() -> Path | None:
    """~/.local/share/cursor-agent/versions/<ver>/cursor-agent (installer layout)."""
    versions = Path.home() / ".local" / "share" / "cursor-agent" / "versions"
    if not versions.is_dir():
        return None
    candidates = sorted(versions.glob("*/cursor-agent"), reverse=True)
    for path in candidates:
        if path.is_file():
            return path
    return None


def resolve_cursor_binary(configured: str) -> Path | None:
    """Resolve CLI name on PATH or an absolute/~/ path (no .zshrc PATH changes needed)."""
    raw = configured.strip()
    if not raw:
        return None
    expanded = Path(raw).expanduser()
    if expanded.is_file():
        return expanded
    # Symlink target may be missing while share binary still exists
    if expanded.is_symlink():
        target = expanded.resolve()
        if target.is_file():
            return target
    found = shutil.which(raw)
    if found:
        return Path(found)
    share = _discover_cursor_agent_in_share()
    if share and raw in ("cursor-agent", "agent", str(share)):
        return share
    for name in ("agent", "cursor-agent"):
        default = Path.home() / ".local" / "bin" / name
        if raw in ("cursor-agent", "agent") and default.is_file():
            return default.resolve() if default.is_symlink() else default
        if raw in ("cursor-agent", "agent") and default.is_symlink():
            target = default.resolve()
            if target.is_file():
                return target
    if raw in ("cursor-agent", "agent"):
        return share
    return None
