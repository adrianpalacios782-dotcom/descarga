from abc import ABC, abstractmethod
from src.domain.entities.download_task import DownloadTask


class IDownloadEngine(ABC):
    """Puerto de dominio que define el contrato para el motor ejecutor de descargas."""

    @abstractmethod
    def download(self, task: DownloadTask) -> None:
        """Inicia el proceso de descarga de una tarea configurada."""
        pass

    @abstractmethod
    def pause(self, task: DownloadTask) -> None:
        """Pausa la ejecución activa de una tarea de descarga."""
        pass

    @abstractmethod
    def resume(self, task: DownloadTask) -> None:
        """Reanuda la ejecución de una tarea de descarga pausada."""
        pass

    @abstractmethod
    def cancel(self, task: DownloadTask) -> None:
        """Cancela y aborta definitivamente la tarea de descarga."""
        pass
