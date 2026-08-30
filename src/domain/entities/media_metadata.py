from dataclasses import dataclass, field
from typing import List, Optional

from src.domain.entities.format_option import (
    FormatOption, VideoFormat, AudioFormat, VideoQualityOption
)
from src.domain.entities.subtitle import SubtitleTrack
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url


@dataclass
class MediaMetadata:
    """Entidad que representa la información normalizada de un contenido multimedia extraído."""
    media_id: MediaId
    url: Url
    platform: str
    title: str
    description: str = ""
    author: str = ""
    duration_seconds: float = 0.0
    thumbnail_url: str = ""
    upload_date: str = ""
    video_quality_options: List[VideoQualityOption] = field(default_factory=list)
    video_formats: List[VideoFormat] = field(default_factory=list)
    audio_formats: List[AudioFormat] = field(default_factory=list)
    formats: List[FormatOption] = field(default_factory=list)
    subtitles: List[SubtitleTrack] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("MediaMetadata debe tener un título no vacío.")

    def get_quality_option_by_height(self, height: int) -> Optional[VideoQualityOption]:
        """Busca y retorna un VideoQualityOption por su altura (ej. 1080)."""
        for vqo in self.video_quality_options:
            if vqo.height == height:
                return vqo
        return None

    def get_format_by_id(self, format_id: str) -> Optional[FormatOption]:
        """Busca y retorna un FormatOption por su ID."""
        for fmt in self.formats:
            if fmt.format_id == format_id:
                return fmt
        return None

    def get_video_format_by_id(self, format_id: str) -> Optional[VideoFormat]:
        """Busca y retorna un VideoFormat por su ID."""
        for vf in self.video_formats:
            if vf.format_id == format_id:
                return vf
        return None

    def get_audio_format_by_id(self, format_id: str) -> Optional[AudioFormat]:
        """Busca y retorna un AudioFormat por su ID."""
        for af in self.audio_formats:
            if af.format_id == format_id:
                return af
        return None

    def get_best_video_format(self) -> Optional[FormatOption]:
        """Devuelve la opción de video de mayor resolución/calidad disponible."""
        video_opts = [f for f in self.formats if not f.is_audio_only]
        if not video_opts:
            return None
        return max(video_opts, key=lambda f: (f.height or 0, f.fps or 0, f.filesize_bytes or 0))

    def get_best_audio_format(self) -> Optional[FormatOption]:
        """Devuelve la opción de solo audio de mayor calidad disponible."""
        audio_opts = [f for f in self.formats if f.is_audio_only]
        if not audio_opts:
            return None
        return max(audio_opts, key=lambda f: (f.bitrate_kbps or 0, f.filesize_bytes or 0))

    def get_duration_formatted(self) -> str:
        """Devuelve la duración formateada como HH:MM:SS o MM:SS."""
        total_seconds = int(self.duration_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
