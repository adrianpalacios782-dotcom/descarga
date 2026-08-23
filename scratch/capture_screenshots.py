"""Capturas de evidencia del flujo corregido (Qt offscreen)."""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

OUT = Path(__file__).parent / "screenshots"
OUT.mkdir(exist_ok=True)

from src.domain.entities.download_task import DownloadTask
from src.domain.entities.format_option import DownloadType
from src.domain.services.format_normalizer import FormatNormalizer
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.domain.entities.media_metadata import MediaMetadata

# Cadena DASH realista de YouTube (itags reales conocidos; alturas recortadas incluidas)
FULL_LADDER = [
    {"format_id": "sb0", "ext": "mhtml", "vcodec": "none", "acodec": "none"},
    {"format_id": "315", "ext": "webm", "height": 2160, "fps": 60, "vcodec": "vp9", "acodec": "none",
     "filesize_approx": 812_000_000},
    {"format_id": "308", "ext": "webm", "height": 1440, "fps": 60, "vcodec": "vp9", "acodec": "none",
     "filesize_approx": 384_000_000},
    {"format_id": "137", "ext": "mp4", "height": 1074, "fps": 24, "vcodec": "avc1.640028", "acodec": "none"},
    {"format_id": "136", "ext": "mp4", "height": 718, "fps": 24, "vcodec": "avc1.4d401f", "acodec": "none"},
    {"format_id": "135", "ext": "mp4", "height": 476, "fps": 24, "vcodec": "avc1.4d401e", "acodec": "none"},
    {"format_id": "18", "ext": "mp4", "height": 354, "fps": 24, "vcodec": "avc1.42001E", "acodec": "mp4a.40.2"},
    {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 129},
    {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus", "tbr": 160,
     "filesize": 4_100_000},
]

# Respuesta real observada en sandbox (cliente android, IP restringida)
CAPPED_REAL = [
    {"format_id": "sb0", "ext": "mhtml", "vcodec": "none", "acodec": "none"},
    {"format_id": "18", "ext": "mp4", "resolution": "640x338", "fps": 24,
     "vcodec": "avc1.42001E", "acodec": "mp4a.40.2"},
]

AUDIO_ONLY = [
    {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 129,
     "filesize": 3_900_000},
]


def make_media(raw, url="https://www.youtube.com/watch?v=eUX086mraqc"):
    u = Url(url)
    return MediaMetadata(
        media_id=MediaId.from_string(u.value),
        url=u,
        platform="YouTube",
        title="Junior H - PARIS [Official Visualizer]",
        duration_seconds=236.0,
        thumbnail_url="",
        video_quality_options=FormatNormalizer.normalize_video_quality_options(raw),
        video_formats=FormatNormalizer.normalize_video_formats(raw),
        audio_formats=FormatNormalizer.normalize_audio_formats(raw),
        formats=FormatNormalizer.normalize(raw),
    )


def flush(app, ms=400):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    from src.presentation.views.inicio_view import InicioView
    from src.presentation.components.download_card import DownloadCardWidget

    # 1) Escalera completa: tarjetas + Mejor calidad + tamanios
    view = InicioView()
    view.resize(980, 900)
    view.set_metadata(make_media(FULL_LADDER))
    flush(app)
    view.grab().save(str(OUT / "01_tarjetas_calidad_escalon_completo.png"))
    print("01 labels:", [r.vqo.label for r in view._iter_quality_rows()])
    view.close()

    # 2) Respuesta real capped (android/IP restringida): una sola tarjeta real
    view = InicioView()
    view.resize(980, 700)
    view.set_metadata(make_media(CAPPED_REAL))
    flush(app)
    view.grab().save(str(OUT / "02_caso_c_ip_restringida_solo_360p.png"))
    print("02 labels:", [r.vqo.label for r in view._iter_quality_rows()],
          "| btn habilitado:", view.btn_download.isEnabled())
    view.close()

    # 3) Sin calidades de video: boton deshabilitado + mensaje inline (sin QMessageBox)
    view = InicioView()
    view.resize(980, 500)
    md = make_media(AUDIO_ONLY)
    view.set_metadata(md)
    flush(app)
    view.btn_format_video.setChecked(True)
    flush(app)
    view.grab().save(str(OUT / "03_sin_calidades_boton_deshabilitado_inline.png"))
    print("03 resumen:", repr(view.lbl_selection_summary.text()), "| btn:", view.btn_download.isEnabled())
    view.close()

    # 4) Tarjeta COMPLETED con advertencia de calidad ambar
    card = DownloadCardWidget(_make_completed_task_with_warning())
    from src.domain.entities.download_task import DownloadState as _DS
    card.set_state(_DS.COMPLETED)
    card.set_quality_warning("Se solicitó 1080p pero el servidor solo permitió descargar 720p.")
    card.resize(560, 190)
    flush(app)
    card.grab().save(str(OUT / "04_tarjeta_completada_con_advertencia.png"))
    print("04 warning label:", repr(card.warning_label.text()))
    card.close()


def _make_completed_task_with_warning():
    from src.domain.entities.format_option import FormatOption, StreamType
    u = Url("https://www.youtube.com/watch?v=eUX086mraqc")
    media = MediaMetadata(
        media_id=MediaId.from_string(u.value), url=u, platform="YouTube",
        title="Junior H - PARIS [Official Visualizer]", duration_seconds=236.0,
        formats=FormatNormalizer.normalize(CAPPED_REAL),
    )
    fmt = FormatOption(
        format_id="137", extension="mp4", height=1080, resolution="1080p",
        stream_type=StreamType.VIDEO_ONLY, needs_ffmpeg_merge=True,
    )
    task = DownloadTask(
        id=DownloadId.generate(), media=media,
        selected_format=fmt, destination_path=r"D:\Descargas\Junior H - PARIS.mp4",
    )
    task.total_bytes = 4_100_000
    task.downloaded_bytes = 4_100_000
    task.progress_percent = 100.0
    task.quality_warning = "Se solicitó 1080p pero el servidor solo permitió descargar 720p."
    return task


if __name__ == "__main__":
    main()
