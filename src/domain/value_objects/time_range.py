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

    @property
    def duration(self) -> Optional[float]:
        """Calcula la duración en segundos del segmento recortado, o None si no hay fin definido."""
        if self.end_seconds is None:
            return None
        return max(0.0, self.end_seconds - self.start_seconds)

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
        return self.to_section_spec()

    def to_section_spec(self) -> str:
        """Formatea la especificación de sección para yt-dlp (ej. '*00:01:25-00:03:40' o '*00:01:25.500-00:03:40.000')."""
        start_fmt = self.format_timestamp(self.start_seconds)
        if self.end_seconds is not None:
            end_fmt = self.format_timestamp(self.end_seconds)
            return f"*{start_fmt}-{end_fmt}"
        return f"*{start_fmt}-inf"

    def format_range(self) -> str:
        """Formatea el rango de tiempo de forma legible para el usuario (ej. '00:01:25 - 00:03:40')."""
        start_fmt = self.format_seconds(self.start_seconds)
        if self.end_seconds is not None:
            end_fmt = self.format_seconds(self.end_seconds)
            return f"{start_fmt} - {end_fmt}"
        return f"{start_fmt} - Fin"

    @staticmethod
    def format_seconds(seconds: float) -> str:
        """Formatea segundos en 'HH:MM:SS'."""
        total = int(seconds)
        hrs = total // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"

    @staticmethod
    def format_timestamp(seconds: float, with_millis: bool = False) -> str:
        """Formatea segundos en 'HH:MM:SS' o 'HH:MM:SS.fff' si hay fracciones."""
        total_int = int(seconds)
        hrs = total_int // 3600
        mins = (total_int % 3600) // 60
        secs = total_int % 60
        frac = abs(seconds - total_int)
        if with_millis or frac > 0.0009:
            millis = int(round(frac * 1000))
            if millis >= 1000:
                millis = 999
            return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
