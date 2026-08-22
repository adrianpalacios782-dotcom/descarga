import pytest

from src.domain.services.content_preview import (
    extract_publication_year,
    format_size_bytes,
    truncate_text,
)


class TestExtractPublicationYear:

    @pytest.mark.parametrize("upload_date,expected", [
        ("20240815", "2024"),
        ("19991231", "1999"),
        ("20240815extra123", "2024"),
        ("2024", "2024"),
    ])
    def test_valid_years(self, upload_date, expected) -> None:
        assert extract_publication_year(upload_date) == expected

    @pytest.mark.parametrize("upload_date", [
        "",
        None,
        "sin fecha",
        "20",
        "abcd",
        "1850",
        "2150",
        "00000000",
    ])
    def test_invalid_or_missing_dates_return_empty(self, upload_date) -> None:
        assert extract_publication_year(upload_date) == ""


class TestTruncateText:

    def test_empty_and_none(self) -> None:
        assert truncate_text("") == ""
        assert truncate_text(None) == ""

    def test_short_text_unchanged(self) -> None:
        text = "Una descripción corta."
        assert truncate_text(text) == text

    def test_whitespace_collapsed(self) -> None:
        assert truncate_text("Hola   mundo\n\nque tal") == "Hola mundo que tal"

    def test_long_text_truncated_with_ellipsis(self) -> None:
        text = "palabra " * 80
        result = truncate_text(text, max_chars=100)
        assert len(result) <= 100
        assert result.endswith("...")
        assert not result.startswith(" ")

    def test_truncation_respects_word_boundary(self) -> None:
        text = "primera segunda tercera cuarta quinta"
        result = truncate_text(text, max_chars=25)
        assert result.endswith("...")
        for word in result[:-3].split():
            assert word in ("primera", "segunda", "tercera")


class TestFormatSizeBytes:

    @pytest.mark.parametrize("size,expected", [
        (None, ""),
        (0, ""),
        (-5, ""),
        (500, "500 B"),
        (2048, "2.0 KB"),
        (84 * 1024 * 1024, "84.0 MB"),
        (1536 * 1024 * 1024, "1.5 GB"),
    ])
    def test_human_sizes(self, size, expected) -> None:
        assert format_size_bytes(size) == expected
