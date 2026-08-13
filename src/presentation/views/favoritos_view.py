from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QPushButton


class FavoritosView(QWidget):
    """Vista para administrar contenidos y descargas favoritas."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Favoritos")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)

        empty_label = QLabel("No tienes contenidos agregados a favoritos.")
        empty_label.setStyleSheet("font-size: 14px; color: #b3b3b3;")
        card_layout.addWidget(empty_label)

        layout.addWidget(card)
        layout.addStretch()
