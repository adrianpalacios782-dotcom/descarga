"""Estado de la sesion de navegador vinculada a una extraccion.

La app vincula la sesion del navegador de forma automatica (sin que el usuario
cargue cookies.txt). Este value object transporta el resultado de esa vinculacion
desde la infraestructura hasta la interfaz, donde se muestra como indicador de
estado en lugar del antiguo banner "cargar cookies.txt".
"""

from dataclasses import dataclass
from enum import Enum


class SessionState(str, Enum):
    """Estado de la vinculacion de sesion durante el analisis."""

    #: La sesion se aplico: la extraccion uso las cookies del navegador.
    LINKED = "linked"

    #: Hay navegador con perfil activo, pero su almacen de cookies esta
    #: bloqueado (normalmente porque el navegador esta abierto en Windows).
    BLOCKED = "blocked"

    #: No hay ningun navegador con perfil activo del que tomar sesion.
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SessionStatus:
    """Describe el origen de la sesion usada en una extraccion.

    Attributes:
        state: estado de la vinculacion.
        browser: identificador del navegador ("chrome", "brave", "edge",
            "firefox"). Vacio si no se detecto ninguno.
        profile: nombre del perfil del que se tomo la sesion. Vacio si no se
            pudo determinar.
    """

    state: SessionState = SessionState.UNAVAILABLE
    browser: str = ""
    profile: str = ""

    @property
    def linked(self) -> bool:
        """Indica si la extraccion uso una sesion de navegador."""
        return self.state == SessionState.LINKED

    @property
    def blocked(self) -> bool:
        """Indica que habia sesion disponible pero no se pudo leer."""
        return self.state == SessionState.BLOCKED
