"""Port del sistema de actualización: fuente oficial de versiones.

Define el contrato que cualquier fuente de actualizaciones debe cumplir.
La implementación oficial es GitHub Releases (ver
src/infrastructure/updater/github_releases_source.py).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RemoteAsset:
    """Asset (archivo publicado) asociado a un release remoto.

    Solo se aceptan assets cuyo `url` sea HTTPS y pertenezca a la fuente
    oficial configurada; la validación de confianza ocurre en el adaptador,
    este DTO es un dato inmutable ya saneado.
    """

    name: str
    url: str
    size_bytes: int | None
    sha256: str | None


@dataclass(frozen=True)
class RemoteRelease:
    """Información saneada del último release disponible en la fuente oficial."""

    tag_name: str
    release_notes: str
    installer_asset: RemoteAsset | None


class IUpdateSource(ABC):
    """Contrato de consulta de la última versión publicada.

    La implementación NO debe lanzar por falta de red sin más: las capas
    superiores deciden cómo tratar UpdateUnavailableError / errores de red.
    """

    @abstractmethod
    def get_latest_release(self) -> RemoteRelease:
        """Obtiene el release más reciente publicado en la fuente oficial.

        Lanza InvalidUpdateInfoError si la información recibida no es fiable
        (versión inválida, asset fuera de la fuente oficial, etc.) y
        UpdateError (o subclases) ante fallos de red/servicio.
        """
        raise NotImplementedError
