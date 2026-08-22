from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame

from src.presentation.components.app_icons import heart_icon
from src.presentation.styles.styles import DARK_PALETTE


class FavoritosView(QWidget):
    """Vista para administrar contenidos y descargas favoritas."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Favoritos")
        title.setObjectName("ViewTitle")
        subtitle = QLabel("Guarda tus contenidos preferidos para acceder a ellos rápidamente.")
        subtitle.setObjectName("ViewSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("EmptyStateCard")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(heart_icon(DARK_PALETTE.text_tertiary).pixmap(QSize(44, 44)))
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_title = QLabel("Aún no tienes favoritos")
        lbl_title.setObjectName("EmptyStateTitle")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_hint = QLabel(
            "Cuando agregues contenidos a favoritos aparecerán aquí como tarjetas "
            "con su miniatura, título y plataforma."
        )
        lbl_hint.setObjectName("EmptyStateHint")
        lbl_hint.setWordWrap(True)
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_layout.addWidget(lbl_icon)
        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_hint)

        layout.addWidget(card)
        layout.addStretch()
