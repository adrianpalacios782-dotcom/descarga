from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import FormatOption, DownloadType, StreamType, AudioFormat
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.exceptions.domain_exceptions import FormatNotFoundError
from src.domain.ports.download_repository import IDownloadRepository
from src.domain.value_objects.download_id import DownloadId


class CreateDownloadUseCase:
    """Caso de uso para crear y registrar una nueva tarea de descarga."""

    def __init__(self, repository: IDownloadRepository) -> None:
        self.repository = repository

    def execute(self, media: MediaMetadata, format_id: str, destination_path: str) -> DownloadTask:
        selected_format: FormatOption | None = None

        if format_id.startswith("vq_"):
            selected_format = self._build_video_quality_format(media, format_id)

        if not selected_format and format_id.startswith("audio_"):
            selected_format = self._build_audio_format(media, format_id)

        if not selected_format:
            # Buscar en formatos de VIDEO directos o fallback
            vf = media.get_video_format_by_id(format_id)
            if vf:
                selected_format = FormatOption.from_video_format(vf, target_container="mp4")
            else:
                selected_format = media.get_format_by_id(format_id)

        if not selected_format:
            raise FormatNotFoundError(f"El formato con ID '{format_id}' no existe para el medio '{media.title}'.")

        task = DownloadTask(
            id=DownloadId.generate(),
            media=media,
            selected_format=selected_format,
            destination_path=destination_path,
            status=DownloadState.QUEUED
        )

        self.repository.save(task)
        return task

    @staticmethod
    def _build_video_quality_format(media: MediaMetadata, format_id: str) -> FormatOption | None:
        """Construye el FormatOption de VIDEO conservando metadata real (height, width, fps, codecs, merge)."""
        if format_id == "vq_best":
            vqo = media.video_quality_options[0] if media.video_quality_options else None
            if not vqo or not vqo.is_best_quality:
                return None
            return FormatOption(
                format_id="best_quality",
                extension="mp4",
                container="mp4",
                resolution="Mejor calidad",
                width=vqo.width,
                height=vqo.height,
                fps=vqo.fps,
                video_codec=vqo.video_codec,
                stream_type=StreamType.VIDEO_ONLY,
                download_type=DownloadType.VIDEO,
                is_audio_only=False,
                is_video_only=True,
                is_best_quality=True,
                needs_ffmpeg_merge=True,
                audio_format_id=vqo.audio_format_id,
                filesize_bytes=vqo.estimated_size_bytes
            )

        try:
            height = int(format_id.replace("vq_", ""))
        except ValueError:
            return None

        vqo = media.get_quality_option_by_height(height)
        if not vqo:
            return None

        needs_merge = vqo.needs_ffmpeg_merge
        return FormatOption(
            format_id=vqo.video_format_id,
            extension=vqo.extension or "mp4",
            container="mp4",
            resolution=vqo.label,
            width=vqo.width,
            height=vqo.height,
            fps=vqo.fps,
            video_codec=vqo.video_codec,
            stream_type=StreamType.VIDEO_ONLY if needs_merge else StreamType.VIDEO_AUDIO,
            download_type=DownloadType.VIDEO,
            is_audio_only=False,
            is_video_only=needs_merge,
            needs_ffmpeg_merge=needs_merge,
            audio_format_id=vqo.audio_format_id,
            filesize_bytes=vqo.estimated_size_bytes
        )

    @staticmethod
    def _build_audio_format(media: MediaMetadata, format_id: str) -> FormatOption | None:
        """Construye el FormatOption de AUDIO (MP3/M4A/WAV + bitrate) desde audio_{af_id}_{fmt}_{br}."""
        parts = format_id.split("_")
        if len(parts) < 3:
            return None

        try:
            target_br = int(parts[-1])
        except ValueError:
            target_br = 320
        target_fmt = parts[-2] if len(parts) >= 3 else "mp3"

        af_id = "_".join(parts[1:-2]) if len(parts) > 3 else parts[1]
        af = media.get_audio_format_by_id(af_id)
        if not af and media.audio_formats:
            af = media.audio_formats[0]
        if not af:
            af = AudioFormat(format_id="best_audio", extension="m4a", bitrate_kbps=128.0)

        return FormatOption.from_audio_format(af, target_format=target_fmt, target_bitrate=target_br)
