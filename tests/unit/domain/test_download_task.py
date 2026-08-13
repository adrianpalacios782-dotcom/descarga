import pytest
from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.exceptions.domain_exceptions import InvalidStateTransitionError
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url


class TestDownloadTaskEntity:

    @pytest.fixture
    def sample_task(self) -> DownloadTask:
        url = Url("https://youtube.com/watch?v=123")
        fmt = FormatOption(format_id="1080p", extension="mp4", height=1080)
        media = MediaMetadata(media_id=MediaId.generate(), url=url, platform="YouTube", title="Test Title", formats=[fmt])
        return DownloadTask(
            id=DownloadId.generate(),
            media=media,
            selected_format=fmt,
            destination_path="C:/Downloads/video.mp4"
        )

    def test_initial_state_and_valid_transitions(self, sample_task: DownloadTask) -> None:
        assert sample_task.status == DownloadState.QUEUED
        assert sample_task.progress_percent == 0.0

        sample_task.transition_to(DownloadState.DOWNLOADING)
        assert sample_task.status == DownloadState.DOWNLOADING
        assert sample_task.started_at is not None

        sample_task.pause()
        assert sample_task.status == DownloadState.PAUSED

        sample_task.resume()
        assert sample_task.status == DownloadState.DOWNLOADING

        sample_task.transition_to(DownloadState.PROCESSING)
        assert sample_task.status == DownloadState.PROCESSING

        sample_task.complete()
        assert sample_task.status == DownloadState.COMPLETED
        assert sample_task.completed_at is not None
        assert sample_task.progress_percent == 100.0

    def test_invalid_state_transition_raises_error(self, sample_task: DownloadTask) -> None:
        # QUEUED -> COMPLETED directly is invalid
        with pytest.raises(InvalidStateTransitionError, match="Transición inválida de estado"):
            sample_task.transition_to(DownloadState.COMPLETED)

    def test_update_progress(self, sample_task: DownloadTask) -> None:
        sample_task.transition_to(DownloadState.DOWNLOADING)
        sample_task.update_progress(downloaded_bytes=500, total_bytes=1000, speed_bps=100.0, eta_seconds=5.0)

        assert sample_task.downloaded_bytes == 500
        assert sample_task.total_bytes == 1000
        assert sample_task.progress_percent == 50.0
        assert sample_task.speed_bps == 100.0
        assert sample_task.eta_seconds == 5.0

    def test_task_fail_and_reset(self, sample_task: DownloadTask) -> None:
        sample_task.transition_to(DownloadState.DOWNLOADING)
        sample_task.fail("Error de conexión a internet")

        assert sample_task.status == DownloadState.FAILED
        assert sample_task.error_message == "Error de conexión a internet"

        # Test reset
        sample_task.reset_to_queued()
        assert sample_task.status == DownloadState.QUEUED
        assert sample_task.error_message is None
        assert sample_task.progress_percent == 0.0
