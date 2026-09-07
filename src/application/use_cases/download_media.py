from typing import Optional, Union

from src.application.use_cases.create_download import CreateDownloadUseCase
from src.domain.entities.download_task import DownloadRequest, DownloadState, DownloadTask
from src.domain.ports.download_engine import IDownloadEngine
from src.domain.ports.download_repository import IDownloadRepository


class DownloadMediaUseCase:
    """Caso de uso para orquestar y ejecutar descargas propagando time_range al motor."""

    def __init__(
        self,
        repository: IDownloadRepository,
        engine: IDownloadEngine,
        create_use_case: Optional[CreateDownloadUseCase] = None,
    ) -> None:
        self.repository = repository
        self.engine = engine
        self.create_use_case = create_use_case or CreateDownloadUseCase(repository)

    def execute(self, request_or_task: Union[DownloadRequest, DownloadTask]) -> DownloadTask:
        """Ejecuta la descarga a partir de un DownloadRequest o DownloadTask existente."""
        if isinstance(request_or_task, DownloadRequest):
            task = self.create_use_case.execute(
                media=request_or_task.media,
                format_id=request_or_task.format_id,
                destination_path=request_or_task.destination_path,
                subtitle_config=request_or_task.subtitle_config,
                time_range=request_or_task.time_range,
                audio_preset=request_or_task.audio_preset,
                embed_thumbnail=request_or_task.embed_thumbnail,
            )
        else:
            task = request_or_task

        if task.status == DownloadState.QUEUED:
            task.transition_to(DownloadState.DOWNLOADING)
        self.repository.save(task)

        self.engine.download(task)
        return task
