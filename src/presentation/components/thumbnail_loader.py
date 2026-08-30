"""Componente de presentación: carga asíncrona y render de miniaturas con esquinas redondeadas.

- ThumbnailLoader: QObject que descarga la miniatura en un hilo daemon usando el
  fetcher seguro de infraestructura y emite una señal Qt al hilo principal.
- ThumbnailLabel: widget que dibuja la imagen preservando el aspect ratio,
  recortada con esquinas redondeadas, con placeholder mientras carga o si falla.
"""

import threading
from collections import OrderedDict
from typing import Optional

from PySide6.QtCore import QObject, Qt, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from src.infrastructure.adapters.media.thumbnail_fetcher import fetch_thumbnail

_CACHE_MAX_ENTRIES = 64
_CACHE_LOCK = threading.Lock()
_CACHE: "OrderedDict[str, Optional[QImage]]" = OrderedDict()


def _cache_get(url: str) -> Optional[QImage]:
    with _CACHE_LOCK:
        if url not in _CACHE:
            return None
        _CACHE.move_to_end(url)
        return _CACHE[url]


def _cache_put(url: str, image: Optional[QImage]) -> None:
    with _CACHE_LOCK:
        _CACHE[url] = image
        _CACHE.move_to_end(url)
        while len(_CACHE) > _CACHE_MAX_ENTRIES:
            _CACHE.popitem(last=False)


def clear_thumbnail_cache() -> None:
    """Vacía la caché de miniaturas (útil en pruebas y al recargar contenido)."""
    with _CACHE_LOCK:
        _CACHE.clear()


class ThumbnailLoader(QObject):
    """Descarga miniaturas fuera del hilo principal sin congelar la UI.

    Señal loaded(url, image): image es QImage o None si falló/canceló.
    Un contador de generación descarta resultados obsoletos si se pide otra URL.
    """

    loaded = Signal(str, object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._generation = 0

    def load(self, url_str: str) -> None:
        """Inicia la descarga asíncrona de la miniatura indicada."""
        self._generation += 1
        generation = self._generation

        cached = _cache_get(url_str)
        if cached is not None:
            self.loaded.emit(url_str, cached)
            return

        if not url_str:
            self.loaded.emit(url_str, None)
            return

        def _worker() -> None:
            image: Optional[QImage] = None
            try:
                data = fetch_thumbnail(url_str)
                decoded = QImage.fromData(data)
                if not decoded.isNull():
                    image = decoded
                    _cache_put(url_str, image)
            except Exception:
                image = None
            if generation == self._generation:
                try:
                    self.loaded.emit(url_str, image)
                except RuntimeError:
                    pass

        thread = threading.Thread(target=_worker, daemon=True, name="thumbnail-loader")
        thread.start()


class ThumbnailLabel(QWidget):
    """Miniatura con esquinas redondeadas, aspect ratio preservado y placeholder."""

    PLACEHOLDER_TEXT_DEFAULT = "Sin vista previa"
    LOADING_TEXT = "Cargando miniatura..."

    def __init__(
        self,
        display_width: int = 320,
        display_height: int = 180,
        corner_radius: int = 12,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(display_width, display_height)
        self._corner_radius = corner_radius
        self._pixmap: Optional[QPixmap] = None
        self._placeholder_text = ""
        self._current_url = ""

        self.loader = ThumbnailLoader(self)
        self.loader.loaded.connect(self._on_loaded)

        self._show_placeholder(self.LOADING_TEXT)

    # ------------------------------------------------------------------ API
    def load_from_url(self, url_str: str) -> None:
        """Carga una miniatura remota de forma asíncrona con placeholder."""
        self._current_url = (url_str or "").strip()
        self._show_placeholder(self.LOADING_TEXT if self._current_url else "")
        if self._current_url:
            self.loader.load(self._current_url)

    def clear(self) -> None:
        """Restablece el widget a su estado vacío sin texto."""
        self._current_url = ""
        self._show_placeholder("")

    # -------------------------------------------------------------- Interno
    def _show_placeholder(self, text: str) -> None:
        self._placeholder_text = text
        self._pixmap = None
        self.update()

    def _on_loaded(self, url: str, image: object) -> None:
        if url != self._current_url or self._current_url == "":
            return  # resultado obsoleto
        if not isinstance(image, QImage) or image.isNull():
            self._show_placeholder("Sin vista previa")
            return
        self._pixmap = QPixmap.fromImage(image)
        self._placeholder_text = ""
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (convención Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)
        painter.setClipPath(path)

        if self._pixmap is not None and not self._pixmap.isNull():
            painter.fillRect(rect, QColor("#101010"))
            scaled = self._pixmap.scaled(
                self.width(),
                self.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) / 2.0
            y = (self.height() - scaled.height()) / 2.0
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            painter.fillRect(rect, QColor("#181818"))
            painter.setPen(QColor("#3e3e3e"))
            font = QFont(self.font())
            font.setPointSize(max(9, self.height() // 14))
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._placeholder_text)

        painter.end()

        # Borde sutil encima del recorte redondeado
        border_painter = QPainter(self)
        border_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        border_path = QPainterPath()
        border_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        border_path.addRoundedRect(border_rect, self._corner_radius, self._corner_radius)
        border_painter.setPen(QColor("#282828"))
        border_painter.drawPath(border_path)
        border_painter.end()
