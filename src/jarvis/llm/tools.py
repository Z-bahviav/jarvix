from __future__ import annotations

DELEGATE_CURSOR_TOOL = {
    "name": "delegate_cursor_task",
    "description": (
        "Delegate a coding or repository task to Cursor Agent. Use only when the user "
        "wants implementation, debugging, RCA in code, or repo work—not for general chat."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Project key from the configured registry (projects.yaml).",
            },
            "folder": {
                "type": "string",
                "description": "Subfolder within the repo; omit to use project default.",
            },
            "ticket": {
                "type": "string",
                "description": "Optional ticket id (e.g. JIRA-123).",
            },
            "instructions": {
                "type": "string",
                "description": "Clear task instructions for Cursor.",
            },
        },
        "required": ["project", "instructions"],
    },
}


def gemini_tools_schema() -> list[dict]:
    return [DELEGATE_CURSOR_TOOL]
