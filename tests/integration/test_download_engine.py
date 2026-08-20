import os
import threading
import time

from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import FormatOption, StreamType
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.exceptions.domain_exceptions import FormatNotFoundError, QualityDegradationError
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


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

# Formatos de prueba que simulan una respuesta real de YouTube (None client)
PROBE_FORMATS_1080P = [
    {"format_id": "sb0", "ext": "mhtml", "height": 180, "vcodec": "none", "acodec": "none"},
    {"format_id": "160", "ext": "mp4", "height": 144, "vcodec": "avc1.4d400c", "acodec": "none"},
    {"format_id": "133", "ext": "mp4", "height": 240, "vcodec": "avc1.4d4015", "acodec": "none"},
    {"format_id": "134", "ext": "mp4", "height": 360, "vcodec": "avc1.4d401e", "acodec": "none"},
    {"format_id": "135", "ext": "mp4", "height": 480, "vcodec": "avc1.4d401e", "acodec": "none"},
    {"format_id": "136", "ext": "mp4", "height": 720, "vcodec": "avc1.4d401f", "acodec": "none"},
    {"format_id": "137", "ext": "mp4", "height": 1080, "vcodec": "avc1.640028", "acodec": "none"},
    {"format_id": "140", "ext": "m4a", "height": 0, "vcodec": "none", "acodec": "mp4a.40.2"},
    {"format_id": "251", "ext": "webm", "height": 0, "vcodec": "none", "acodec": "opus"},
]

PROBE_FORMATS_MAX_720P = [
    {"format_id": "sb0", "ext": "mhtml", "height": 180, "vcodec": "none", "acodec": "none"},
    {"format_id": "160", "ext": "mp4", "height": 144, "vcodec": "avc1.4d400c", "acodec": "none"},
    {"format_id": "133", "ext": "mp4", "height": 240, "vcodec": "avc1.4d4015", "acodec": "none"},
    {"format_id": "134", "ext": "mp4", "height": 360, "vcodec": "avc1.4d401e", "acodec": "none"},
    {"format_id": "135", "ext": "mp4", "height": 480, "vcodec": "avc1.4d401e", "acodec": "none"},
    {"format_id": "136", "ext": "mp4", "height": 720, "vcodec": "avc1.4d401f", "acodec": "none"},
    {"format_id": "140", "ext": "m4a", "height": 0, "vcodec": "none", "acodec": "mp4a.40.2"},
]

PROBE_FORMATS_360P_ONLY = [
    {"format_id": "18", "ext": "mp4", "height": 360, "vcodec": "avc1.42001E", "acodec": "mp4a.40.2"},
    {"format_id": "140", "ext": "m4a", "height": 0, "vcodec": "none", "acodec": "mp4a.40.2"},
]


class FakeYoutubeDL:
    """Fake de yt_dlp.YoutubeDL que simula sondeo y descarga real escribiendo bytes en disco."""

    def __init__(self, opts, fail_with=None, probe_formats=None):
        self.opts = opts
        self.fail_with = fail_with
        self.probe_formats = probe_formats or PROBE_FORMATS_1080P
        self.closed = False

    def extract_info(self, url, download=True):
        if self.fail_with:
            raise self.fail_with

        if not download:
            return {"formats": self.probe_formats}

        for hook in self.opts.get("progress_hooks", []):
            hook({"status": "downloading", "downloaded_bytes": 512, "total_bytes": 1024, "speed": 2048, "eta": 3})
            hook({"status": "finished", "downloaded_bytes": 1024, "total_bytes": 1024})

        outtmpl = self.opts["outtmpl"]
        final_path = outtmpl.replace("%(ext)s", "mp4")
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        with open(final_path, "wb") as f:
            f.write(b"\x00" * 1024)

        return {"requested_downloads": [{"filepath": final_path}]}

    def close(self):
        self.closed = True


class FakeFFmpeg:
    """Fake del adaptador FFmpeg: registra llamadas y escribe archivos de salida."""

    def __init__(self, video_height=1080):
        self.extract_calls = []
        self.probed_paths = []
        self._video_height = video_height

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
            "video": {"codec": "h264", "width": 1920, "height": self._video_height, "fps": 25.0},
            "audio": {"codec": "aac", "sample_rate": 44100},
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(tmp_path, fmt, probe_formats=None) -> tuple:
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


