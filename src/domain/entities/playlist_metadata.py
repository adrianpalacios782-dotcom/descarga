from dataclasses import dataclass, field
from typing import List, Optional

from src.domain.value_objects.url import Url


@dataclass(frozen=True)
class PlaylistEntry:
    """Representa un elemento/video individual dentro de una lista de reproducción."""

    video_id: str
    title: str
    url: str
    duration_seconds: float = 0.0
    thumbnail_url: str = ""
    uploader: str = ""

    @property
    def id(self) -> str:
        return self.video_id

    def get_duration_formatted(self) -> str:
        total = int(self.duration_seconds)
        hrs = total // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        if hrs > 0:
            return f"{hrs:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"


@dataclass
class PlaylistMetadata:
    """Entidad que agrupa la información y entradas de una lista de reproducción."""

    playlist_id: str
    title: str
    url: Url
    platform: str
    uploader: str = ""
    description: str = ""
    entries: List[PlaylistEntry] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.playlist_id

    @property
    def author(self) -> str:
        return self.uploader

    @property
    def total_count(self) -> int:
        return len(self.entries)

    @property
    def item_count(self) -> int:
        return len(self.entries)

    @property
    def total_duration_seconds(self) -> float:
        return sum(e.duration_seconds for e in self.entries)
