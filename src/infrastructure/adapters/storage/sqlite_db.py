import sqlite3
from typing import List, Optional, Tuple


class DatabaseManager:
    """Administrador de la base de datos SQLite con soporte nativo de modo WAL y migraciones ligeras."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

    def get_connection(self) -> sqlite3.Connection:
        """Obtiene o crea una conexión configurada a la base de datos SQLite."""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row

            # Si no es en memoria, activar modo WAL y Foreign Keys
            if self.db_path != ":memory:":
                self._connection.execute("PRAGMA journal_mode=WAL;")
            self._connection.execute("PRAGMA foreign_keys=ON;")

        return self._connection

    def init_tables(self) -> None:
        """Crea las tablas necesarias si no existen y aplica migraciones de columnas."""
        conn = self.get_connection()
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS media_items (
                    id TEXT PRIMARY KEY,
                    original_url TEXT NOT NULL,
                    platform_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    duration_seconds REAL DEFAULT 0,
                    thumbnail_url TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS format_options (
                    id TEXT PRIMARY KEY,
                    media_id TEXT NOT NULL,
                    format_id TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    resolution TEXT,
                    width INTEGER,
                    height INTEGER,
                    fps REAL,
                    filesize_bytes INTEGER,
                    is_audio_only INTEGER DEFAULT 0,
                    is_video_only INTEGER DEFAULT 0,
                    FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS download_tasks (
                    id TEXT PRIMARY KEY,
                    media_id TEXT NOT NULL,
                    chosen_format_id TEXT NOT NULL,
                    destination_path TEXT NOT NULL,
                    current_state TEXT NOT NULL,
                    progress_percent REAL DEFAULT 0.0,
                    downloaded_bytes INTEGER DEFAULT 0,
                    total_bytes INTEGER DEFAULT 0,
                    speed_bps REAL DEFAULT 0.0,
                    eta_seconds REAL DEFAULT 0.0,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY(media_id) REFERENCES media_items(id)
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    category TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS system_error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    module TEXT NOT NULL,
                    message TEXT NOT NULL,
                    stack_trace TEXT
                );
            """)

            self._migrate_format_options(conn)
            self._migrate_download_tasks(conn)

    @staticmethod
    def _migrate_format_options(conn: sqlite3.Connection) -> None:
        """Añade columnas nuevas a format_options si la tabla ya existía sin ellas."""
        existing: List[str] = [
            row[1]
            for row in conn.execute("PRAGMA table_info(format_options)").fetchall()
        ]

        columns: List[Tuple[str, str]] = [
            ("stream_type", "TEXT DEFAULT 'VIDEO_AUDIO'"),
            ("needs_ffmpeg_merge", "INTEGER DEFAULT 0"),
            ("audio_format_id", "TEXT"),
            ("bitrate_kbps", "REAL"),
            ("target_audio_format", "TEXT"),
            ("target_audio_bitrate", "INTEGER"),
            ("is_best_quality", "INTEGER DEFAULT 0"),
            ("video_codec", "TEXT"),
            ("audio_codec", "TEXT"),
        ]

        for column, ddl in columns:
            if column not in existing:
                conn.execute(f"ALTER TABLE format_options ADD COLUMN {column} {ddl}")

    @staticmethod
    def _migrate_download_tasks(conn: sqlite3.Connection) -> None:
        """Añade columnas nuevas a download_tasks si la tabla ya existía sin ellas."""
        existing: List[str] = [
            row[1]
            for row in conn.execute("PRAGMA table_info(download_tasks)").fetchall()
        ]
        if "quality_warning" not in existing:
            conn.execute("ALTER TABLE download_tasks ADD COLUMN quality_warning TEXT")

    def close(self) -> None:
        """Cierra la conexión activa."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
