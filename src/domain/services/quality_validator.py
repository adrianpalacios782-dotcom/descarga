"""Servicio de dominio para validar técnicamente la calidad del archivo descargado.

Compara la resolución, relación de aspecto (aspect ratio), códecs, tasa de cuadros
(FPS) y presencia de flujos respecto a lo solicitado por el usuario o publicado por
la plataforma, previniendo falsas alarmas en videos panorámicos (2.39:1 / 2.40:1)
o formatos verticales (9:16 Shorts/TikTok).
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from src.domain.entities.format_option import FormatOption


class QualityMatchStatus(str, Enum):
    """Resultado de la comparación entre lo solicitado y lo obtenido."""
    EXACT_OR_COMPATIBLE = "EXACT_OR_COMPATIBLE"
    DEGRADED = "DEGRADED"
    INVALID_OR_EMPTY = "INVALID_OR_EMPTY"


@dataclass(frozen=True)
class QualityValidationResult:
    """Detalle inmutable del diagnóstico de calidad realizado sobre un archivo final."""
    status: QualityMatchStatus
    is_acceptable: bool
    effective_height: int
    requested_height: int
    actual_height: int
    actual_width: int
    actual_fps: float
    message: str = ""


class QualityValidator:
    """Validador de dominio para archivos multimedia inspeccionados."""

    TOLERANCE_THRESHOLD = 0.85

    @classmethod
    def calculate_effective_height(cls, height: int, width: int = 0) -> int:
        """Calcula la altura estándar equivalente considerando la relación de aspecto cinematográfica.

        - Formato 16:9 tradicional (1920x1080) -> 1080
        - Formato 2.39:1 panorámico de cine (1920x806) -> 1080 (ar ~ 2.38)
        - Formato 9:16 vertical móvil (1080x1920) -> 1080 (inv_ar ~ 1.78)
        - Formatos no cinematográficos o desproporcionados (ej. 1920x360) -> 360
        """
        if height <= 0 and width <= 0:
            return 0

        if width > 0 and height > 0:
            ar = width / height
            if height > width:
                # Video vertical (Shorts / Reels / TikTok)
                inv_ar = height / width
                if 1.20 <= inv_ar <= 2.45:
                    equiv_from_height = int(round(height * 9.0 / 16.0))
                    return max(width, equiv_from_height)
                return width
            else:
                # Video horizontal cinematográfico (16:9 a 2.40:1)
                # YouTube 1080p ultrapanorámico es 1920x806 (ar ~ 2.38)
                if 1.70 <= ar <= 2.45:
                    equiv_from_width = int(round(width * 9.0 / 16.0))
                    return max(height, equiv_from_width)
                return height

        return height

    @classmethod
    def validate_video_quality(
        cls,
        requested_format: FormatOption,
        probe_info: Dict[str, Any],
    ) -> QualityValidationResult:
        """Valida que el video descargado cumpla con la calidad solicitada."""
        video_stream = probe_info.get("video") or {}
        if not isinstance(video_stream, dict):
            video_stream = {}

        actual_width = int(video_stream.get("width") or 0)
        actual_height = int(video_stream.get("height") or 0)
        actual_fps = float(video_stream.get("fps") or 0.0)

        if actual_height <= 0 and actual_width <= 0:
            return QualityValidationResult(
                status=QualityMatchStatus.INVALID_OR_EMPTY,
                is_acceptable=False,
                effective_height=0,
                requested_height=requested_format.height or 0,
                actual_height=0,
                actual_width=0,
                actual_fps=0.0,
                message="El archivo resultante no contiene un flujo de video válido.",
            )

        effective_h = cls.calculate_effective_height(actual_height, actual_width)
        requested_h = requested_format.height or 0

        actual_label = f"{actual_height}p"
        if actual_fps > 0:
            actual_label += f"@{int(actual_fps)}fps"

        requested_label = f"{requested_h}p" if requested_h > 0 else "Mejor calidad"

        # Si el usuario solicitó "Mejor calidad", cualquier resolución válida es aceptable
        if requested_format.is_best_quality or requested_h <= 0:
            return QualityValidationResult(
                status=QualityMatchStatus.EXACT_OR_COMPATIBLE,
                is_acceptable=True,
                effective_height=effective_h,
                requested_height=requested_h,
                actual_height=actual_height,
                actual_width=actual_width,
                actual_fps=actual_fps,
                message="",
            )

        # Si la altura fue estimada (etiquetas sd/hd en plataformas como Facebook)
        if getattr(requested_format, "height_estimated", False):
            return QualityValidationResult(
                status=QualityMatchStatus.EXACT_OR_COMPATIBLE,
                is_acceptable=True,
                effective_height=effective_h,
                requested_height=requested_h,
                actual_height=actual_height,
                actual_width=actual_width,
                actual_fps=actual_fps,
                message="",
            )

        # Comprobar contra el umbral de tolerancia usando la altura efectiva
        if effective_h >= requested_h * cls.TOLERANCE_THRESHOLD:
            return QualityValidationResult(
                status=QualityMatchStatus.EXACT_OR_COMPATIBLE,
                is_acceptable=True,
                effective_height=effective_h,
                requested_height=requested_h,
                actual_height=actual_height,
                actual_width=actual_width,
                actual_fps=actual_fps,
                message="",
            )

        # Si no alcanza la tolerancia, es una degradación real (ej. se pidió 1080p y llegó 360p/480p)
        msg = (
            f"Calidad degradada: se solicitó {requested_label} pero el archivo "
            f"resultante tiene {actual_label}. La resolución solicitada no pudo ser entregada."
        )
        return QualityValidationResult(
            status=QualityMatchStatus.DEGRADED,
            is_acceptable=True,
            effective_height=effective_h,
            requested_height=requested_h,
            actual_height=actual_height,
            actual_width=actual_width,
            actual_fps=actual_fps,
            message=msg,
        )
