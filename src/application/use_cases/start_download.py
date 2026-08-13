from src.domain.entities.download_task import DownloadState
from src.domain.exceptions.domain_exceptions import TaskNotFoundError
from src.domain.ports.download_engine import IDownloadEngine
from src.domain.ports.download_repository import IDownloadRepository
from src.domain.value_objects.download_id import DownloadId


class StartDownloadUseCase:
    """Caso de uso para iniciar una descarga registrada en el motor de descargas."""

    def __init__(self, repository: IDownloadRepository, engine: IDownloadEngine) -> None:
        self.repository = repository
        self.engine = engine

    def execute(self, task_id: DownloadId) -> None:
        task = self.repository.get_by_id(task_id)
        if not task:
            raise TaskNotFoundError(f"No se encontró la tarea de descarga con ID '{task_id.value}'.")

        task.transition_to(DownloadState.DOWNLOADING)
        self.repository.save(task)
        self.engine.download(task)
