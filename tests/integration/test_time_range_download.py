import os
import threading
import time
from typing import Any, Dict, List, Optional
import pytest

from src.application.use_cases.download_media import DownloadMediaUseCase
from src.domain.entities.download_task import DownloadRequest, DownloadTask, DownloadState
from src.domain.entities.format_option import FormatOption, StreamType, DownloadType
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.time_range import TimeRange
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine


class CapturingFakeYoutubeDL:
    """Fake de yt-dlp que almacena todas las opciones configuradas para aserciones."""

    captured_opts: List[Dict[str, Any]] = []

    def __init__(self, opts: Dict[str, Any], fail_with: Optional[Exception] = None) -> None:
        self.opts = opts
        self.fail_with = fail_with
        CapturingFakeYoutubeDL.captured_opts.append(opts)
        self.closed = False

    def extract_info(self, url: str, download: bool = True) -> Dict[str, Any]:
        if not download:
            return {
                "formats": [
                    {"format_id": "137", "ext": "mp4", "height": 1080, "vcodec": "avc1", "acodec": "none"},
                    {"format_id": "140", "ext": "m4a", "height": 0, "vcodec": "none", "acodec": "mp4a"},
                ]
            }

        outtmpl = self.opts["outtmpl"]
        final_path = outtmpl.replace("%(ext)s", "mp4").replace(".audio_src.mp4", ".audio_src.m4a")
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        with open(final_path, "wb") as f:
            f.write(b"\x00" * 2048)

        return {"requested_downloads": [{"filepath": final_path}]}

    def close(self) -> None:
        self.closed = True


class FakeFFmpegAdapter:
    def get_ffmpeg_executable(self) -> str:
        return "ffmpeg"

    def extract_audio_sync(
        self,
        input_path: str,
        output_path: str,
        audio_format: str = "mp3",
        bitrate_kbps: int = 320,
        cancel_event: Optional[threading.Event] = None,
    ) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(b"\x00" * 2048)

    def probe_streams(self, file_path: str) -> Dict[str, Any]:
        return {
            "format_name": "mp4",
            "duration_seconds": 30.0,
            "video": {"codec": "h264", "width": 1920, "height": 1080, "fps": 30.0},
            "audio": {"codec": "aac", "sample_rate": 44100},
        }


class MemoryDownloadRepository:
    def __init__(self) -> None:
        self.saved_tasks: Dict[str, DownloadTask] = {}

    def save(self, task: DownloadTask) -> None:
        self.saved_tasks[task.id.value] = task

    def get_by_id(self, task_id: DownloadId) -> Optional[DownloadTask]:
        return self.saved_tasks.get(task_id.value)


def _make_task(time_range: Optional[TimeRange] = None, is_audio: bool = False, tmp_path=None) -> DownloadTask:
    dest = str(tmp_path / ("test_audio.mp3" if is_audio else "test_video.mp4")) if tmp_path else "test.mp4"
    stream = StreamType.AUDIO_ONLY if is_audio else StreamType.VIDEO_AUDIO
    dl_type = DownloadType.AUDIO if is_audio else DownloadType.VIDEO
    fmt = FormatOption(
        format_id="best" if not is_audio else "best_audio",
        extension="mp3" if is_audio else "mp4",
        resolution="1080p" if not is_audio else "audio",
        stream_type=stream,
        download_type=dl_type,
        is_audio_only=is_audio,
        is_video_only=not is_audio,
        height=0 if is_audio else 1080,
    )
    media = MediaMetadata(
        media_id=MediaId.from_string("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        url=Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        platform="YouTube",
        title="Rick Astley - Never Gonna Give You Up",
        duration_seconds=212.0,
        formats=[fmt],
    )
    return DownloadTask(
        id=DownloadId.generate(),
        media=media,
        selected_format=fmt,
        destination_path=dest,
        time_range=time_range,
    )


def test_ytdlp_engine_configures_time_range_video(tmp_path):
    CapturingFakeYoutubeDL.captured_opts.clear()
    repo = MemoryDownloadRepository()
    engine = YtDlpDownloadEngine(
        repository=repo,
        ffmpeg_adapter=FakeFFmpegAdapter(),
        ydl_factory=CapturingFakeYoutubeDL,
    )

def _wait_for(predicate, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_ytdlp_engine_configures_time_range_video(tmp_path):
    CapturingFakeYoutubeDL.captured_opts.clear()
    repo = MemoryDownloadRepository()
    engine = YtDlpDownloadEngine(
        repository=repo,
        ffmpeg_adapter=FakeFFmpegAdapter(),
        ydl_factory=CapturingFakeYoutubeDL,
    )

    tr = TimeRange(start_seconds=15.0, end_seconds=45.0)
    task = _make_task(time_range=tr, is_audio=False, tmp_path=tmp_path)
    task.transition_to(DownloadState.DOWNLOADING)

    engine.download(task)

    assert _wait_for(lambda: task.status in (DownloadState.COMPLETED, DownloadState.FAILED), timeout=8.0)
    assert task.status == DownloadState.COMPLETED
    assert len(CapturingFakeYoutubeDL.captured_opts) >= 1

    # Verificar que las opciones pasadas a yt-dlp contengan download_ranges y force_keyframes_at_cuts
    download_opts = [o for o in CapturingFakeYoutubeDL.captured_opts if not o.get("skip_download")]
    assert len(download_opts) >= 1
    opt = download_opts[0]
    assert "download_ranges" in opt
    assert opt.get("force_keyframes_at_cuts") is True


def test_ytdlp_engine_configures_time_range_audio(tmp_path):
    CapturingFakeYoutubeDL.captured_opts.clear()
    repo = MemoryDownloadRepository()
    engine = YtDlpDownloadEngine(
        repository=repo,
        ffmpeg_adapter=FakeFFmpegAdapter(),
        ydl_factory=CapturingFakeYoutubeDL,
    )

    tr = TimeRange(start_seconds=30.0, end_seconds=90.0)
    task = _make_task(time_range=tr, is_audio=True, tmp_path=tmp_path)
    task.transition_to(DownloadState.DOWNLOADING)

    engine.download(task)

    assert _wait_for(lambda: task.status in (DownloadState.COMPLETED, DownloadState.FAILED), timeout=8.0)
    assert task.status == DownloadState.COMPLETED
    download_opts = [o for o in CapturingFakeYoutubeDL.captured_opts if not o.get("skip_download")]
    assert len(download_opts) >= 1
    opt = download_opts[0]
    assert "download_ranges" in opt
    assert opt.get("force_keyframes_at_cuts") is True


def test_download_media_use_case_with_request(tmp_path):
    repo = MemoryDownloadRepository()
    engine = YtDlpDownloadEngine(
        repository=repo,
        ffmpeg_adapter=FakeFFmpegAdapter(),
        ydl_factory=CapturingFakeYoutubeDL,
    )

    use_case = DownloadMediaUseCase(repository=repo, engine=engine)

    media = MediaMetadata(
        media_id=MediaId.from_string("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        url=Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        platform="YouTube",
        title="Rick Astley - Never Gonna Give You Up",
        duration_seconds=212.0,
        formats=[FormatOption(format_id="best", extension="mp4", resolution="1080p")],
    )

    tr = TimeRange(start_seconds=10.0, end_seconds=60.0)
    dest = str(tmp_path / "clip.mp4")

    req = DownloadRequest(
        media=media,
        format_id="best",
        destination_path=dest,
        time_range=tr,
    )

    task = use_case.execute(req)
    assert task.time_range == tr
    assert task.destination_path == dest
    assert repo.get_by_id(task.id) is not None
