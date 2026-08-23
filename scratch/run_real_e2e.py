"""Prueba funcional REAL de extremo a extremo: analisis -> creacion -> descarga.

Ejecuta el pipeline completo de la app (adapter yt-dlp real, motor de descarga
real, ffmpeg incluido en bin/) contra YouTube desde esta maquina.
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OUT_DIR = Path(__file__).parent / "e2e_output"
OUT_DIR.mkdir(exist_ok=True)

from src.application.use_cases import CreateDownloadUseCase, StartDownloadUseCase
from src.domain.entities.download_task import DownloadState
from src.domain.events.domain_events import (
    DownloadCompletedEvent,
    DownloadFailedEvent,
    DownloadProgressChangedEvent,
)
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter
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


def run_case(label: str, url: str, quality: str, dest_name: str) -> None:
    print(f"\n========== {label} ==========")
    bus = InProcessEventBus()
    log = []
    bus.subscribe(DownloadProgressChangedEvent, lambda e: log.append(("progress", round(e.progress_percentage or 0))))
    bus.subscribe(DownloadCompletedEvent, lambda e: log.append(("completed", e.warning_message)))
    bus.subscribe(DownloadFailedEvent, lambda e: log.append(("failed", e.error_message)))

    repo = MemRepo()
    engine = YtDlpDownloadEngine(
        event_bus=bus,
        ffmpeg_adapter=FFmpegProcessAdapter(custom_binary_path=str(Path(__file__).parents[1] / "bin" / "ffmpeg.exe")),
        repository=repo,
    )
    create = CreateDownloadUseCase(repo)
    start = StartDownloadUseCase(repo, engine)

    print("[1] Analizando con adapter real...")
    metadata = YouTubeAdapter().analyze(Url(url))
    print("    tarjetas:", [o.label for o in metadata.video_quality_options])

    print(f"[2] Creando tarea con seleccion '{quality}'...")
    try:
        task = create.execute(metadata, quality, str(OUT_DIR / dest_name))
    except Exception as ex:
        print(f"    -> {type(ex).__name__}: {str(ex)[:140]} (esperado si la calidad no existe)")
        return

    fmt = task.selected_format
    print(
        f"    formato elegido: id={fmt.format_id} h={fmt.height} "
        f"audio={fmt.audio_format_id} merge={fmt.needs_ffmpeg_merge}"
    )

    print("[3] Descargando con motor + ffmpeg reales...")
    import time as _t
    start.execute(task.id)
    final = None
    for _ in range(600):  # hasta 5 minutos
        _t.sleep(0.5)
        final = repo.get_by_id(task.id)
        if final.status in (DownloadState.COMPLETED, DownloadState.FAILED, DownloadState.CANCELLED):
            break

    events = [l for l in log if l[0] != "progress"]
    last_progress = max([p for t, p in log if t == "progress"], default=None)
    print(f"    progreso maximo observado: {last_progress}%")
    for ev in events:
        print("    evento:", ev)
    print(f"    estado final: {final.status}")
    print(f"    quality_warning: {final.quality_warning!r}")
    if final.error_message:
        print(f"    error_message: {final.error_message[:200]}")
    out = Path(final.destination_path)
    print(f"    archivo existe: {out.exists()}  tamano: {out.stat().st_size if out.exists() else 0:,} bytes")


if __name__ == "__main__":
    # CASO C: el video que antes mostraba CALIDAD DE VIDEO vacia -> ahora descarga.
    run_case(
        "CASO C - PARIS 360p (antes sin tarjetas)",
        "https://www.youtube.com/watch?v=eUX086mraqc",
        "vq_360",
        "paris_360.mp4",
    )
    # CASO B invertido: pedir una calidad que el servidor NO ofrece -> debe fallar
    # ANTES de descargar y conservar estado FAILED coherente (sin archivo parcial).
    run_case(
        "CASO NEGATIVO - OTRO AMOR pidiendo 1080p no disponible",
        "https://www.youtube.com/watch?v=F3tKutGo1Fo",
        "vq_1080",
        "otroamor_1080.mp4",
    )
