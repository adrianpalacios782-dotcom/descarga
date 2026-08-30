from abc import ABC, abstractmethod
from typing import List

from src.domain.entities.favorite_item import FavoriteItem


class IFavoriteRepository(ABC):
    """Puerto que define el contrato de almacenamiento y consulta de favoritos."""

    @abstractmethod
    def add(self, item: FavoriteItem) -> None:
        """Guarda o actualiza un elemento en favoritos."""
        pass

    @abstractmethod
    def remove(self, url: str) -> None:
        """Elimina un elemento de favoritos dada su URL."""
        pass

    @abstractmethod
    def exists(self, url: str) -> bool:
        """Comprueba si una URL ya se encuentra en favoritos."""
        pass

    @abstractmethod
    def get_all(self) -> List[FavoriteItem]:
        """Obtiene todos los elementos favoritos ordenados por fecha de creación descendente."""
        pass
