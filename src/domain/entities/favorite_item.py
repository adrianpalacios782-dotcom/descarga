from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FavoriteItem:
    """Entidad que representa un contenido multimedia guardado en favoritos."""
    url: str
    title: str
    author: str = ""
    platform: str = "YouTube"
    duration_seconds: float = 0.0
    thumbnail_url: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.url or not self.url.strip():
            raise ValueError("FavoriteItem debe tener una URL no vacía.")
        if not self.title or not self.title.strip():
            raise ValueError("FavoriteItem debe tener un título no vacío.")
