from typing import List, Optional
import pytest

from src.application.use_cases import (
    AnalyzeUrlUseCase,
    CreateDownloadUseCase,
    StartDownloadUseCase,
    PauseDownloadUseCase,
    ResumeDownloadUseCase,
    CancelDownloadUseCase,
    RetryDownloadUseCase,
)
from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.exceptions.domain_exceptions import (
    UnsupportedPlatformError,
    FormatNotFoundError,
    TaskNotFoundError,
)
from src.domain.ports.download_engine import IDownloadEngine
from src.domain.ports.download_repository import IDownloadRepository
from src.domain.ports.platform_adapter import IPlatformAdapter
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url


# Mocks para pruebas unitarias de la capa de Aplicación
class MockPlatformAdapter(IPlatformAdapter):

    def detect(self, url: Url) -> bool:
        return "youtube.com" in url.value or "tiktok.com" in url.value

    def analyze(self, url: Url) -> MediaMetadata:
        fmt1 = FormatOption(format_id="1080p", extension="mp4", height=1080)
        return MediaMetadata(
            media_id=MediaId.from_string(url.value),
            url=url,
            platform=url.detect_platform(),
            title="Video Mock de Prueba",
            duration_seconds=120.0,
            formats=[fmt1]
        )


class MockDownloadEngine(IDownloadEngine):

    def __init__(self) -> None:
        self.download_calls: List[str] = []
        self.pause_calls: List[str] = []
        self.resume_calls: List[str] = []
        self.cancel_calls: List[str] = []

    def download(self, task: DownloadTask) -> None:
        self.download_calls.append(task.id.value)

    def pause(self, task: DownloadTask) -> None:
        self.pause_calls.append(task.id.value)

    def resume(self, task: DownloadTask) -> None:
        self.resume_calls.append(task.id.value)

    def cancel(self, task: DownloadTask) -> None:
        self.cancel_calls.append(task.id.value)


class MockDownloadRepository(IDownloadRepository):

    def __init__(self) -> None:
        self.tasks: dict[str, DownloadTask] = {}

    def save(self, task: DownloadTask) -> None:
        self.tasks[task.id.value] = task

    def get_by_id(self, task_id: DownloadId) -> Optional[DownloadTask]:
        return self.tasks.get(task_id.value)

    def get_all(self) -> List[DownloadTask]:
        return list(self.tasks.values())

    def delete(self, task_id: DownloadId) -> None:
        self.tasks.pop(task_id.value, None)


