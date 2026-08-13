import pytest
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.platform_registry import PlatformRegistry
from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter
from src.infrastructure.adapters.platforms.tiktok_adapter import TikTokAdapter
from src.infrastructure.adapters.platforms.instagram_adapter import InstagramAdapter
from src.infrastructure.adapters.platforms.facebook_adapter import FacebookAdapter
from src.infrastructure.adapters.platforms.generic_adapter import GenericAdapter


class TestPlatformAdapters:

    def test_registry_detection_routing(self) -> None:
        registry = PlatformRegistry()

        url_yt = Url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        url_tt = Url("https://www.tiktok.com/@user/video/12345")
        url_ig = Url("https://www.instagram.com/reel/C123/")
        url_fb = Url("https://www.facebook.com/watch/?v=456")
        url_gen = Url("https://vimeo.com/78910")

        assert isinstance(registry.find_adapter(url_yt), YouTubeAdapter)
        assert isinstance(registry.find_adapter(url_tt), TikTokAdapter)
        assert isinstance(registry.find_adapter(url_ig), InstagramAdapter)
        assert isinstance(registry.find_adapter(url_fb), FacebookAdapter)
        assert isinstance(registry.find_adapter(url_gen), GenericAdapter)
