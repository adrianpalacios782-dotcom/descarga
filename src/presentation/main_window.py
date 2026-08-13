import threading
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget

from src.presentation.components.sidebar import SidebarWidget
from src.presentation.styles.styles import DARK_STYLE
from src.presentation.view_models.main_view_model import MainViewModel
from src.presentation.views import (
    InicioView,
    DescargasView,
    HistorialView,
    FavoritosView,
    ConfiguracionView,
    AcercaDeView,
)


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación osvaldoDownloaderPro."""

    def __init__(self, view_model: MainViewModel) -> None:
        super().__init__()
        self.view_model = view_model

        self.setWindowTitle("osvaldoDownloaderPro")
        self.resize(1020, 680)
        self.setStyleSheet(DARK_STYLE)

        # Widget central y layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = SidebarWidget()
        main_layout.addWidget(self.sidebar)

        # Stacked Views
        self.stacked = QStackedWidget()
        
        self.inicio_view = InicioView()
        self.descargas_view = DescargasView()
        self.historial_view = HistorialView()
        self.favoritos_view = FavoritosView()
        self.configuracion_view = ConfiguracionView()
        self.acerca_de_view = AcercaDeView()

        self.stacked.addWidget(self.inicio_view)
        self.stacked.addWidget(self.descargas_view)
        self.stacked.addWidget(self.historial_view)
        self.stacked.addWidget(self.favoritos_view)
        self.stacked.addWidget(self.configuracion_view)
        self.stacked.addWidget(self.acerca_de_view)

        main_layout.addWidget(self.stacked, stretch=1)

        # Conectar Sidebar con StackedWidget
        self.sidebar.nav_changed.connect(self.stacked.setCurrentIndex)
        self.sidebar.nav_changed.connect(self._on_tab_changed)

        # Conectar Signals del ViewModel
        self._connect_signals()

    def _connect_signals(self) -> None:
        # InicioView -> ViewModel
        self.inicio_view.analyze_requested.connect(self.view_model.analyze_url)
        self.inicio_view.download_requested.connect(self._on_download_requested)

        # ViewModel -> InicioView
        self.view_model.analysis_started.connect(lambda: self.inicio_view.set_analyzing_state(True))
        self.view_model.media_analyzed.connect(self.inicio_view.set_metadata)
        self.view_model.analysis_failed.connect(self.inicio_view.show_error)

        # ViewModel -> DescargasView
        self.view_model.download_created.connect(self.descargas_view.add_task)
        self.view_model.download_progress.connect(self.descargas_view.update_progress)
        self.view_model.download_state_changed.connect(self.descargas_view.set_state)

        # DescargasView -> ViewModel
        self.descargas_view.pause_requested.connect(self.view_model.pause_download)
        self.descargas_view.resume_requested.connect(self.view_model.resume_download)
        self.descargas_view.cancel_requested.connect(self.view_model.cancel_download)
        self.descargas_view.retry_requested.connect(self.view_model.retry_download)

    def _on_download_requested(self, media, format_id: str, dest_path: str) -> None:
        self.view_model.create_and_start_download(media, format_id, dest_path)
        self.sidebar.button_group.button(1).setChecked(True)
        self.stacked.setCurrentIndex(1)

    def _on_tab_changed(self, index: int) -> None:
        if index == 2:  # Historial
            tasks = self.view_model.get_all_tasks()
            self.historial_view.load_history(tasks)
        elif index == 5:  # Acerca de
            self._check_ffmpeg_status()

    def _check_ffmpeg_status(self) -> None:
        def _worker() -> None:
            from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
            adapter = FFmpegProcessAdapter()
            ok, version = adapter.check_availability_sync()
            self.acerca_de_view.set_ffmpeg_status(ok, version)

        threading.Thread(target=_worker, daemon=True).start()