def _make_engine(event_bus=None, repo=None, fail_with=None, ffmpeg=None, probe_formats=None):
    ffmpeg = ffmpeg or FakeFFmpeg()
    pf = probe_formats or PROBE_FORMATS_1080P
    engine = YtDlpDownloadEngine(
        event_bus=event_bus,
        ffmpeg_adapter=ffmpeg,
        repository=repo,
        ydl_factory=lambda opts: FakeYoutubeDL(opts, fail_with=fail_with, probe_formats=pf),
    )
    return engine, ffmpeg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

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
            "137+bestaudio[acodec^=mp4a]"
            "/137+bestaudio"
            "/bestvideo[height<=1080][vcodec^=avc1]+bestaudio[acodec^=mp4a]"
            "/bestvideo[height<=1080]+bestaudio[acodec^=mp4a]"
            "/bestvideo[height<=1080]+bestaudio"
            "/bestvideo+bestaudio"
            "/best"
        )
        assert seen_opts["merge_output_format"] == "mp4"
        assert seen_opts["allow_multi_streams"] is True

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
        assert seen_opts["allow_multi_streams"] is True

    def test_cancel_cleans_temporary_files(self, tmp_path) -> None:
        class CancelFakeYDL(FakeYoutubeDL):
            def extract_info(self, url, download=True):
                if not download:
                    return super().extract_info(url, download=False)
                for hook in self.opts.get("progress_hooks", []):
                    hook({"status": "downloading", "downloaded_bytes": 128, "total_bytes": 1024})
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

    def test_no_player_client_restriction(self, tmp_path) -> None:
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
        assert "extractor_args" not in seen_opts

    def test_probe_uses_no_restriction(self, tmp_path) -> None:
        seen_opts = []

        def factory(opts):
            seen_opts.append(opts)
            return FakeYoutubeDL(opts)

        engine, _ = _make_engine(event_bus=None)
        engine._ydl_factory = factory

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        probe_opts = seen_opts[0]
        assert probe_opts["skip_download"] is True
        assert probe_opts["format"] == "all"
        assert "extractor_args" not in probe_opts

    def test_360p_request(self, tmp_path) -> None:
        seen_opts = {}

        def factory(opts):
            seen_opts.update(opts)
            return FakeYoutubeDL(opts)

        engine, ffmpeg = _make_engine(event_bus=None, ffmpeg=FakeFFmpeg(video_height=360))
        engine._ydl_factory = factory

        fmt = FormatOption(format_id="134", extension="mp4", height=360, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        assert "134+bestaudio" in seen_opts["format"]

    def test_480p_request(self, tmp_path) -> None:
        seen_opts = {}

        def factory(opts):
            seen_opts.update(opts)
            return FakeYoutubeDL(opts)

        engine, ffmpeg = _make_engine(event_bus=None, ffmpeg=FakeFFmpeg(video_height=480))
        engine._ydl_factory = factory

        fmt = FormatOption(format_id="135", extension="mp4", height=480, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        assert "135+bestaudio" in seen_opts["format"]

    def test_720p_request(self, tmp_path) -> None:
        seen_opts = {}

        def factory(opts):
            seen_opts.update(opts)
            return FakeYoutubeDL(opts)

        engine, ffmpeg = _make_engine(event_bus=None, ffmpeg=FakeFFmpeg(video_height=720))
        engine._ydl_factory = factory

        fmt = FormatOption(format_id="136", extension="mp4", height=720, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        assert "136+bestaudio" in seen_opts["format"]

    def test_1080p_request(self, tmp_path) -> None:
        seen_opts = {}

        def factory(opts):
            seen_opts.update(opts)
            return FakeYoutubeDL(opts)

        engine, ffmpeg = _make_engine(event_bus=None, ffmpeg=FakeFFmpeg(video_height=1080))
        engine._ydl_factory = factory

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        assert "137+bestaudio" in seen_opts["format"]
        assert "format_sort" not in seen_opts

    def test_1080p_not_available_fails(self, tmp_path) -> None:
        event_bus = InProcessEventBus()
        failed = []
        event_bus.subscribe(DownloadFailedEvent, lambda e: failed.append(e))

        engine, _ = _make_engine(event_bus=event_bus, probe_formats=PROBE_FORMATS_MAX_720P)

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: len(failed) == 1, timeout=15.0)
        assert task.status == DownloadState.FAILED
        assert "1080p" in (task.error_message or "")
        assert "no está disponible" in (task.error_message or "")
        assert "720p" in (task.error_message or "")

    def test_1080p_only_360p_available_fails(self, tmp_path) -> None:
        event_bus = InProcessEventBus()
        failed = []
        event_bus.subscribe(DownloadFailedEvent, lambda e: failed.append(e))

        engine, _ = _make_engine(event_bus=event_bus, probe_formats=PROBE_FORMATS_360P_ONLY)

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: len(failed) == 1, timeout=15.0)
        assert task.status == DownloadState.FAILED
        assert "1080p" in (task.error_message or "")
        assert "360p" in (task.error_message or "")

    def test_quality_degradation_detected(self, tmp_path) -> None:
        event_bus = InProcessEventBus()
        failed = []
        event_bus.subscribe(DownloadFailedEvent, lambda e: failed.append(e))

        ffmpeg = FakeFFmpeg(video_height=360)
        engine, _ = _make_engine(event_bus=event_bus, ffmpeg=ffmpeg)

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: len(failed) == 1, timeout=15.0)
        assert task.status == DownloadState.FAILED
        assert "degradada" in (task.error_message or "").lower()
        assert "1080p" in (task.error_message or "")
        assert "360p" in (task.error_message or "")

    def test_quality_within_tolerance_accepted(self, tmp_path) -> None:
        event_bus = InProcessEventBus()
        completed = []
        event_bus.subscribe(DownloadCompletedEvent, lambda e: completed.append(e))

        ffmpeg = FakeFFmpeg(video_height=1000)
        engine, _ = _make_engine(event_bus=event_bus, ffmpeg=ffmpeg)

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: len(completed) == 1)
        assert task.status == DownloadState.COMPLETED

    def test_no_silent_degradation_to_360p(self, tmp_path) -> None:
        event_bus = InProcessEventBus()
        completed = []
        failed = []
        event_bus.subscribe(DownloadCompletedEvent, lambda e: completed.append(e))
        event_bus.subscribe(DownloadFailedEvent, lambda e: failed.append(e))

        ffmpeg = FakeFFmpeg(video_height=360)
        engine, _ = _make_engine(event_bus=event_bus, ffmpeg=ffmpeg)

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: len(completed) == 1 or len(failed) == 1, timeout=15.0)
        assert len(completed) == 0, "La descarga NO debe completarse si la calidad se degradó a 360p"
        assert len(failed) == 1, "Debe reportarse como fallida"

    def test_format_not_found_error_message_includes_available(self, tmp_path) -> None:
        event_bus = InProcessEventBus()
        failed = []
        event_bus.subscribe(DownloadFailedEvent, lambda e: failed.append(e))

        engine, _ = _make_engine(event_bus=event_bus, probe_formats=PROBE_FORMATS_MAX_720P)

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: len(failed) == 1, timeout=15.0)
        msg = task.error_message or ""
        assert "no está disponible" in msg
        assert "720p" in msg
        assert "480p" in msg
        assert "360p" in msg

    def test_no_download_when_format_not_available(self, tmp_path) -> None:
        download_attempted = []

        class ProbeOnlyYDL(FakeYoutubeDL):
            def extract_info(self, url, download=True):
                if download:
                    download_attempted.append(True)
                return super().extract_info(url, download=download)

        engine, _ = _make_engine(event_bus=None, probe_formats=PROBE_FORMATS_MAX_720P)
        engine._ydl_factory = lambda opts: ProbeOnlyYDL(opts, probe_formats=PROBE_FORMATS_MAX_720P)

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)

        try:
            engine.download(task)
        except Exception:
            pass

        assert len(download_attempted) == 0, "No se debe intentar descargar si el formato no está disponible"

    def test_three_phase_logging(self, tmp_path) -> None:
        logs = []
        import logging

        eng_logger = logging.getLogger("src.infrastructure.adapters.download.ytdlp_download_engine")
        handler = logging.Handler()
        handler.emit = lambda record: logs.append(record.getMessage())
        eng_logger.addHandler(handler)
        eng_logger.setLevel(logging.DEBUG)

        engine, _ = _make_engine(event_bus=None, ffmpeg=FakeFFmpeg(video_height=1080))

        fmt = FormatOption(format_id="137", extension="mp4", height=1080, stream_type=StreamType.VIDEO_ONLY,
                           needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        log_text = " ".join(logs)
        assert "Solicitado=1080p" in log_text
        assert "final=1080p" in log_text

        eng_logger.removeHandler(handler)

    def test_format_id_used_in_spec(self, tmp_path) -> None:
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
        spec = seen_opts["format"]
        assert spec.startswith("137+bestaudio"), f"El spec debe usar format_id '137' como primario, got: {spec}"
        assert "137" in spec
        assert "bestvideo[height<=1080]" in spec

    def test_non_numeric_format_id_uses_height_fallback(self, tmp_path) -> None:
        seen_opts = {}

        def factory(opts):
            seen_opts.update(opts)
            return FakeYoutubeDL(opts)

        engine, _ = _make_engine(event_bus=None)
        engine._ydl_factory = factory

        fmt = FormatOption(format_id="best_quality", extension="mp4", height=1080,
                           stream_type=StreamType.VIDEO_ONLY, is_best_quality=True, needs_ffmpeg_merge=True)
        task, _ = _make_task(tmp_path, fmt)
        task.transition_to(DownloadState.DOWNLOADING)
        engine.download(task)

        assert _wait_for(lambda: task.status == DownloadState.COMPLETED)
        spec = seen_opts["format"]
        assert spec.startswith("bestvideo[vcodec^=avc1]"), f"best_quality no debe usar format_id crudo, got: {spec}"

    def test_best_quality_never_uses_raw_format_id(self, tmp_path) -> None:
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
        spec = seen_opts["format"]
        assert "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]" in spec
