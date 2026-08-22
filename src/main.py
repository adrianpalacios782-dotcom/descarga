import os
import sys

# Agregar la raíz del proyecto a sys.path para permitir ejecuciones directas (python src/main.py)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
from src.infrastructure.adapters.platforms.platform_registry import PlatformRegistry
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
from src.infrastructure.adapters.storage.sqlite_repository import SQLiteDownloadRepository
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus
from src.infrastructure.logging.logger_config import setup_logger
from src.presentation.main_window import MainWindow
from src.presentation.view_models.main_view_model import MainViewModel


def main() -> None:
    # 1. Setup Logging
    app_data_dir = os.path.join(os.path.expanduser("~"), ".osvaldoDownloaderPro")
    os.makedirs(app_data_dir, exist_ok=True)
    setup_logger(log_dir=os.path.join(app_data_dir, "logs"))

    # 2. Infraestructura
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

    # 3. ViewModel & GUI
    app = QApplication(sys.argv)

    view_model = MainViewModel(
        platform_adapter=platform_registry,
        download_engine=download_engine,
        repository=repository,
        event_bus=event_bus
    )

    window = MainWindow(view_model=view_model)
    window.show()

    # Chequeo único de actualizaciones al iniciar (no bloqueante; falla en silencio).
    window.schedule_startup_update_check()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
