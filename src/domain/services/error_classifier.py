"""Clasificador de errores de descarga y análisis de medios.

Traduce excepciones técnicas de bajo nivel (yt-dlp, redes, ffmpeg) en
estructuras de error comprensibles para el usuario con mensajes en español y
sugerencias accionables de resolución.
"""
from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional


class ErrorCategory(str, Enum):
    """Categorías semánticas de errores de descarga y análisis."""

    BOT_DETECTION = "bot_detection"
    AGE_RESTRICTION = "age_restriction"
    MEMBERS_ONLY = "members_only"
    PRIVATE_CONTENT = "private_content"
    SIGN_IN_REQUIRED = "sign_in_required"
    GEO_BLOCKED = "geo_blocked"
    EXTRACTOR_OUTDATED = "extractor_outdated"
    UNAVAILABLE = "unavailable"
    NOT_FOUND = "not_found"
    NETWORK_ERROR = "network_error"
    COOKIES_ERROR = "cookies_error"
    FFMPEG_ERROR = "ffmpeg_error"
    FORMAT_UNAVAILABLE = "format_unavailable"
    INVALID_URL = "invalid_url"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifiedError:
    """Representación de un error clasificado con orientación al usuario."""

    category: ErrorCategory
    user_message: str
    suggestion: Optional[str]
    technical_detail: str
    is_cookie_recoverable: bool


