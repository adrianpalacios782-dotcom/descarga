from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DownloadType(str, Enum):
    """Modo de descarga seleccionado por el usuario: VIDEO o AUDIO."""
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"


class StreamType(str, Enum):
    """Clasificación del tipo de flujo multimedia fuente."""
    VIDEO_AUDIO = "VIDEO_AUDIO"  # Video y Audio combinados en un solo flujo
    VIDEO_ONLY = "VIDEO_ONLY"    # Solo Video (DASH/HLS)
    AUDIO_ONLY = "AUDIO_ONLY"    # Solo Audio


@dataclass(frozen=True)
class VideoQualityOption:
    """Modelo de presentación/dominio para la lista de resoluciones de video orientada al usuario."""
    height: int
    label: str                      # ej. "1080p", "720p", "360p" o "Mejor calidad"
    badge: str                      # ej. "4K", "2K", "HD" o ""
    video_format_id: str
    audio_format_id: Optional[str] = None
    needs_ffmpeg_merge: bool = False
    estimated_size_bytes: Optional[int] = None
    fps: Optional[float] = None
    extension: str = "mp4"
    width: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    is_best_quality: bool = False
    height_estimated: bool = False

    def get_display_label(self) -> str:
        if self.badge:
            return f"{self.label:<12} {self.badge}"
        return self.label

    def get_technical_info(self) -> str:
        """Devuelve la información técnica secundaria (ext · fps · flujos · tamaño)."""
        parts = [self.extension.upper()]
        if self.fps and self.fps > 0:
            parts.append(f"{int(self.fps)} FPS")
        if self.is_best_quality:
            parts.append("Video + Audio")
        elif self.needs_ffmpeg_merge:
            parts.append("Video + Audio")
        else:
            parts.append("Video + Audio")

        if self.estimated_size_bytes and self.estimated_size_bytes > 0:
            parts.append(self.get_human_filesize())
        return " · ".join(parts)

    def get_human_filesize(self) -> str:
        if self.estimated_size_bytes is None or self.estimated_size_bytes <= 0:
            return "Tamaño desconocido"

        size = float(self.estimated_size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0 or unit == "TB":
                return f"~{size:.1f} {unit}"
            size /= 1024.0
        return f"~{size:.1f} GB"


@dataclass(frozen=True)
class VideoFormat:
    """Representación de dominio específica para opciones de VIDEO."""
    format_id: str
    extension: str
    resolution: str
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    has_audio: bool = True
    needs_ffmpeg_merge: bool = False
    audio_format_id: Optional[str] = None
    filesize_bytes: Optional[int] = None
    is_best_quality: bool = False
    height_estimated: bool = False

    def get_human_filesize(self) -> str:
        if self.filesize_bytes is None or self.filesize_bytes <= 0:
            return "Tamaño desconocido"

        size = float(self.filesize_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0 or unit == "TB":
                return f"~{size:.1f} {unit}"
            size /= 1024.0
        return f"~{size:.1f} GB"

    def get_description(self) -> str:
        if self.is_best_quality:
            res_str = self.resolution or (f"{self.height}p" if self.height else "HD")
            return f"Mejor calidad · {self.extension.upper()} · {res_str} · Video + Audio"

        parts = []
        res_str = self.resolution or (f"{self.height}p" if self.height else "Video")
        parts.append(res_str)
        parts.append(self.extension.upper())
        if self.fps and self.fps > 0:
            parts.append(f"{int(self.fps)} FPS")

        if self.has_audio or self.needs_ffmpeg_merge:
            parts.append("Video + Audio")
        else:
            parts.append("Solo Video")

        parts.append(self.get_human_filesize())
        return " · ".join(parts)


@dataclass(frozen=True)
class AudioFormat:
    """Representación de dominio específica para opciones de AUDIO."""
    format_id: str
    extension: str
    bitrate_kbps: Optional[float] = None
    audio_codec: Optional[str] = None
    filesize_bytes: Optional[int] = None

    def get_human_filesize(self) -> str:
        if self.filesize_bytes is None or self.filesize_bytes <= 0:
            return "Tamaño desconocido"

        size = float(self.filesize_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0 or unit == "TB":
                return f"~{size:.1f} {unit}"
            size /= 1024.0
        return f"~{size:.1f} GB"

    def get_description(self) -> str:
        parts = [self.extension.upper()]
        if self.bitrate_kbps and self.bitrate_kbps > 0:
            parts.append(f"{int(self.bitrate_kbps)} kbps")
        else:
            parts.append("Calidad Estándar")
        parts.append(self.get_human_filesize())
        return " · ".join(parts)


@dataclass(frozen=True)
class FormatOption:
    """Entidad de dominio que representa una opción de formato/calidad normalizada para una descarga."""
    format_id: str
    extension: str
    container: str = ""
    resolution: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    stream_type: StreamType = StreamType.VIDEO_AUDIO
    download_type: DownloadType = DownloadType.VIDEO
    target_audio_format: Optional[str] = None
    target_audio_bitrate: Optional[int] = None
    is_audio_only: bool = False
    is_video_only: bool = False
    is_best_quality: bool = False
    needs_ffmpeg_merge: bool = False
    audio_format_id: Optional[str] = None
    filesize_bytes: Optional[int] = None
    bitrate_kbps: Optional[float] = None
    height_estimated: bool = False

    def __post_init__(self) -> None:
        if not self.format_id or not isinstance(self.format_id, str):
            raise ValueError("format_id debe ser una cadena no vacía.")
        if not self.extension or not isinstance(self.extension, str):
            raise ValueError("extension debe ser una cadena no vacía.")

    @classmethod
    def from_video_format(cls, vf: VideoFormat, target_container: str = "mp4") -> "FormatOption":
        return cls(
            format_id=vf.format_id,
            extension=target_container,
            container=target_container,
            resolution=vf.resolution,
            width=vf.width,
            height=vf.height,
            fps=vf.fps,
            video_codec=vf.video_codec,
            stream_type=StreamType.VIDEO_AUDIO if (vf.has_audio or vf.needs_ffmpeg_merge) else StreamType.VIDEO_ONLY,
            download_type=DownloadType.VIDEO,
            is_audio_only=False,
            is_video_only=not (vf.has_audio or vf.needs_ffmpeg_merge),
            is_best_quality=vf.is_best_quality,
            needs_ffmpeg_merge=vf.needs_ffmpeg_merge,
            audio_format_id=vf.audio_format_id,
            filesize_bytes=vf.filesize_bytes,
            height_estimated=vf.height_estimated
        )

    @classmethod
    def from_audio_format(cls, af: AudioFormat, target_format: str = "mp3", target_bitrate: int = 320) -> "FormatOption":
        return cls(
            format_id=f"audio_{af.format_id}_{target_format}_{target_bitrate}",
            extension=target_format.lower(),
            container=target_format.lower(),
            resolution="Solo Audio",
            stream_type=StreamType.AUDIO_ONLY,
            download_type=DownloadType.AUDIO,
            target_audio_format=target_format.lower(),
            target_audio_bitrate=target_bitrate,
            is_audio_only=True,
            is_video_only=False,
            audio_format_id=af.format_id,
            filesize_bytes=af.filesize_bytes,
            bitrate_kbps=float(target_bitrate)
        )

    def get_human_filesize(self) -> str:
        if self.filesize_bytes is None or self.filesize_bytes <= 0:
            return "Tamaño desconocido"

        size = float(self.filesize_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0 or unit == "TB":
                return f"~{size:.1f} {unit}"
            size /= 1024.0
        return f"~{size:.1f} GB"

    def get_description(self) -> str:
        if self.is_best_quality:
            res_str = self.resolution or (f"{self.height}p" if self.height else "HD")
            return f"Mejor calidad · {self.extension.upper()} · {res_str} · Video + Audio"

        parts = []

        if self.download_type == DownloadType.AUDIO or self.stream_type == StreamType.AUDIO_ONLY or self.is_audio_only:
            parts.append("Solo Audio")
            parts.append(self.extension.upper())
            if self.target_audio_bitrate:
                parts.append(f"{self.target_audio_bitrate} kbps")
            elif self.bitrate_kbps and self.bitrate_kbps > 0:
                parts.append(f"{int(self.bitrate_kbps)} kbps")
        else:
            res_str = self.resolution or (f"{self.height}p" if self.height else "Video")
            parts.append(res_str)
            parts.append(self.extension.upper())
            if self.fps and self.fps > 0:
                parts.append(f"{int(self.fps)} FPS")

            if self.stream_type == StreamType.VIDEO_AUDIO or self.needs_ffmpeg_merge:
                parts.append("Video + Audio")
            elif self.stream_type == StreamType.VIDEO_ONLY or self.is_video_only:
                parts.append("Solo Video")

        parts.append(self.get_human_filesize())
        return " · ".join(parts)
