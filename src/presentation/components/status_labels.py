"""Etiquetas humanizadas compartidas para los estados de descarga en la presentación."""

from src.domain.entities.download_task import DownloadState


STATUS_TEXT = {
    DownloadState.QUEUED: "En cola",
    DownloadState.ANALYZING: "Analizando",
    DownloadState.READY: "Lista para descargar",
    DownloadState.DOWNLOADING: "Descargando",
    DownloadState.PAUSED: "Pausada",
    DownloadState.PROCESSING: "Procesando",
    DownloadState.COMPLETED: "Completada",
    DownloadState.FAILED: "Error",
    DownloadState.CANCELLED: "Cancelada",
}


def humanize_download_state(state) -> str:
    """Convierte un DownloadState (o su valor textual) en etiqueta legible."""
    try:
        key = state if isinstance(state, DownloadState) else DownloadState(str(state))
    except (ValueError, TypeError):
        return str(state)
    return STATUS_TEXT.get(key, key.value)
