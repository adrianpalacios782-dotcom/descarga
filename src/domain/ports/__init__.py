from src.domain.ports.favorite_repository import IFavoriteRepository
from src.domain.ports.platform_adapter import IPlatformAdapter
from src.domain.ports.download_engine import IDownloadEngine
from src.domain.ports.download_repository import IDownloadRepository
from src.domain.ports.settings_repository import ISettingsRepository
from src.domain.ports.update_source import IUpdateSource, RemoteAsset, RemoteRelease

__all__ = [
    "IFavoriteRepository",
    "IPlatformAdapter",
    "IDownloadEngine",
    "IDownloadRepository",
    "ISettingsRepository",
    "IUpdateSource",
    "RemoteAsset",
    "RemoteRelease",
]
