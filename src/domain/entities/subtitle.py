from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SubtitleMode(str, Enum):
    """Modo de gestión de subtítulos."""
    NONE = "NONE"
    EMBED = "EMBED"
    EXTERNAL = "EXTERNAL"


@dataclass(frozen=True)
class SubtitleTrack:
    """Representación de dominio para una pista de subtítulos disponible."""
    language_code: str
    name: str = ""
    extension: str = "vtt"
    is_auto_generated: bool = False

    def __post_init__(self) -> None:
        if not self.language_code or not self.language_code.strip():
            raise ValueError("language_code debe ser una cadena no vacía.")


@dataclass(frozen=True)
class SubtitleConfig:
    """Configuración de subtítulos solicitada por el usuario para una descarga."""
    mode: SubtitleMode = SubtitleMode.NONE
    language_code: Optional[str] = None
    is_auto_generated: bool = False
