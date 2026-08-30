import threading
from typing import Any, Dict, Optional

from src.domain.ports.settings_repository import ISettingsRepository
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager


class SQLiteSettingsRepository(ISettingsRepository):
    """Implementación de persistencia para configuraciones de usuario en SQLite (thread-safe)."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene una configuración deserializada según su data_type."""
        with self._lock:
            conn = self.db_manager.get_connection()
            cur = conn.execute("SELECT value, data_type FROM user_settings WHERE key = ?", (key,))
            row = cur.fetchone()
            if not row:
                return default
            return self._deserialize(str(row["value"]), str(row["data_type"]))

    def set(
        self,
        key: str,
        value: Any,
        data_type: Optional[str] = None,
        category: str = "general",
    ) -> None:
        """Guarda o actualiza una configuración de forma idempotente."""
        resolved_type = data_type or self._infer_data_type(value)
        val_str = "true" if isinstance(value, bool) and value else ("false" if isinstance(value, bool) else str(value))

        with self._lock:
            conn = self.db_manager.get_connection()
            with conn:
                conn.execute(
                    """
                    INSERT INTO user_settings (key, value, data_type, category)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        data_type = excluded.data_type,
                        category = excluded.category
                    """,
                    (key, val_str, resolved_type, category),
                )

    def get_all(self) -> Dict[str, Any]:
        """Obtiene todas las configuraciones persistidas deserializadas."""
        with self._lock:
            conn = self.db_manager.get_connection()
            rows = conn.execute("SELECT key, value, data_type FROM user_settings").fetchall()
            results: Dict[str, Any] = {}
            for row in rows:
                results[str(row["key"])] = self._deserialize(
                    str(row["value"]), str(row["data_type"])
                )
            return results

    @staticmethod
    def _infer_data_type(value: Any) -> str:
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        return "str"

    @staticmethod
    def _deserialize(value: str, dtype: str) -> Any:
        if dtype == "bool":
            return value.strip().lower() in ("true", "1", "yes", "t")
        if dtype == "int":
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        if dtype == "float":
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        return value
