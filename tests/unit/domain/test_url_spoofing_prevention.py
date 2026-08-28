"""Test de regresión para prevención de platform spoofing en URLs."""
from unittest.mock import MagicMock
from src.domain.value_objects.url import Url
from src.application.use_cases.analyze_url import AnalyzeUrlUseCase
from src.domain.ports.platform_adapter import IPlatformAdapter


def test_platform_detection_resists_query_param_spoofing():
    # URL de Facebook con 'youtube.com' en query param
    url_fb = Url("https://www.facebook.com/watch/?v=456&ref=youtube.com")
    assert url_fb.detect_platform() == "Facebook"

    # URL de TikTok con 'instagram.com' en query param
    url_tt = Url("https://www.tiktok.com/@user/video/999?share=instagram.com")
    assert url_tt.detect_platform() == "TikTok"

    # URL de YouTube con 'facebook.com' en query param
    url_yt = Url("https://www.youtube.com/watch?v=123&source=facebook.com")
    assert url_yt.detect_platform() == "YouTube"


def test_analyze_url_use_case_sanitizes_playlist_parameters():
    mock_adapter = MagicMock(spec=IPlatformAdapter)
    mock_adapter.detect.return_value = True
    mock_adapter.analyze.return_value = MagicMock()

    use_case = AnalyzeUrlUseCase(mock_adapter)
    raw_url = "https://www.youtube.com/watch?v=F3tKutGo1Fo&list=PL12345&index=3"
    use_case.execute(raw_url)

    mock_adapter.detect.assert_called_once()
    called_url = mock_adapter.detect.call_args[0][0]
    assert "list=" not in called_url.value
    assert "index=" not in called_url.value
    assert called_url.value == "https://www.youtube.com/watch?v=F3tKutGo1Fo"
