import logging
from src.infrastructure.logging.logger_config import setup_logger, sanitize_log_message


class TestLoggingSystem:

    def test_sanitize_log_message_tokens(self) -> None:
        raw_msg = "Descargando desde https://video.site/stream?token=abc123secret&auth=xyz"
        sanitized = sanitize_log_message(raw_msg)

        assert "abc123secret" not in sanitized
        assert "xyz" not in sanitized
        assert "***REDACTED***" in sanitized

    def test_setup_logger_creates_handlers(self, tmp_path) -> None:
        log_dir = str(tmp_path / "logs")
        logger = setup_logger(log_dir=log_dir, level=logging.DEBUG)

        assert logger.name == "osvaldoDownloaderPro"
        assert len(logger.handlers) >= 2

        logger.info("Prueba de log con token=secret12345")

        log_file = tmp_path / "logs" / "osvaldo_downloader.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "Prueba de log" in content
        assert "secret12345" not in content
        assert "***REDACTED***" in content
