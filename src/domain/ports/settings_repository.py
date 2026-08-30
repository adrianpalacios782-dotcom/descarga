from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ISettingsRepository(ABC):
    """Puerto de dominio para la persistencia y consulta de configuraciones de usuario."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene el valor de una configuración por su clave."""
        pass

    @abstractmethod
    def set(
        self,
        key: str,
        value: Any,
        data_type: Optional[str] = None,
        category: str = "general",
    ) -> None:
        """Guarda o actualiza una configuración en el almacenamiento persistente."""
        pass

    @abstractmethod
    def get_all(self) -> Dict[str, Any]:
        """Obtiene todas las configuraciones persistidas como diccionario clave-valor tipado."""
        pass
