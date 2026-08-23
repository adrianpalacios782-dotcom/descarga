"""Contratos de selección de calidad: InicioView → vq_best / vq_{h} / audio_* → CreateDownloadUseCase.

Casos obligatorios 5-10 y 12 del plan de corrección.
"""
import pytest

from src.application.use_cases import CreateDownloadUseCase
from src.domain.entities.download_task import DownloadState
from src.domain.entities.format_option import DownloadType, StreamType
from src.domain.exceptions.domain_exceptions import FormatNotFoundError
from src.domain.services.format_normalizer import FormatNormalizer
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.domain.entities.media_metadata import MediaMetadata

# Cadena realista estilo YouTube (DASH video-only WEBM/MP4 + audio-only + progresivos)
RAW_FORMATS = [
    {"format_id": "sb0", "ext": "mhtml", "vcodec": "none", "acodec": "none", "format_note": "storyboard"},
    {"format_id": "315", "ext": "webm", "height": 2160, "fps": 60, "vcodec": "vp9", "acodec": "none",
     "filesize": 900 * 1024 * 1024},
    {"format_id": "308", "ext": "webm", "height": 1440, "fps": 60, "vcodec": "vp9", "acodec": "none",
     "filesize_approx": 380 * 1024 * 1024},
    {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 24, "vcodec": "avc1.640028", "acodec": "none"},
    {"format_id": "136", "ext": "mp4", "height": 720, "fps": 24, "vcodec": "avc1.4d401f", "acodec": "none"},
    {"format_id": "18", "ext": "mp4", "height": 360, "fps": 24, "vcodec": "avc1.42001E", "acodec": "mp4a.40.2"},
    {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 129},
    {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus", "tbr": 160,
     "filesize": 4 * 1024 * 1024},
]


class InMemoryRepo:
    def __init__(self):
        self.tasks = {}

    def save(self, task):
        self.tasks[task.id.value] = task

    def get_by_id(self, task_id):
        return self.tasks.get(task_id.value)

    def get_all(self):
        return list(self.tasks.values())

    def delete(self, task_id):
        self.tasks.pop(task_id.value, None)


def make_media(**overrides) -> MediaMetadata:
    url = Url("https://www.youtube.com/watch?v=F3tKutGo1Fo")
    return MediaMetadata(
        media_id=MediaId.from_string(url.value),
        url=url,
        platform="YouTube",
        title="Junior H - OTRO AMOR [Official Visualizer]",
        duration_seconds=247.0,
        video_quality_options=FormatNormalizer.normalize_video_quality_options(RAW_FORMATS),
        video_formats=FormatNormalizer.normalize_video_formats(RAW_FORMATS),
        audio_formats=FormatNormalizer.normalize_audio_formats(RAW_FORMATS),
        formats=FormatNormalizer.normalize(RAW_FORMATS),
        **overrides,
    )


@pytest.fixture
def use_case():
    return CreateDownloadUseCase(InMemoryRepo())


class TestVideoQualityContracts:

    def test_vq_best_selects_synthetic_best(self, use_case) -> None:
        """Caso obligatorio 9: Mejor calidad → vq_best → formato sintético con merge."""
        task = use_case.execute(make_media(), "vq_best", "D:\\x\\a.mp4")
        fmt = task.selected_format
        assert fmt.is_best_quality is True
        assert fmt.format_id == "best_quality"
        assert fmt.height == 2160
        assert fmt.needs_ffmpeg_merge is True
        assert fmt.audio_format_id == "251"

    def test_vq_1440_regression_caso_a(self, use_case) -> None:
        """Caso obligatorio 6 (CASO A): 1440p sigue funcionando tras la corrección."""
        task = use_case.execute(make_media(), "vq_1440", "D:\\x\\a.mp4")
        fmt = task.selected_format
        assert fmt.height == 1440
        assert fmt.format_id == "308", "Debe usar el format_id REAL del servidor"
        assert fmt.needs_ffmpeg_merge is True
        assert fmt.audio_format_id == "251"
        assert fmt.download_type == DownloadType.VIDEO

    def test_vq_1080_selects_real_format(self, use_case) -> None:
        """Caso obligatorio 7: 1080p selecciona el formato disponible (no inventa)."""
        task = use_case.execute(make_media(), "vq_1080", "D:\\x\\a.mp4")
        fmt = task.selected_format
        assert fmt.height == 1080
        assert fmt.format_id == "137"
        spec = __import__(
            "src.infrastructure.adapters.download.ytdlp_download_engine", fromlist=["YtDlpDownloadEngine"]
        ).YtDlpDownloadEngine._build_video_format_spec(fmt)
        assert spec.startswith("137+bestaudio")
        assert "bestvideo[height=1080]" in spec.split("/bestvideo[height<=1080]")[0]

    def test_vq_720_selects_real_format(self, use_case) -> None:
        """Caso obligatorio 8: 720p selecciona correctamente."""
        task = use_case.execute(make_media(), "vq_720", "D:\\x\\a.mp4")
        fmt = task.selected_format
        assert fmt.height == 720
        assert fmt.format_id == "136"

    def test_video_only_plus_audio_only_merge_contract(self, use_case) -> None:
        """Caso obligatorio 5: video-only + audio-only se construyen para merge."""
        media = make_media()
        vqo = media.get_quality_option_by_height(1080)
        assert vqo.needs_ffmpeg_merge is True
        assert vqo.video_format_id == "137" and vqo.audio_format_id
        task = use_case.execute(media, "vq_1080", "D:\\x\\a.mp4")
        fmt = task.selected_format
        assert fmt.is_video_only is True
        assert fmt.stream_type == StreamType.VIDEO_ONLY
        assert fmt.needs_ffmpeg_merge is True and fmt.audio_format_id == "251"


class TestAudioContracts:

    def test_audio_contract_preserved(self, use_case) -> None:
        """Caso obligatorio 10: audio_* intacto tras las correcciones de video."""
        task = use_case.execute(make_media(), "audio_140_mp3_320", "D:\\x\\a.mp3")
        fmt = task.selected_format
        assert fmt.is_audio_only is True
        assert fmt.download_type == DownloadType.AUDIO
        assert fmt.target_audio_format == "mp3"
        assert fmt.target_audio_bitrate == 320
        assert fmt.format_id == "audio_140_mp3_320"

    def test_audio_m4a_fallback_to_best_available(self, use_case) -> None:
        task = use_case.execute(make_media(), "audio_251_m4a_192", "D:\\x\\a.m4a")
        fmt = task.selected_format
        assert fmt.audio_format_id == "251"
        assert fmt.target_audio_bitrate == 192


class TestInvalidSelections:

    def test_unavailable_height_raises_format_not_found(self, use_case) -> None:
        """Caso obligatorio 11 (parte): pedir una calidad inexistente falla explícitamente."""
        with pytest.raises(FormatNotFoundError):
            use_case.execute(make_media(), "vq_999", "D:\\x\\a.mp4")

    def test_unknown_prefix_raises(self, use_case) -> None:
        with pytest.raises(FormatNotFoundError):
            use_case.execute(make_media(), "xyz_no_existe", "D:\\x\\a.mp4")

    def test_created_task_starts_queued(self, use_case) -> None:
        task = use_case.execute(make_media(), "vq_720", "D:\\x\\a.mp4")
        assert task.status == DownloadState.QUEUED
