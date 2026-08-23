"""Gestor dinamico del motor yt-dlp (wheel actualizable en AppData)."""
from src.infrastructure.adapters.engine.engine_manager import (
    EngineAsset,
    EngineManager,
    EngineStatus,
    EngineUpdateInfo,
    MODE_APPDATA_WHEEL,
    MODE_PACKAGED,
    SOURCE_GITHUB,
    SOURCE_PYPI,
    get_engine_manager,
    is_newer_version,
    parse_calendar_version,
)

__all__ = [
    "EngineAsset",
    "EngineManager",
    "EngineStatus",
    "EngineUpdateInfo",
    "MODE_APPDATA_WHEEL",
    "MODE_PACKAGED",
    "SOURCE_GITHUB",
    "SOURCE_PYPI",
    "get_engine_manager",
    "is_newer_version",
    "parse_calendar_version",
]