class TestApplicationUseCases:

    @pytest.fixture
    def setup_context(self):
        adapter = MockPlatformAdapter()
        engine = MockDownloadEngine()
        repo = MockDownloadRepository()
        return adapter, engine, repo

    def test_analyze_url_use_case_success(self, setup_context) -> None:
        adapter, _, _ = setup_context
        use_case = AnalyzeUrlUseCase(platform_adapter=adapter)
        metadata = use_case.execute("https://youtube.com/watch?v=123")

        assert metadata.title == "Video Mock de Prueba"
        assert metadata.platform == "YouTube"

    def test_analyze_url_unsupported_platform(self, setup_context) -> None:
        adapter, _, _ = setup_context
        use_case = AnalyzeUrlUseCase(platform_adapter=adapter)

        with pytest.raises(UnsupportedPlatformError):
            use_case.execute("https://unsupported-site.com/video")

    def test_create_download_use_case_success(self, setup_context) -> None:
        adapter, _, repo = setup_context
        analyze_uc = AnalyzeUrlUseCase(adapter)
        create_uc = CreateDownloadUseCase(repo)

        metadata = analyze_uc.execute("https://youtube.com/watch?v=123")
        task = create_uc.execute(media=metadata, format_id="1080p", destination_path="C:/Downloads/video.mp4")

        assert task.status == DownloadState.QUEUED
        assert repo.get_by_id(task.id) == task

    def test_create_download_invalid_format_raises_error(self, setup_context) -> None:
        adapter, _, repo = setup_context
        analyze_uc = AnalyzeUrlUseCase(adapter)
        create_uc = CreateDownloadUseCase(repo)

        metadata = analyze_uc.execute("https://youtube.com/watch?v=123")
        with pytest.raises(FormatNotFoundError):
            create_uc.execute(media=metadata, format_id="4k_non_existent", destination_path="C:/Downloads/video.mp4")

    def test_start_pause_resume_cancel_use_cases(self, setup_context) -> None:
        adapter, engine, repo = setup_context
        analyze_uc = AnalyzeUrlUseCase(adapter)
        create_uc = CreateDownloadUseCase(repo)
        start_uc = StartDownloadUseCase(repo, engine)
        pause_uc = PauseDownloadUseCase(repo, engine)
        resume_uc = ResumeDownloadUseCase(repo, engine)
        cancel_uc = CancelDownloadUseCase(repo, engine)

        metadata = analyze_uc.execute("https://youtube.com/watch?v=123")
        task = create_uc.execute(media=metadata, format_id="1080p", destination_path="C:/Downloads/video.mp4")

        # Start
        start_uc.execute(task.id)
        assert task.status == DownloadState.DOWNLOADING
        assert task.id.value in engine.download_calls

        # Pause
        pause_uc.execute(task.id)
        assert task.status == DownloadState.PAUSED
        assert task.id.value in engine.pause_calls

        # Resume
        resume_uc.execute(task.id)
        assert task.status == DownloadState.DOWNLOADING
        assert task.id.value in engine.resume_calls

        # Cancel
        cancel_uc.execute(task.id)
        assert task.status == DownloadState.CANCELLED
        assert task.id.value in engine.cancel_calls

    def test_retry_download_use_case(self, setup_context) -> None:
        adapter, engine, repo = setup_context
        analyze_uc = AnalyzeUrlUseCase(adapter)
        create_uc = CreateDownloadUseCase(repo)
        start_uc = StartDownloadUseCase(repo, engine)
        retry_uc = RetryDownloadUseCase(repo, engine)

        metadata = analyze_uc.execute("https://youtube.com/watch?v=123")
        task = create_uc.execute(media=metadata, format_id="1080p", destination_path="C:/Downloads/video.mp4")

        start_uc.execute(task.id)
        task.fail("Error de conexión")
        assert task.status == DownloadState.FAILED

        # Retry
        retry_uc.execute(task.id)
        assert task.status == DownloadState.DOWNLOADING
        assert task.error_message is None

    # ---------------------------------------------------------------- vq_ / audio_ parsing

    @staticmethod
    def _rich_metadata() -> MediaMetadata:
        from src.domain.entities.format_option import AudioFormat, VideoFormat, VideoQualityOption

        vqo_best = VideoQualityOption(
            height=2160, label="Mejor calidad", badge="", video_format_id="best_quality",
            audio_format_id="140", needs_ffmpeg_merge=True, estimated_size_bytes=342 * 1024 * 1024,
            fps=25.0, extension="webm", width=3840, video_codec="vp9", is_best_quality=True,
        )
        vqo_1080 = VideoQualityOption(
            height=1080, label="1080p", badge="HD", video_format_id="137",
            audio_format_id="140", needs_ffmpeg_merge=True, estimated_size_bytes=77 * 1024 * 1024,
            fps=25.0, extension="mp4", width=1920, video_codec="avc1",
        )
        af = AudioFormat(format_id="140", extension="m4a", bitrate_kbps=129.5, audio_codec="mp4a")
        vf = VideoFormat(format_id="137", extension="mp4", resolution="1080p", width=1920, height=1080,
                         fps=25.0, video_codec="avc1", has_audio=False, needs_ffmpeg_merge=True,
                         audio_format_id="140", filesize_bytes=77 * 1024 * 1024)

        url = Url("https://youtube.com/watch?v=rich")
        return MediaMetadata(
            media_id=MediaId.from_string(url.value), url=url, platform="YouTube",
            title="Video Rico", duration_seconds=200.0,
            video_quality_options=[vqo_best, vqo_1080],
            video_formats=[vf], audio_formats=[af],
        )

    def test_create_download_vq_best(self) -> None:
        repo = MockDownloadRepository()
        create_uc = CreateDownloadUseCase(repo)
        metadata = self._rich_metadata()

        task = create_uc.execute(media=metadata, format_id="vq_best", destination_path="C:/Downloads/best.mp4")

        fmt = task.selected_format
        assert fmt.is_best_quality is True
        assert fmt.format_id == "best_quality"
        assert fmt.is_video_only is True
        assert fmt.needs_ffmpeg_merge is True
        assert fmt.height == 2160
        assert fmt.width == 3840
        assert fmt.video_codec == "vp9"
        assert fmt.audio_format_id == "140"
        assert task.status == DownloadState.QUEUED
        assert repo.get_by_id(task.id) == task

    def test_create_download_vq_height_preserves_fields(self) -> None:
        repo = MockDownloadRepository()
        create_uc = CreateDownloadUseCase(repo)
        metadata = self._rich_metadata()

        task = create_uc.execute(media=metadata, format_id="vq_1080", destination_path="C:/Downloads/1080.mp4")

        fmt = task.selected_format
        assert fmt.format_id == "137"
        assert fmt.height == 1080
        assert fmt.width == 1920
        assert fmt.video_codec == "avc1"
        assert fmt.needs_ffmpeg_merge is True
        assert fmt.is_video_only is True
        assert fmt.filesize_bytes == 77 * 1024 * 1024

    def test_create_download_audio_format(self) -> None:
        repo = MockDownloadRepository()
        create_uc = CreateDownloadUseCase(repo)
        metadata = self._rich_metadata()

        task = create_uc.execute(media=metadata, format_id="audio_140_mp3_320", destination_path="C:/Downloads/a.mp3")

        fmt = task.selected_format
        assert fmt.is_audio_only is True
        assert fmt.download_type == fmt.download_type.AUDIO
        assert fmt.target_audio_format == "mp3"
        assert fmt.target_audio_bitrate == 320
        assert fmt.extension == "mp3"
        assert fmt.format_id == "audio_140_mp3_320"
