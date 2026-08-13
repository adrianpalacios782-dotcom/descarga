from concurrent.futures import ThreadPoolExecutor
from src.domain.events.domain_events import DownloadCreatedEvent, DownloadProgressChangedEvent
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus


class TestInProcessEventBus:

    def test_subscribe_and_publish_event(self) -> None:
        bus = InProcessEventBus()
        received_events = []

        def handler(event: DownloadCreatedEvent) -> None:
            received_events.append(event)

        bus.subscribe(DownloadCreatedEvent, handler)

        event = DownloadCreatedEvent(
            task_id="task_001",
            url="https://youtube.com/watch?v=123",
            destination_path="C:/Downloads/video.mp4"
        )
        bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0].task_id == "task_001"

    def test_unsubscribe(self) -> None:
        bus = InProcessEventBus()
        received_events = []

        def handler(event: DownloadCreatedEvent) -> None:
            received_events.append(event)

        bus.subscribe(DownloadCreatedEvent, handler)
        bus.unsubscribe(DownloadCreatedEvent, handler)

        event = DownloadCreatedEvent(
            task_id="task_002",
            url="https://youtube.com/watch?v=123",
            destination_path="C:/Downloads/video.mp4"
        )
        bus.publish(event)

        assert len(received_events) == 0

    def test_error_isolation_in_handler(self) -> None:
        bus = InProcessEventBus()
        successful_calls = []

        def failing_handler(event: DownloadCreatedEvent) -> None:
            raise RuntimeError("Fallo simulado en el listener")

        def ok_handler(event: DownloadCreatedEvent) -> None:
            successful_calls.append(event.task_id)

        bus.subscribe(DownloadCreatedEvent, failing_handler)
        bus.subscribe(DownloadCreatedEvent, ok_handler)

        event = DownloadCreatedEvent(
            task_id="task_003",
            url="https://youtube.com/watch?v=123",
            destination_path="C:/Downloads/video.mp4"
        )
        bus.publish(event)

        # El ok_handler debe ejecutarse a pesar del fallo en failing_handler
        assert len(successful_calls) == 1
        assert successful_calls[0] == "task_003"

    def test_concurrent_publishing(self) -> None:
        bus = InProcessEventBus()
        counter = {"count": 0}

        def handler(event: DownloadProgressChangedEvent) -> None:
            counter["count"] += 1

        bus.subscribe(DownloadProgressChangedEvent, handler)

        def publish_task(i: int) -> None:
            event = DownloadProgressChangedEvent(
                task_id=f"task_{i}",
                progress_percent=float(i),
                downloaded_bytes=i * 10,
                total_bytes=1000,
                speed_bps=100.0,
                eta_seconds=10.0
            )
            bus.publish(event)

        with ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(publish_task, range(20)))

        assert counter["count"] == 20
