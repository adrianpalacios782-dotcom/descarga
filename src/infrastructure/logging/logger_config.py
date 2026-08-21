import logging
from logging.handlers import RotatingFileHandler
import os
import re


def sanitize_log_message(message: str) -> str:
    """Sanitiza mensajes de log eliminando tokens e información sensible.

    Cubre: tokens de URL, Bearer tokens, cookies, session IDs,
    auth headers y caracteres de control de terminal.
    """
    sanitized = re.sub(r"(token|auth|key|secret|password|cookie|session)=[^\s&\"'<>]+", r"\1=***REDACTED***", message, flags=re.IGNORECASE)
    sanitized = re.sub(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer ***REDACTED***", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"Authorization:\s*\S+(?:\s+\S+)?", "Authorization: ***REDACTED***", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"Cookie:\s*[^\s]+", "Cookie: ***REDACTED***", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", sanitized)
    return sanitized


class SensitiveDataFilter(logging.Filter):
    """Filtro de Logging que sanitiza automáticamente los mensajes antes de escribirlos."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_log_message(record.msg)
        return True


def setup_logger(log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    """Configura el sistema de logging centralizado con rotación de archivos y sanitización."""
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "osvaldo_downloader.log")

    logger = logging.getLogger("osvaldoDownloaderPro")
    logger.setLevel(level)

    # Evitar handlers duplicados
    if logger.handlers:
        return logger

    # Formateador
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(filename)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Filter
    sanitizer_filter = SensitiveDataFilter()

    # Handler Consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sanitizer_filter)
    logger.addHandler(console_handler)

    # Handler Archivo Rotativo (Máx 5MB por archivo, conserva 5)
    file_handler = RotatingFileHandler(log_file_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sanitizer_filter)
    logger.addHandler(file_handler)

    return logger
