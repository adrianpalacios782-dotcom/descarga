import os
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.presentation.styles.styles import DARK_STYLE


class BatchDownloadDialog(QDialog):
    """Diálogo modal para el procesamiento y encolamiento de descargas masivas."""

    batch_requested = Signal(list, str, str)  # (urls: List[str], quality: str, dest_dir: str)

    def __init__(
        self,
        default_dir: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Descarga Masiva por Lotes")
        self.resize(600, 520)
        self.setMinimumSize(520, 440)
        self.setStyleSheet(DARK_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Encabezado
        title = QLabel("Descarga Masiva por Lotes")
        title.setObjectName("ViewTitle")
        subtitle = QLabel(
            "Pega una lista de enlaces (uno por línea) o importa un archivo de texto para encolarlos automáticamente."
        )
        subtitle.setObjectName("ViewSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Área de texto
        self.txt_urls = QPlainTextEdit()
        self.txt_urls.setPlaceholderText(
            "https://www.youtube.com/watch?v=...\n"
            "https://www.tiktok.com/@usuario/video/...\n"
            "https://www.instagram.com/reel/...\n"
            "https://www.facebook.com/watch?v=..."
        )
        self.txt_urls.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.txt_urls, stretch=1)

        # Fila de acciones sobre el texto: Cargar archivo + Contador
        import_row = QHBoxLayout()
        self.btn_import_file = QPushButton("📁 Cargar archivo .txt...")
        self.btn_import_file.setObjectName("SecondaryButton")
        self.btn_import_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_import_file.clicked.connect(self._on_import_file_clicked)
        import_row.addWidget(self.btn_import_file)

        self.lbl_count = QLabel("0 enlaces detectados")
        self.lbl_count.setObjectName("HintLabel")
        import_row.addStretch()
        import_row.addWidget(self.lbl_count)
        layout.addLayout(import_row)

        # Opciones: Calidad y Carpeta
        options_card = QFrame()
        options_card.setObjectName("Card")
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(14, 12, 14, 12)
        options_layout.setSpacing(10)

        # Selector de calidad
        quality_row = QHBoxLayout()
        lbl_quality = QLabel("Calidad deseada:")
        self.combo_quality = QComboBox()
        self.combo_quality.addItems([
            "Mejor calidad disponible (Video)",
            "1080p (Full HD)",
            "720p (HD)",
            "Solo Audio (MP3 / Mejor disponible)",
        ])
        quality_row.addWidget(lbl_quality)
        quality_row.addWidget(self.combo_quality, stretch=1)
        options_layout.addLayout(quality_row)

        # Carpeta de destino
        dir_row = QHBoxLayout()
        lbl_dir = QLabel("Carpeta destino:")
        resolved_dir = default_dir or os.path.join(os.path.expanduser("~"), "Downloads")
        self.txt_dir = QLineEdit(os.path.normpath(resolved_dir))
        self.btn_browse = QPushButton("Examinar...")
        self.btn_browse.setObjectName("SecondaryButton")
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.clicked.connect(self._on_browse_clicked)
        dir_row.addWidget(lbl_dir)
        dir_row.addWidget(self.txt_dir, stretch=1)
        dir_row.addWidget(self.btn_browse)
        options_layout.addLayout(dir_row)

        layout.addWidget(options_card)

        # Barra de progreso para feedback
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Botones finales
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_start = QPushButton("Iniciar Descargas")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start_clicked)
        btn_row.addWidget(self.btn_start)

        layout.addLayout(btn_row)

    def extract_urls(self) -> List[str]:
        """Extrae y normaliza las URLs válidas presentes en el área de texto."""
        raw_text = self.txt_urls.toPlainText()
        urls: List[str] = []
        for line in raw_text.splitlines():
            cleaned = line.strip()
            if cleaned.startswith("http://") or cleaned.startswith("https://"):
                urls.append(cleaned)
        return urls

    def _on_text_changed(self) -> None:
        urls = self.extract_urls()
        count = len(urls)
        self.lbl_count.setText(f"{count} enlace(s) detectado(s)")
        self.btn_start.setEnabled(count > 0)

    def _on_import_file_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo de enlaces",
            "",
            "Archivos de texto (*.txt);;Todos los archivos (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            self.txt_urls.setPlainText(content)
        except OSError as ex:
            QMessageBox.warning(self, "Error", f"No se pudo leer el archivo:\n{ex}")

    def _on_browse_clicked(self) -> None:
        current_dir = self.txt_dir.text().strip() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Carpeta de Destino",
            current_dir,
        )
        if folder:
            self.txt_dir.setText(os.path.normpath(folder))

    def _on_start_clicked(self) -> None:
        urls = self.extract_urls()
        if not urls:
            return

        dest_dir = self.txt_dir.text().strip()
        if not os.path.isdir(dest_dir):
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except OSError as ex:
                QMessageBox.warning(self, "Carpeta inválida", f"No se pudo crear la carpeta destino:\n{ex}")
                return

        quality = self.combo_quality.currentText()
        self.batch_requested.emit(urls, quality, dest_dir)
        self.accept()
