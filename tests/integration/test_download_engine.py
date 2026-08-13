import os
import threading
import time

from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import FormatOption, StreamType
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.events.domain_events import (
    DownloadCompletedEvent,
    DownloadFailedEvent,
    DownloadProgressChangedEvent,
)
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus


class FakeYoutubeDL:
    """Fake de yt_dlp.YoutubeDL que simula una descarga real escribiendo bytes en disco."""

    def __init__(self, opts, fail_with=None):
        self.opts = opts
        self.fail_with = fail_with
        self.closed = False

    def extract_info(self, url, download=True):
        if self.fail_with:
            raise self.fail_with

        if download:
            for hook in self.opts.get("progress_hooks", []):
                hook({"status": "downloading", "downloaded_bytes": 512, "total_bytes": 1024, "speed": 2048, "eta": 3})
                hook({"status": "finished", "downloaded_bytes": 1024, "total_bytes": 1024})

            outtmpl = self.opts["outtmpl"]
            final_path = outtmpl.replace("%(ext)s", "mp4")
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            with open(final_path, "wb") as f:
                f.write(b"\x00" * 1024)

            return {"requested_downloads": [{"filepath": final_path}]}
        return {"requested_downloads": []}

    def close(self):
        self.closed = True


class FakeFFmpeg:
    """Fake del adaptador FFmpeg: registra llamadas y escribe archivos de salida."""

    def __init__(self):
        self.extract_calls = []
        self.probed_paths = []

    def get_ffmpeg_executable(self):
        return "ffmpeg"

    def extract_audio_sync(self, input_path, output_path, audio_format="mp3", bitrate_kbps=320, cancel_event=None):
        self.extract_calls.append({
            "input_path": input_path,
            "output_path": output_path,
            "audio_format": audio_format,
            "bitrate_kbps": bitrate_kbps,
        })
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(b"\x00" * 2048)

    def probe_streams(self, file_path):
        self.probed_paths.append(file_path)
        return {
            "format_name": "mp4",
            "duration_seconds": 120.0,
            "video": {"codec": "h264", "width": 1920, "height": 1080, "fps": 25.0},
            "audio": {"codec": "aac", "sample_rate": 44100},
        }


def _make_task(tmp_path, fmt) -> tuple[DownloadTask, str]:
    url = Url("https://youtube.com/watch?v=123")
    media = MediaMetadata(media_id=MediaId.generate(), url=url, platform="YouTube", title="Test Stream", formats=[fmt])
    dest_file = str(tmp_path / "output_test.mp4")
    task = DownloadTask(id=DownloadId.generate(), media=media, selected_format=fmt, destination_path=dest_file)
    return task, dest_file


