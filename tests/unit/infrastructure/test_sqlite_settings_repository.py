import pytest
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
from src.infrastructure.adapters.storage.sqlite_settings_repository import SQLiteSettingsRepository


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_settings.db"
    manager = DatabaseManager(db_path=str(db_file))
    manager.init_tables()
    yield manager
    manager.close()


def test_settings_get_default_when_not_found(temp_db):
    repo = SQLiteSettingsRepository(temp_db)
    assert repo.get("non_existent_key", default="fallback") == "fallback"
    assert repo.get("another_missing") is None


def test_settings_set_and_get_string(temp_db):
    repo = SQLiteSettingsRepository(temp_db)
    repo.set("default_dir", "D:\\Descargas", category="downloads")
    assert repo.get("default_dir") == "D:\\Descargas"


def test_settings_set_and_get_bool(temp_db):
    repo = SQLiteSettingsRepository(temp_db)
    repo.set("ask_destination", True, category="downloads")
    assert repo.get("ask_destination") is True

    repo.set("animations_enabled", False, category="appearance")
    assert repo.get("animations_enabled") is False


def test_settings_set_and_get_int(temp_db):
    repo = SQLiteSettingsRepository(temp_db)
    repo.set("max_concurrent", 5, category="downloads")
    assert repo.get("max_concurrent") == 5


def test_settings_update_idempotent(temp_db):
    repo = SQLiteSettingsRepository(temp_db)
    repo.set("theme", "Oscuro Multimedia", category="appearance")
    assert repo.get("theme") == "Oscuro Multimedia"

    repo.set("theme", "Oscuro OLED", category="appearance")
    assert repo.get("theme") == "Oscuro OLED"


def test_settings_get_all(temp_db):
    repo = SQLiteSettingsRepository(temp_db)
    repo.set("str_val", "hola")
    repo.set("int_val", 42)
    repo.set("bool_val", True)

    all_settings = repo.get_all()
    assert all_settings["str_val"] == "hola"
    assert all_settings["int_val"] == 42
    assert all_settings["bool_val"] is True
