class DomainError(Exception):
    """Excepción base para todos los errores del dominio de negocio."""
    pass


class InvalidUrlError(DomainError):
    """Lanzada cuando una URL no cumple con los criterios de formato o seguridad."""
    pass


class UnsupportedPlatformError(DomainError):
    """Lanzada cuando una URL pertenece a una plataforma no soportada."""
    pass


class InvalidStateTransitionError(DomainError):
    """Lanzada cuando se intenta una transición no permitida en la máquina de estados de descarga."""
    pass


class MediaAnalysisError(DomainError):
    """Lanzada cuando falla la extracción o parsing de metadatos de un medio."""
    pass


class DownloadError(DomainError):
    """Excepción general durante el proceso de descarga."""
    pass


class FormatNotFoundError(DomainError):
    """Lanzada cuando el formato seleccionado no existe dentro de las opciones disponibles."""
    pass


class TaskNotFoundError(DomainError):
    """Lanzada cuando no se encuentra la tarea de descarga especificada."""
    pass


class QualityDegradationError(DomainError):
    """Lanzada cuando la calidad descargada es significativamente inferior a la solicitada."""
    pass


class UpdateError(DomainError):
    """Excepción general del sistema de actualización automática."""
    pass


class InvalidUpdateInfoError(UpdateError):
    """Lanzada cuando la información remota de actualización es inválida o no confiable.

    Incluye: versión remota con formato no SemVer, URL de asset fuera de la
    fuente oficial, checksum ausente/malformado o nombre de instalador inesperado.
    """
    pass


class UpdateDownloadError(UpdateError):
    """Lanzada cuando la descarga del instalador falla, está incompleta o corrompida."""
    pass
