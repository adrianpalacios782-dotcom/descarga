"""Prueba funcional REAL del motor de descarga sobre HTTP local.

YouTube bloquea por IP este entorno (bot-check en todos los clientes), así que
se ejercita el pipeline REAL completo — yt-dlp real, progreso real, ffprobe real,
eventos reales — contra un MP4 servido por HTTP local:

  CASO 1 (feliz):    pedir exactamente lo que existe (360p) -> COMPLETED sin warning.
  CASO 2 (anti-CASO B): pedir 720p cuando solo hay 360p -> FAILED temprano con
                     FormatNotFoundError listando calidades, sin archivo parcial.
"""
import io
import sys
import threading
import functools
import http.server
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).parents[1]
SRC_DIR = Path(__file__).parent / "e2e_output" / "src"
OUT_DIR = Path(__file__).parent / "e2e_output"
PORT = 8765

from src.domain.entities.download_task import DownloadState
from src.domain.entities.format_option import FormatOption, StreamType
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus


class MemRepo:
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


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SRC_DIR))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def run_case(label: str, requested_height: int) -> None:
    print(f"\n===== {label} =====")
    bus = InProcessEventBus()
    log = []
    bus.subscribe(type("P", (), {}), lambda e: None) if False else None
    from src.domain.events.domain_events import (
        DownloadCompletedEvent, DownloadFailedEvent, DownloadProgressChangedEvent,
    )
    bus.subscribe(DownloadProgressChangedEvent, lambda e: log.append(("progress", round(e.progress_percentage or 0))))
    bus.subscribe(DownloadCompletedEvent, lambda e: log.append(("completed", e.warning_message)))
    bus.subscribe(DownloadFailedEvent, lambda e: log.append(("failed", e.error_message)))

    url = Url(f"http://127.0.0.1:{PORT}/test_360.mp4")
    media = MediaMetadata(
        media_id=MediaId.from_string(url.value),
        url=url,
        platform="Generic",
        title="test_360",
        duration_seconds=5.0,
        formats=[],
    )
    fmt = FormatOption(
        format_id="mp4",
        extension="mp4",
        height=requested_height,
        stream_type=StreamType.VIDEO_AUDIO,
        needs_ffmpeg_merge=False,
    )
    dest = str(OUT_DIR / f"descarga_{requested_height}p.mp4")
    task = DownloadTask(id=DownloadId.generate(), media=media, selected_format=fmt, destination_path=dest)

    engine = YtDlpDownloadEngine(
        event_bus=bus,
        ffmpeg_adapter=FFmpegProcessAdapter(custom_binary_path=str(ROOT / "bin" / "ffmpeg.exe")),
        repository=MemRepo(),
    )
    task.transition_to(DownloadState.DOWNLOADING)
    engine.download(task)

    import time as _t
    for _ in range(240):
        if task.status in (DownloadState.COMPLETED, DownloadState.FAILED):
            break
        _t.sleep(0.25)

    prog = [p for k, p in log if k == "progress"]
    print(f"    estado final: {task.status}")
    print(f"    eventos de progreso: {len(prog)} (max {max(prog) if prog else '-'}%)")
    for k, v in log:
        if k in ("completed", "failed"):
            print(f"    evento {k}: {str(v)[:160]}")
    out = Path(dest)
    print(f"    archivo existe: {out.exists()}  tamano: {out.stat().st_size if out.exists() else 0:,} bytes")
    if out.exists():
        probe = FFmpegProcessAdapter(custom_binary_path=str(ROOT / 'bin' / 'ffmpeg.exe')).probe_streams(str(out))
        print(f"    ffprobe del archivo descargado: video={probe['video']['codec']} "
              f"{probe['video']['width']}x{probe['video']['height']} audio={probe.get('audio', {}).get('codec')}")


if __name__ == "__main__":
    httpd = serve()
    try:
        run_case("CASO 1 - pedido 360p (existe) -> COMPLETED", 360)
        run_case("CASO 2 - pedido 720p (NO existe) -> FAILED temprano", 720)
    finally:
        httpd.shutdown()
