"""Componente de presentación: carga asíncrona y render de miniaturas con esquinas redondeadas.

- ThumbnailLoader: QObject que descarga la miniatura en un hilo daemon usando el
  fetcher seguro de infraestructura y emite una señal Qt al hilo principal.
- ThumbnailLabel: widget que dibuja la imagen preservando el aspect ratio,
  recortada con esquinas redondeadas, con placeholder mientras carga o si falla.
"""

import atexit
import re
import threading
from collections import OrderedDict
from typing import Optional

from PySide6.QtCore import QEvent, QObject, Qt, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from src.infrastructure.adapters.media.thumbnail_fetcher import fetch_thumbnail
from src.presentation.styles.theme import get_current_palette


def _to_qcolor(color_str: str) -> QColor:
    """Convierte cadenas hexadecimales o rgba() en un QColor válido."""
    c = color_str.strip()
    m = re.match(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)", c)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a = int(float(m.group(4)) * 255) if m.group(4) is not None else 255
        return QColor(r, g, b, a)
    return QColor(c)

_CACHE_MAX_ENTRIES = 64
_CACHE_LOCK = threading.Lock()
_CACHE: "OrderedDict[str, Optional[QImage]]" = OrderedDict()

# Hilos de descarga activos. Se rastrean para poder esperarlos ordenadamente al
# cerrar la aplicación y evitar que el intérprete los aborte a mitad de una
# operación de red/SSL (lo que provoca un fallo nativo de Windows al salir).
_WORKER_THREADS: "set[threading.Thread]" = set()
_WORKER_THREADS_LOCK = threading.Lock()


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


def wait_for_thumbnail_threads(timeout: Optional[float] = None) -> None:
    """Espera a que finalicen los hilos de descarga de miniaturas en curso.

    Se invoca automáticamente al cerrar el intérprete. Los hilos son daemon, así
    que sin esta espera explícita el proceso podría terminarlos abruptamente a
    mitad de una lectura de socket/SSL.
    """
    with _WORKER_THREADS_LOCK:
        pending = list(_WORKER_THREADS)
    for thread in pending:
        thread.join(timeout)


# Al cerrar la aplicación esperamos a los hilos de miniaturas en curso para que
# el intérprete no los mate a mitad de una operación de red/SSL (evita crashes).
atexit.register(wait_for_thumbnail_threads)


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
            finally:
                with _WORKER_THREADS_LOCK:
                    _WORKER_THREADS.discard(thread)
            if generation == self._generation:
                try:
                    self.loaded.emit(url_str, image)
                except RuntimeError:
                    pass

        thread = threading.Thread(target=_worker, daemon=True, name="thumbnail-loader")
        with _WORKER_THREADS_LOCK:
            _WORKER_THREADS.add(thread)
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

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (convención Qt)
        super().changeEvent(event)
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (convención Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)
        painter.setClipPath(path)

        palette = get_current_palette()

        if self._pixmap is not None and not self._pixmap.isNull():
            painter.fillRect(rect, _to_qcolor(palette.bg_window))
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
            painter.fillRect(rect, _to_qcolor(palette.surface_sunken))
            painter.setPen(_to_qcolor(palette.text_tertiary))
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
        border_painter.setPen(_to_qcolor(palette.border_strong))
        border_painter.drawPath(border_path)
        border_painter.end()
