from abc import ABC, abstractmethod
from typing import Optional
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.entities.playlist_metadata import PlaylistMetadata
from src.domain.value_objects.url import Url


class IPlatformAdapter(ABC):
    """Puerto de dominio que define el contrato para los adaptadores de extracción de plataformas."""

    @abstractmethod
    def detect(self, url: Url) -> bool:
        """Determina si este adaptador puede procesar la URL proporcionada."""
        pass

    @abstractmethod
    def analyze(self, url: Url) -> MediaMetadata:
        """Analiza la URL y extrae la información normalizada del medio."""
        pass

    def analyze_playlist(self, url: Url) -> Optional[PlaylistMetadata]:
        """Analiza una lista de reproducción / álbum (opcionalmente implementado por adaptadores compatibles)."""
        return None
