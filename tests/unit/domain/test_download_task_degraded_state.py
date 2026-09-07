"""Pruebas unitarias para el estado COMPLETED_WITH_DEGRADED_QUALITY y máquina de estados."""
import pytest

from src.domain.entities.download_task import DownloadState, DownloadTask
from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.exceptions.domain_exceptions import InvalidStateTransitionError
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url


def _create_sample_task() -> DownloadTask:
    url = Url("https://youtube.com/watch?v=sample123")
    media = MediaMetadata(media_id=MediaId.generate(), url=url, platform="YouTube", title="Test Title")
    fmt = FormatOption(format_id="137", extension="mp4", height=1080)
    return DownloadTask(
        id=DownloadId.generate(),
        media=media,
        selected_format=fmt,
        destination_path="C:/downloads/sample.mp4",
    )


class TestDownloadTaskDegradedState:
    """Verifica el comportamiento de la máquina de estados con el nuevo estado de calidad adaptada."""

    def test_transition_from_downloading_to_degraded_quality(self) -> None:
        task = _create_sample_task()
        task.transition_to(DownloadState.DOWNLOADING)
        assert task.status == DownloadState.DOWNLOADING

        task.complete_with_degraded_quality("Calidad adaptada a 720p")
        assert task.status == DownloadState.COMPLETED_WITH_DEGRADED_QUALITY
        assert task.quality_warning == "Calidad adaptada a 720p"
        assert task.progress_percent == 100.0
        assert task.completed_at is not None

    def test_transition_from_processing_to_degraded_quality(self) -> None:
        task = _create_sample_task()
        task.transition_to(DownloadState.DOWNLOADING)
        task.transition_to(DownloadState.PROCESSING)
        assert task.status == DownloadState.PROCESSING

        task.complete_with_degraded_quality("Subtítulo omitido")
        assert task.status == DownloadState.COMPLETED_WITH_DEGRADED_QUALITY
        assert task.quality_warning == "Subtítulo omitido"
        assert task.progress_percent == 100.0

    def test_degraded_quality_is_terminal_state(self) -> None:
        task = _create_sample_task()
        task.transition_to(DownloadState.DOWNLOADING)
        task.complete_with_degraded_quality("Aviso")

        with pytest.raises(InvalidStateTransitionError):
            task.transition_to(DownloadState.DOWNLOADING)

        with pytest.raises(InvalidStateTransitionError):
            task.transition_to(DownloadState.COMPLETED)

    def test_cancel_does_nothing_when_already_degraded_completed(self) -> None:
        task = _create_sample_task()
        task.transition_to(DownloadState.DOWNLOADING)
        task.complete_with_degraded_quality("Aviso")

        # Cancelar una tarea ya completada con calidad adaptada es no-op
        task.cancel()
        assert task.status == DownloadState.COMPLETED_WITH_DEGRADED_QUALITY
