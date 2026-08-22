"""Caso de uso: comprobar si existe una actualización disponible.

Política de actualización (dominio puro):
- Solo se ofrece actualizar a versiones ESTRICTAMENTE superiores.
- Igual versión o inferior → sin actualización (nunca downgrade).
- Información remota inválida → rechazo (InvalidUpdateInfoError); la
  aplicación continúa funcionando con normalidad.
"""
from dataclasses import dataclass
from enum import Enum

from src.domain.exceptions.domain_exceptions import InvalidUpdateInfoError
from src.domain.ports.update_source import IUpdateSource, RemoteRelease
from src.domain.value_objects.semantic_version import SemanticVersion


class UpdateCheckStatus(str, Enum):
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"


@dataclass(frozen=True)
class UpdateCheckResult:
    status: UpdateCheckStatus
    current_version: SemanticVersion
    latest_version: SemanticVersion
    release: RemoteRelease | None

    @property
    def update_available(self) -> bool:
        return self.status is UpdateCheckStatus.UPDATE_AVAILABLE


class CheckForUpdatesUseCase:
    """Consulta la fuente oficial y decide si se ofrece una actualización."""

    def __init__(self, update_source: IUpdateSource) -> None:
        self._update_source = update_source

    def execute(self, current_version: str) -> UpdateCheckResult:
        current = SemanticVersion.parse(current_version)
        release = self._update_source.get_latest_release()
        latest = SemanticVersion.parse(release.tag_name)

        if latest > current:
            return UpdateCheckResult(
                status=UpdateCheckStatus.UPDATE_AVAILABLE,
                current_version=current,
                latest_version=latest,
                release=release,
            )

        # Igual o inferior: no se ofrece downgrade.
        return UpdateCheckResult(
            status=UpdateCheckStatus.UP_TO_DATE,
            current_version=current,
            latest_version=latest,
            release=None,
        )
