from datetime import datetime
import logging
import threading
from typing import List

from src.domain.entities.favorite_item import FavoriteItem
from src.domain.ports.favorite_repository import IFavoriteRepository
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager

logger = logging.getLogger(__name__)


class SQLiteFavoriteRepository(IFavoriteRepository):
    """Adaptador de persistencia para contenidos favoritos usando SQLite."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db = db_manager
        self._lock = threading.RLock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        query = """
            CREATE TABLE IF NOT EXISTS user_favorites (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL DEFAULT '',
                duration_seconds REAL NOT NULL DEFAULT 0.0,
                thumbnail_url TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
        """
        with self._lock:
            with self._db.get_connection() as conn:
                conn.execute(query)

    def add(self, item: FavoriteItem) -> None:
        """Inserta o actualiza un favorito en la base de datos."""
        query = """
            INSERT INTO user_favorites (url, title, author, platform, duration_seconds, thumbnail_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                author = excluded.author,
                platform = excluded.platform,
                duration_seconds = excluded.duration_seconds,
                thumbnail_url = excluded.thumbnail_url
        """
        with self._lock:
            with self._db.get_connection() as conn:
                conn.execute(
                    query,
                    (
                        item.url,
                        item.title,
                        item.author,
                        item.platform,
                        item.duration_seconds,
                        item.thumbnail_url,
                        item.created_at.isoformat(),
                    ),
                )

    def remove(self, url: str) -> None:
        """Elimina un favorito de la base de datos."""
        query = "DELETE FROM user_favorites WHERE url = ?"
        with self._lock:
            with self._db.get_connection() as conn:
                conn.execute(query, (url,))

    def exists(self, url: str) -> bool:
        """Verifica si una URL está registrada en favoritos."""
        query = "SELECT 1 FROM user_favorites WHERE url = ? LIMIT 1"
        with self._lock:
            with self._db.get_connection() as conn:
                cursor = conn.execute(query, (url,))
                return cursor.fetchone() is not None

    def get_all(self) -> List[FavoriteItem]:
        """Obtiene la lista completa de favoritos ordenados por fecha descendente."""
        query = """
            SELECT url, title, author, platform, duration_seconds, thumbnail_url, created_at
            FROM user_favorites
            ORDER BY created_at DESC
        """
        results: List[FavoriteItem] = []
        with self._lock:
            with self._db.get_connection() as conn:
                cursor = conn.execute(query)
                for row in cursor.fetchall():
                    try:
                        created = datetime.fromisoformat(row[6])
                    except (ValueError, TypeError):
                        created = datetime.now()

                    results.append(
                        FavoriteItem(
                            url=str(row[0]),
                            title=str(row[1]),
                            author=str(row[2]),
                            platform=str(row[3]),
                            duration_seconds=float(row[4]),
                            thumbnail_url=str(row[5]),
                            created_at=created,
                        )
                    )
        return results
