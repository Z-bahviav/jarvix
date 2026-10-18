from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_config_dir() -> Path:
    env = os.environ.get("JARVIS_CONFIG_DIR")
    if env:
        return Path(env).expanduser().resolve()
    repo = Path(__file__).resolve().parents[2] / "config"
    if repo.is_dir():
        return repo
    return Path.home() / ".config" / "jarvis"


def default_data_dir() -> Path:
    app = os.environ.get("JARVIS_DATA_DIR")
    if app:
        return Path(app).expanduser().resolve()
    # macOS default; falls back cleanly on Linux dev VMs
    mac = Path.home() / "Library" / "Application Support" / "Jarvis"
    if mac.parent.exists():
        return mac
    return Path.home() / ".local" / "share" / "jarvis"


class HotkeySettings(BaseModel):
    enabled: bool = False
    hold_key: str = "f8"


class AudioSettings(BaseModel):
    sample_rate: int = 16000
    channels: int = 1
    max_record_seconds: int = 120


class STTSettings(BaseModel):
    model: str = "base"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "en"


class LLMSettings(BaseModel):
    provider: str = "gemini"
    model: str = "gemini-3.5-flash"
    fallback_models: list[str] = Field(
        default_factory=lambda: ["gemini-3.6-flash", "gemini-3.8-flash", "gemini-flash-latest"]
    )
    timeout_seconds: int = 45
    max_output_tokens: int = 2048


class TTSSettings(BaseModel):
    engine: str = "auto"
    max_chars: int = 4000
    interrupt_on_new_message: bool = True


class ConversationSettings(BaseModel):
    max_messages: int = 40
    require_stt_confirm: bool = True
    voice_pause_seconds: float = 5.0


class CursorSettings(BaseModel):
    binary: str = "cursor-agent"
    default_timeout_seconds: int = 3600
    require_confirmation: bool = True
    focus_on_complete: bool = True


class NotificationSettings(BaseModel):
    enabled: bool = True


class UISettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765


class JobsSettings(BaseModel):
    database_path: str = "data/jobs.sqlite"
    poll_interval_seconds: int = 2


class AppSection(BaseModel):
    data_dir: str = ""


class AppSettings(BaseModel):
    app: AppSection = Field(default_factory=AppSection)
    hotkey: HotkeySettings = Field(default_factory=HotkeySettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    stt: STTSettings = Field(default_factory=STTSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    conversation: ConversationSettings = Field(default_factory=ConversationSettings)
    cursor: CursorSettings = Field(default_factory=CursorSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    ui: UISettings = Field(default_factory=UISettings)
    jobs: JobsSettings = Field(default_factory=JobsSettings)


class ProjectEntry(BaseModel):
    repo: str
    default_folder: str = "."
    description: str = ""


class ProjectsConfig(BaseModel):
    projects: dict[str, ProjectEntry] = Field(default_factory=dict)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", extra="ignore")

    config_dir: Path = Field(default_factory=default_config_dir)

    def data_dir(self, app: AppSettings) -> Path:
        if app.app.data_dir:
            return Path(app.app.data_dir).expanduser().resolve()
        return default_data_dir()

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        for key, value in override.items():
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
            ):
                Settings._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def load_app_settings(self) -> AppSettings:
        path = self.config_dir / "settings.yaml"
        data: dict[str, Any] = {}
        if path.is_file():
            data = yaml.safe_load(path.read_text()) or {}
        local_path = self.config_dir / "settings.local.yaml"
        if local_path.is_file():
            local = yaml.safe_load(local_path.read_text()) or {}
            if isinstance(local, dict):
                data = self._deep_merge(data, local)
        return AppSettings.model_validate(data)

    def load_projects(self) -> ProjectsConfig:
        path = self.config_dir / "projects.yaml"
        data: dict[str, Any] = {"projects": {}}
        if path.is_file():
            data = yaml.safe_load(path.read_text()) or data
        return ProjectsConfig.model_validate(data)

    def resolve_path(self, relative: str, app: AppSettings) -> Path:
        p = Path(relative)
        if p.is_absolute():
            return p
        base = self.data_dir(app)
        base.mkdir(parents=True, exist_ok=True)
        return (base / relative).resolve()

    @staticmethod
    def gemini_api_key() -> str | None:
        return os.environ.get("JARVIS_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