def _wait_for(predicate, timeout=8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _make_engine(event_bus=None, repo=None, fail_with=None, ffmpeg=None):
    ffmpeg = ffmpeg or FakeFFmpeg()
    engine = YtDlpDownloadEngine(
        event_bus=event_bus,
        ffmpeg_adapter=ffmpeg,
        repository=repo,
        ydl_factory=lambda opts: FakeYoutubeDL(opts, fail_with=fail_with),
    )
    return engine, ffmpeg


class TestYtDlpDownloadEngine:

    def test_full_download_flow_with_event_bus(self, tmp_path) -> None:
        event_bus = InProcessEventBus()
        completed = []
        event_bus.subscribe(DownloadCompletedEvent, lambda e: completed.append(e))

        engine, ffmpeg = _make_engine(event_bus=event_bus)

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, dest_file = _make_task(tmp_path, fmt)

        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: len(completed) == 1)
        assert os.path.exists(dest_file)
        assert os.path.getsize(dest_file) > 0
        assert task.status == DownloadState.COMPLETED
        assert task.progress_percent == 100.0
        assert ffmpeg.probed_paths, "Se debe verificar el archivo final con ffmpeg -i"

    def test_failure_publishes_failed_event_and_persists(self, tmp_path) -> None:
        event_bus = InProcessEventBus()
        failed = []
        event_bus.subscribe(DownloadFailedEvent, lambda e: failed.append(e))

        saved_tasks = []

        class FakeRepo:
            def save(self, task):
                saved_tasks.append(task)

        engine, _ = _make_engine(event_bus=event_bus, repo=FakeRepo(),
                                 fail_with=RuntimeError("HTTP Error 403: Forbidden"))

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY)
        task, dest_file = _make_task(tmp_path, fmt)

        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: len(failed) == 1, timeout=20.0)
        assert task.status == DownloadState.FAILED
        assert "403" in (task.error_message or "")
        assert any(t.status == DownloadState.FAILED for t in saved_tasks)

    def test_progress_events_published(self, tmp_path) -> None:
        event_bus = InProcessEventBus()
        progress = []
        event_bus.subscribe(DownloadProgressChangedEvent, lambda e: progress.append(e))

        engine, _ = _make_engine(event_bus=event_bus)

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY)
        task, _ = _make_task(tmp_path, fmt)

        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        assert len(progress) > 0
        assert all(e.task_id == task.id.value for e in progress)

    def test_audio_extracts_with_own_ffmpeg(self, tmp_path) -> None:
        engine, ffmpeg = _make_engine(event_bus=None)

        fmt = FormatOption(format_id="audio_140_mp3_320", extension="mp3", is_audio_only=True,
                           target_audio_format="mp3", target_audio_bitrate=320)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        assert len(ffmpeg.extract_calls) == 1
        call = ffmpeg.extract_calls[0]
        assert call["audio_format"] == "mp3"
        assert call["bitrate_kbps"] == 320
        assert call["output_path"] == task.destination_path
        assert call["input_path"].endswith(".audio_src.mp4")

    def test_audio_bestaudio_spec(self, tmp_path) -> None:
        seen_opts = {}

        def factory(opts):
            seen_opts.update(opts)
            return FakeYoutubeDL(opts)

        engine, ffmpeg = _make_engine(event_bus=None)
        engine._ydl_factory = factory

        fmt = FormatOption(format_id="audio_251_m4a_192", extension="m4a", is_audio_only=True,
                           target_audio_format="m4a", target_audio_bitrate=192)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        assert seen_opts["format"] == "bestaudio/best"
        assert ffmpeg.extract_calls[0]["audio_format"] == "m4a"
        assert ffmpeg.extract_calls[0]["bitrate_kbps"] == 192

    def test_video_height_spec_prefers_avc1_mp4a(self, tmp_path) -> None:
        seen_opts = {}

        def factory(opts):
            seen_opts.update(opts)
            return FakeYoutubeDL(opts)

        engine, _ = _make_engine(event_bus=None)
        engine._ydl_factory = factory

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        assert seen_opts["format"] == (
            "bestvideo[height<=?1080][vcodec^=avc1]+bestaudio[acodec^=mp4a]"
            "/bestvideo[height<=?1080]+bestaudio[acodec^=mp4a]"
            "/bestvideo[height<=?1080]+bestaudio/best"
        )
        assert seen_opts["merge_output_format"] == "mp4"

    def test_best_quality_spec_no_height_limit(self, tmp_path) -> None:
        seen_opts = {}

        def factory(opts):
            seen_opts.update(opts)
            return FakeYoutubeDL(opts)

        engine, _ = _make_engine(event_bus=None)
        engine._ydl_factory = factory

        fmt = FormatOption(format_id="best_quality", extension="mp4", height=2160,
                           stream_type=StreamType.VIDEO_ONLY, is_best_quality=True, needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        assert seen_opts["format"] == (
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
            "/bestvideo+bestaudio[acodec^=mp4a]"
            "/bestvideo+bestaudio/best"
        )

    def test_cancel_cleans_temporary_files(self, tmp_path) -> None:
        class CancelFakeYDL(FakeYoutubeDL):
            def extract_info(self, url, download=True):
                # Simular que el usuario cancela durante la descarga
                for hook in self.opts.get("progress_hooks", []):
                    hook({"status": "downloading", "downloaded_bytes": 128, "total_bytes": 1024})
                # Escribir un .part residual para verificar la limpieza
                outtmpl = self.opts["outtmpl"]
                part_path = outtmpl.replace("%(ext)s", "mp4") + ".part"
                os.makedirs(os.path.dirname(part_path), exist_ok=True)
                with open(part_path, "wb") as f:
                    f.write(b"\x00" * 256)
                return super().extract_info(url, download=download)

        event_bus = InProcessEventBus()
        saved = []

        class FakeRepo:
            def save(self, task):
                saved.append(task)

        ffmpeg = FakeFFmpeg()
        engine = YtDlpDownloadEngine(
            event_bus=event_bus,
            ffmpeg_adapter=ffmpeg,
            repository=FakeRepo(),
            ydl_factory=lambda opts: CancelFakeYDL(opts),
        )

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY)
        task, dest_file = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)
        engine.cancel(task)

        assert _wait_for(lambda: task.status == DownloadState.CANCELLED, timeout=15.0)
        assert not os.path.exists(dest_file + ".part")
        assert any(t.status == DownloadState.CANCELLED for t in saved)
