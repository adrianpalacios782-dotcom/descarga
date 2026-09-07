from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.twitch_adapter import TwitchAdapter
from src.infrastructure.adapters.platforms.kick_adapter import KickAdapter
from src.infrastructure.adapters.platforms.platform_registry import PlatformRegistry


def test_twitch_adapter_detect():
    adapter = TwitchAdapter()
    assert adapter.detect(Url("https://www.twitch.tv/videos/123456789")) is True
    assert adapter.detect(Url("https://clips.twitch.tv/FrailTameEagle")) is True
    assert adapter.detect(Url("https://youtube.com/watch?v=123")) is False


def test_kick_adapter_detect():
    adapter = KickAdapter()
    assert adapter.detect(Url("https://kick.com/streamer/clips/clip_123")) is True
    assert adapter.detect(Url("https://kick.com/video/12345")) is True
    assert adapter.detect(Url("https://twitch.tv/streamer")) is False


def test_platform_registry_routes_twitch_and_kick():
    registry = PlatformRegistry()
    assert isinstance(registry.find_adapter(Url("https://www.twitch.tv/videos/123")), TwitchAdapter)
    assert isinstance(registry.find_adapter(Url("https://kick.com/streamer/video/123")), KickAdapter)
