from dataclasses import dataclass
from typing import Optional

from src.domain.exceptions.domain_exceptions import InvalidParameterError


@dataclass(frozen=True)
class TimeRange:
    """Representa un intervalo de tiempo validado (inicio y fin) para recorte de multimedia."""

    start_seconds: float
    end_seconds: Optional[float] = None

    def __post_init__(self) -> None:
        if self.start_seconds < 0:
            raise InvalidParameterError("El tiempo de inicio no puede ser negativo.")
        if self.end_seconds is not None:
            if self.end_seconds <= self.start_seconds:
                raise InvalidParameterError(
                    f"El tiempo final ({self.end_seconds}s) debe ser mayor que el tiempo de inicio ({self.start_seconds}s)."
                )

    @classmethod
    def parse_timestamp(cls, raw: str) -> float:
        """Parsea una cadena de tiempo en formato 'HH:MM:SS', 'MM:SS' o 'SS' a segundos flotantes."""
        if not raw or not raw.strip():
            return 0.0

        cleaned = raw.strip()
        parts = cleaned.split(":")
        try:
            if len(parts) == 1:
                return float(parts[0])
            elif len(parts) == 2:
                mins, secs = parts
                return int(mins) * 60.0 + float(secs)
            elif len(parts) == 3:
                hrs, mins, secs = parts
                return int(hrs) * 3600.0 + int(mins) * 60.0 + float(secs)
            else:
                raise ValueError("Demasiadas secciones separadas por dos puntos.")
        except (ValueError, TypeError) as exc:
            raise InvalidParameterError(
                f"Formato de tiempo inválido: '{raw}'. Use 'MM:SS' o 'HH:MM:SS'."
            ) from exc

    @classmethod
    def from_strings(cls, start_str: str, end_str: Optional[str] = None) -> "TimeRange":
        """Crea un TimeRange a partir de cadenas formateadas (ej. '01:30', '03:45')."""
        start = cls.parse_timestamp(start_str) if start_str and start_str.strip() else 0.0
        end = cls.parse_timestamp(end_str) if end_str and end_str.strip() else None
        return cls(start_seconds=start, end_seconds=end)

    def to_ytdlp_section(self) -> str:
        """Formatea la sección para el argumento --download-sections de yt-dlp (ej. '*00:01:30-00:03:00')."""
        start_fmt = self.format_seconds(self.start_seconds)
        if self.end_seconds is not None:
            end_fmt = self.format_seconds(self.end_seconds)
            return f"*{start_fmt}-{end_fmt}"
        return f"*{start_fmt}-inf"

    @staticmethod
    def format_seconds(seconds: float) -> str:
        """Formatea segundos en 'HH:MM:SS'."""
        total = int(seconds)
        hrs = total // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
