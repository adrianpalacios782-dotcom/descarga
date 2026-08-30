import pytest
from src.domain.entities.favorite_item import FavoriteItem
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
from src.infrastructure.adapters.storage.sqlite_favorite_repository import (
    SQLiteFavoriteRepository,
)


@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test_favorites.db"
    db_manager = DatabaseManager(db_path=str(db_file))
    repo_obj = SQLiteFavoriteRepository(db_manager=db_manager)
    yield repo_obj
    db_manager.close()


def test_add_and_get_all_favorites(repo):
    assert repo.get_all() == []

    item1 = FavoriteItem(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Rick Astley - Never Gonna Give You Up",
        author="Rick Astley",
        platform="YouTube",
        duration_seconds=212.0,
        thumbnail_url="https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
    )
    repo.add(item1)

    items = repo.get_all()
    assert len(items) == 1
    assert items[0].url == item1.url
    assert items[0].title == item1.title
    assert items[0].author == "Rick Astley"
    assert items[0].duration_seconds == 212.0


def test_exists_and_remove_favorite(repo):
    url = "https://www.tiktok.com/@user/video/123"
    assert repo.exists(url) is False

    item = FavoriteItem(
        url=url,
        title="TikTok Dance",
        author="dancer",
        platform="TikTok",
    )
    repo.add(item)
    assert repo.exists(url) is True

    repo.remove(url)
    assert repo.exists(url) is False
    assert repo.get_all() == []


def test_add_conflict_updates_existing(repo):
    url = "https://www.instagram.com/reel/abc"
    item1 = FavoriteItem(url=url, title="Original Title", author="user1")
    repo.add(item1)

    item2 = FavoriteItem(url=url, title="Updated Title", author="user2")
    repo.add(item2)

    items = repo.get_all()
    assert len(items) == 1
    assert items[0].title == "Updated Title"
    assert items[0].author == "user2"


def test_favorite_item_validation():
    with pytest.raises(ValueError, match="URL"):
        FavoriteItem(url="", title="Test")

    with pytest.raises(ValueError, match="título"):
        FavoriteItem(url="https://example.com", title="")
