import os
import sys

# Agregar la raíz del proyecto a sys.path para permitir ejecuciones directas (python src/main.py)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def main() -> None:
    # 1. Setup Logging
    from src.infrastructure.logging.logger_config import setup_logger

    app_data_dir = os.path.join(os.path.expanduser("~"), ".osvaldoDownloaderPro")
    os.makedirs(app_data_dir, exist_ok=True)
    setup_logger(log_dir=os.path.join(app_data_dir, "logs"))

    # 2. ACTIVACIÓN TEMPRANA DEL MOTOR --------------------------------------
    # Debe ejecutarse ANTES de cualquier módulo que haga `import yt_dlp`
    # (adaptadores de plataformas/descarga): si hay una wheel verificada en
    # %APPDATA%/osvaldoDownloaderPro/engine/, sys.path se antepone aquí y el
    # primer import resuelve ESA versión. Falta/corrupción → fallback
    # transparente al motor empaquetado. Por eso todos los imports pesados del
    # proyecto viven dentro de esta función y NO a nivel de módulo.
    from src.infrastructure.adapters.engine import get_engine_manager

    try:
        get_engine_manager().activate()
    except Exception:  # noqa: BLE001 - sin motor dinámico la app sigue igual
        pass

    # 3. Infraestructura (imports tras activar el motor)
    from PySide6.QtWidgets import QApplication

    from src.infrastructure.adapters.download.download_queue_manager import (
        DownloadQueueManager,
    )
    from src.infrastructure.adapters.download.ytdlp_download_engine import (
        YtDlpDownloadEngine,
    )
    from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
    from src.infrastructure.adapters.platforms.platform_registry import PlatformRegistry
    from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
    from src.infrastructure.adapters.storage.sqlite_repository import (
        SQLiteDownloadRepository,
    )
    from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus
    from src.presentation.main_window import MainWindow
    from src.presentation.view_models.main_view_model import MainViewModel

    db_path = os.path.join(app_data_dir, "osvaldo_downloader.db")
    db_manager = DatabaseManager(db_path=db_path)
    db_manager.init_tables()

    repository = SQLiteDownloadRepository(db_manager=db_manager)
    event_bus = InProcessEventBus()
    platform_registry = PlatformRegistry()
    ffmpeg_adapter = FFmpegProcessAdapter()
    download_engine = YtDlpDownloadEngine(
        event_bus=event_bus,
        ffmpeg_adapter=ffmpeg_adapter,
        repository=repository
    )

    # Cola de descargas: 2 descargas simultáneas por defecto, resto "En cola".
    download_queue = DownloadQueueManager(
        engine=download_engine,
        event_bus=event_bus,
        repository=repository,
        max_concurrent=2,
    )

    # 4. ViewModel & GUI
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("osvaldoDownloaderPro.desktop.v1")
        except Exception:
            pass

    app = QApplication(sys.argv)

    from PySide6.QtGui import QIcon
    icon_candidates = [
        os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png"),
        os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "icon.png"),
        os.path.join(os.path.dirname(sys.executable), "assets", "icon.png"),
    ]
    for candidate in icon_candidates:
        if candidate and os.path.exists(candidate):
            app.setWindowIcon(QIcon(candidate))
            break

    view_model = MainViewModel(
        platform_adapter=platform_registry,
        download_engine=download_engine,
        repository=repository,
        event_bus=event_bus,
        download_queue=download_queue,
    )

    window = MainWindow(view_model=view_model)
    if not app.windowIcon().isNull():
        window.setWindowIcon(app.windowIcon())
    window.show()

    # Chequeo único de actualizaciones al iniciar (no bloqueante; falla en silencio).
    window.schedule_startup_update_check()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
