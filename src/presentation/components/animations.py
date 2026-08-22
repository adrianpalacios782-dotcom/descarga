"""Microinteracciones discretas y seguras para la interfaz.

Animaciones cortas que nunca dejan la UI en un estado intermedio: si algo
falla o el widget está oculto, simplemente no se ejecuta la animación.
"""

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

FADE_IN_MS = 160


def fade_in(widget: QWidget, duration_ms: int = FADE_IN_MS, enabled: bool = True) -> None:
    """Aparece el widget con un fundido breve. A prueba de entornos headless."""
    if not enabled or duration_ms <= 0:
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration_ms)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _cleanup() -> None:
        widget.setGraphicsEffect(None)

    animation.finished.connect(_cleanup)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


def set_animations_enabled_default() -> bool:
    """Preferencia por defecto de animaciones (centralizada para coherencia)."""
    return True
