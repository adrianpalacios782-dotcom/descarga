from src.domain.services.filename_sanitizer import sanitize_filename


def test_sanitize_filename_normal():
    assert sanitize_filename("Mi Video Favorito") == "Mi Video Favorito"


def test_sanitize_filename_invalid_chars():
    raw = 'Video: "Parte 1" <HD> / 2024? *super* | cool'
    cleaned = sanitize_filename(raw)
    for bad_char in '<>:"/\\|?*':
        assert bad_char not in cleaned
    assert "_" in cleaned


def test_sanitize_filename_empty_and_fallback():
    assert sanitize_filename("") == "descarga"
    assert sanitize_filename("   ") == "descarga"
    assert sanitize_filename("...", fallback="custom") == "custom"


def test_sanitize_filename_trailing_dots_and_spaces():
    assert sanitize_filename("video...") == "video"
    assert sanitize_filename("video   ") == "video"


def test_sanitize_filename_truncation():
    long_name = "a" * 300
    cleaned = sanitize_filename(long_name, max_length=150)
    assert len(cleaned) == 150


def test_sanitize_filename_windows_reserved_names():
    assert sanitize_filename("con") == "_con"
    assert sanitize_filename("AUX") == "_AUX"
    assert sanitize_filename("NUL") == "_NUL"
    assert sanitize_filename("com1") == "_com1"
    assert sanitize_filename("lpt3") == "_lpt3"

