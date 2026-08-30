from typing import List

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.domain.entities.favorite_item import FavoriteItem
from src.domain.services.content_preview import format_duration_seconds
from src.presentation.components.app_icons import heart_icon
from src.presentation.components.thumbnail_loader import ThumbnailLabel
from src.presentation.styles.styles import DARK_PALETTE


class FavoriteCard(QFrame):
    """Tarjeta interactiva para un elemento de la lista de favoritos."""

    download_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(
        self,
        item: FavoriteItem,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.item = item
        self.setObjectName("Card")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(16)

        # 1. Miniatura
        self.thumbnail = ThumbnailLabel(140, 79, corner_radius=8)
        if item.thumbnail_url:
            self.thumbnail.load_from_url(item.thumbnail_url)
        layout.addWidget(self.thumbnail)

        # 2. Información
        info_col = QVBoxLayout()
        info_col.setSpacing(4)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        chip_platform = QLabel(item.platform or "Desconocido")
        chip_platform.setObjectName("ChipAccent")
        meta_row.addWidget(chip_platform)

        if item.duration_seconds > 0:
            chip_dur = QLabel(format_duration_seconds(item.duration_seconds))
            chip_dur.setObjectName("Chip")
            meta_row.addWidget(chip_dur)

        meta_row.addStretch()
        info_col.addLayout(meta_row)

        lbl_title = QLabel(item.title)
        lbl_title.setObjectName("CardTitle")
        lbl_title.setWordWrap(True)
        info_col.addWidget(lbl_title)

        if item.author:
            lbl_author = QLabel(f"Por {item.author}")
            lbl_author.setObjectName("PreviewChannel")
            info_col.addWidget(lbl_author)

        info_col.addStretch()
        layout.addLayout(info_col, stretch=1)

        # 3. Acciones
        actions_col = QVBoxLayout()
        actions_col.setSpacing(8)
        actions_col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_download = QPushButton("▶ Descargar")
        btn_download.setObjectName("PrimaryButton")
        btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_download.setFixedHeight(34)
        btn_download.clicked.connect(lambda: self.download_requested.emit(item.url))
        actions_col.addWidget(btn_download)

        btn_remove = QPushButton("Eliminar")
        btn_remove.setObjectName("SecondaryButton")
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setFixedHeight(30)
        btn_remove.clicked.connect(lambda: self.remove_requested.emit(item.url))
        actions_col.addWidget(btn_remove)

        layout.addLayout(actions_col)


class FavoritosView(QWidget):
    """Vista para consultar y administrar contenidos favoritos guardados."""

    download_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all_items: List[FavoriteItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(14)

        # Encabezado
        title = QLabel("Favoritos")
        title.setObjectName("ViewTitle")
        subtitle = QLabel("Accede rápidamente a tus contenidos preferidos y descárgalos con un clic.")
        subtitle.setObjectName("ViewSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("HintLabel")
        layout.addWidget(self.lbl_count)

        # Estado Vacío
        self.empty_card = QFrame()
        self.empty_card.setObjectName("EmptyStateCard")
        empty_layout = QVBoxLayout(self.empty_card)
        empty_layout.setSpacing(10)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(heart_icon(DARK_PALETTE.text_tertiary).pixmap(QSize(44, 44)))
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_title = QLabel("Aún no tienes favoritos")
        lbl_title.setObjectName("EmptyStateTitle")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_hint = QLabel(
            "Cuando analices un contenido en Inicio, pulsa el botón '♡ Guardar' "
            "para conservarlo en esta lista."
        )
        lbl_hint.setObjectName("EmptyStateHint")
        lbl_hint.setWordWrap(True)
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_layout.addWidget(lbl_icon)
        empty_layout.addWidget(lbl_title)
        empty_layout.addWidget(lbl_hint)
        layout.addWidget(self.empty_card)

        # Área de tarjetas (Scrollable)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setObjectName("FavoritosScrollArea")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area, stretch=1)

        # Inicialmente vacío
        self.scroll_area.hide()

    def load_favorites(self, items: List[FavoriteItem]) -> None:
        """Carga y visualiza los elementos favoritos."""
        self._all_items = items

        # Limpiar tarjetas existentes
        while self.cards_layout.count() > 1:
            child = self.cards_layout.takeAt(0)
            if child is not None:
                w = child.widget()
                if w is not None:
                    w.deleteLater()

        if not items:
            self.empty_card.show()
            self.scroll_area.hide()
            self.lbl_count.setText("")
            return

        self.empty_card.hide()
        self.scroll_area.show()
        self.lbl_count.setText(f"{len(items)} contenido(s) guardado(s)")

        for item in items:
            card = FavoriteCard(item=item)
            card.download_requested.connect(self.download_requested)
            card.remove_requested.connect(self.remove_requested)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
