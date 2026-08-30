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
    from src.infrastructure.adapters.storage.sqlite_favorite_repository import (
        SQLiteFavoriteRepository,
    )
    from src.infrastructure.adapters.storage.sqlite_repository import (
        SQLiteDownloadRepository,
    )
    from src.infrastructure.adapters.storage.sqlite_settings_repository import (
        SQLiteSettingsRepository,
    )
    from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus
    from src.presentation.main_window import MainWindow
    from src.presentation.view_models.main_view_model import MainViewModel

    db_path = os.path.join(app_data_dir, "osvaldo_downloader.db")
    db_manager = DatabaseManager(db_path=db_path)
    db_manager.init_tables()

    repository = SQLiteDownloadRepository(db_manager=db_manager)
    settings_repository = SQLiteSettingsRepository(db_manager=db_manager)
    favorite_repository = SQLiteFavoriteRepository(db_manager=db_manager)
    event_bus = InProcessEventBus()

    # Cargar preferencias persistidas
    saved_browser = settings_repository.get("cookies_browser", default="")
    saved_max_concurrent = settings_repository.get("max_concurrent_downloads", default=2)
    saved_default_dir = settings_repository.get(
        "default_download_dir",
        default=os.path.join(os.path.expanduser("~"), "Downloads"),
    )

    platform_registry = PlatformRegistry(cookies_from_browser=saved_browser or None)
    ffmpeg_adapter = FFmpegProcessAdapter()
    download_engine = YtDlpDownloadEngine(
        event_bus=event_bus,
        ffmpeg_adapter=ffmpeg_adapter,
        repository=repository,
        cookies_from_browser=saved_browser or None,
    )

    # Cola de descargas: concurrencia según preferencia guardada, resto "En cola".
    download_queue = DownloadQueueManager(
        engine=download_engine,
        event_bus=event_bus,
        repository=repository,
        max_concurrent=int(saved_max_concurrent),
    )

    # 4. ViewModel & GUI
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("osvaldoDownloaderPro.desktop.v1")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from src.presentation.styles.styles import DARK_STYLE
    app.setStyleSheet(DARK_STYLE)

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
        settings_repository=settings_repository,
    )

    window = MainWindow(view_model=view_model, favorite_repository=favorite_repository)
    if saved_default_dir:
        window.inicio_view.set_default_download_dir(str(saved_default_dir))
    if not app.windowIcon().isNull():
        window.setWindowIcon(app.windowIcon())
    window.show()

    # Chequeo único de actualizaciones al iniciar (no bloqueante; falla en silencio).
    window.schedule_startup_update_check()

    exit_code = app.exec()
    try:
        db_manager.close()
    except Exception:
        pass
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