class ErrorClassifier:
    """Servicio de dominio para categorizar errores y generar sugerencias útiles."""

    _PATTERNS: list[tuple[ErrorCategory, str]] = [
        (ErrorCategory.MEMBERS_ONLY, r"members[- ]only|member[- ]only|subscribers?[- ]only|premium[- ]only"),
        (ErrorCategory.AGE_RESTRICTION, r"age[- ]restricted|confirm your age|verify your age|iniciar sesión para confirmar tu edad"),
        (ErrorCategory.BOT_DETECTION, r"not a bot|bot check|bot verification|unusual traffic|request complete verification|rate limit|too many requests|challenge|tráfico inusual"),
        (ErrorCategory.COOKIES_ERROR, r"could not extract cookies|session expired|keyring|cookie.*error|decryption failed"),
        (ErrorCategory.SIGN_IN_REQUIRED, r"granted access|requires authentication|must be logged|login required|log ?in required|requiere iniciar sesión"),
        (ErrorCategory.GEO_BLOCKED, r"not available in your country|geo[- ]?restricted|blocked in your country|unavailable in your (region|country)|no disponible en tu país"),
        (ErrorCategory.SIGN_IN_REQUIRED, r"\b(sign in|log ?in|login)\b"),
        (ErrorCategory.UNAVAILABLE, r"video unavailable|no longer available|has been removed|has been deleted|content is not available|ya no est[aá] disponible|no est[aá] disponible"),
        (ErrorCategory.PRIVATE_CONTENT, r"private video|video is private|this video is private|account is private|private account|cuenta privada|contenido privado"),
        (ErrorCategory.EXTRACTOR_OUTDATED, r"unable to extract|nsig|signature extraction|no video formats|did not get a match|failed to resolve|precondition check failed|unexpected response from webpage request|impersonat"),
        (ErrorCategory.FORMAT_UNAVAILABLE, r"requested format is not available|no suitable format found|formato no disponible"),
        (ErrorCategory.NETWORK_ERROR, r"http error 403|http error 429|forbidden|urlerror|urlopen error|connection|getaddrinfo|temporary failure|timed? ?out|ssl|reset by peer|name or service not known|timeout"),
        (ErrorCategory.INVALID_URL, r"is not a valid url|invalid url|unsupported url|not a valid|url no válida"),
        (ErrorCategory.FFMPEG_ERROR, r"ffmpeg|postprocessing|conversion failed|muxing failed"),
        (ErrorCategory.NOT_FOUND, r"video not found|no such video|404|not found|no se encontr[oó]"),
    ]

    _PLATFORM_MESSAGES: dict[ErrorCategory, dict[str, str]] = {
        ErrorCategory.PRIVATE_CONTENT: {
            "YouTube": "Este video de YouTube es privado o ha sido configurado como no público por su creador.",
            "Instagram": "Esta publicación o historia de Instagram pertenece a una cuenta privada o ya ha expirado.",
            "Facebook": "Este video de Facebook es privado o solo está disponible para amigos del autor.",
            "TikTok": "Este video de TikTok pertenece a una cuenta privada.",
        },
        ErrorCategory.MEMBERS_ONLY: {
            "YouTube": "Este video es exclusivo para miembros suscritos al canal.",
        },
        ErrorCategory.AGE_RESTRICTION: {
            "YouTube": "Este video tiene restricción de edad (+18) y requiere verificación de cuenta.",
        },
        ErrorCategory.BOT_DETECTION: {
            "YouTube": "YouTube detectó solicitudes automatizadas (Anti-Bot / Tráfico inusual).",
            "TikTok": "TikTok activó un desafío de verificación anti-bot temporal.",
        },
        ErrorCategory.UNAVAILABLE: {
            "YouTube": "El video de YouTube ya no se encuentra disponible (pudo haber sido borrado o dado de baja).",
            "Instagram": "El contenido de Instagram ya no está disponible en los servidores.",
            "Facebook": "El video de Facebook fue eliminado o la página restringió su visualización.",
            "TikTok": "El video de TikTok no está disponible o ha sido eliminado.",
        },
        ErrorCategory.GEO_BLOCKED: {
            "YouTube": "Este contenido tiene bloqueo geográfico y no está disponible en tu región.",
        },
        ErrorCategory.SIGN_IN_REQUIRED: {
            "YouTube": "YouTube requiere iniciar sesión con una cuenta para acceder a este contenido.",
            "Instagram": "Instagram requiere iniciar sesión para visualizar este perfil o publicación.",
            "Facebook": "Facebook requiere iniciar sesión para ver este video.",
            "TikTok": "TikTok requiere iniciar sesión para ver este video.",
        },
    }

    _GENERIC_MESSAGES: dict[ErrorCategory, str] = {
        ErrorCategory.PRIVATE_CONTENT: "El contenido es privado o requiere permisos especiales.",
        ErrorCategory.MEMBERS_ONLY: "Este contenido es exclusivo para miembros con suscripción de pago.",
        ErrorCategory.AGE_RESTRICTION: "El contenido tiene restricción de edad y requiere iniciar sesión.",
        ErrorCategory.BOT_DETECTION: "La plataforma detectó tráfico inusual o bloqueo anti-bot.",
        ErrorCategory.COOKIES_ERROR: "No se pudieron extraer las cookies de sesión del navegador seleccionado.",
        ErrorCategory.SIGN_IN_REQUIRED: "La plataforma requiere iniciar sesión para visualizar el contenido.",
        ErrorCategory.GEO_BLOCKED: "El contenido no se encuentra disponible en tu ubicación geográfica.",
        ErrorCategory.UNAVAILABLE: "El contenido ya no está disponible o ha sido retirado.",
        ErrorCategory.NOT_FOUND: "No se encontró el contenido en la dirección indicada. Verifica el enlace.",
        ErrorCategory.INVALID_URL: "La URL ingresada no es válida o no es reconocida por el sistema.",
        ErrorCategory.EXTRACTOR_OUTDATED: (
            "El motor de extracción encontró cambios recientes en la plataforma. "
            "Se recomienda actualizar el motor yt-dlp."
        ),
        ErrorCategory.FORMAT_UNAVAILABLE: "No se encontró un formato compatible con la resolución seleccionada.",
        ErrorCategory.NETWORK_ERROR: "Ocurrió un error de conexión o tiempo de espera al comunicar con el servidor.",
        ErrorCategory.FFMPEG_ERROR: "Ocurrió un error durante el procesamiento o conversión con FFmpeg.",
        ErrorCategory.UNKNOWN: "No fue posible procesar el contenido multimedia. Verifica que el enlace esté disponible.",
    }

    _SUGGESTIONS: dict[ErrorCategory, str] = {
        ErrorCategory.PRIVATE_CONTENT: (
            "Si tienes acceso a esta cuenta, activa 'Usar cookies de navegador' "
            "en Configuración seleccionando tu navegador habitual."
        ),
        ErrorCategory.MEMBERS_ONLY: (
            "Inicia sesión en tu navegador con la cuenta que posee la membresía "
            "y activa 'Usar cookies de navegador' en Configuración."
        ),
        ErrorCategory.AGE_RESTRICTION: (
            "Inicia sesión en tu navegador con una cuenta mayor de edad "
            "y activa 'Usar cookies de navegador' en Configuración."
        ),
        ErrorCategory.BOT_DETECTION: (
            "Prueba activar 'Usar cookies de navegador' en Configuración, "
            "o espera unos minutos antes de reintentar la descarga."
        ),
        ErrorCategory.COOKIES_ERROR: (
            "Abre tu navegador habitual, asegúrate de estar logueado en la plataforma "
            "y de que el navegador esté cerrado si bloquea el almacén de cookies."
        ),
        ErrorCategory.GEO_BLOCKED: "Utiliza una conexión de red ubicada en la región admitida por el creador.",
        ErrorCategory.SIGN_IN_REQUIRED: (
            "Inicia sesión en la plataforma desde tu navegador y activa "
            "'Usar cookies de navegador' en la pestaña de Configuración."
        ),
        ErrorCategory.EXTRACTOR_OUTDATED: (
            "Actualiza el motor yt-dlp desde la pestaña 'Configuración' o 'Acerca de' "
            "para incorporar los últimos extractores."
        ),
        ErrorCategory.FORMAT_UNAVAILABLE: "Intenta seleccionar otra calidad o la opción 'Mejor calidad disponible'.",
        ErrorCategory.NETWORK_ERROR: "Verifica tu conexión a internet o intenta nuevamente en unos instantes.",
        ErrorCategory.NOT_FOUND: "Comprueba que la URL esté escrita correctamente y no contenga caracteres cortados.",
        ErrorCategory.INVALID_URL: "Pega una URL completa de una plataforma soportada (YouTube, TikTok, Instagram, etc.).",
        ErrorCategory.FFMPEG_ERROR: "Verifica que los ejecutables de FFmpeg estén presentes y no bloqueados por el antivirus.",
    }

    _COOKIE_RECOVERABLE_CATEGORIES: set[ErrorCategory] = {
        ErrorCategory.BOT_DETECTION,
        ErrorCategory.AGE_RESTRICTION,
        ErrorCategory.MEMBERS_ONLY,
        ErrorCategory.PRIVATE_CONTENT,
        ErrorCategory.SIGN_IN_REQUIRED,
        ErrorCategory.COOKIES_ERROR,
    }

    @classmethod
    def classify(cls, exc: Exception | str, platform_name: str = "") -> ClassifiedError:
        """Clasifica una excepción o mensaje crudo y genera la recomendación adecuada."""
        raw_text = str(exc)
        lower_text = raw_text.lower()
        detail = raw_text.strip()
        if len(detail) > 300:
            detail = detail[:297] + "..."

        matched_category = ErrorCategory.UNKNOWN
        for category, pattern in cls._PATTERNS:
            if re.search(pattern, lower_text):
                matched_category = category
                break

        # Obtener mensaje específico por plataforma o genérico
        platform_normalized = platform_name.strip()
        user_message = (
            cls._PLATFORM_MESSAGES.get(matched_category, {}).get(platform_normalized)
            or cls._GENERIC_MESSAGES.get(matched_category, cls._GENERIC_MESSAGES[ErrorCategory.UNKNOWN])
        )

        suggestion = cls._SUGGESTIONS.get(matched_category)
        is_recoverable = matched_category in cls._COOKIE_RECOVERABLE_CATEGORIES

        return ClassifiedError(
            category=matched_category,
            user_message=user_message,
            suggestion=suggestion,
            technical_detail=detail,
            is_cookie_recoverable=is_recoverable,
        )
