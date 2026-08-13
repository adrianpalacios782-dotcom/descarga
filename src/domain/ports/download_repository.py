from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.entities.download_task import DownloadTask
from src.domain.value_objects.download_id import DownloadId


class IDownloadRepository(ABC):
    """Puerto de dominio que define el contrato de persistencia para tareas de descarga."""

    @abstractmethod
    def save(self, task: DownloadTask) -> None:
        """Guarda o actualiza una tarea de descarga en la persistencia."""
        pass

    @abstractmethod
    def get_by_id(self, task_id: DownloadId) -> Optional[DownloadTask]:
        """Obtiene una tarea de descarga por su identificador único."""
        pass

    @abstractmethod
    def get_all(self) -> List[DownloadTask]:
        """Obtiene la lista completa de tareas de descarga registradas."""
        pass

    @abstractmethod
    def delete(self, task_id: DownloadId) -> None:
        """Elimina una tarea de descarga de la persistencia."""
        pass
