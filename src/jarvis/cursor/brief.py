from __future__ import annotations


def build_brief(
    project: str,
    repo: str,
    folder: str,
    ticket: str | None,
    instructions: str,
    session_id: str | None = None,
) -> str:
    scope = folder.strip() or "."
    ticket_block = f"Ticket: {ticket}\n" if ticket else ""
    session_block = f"Jarvis session: {session_id}\n" if session_id else ""
    return f"""[Jarvis delegated task]
{session_block}Project: {project}
Repository root: {repo}
Work scope: prefer `{scope}` unless the task requires otherwise.

{ticket_block}
Task:
{instructions}

Rules:
- Put the complete answer and work in this Cursor agent chat.
- Start with a line: Title: <short title>
- Read AGENTS.md and project conventions if present.
- Do not commit or push unless explicitly instructed.
"""
