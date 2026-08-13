from src.domain.events.domain_events import (
    DownloadCreatedEvent,
    DownloadProgressChangedEvent,
    DownloadCompletedEvent,
    DownloadFailedEvent,
)
from src.domain.exceptions.domain_exceptions import (
    DomainError,
    InvalidUrlError,
    UnsupportedPlatformError,
    InvalidStateTransitionError,
    DownloadError,
)


class TestDomainEventsAndExceptions:

    def test_domain_events_instantiation(self) -> None:
        event = DownloadCreatedEvent(
            task_id="task_123",
            url="https://youtube.com/watch?v=1",
            destination_path="C:/Downloads/v.mp4"
        )
        assert event.task_id == "task_123"
        assert event.event_id is not None
        assert event.timestamp is not None

        progress_event = DownloadProgressChangedEvent(
            task_id="task_123",
            progress_percent=45.5,
            downloaded_bytes=455,
            total_bytes=1000,
            speed_bps=50.0,
            eta_seconds=10.0
        )
        assert progress_event.progress_percent == 45.5

    def test_domain_exceptions_hierarchy(self) -> None:
        err = InvalidUrlError("URL no válida")
        assert isinstance(err, DomainError)

        plat_err = UnsupportedPlatformError("Plataforma no soportada")
        assert isinstance(plat_err, DomainError)

        trans_err = InvalidStateTransitionError("Transición no válida")
        assert isinstance(trans_err, DomainError)
