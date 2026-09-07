"""Tests exhaustivos para ErrorClassifier."""
import pytest

from src.domain.services.error_classifier import ClassifiedError, ErrorCategory, ErrorClassifier


class TestErrorClassifier:

    @pytest.mark.parametrize(
        "error_str, expected_category",
        [
            ("ERROR: [youtube] abc: This video is private.", ErrorCategory.PRIVATE_CONTENT),
            ("This video is members-only and requires a join subscription", ErrorCategory.MEMBERS_ONLY),
            ("Sign in to confirm your age", ErrorCategory.AGE_RESTRICTION),
            ("Sign in to confirm you're not a bot", ErrorCategory.BOT_DETECTION),
            ("TikTok challenge detected: unusual traffic", ErrorCategory.BOT_DETECTION),
            ("Could not extract cookies from chrome", ErrorCategory.COOKIES_ERROR),
            ("This video is not available in your country", ErrorCategory.GEO_BLOCKED),
            ("Video unavailable - this content is no longer available", ErrorCategory.UNAVAILABLE),
            ("Please sign in to view this video", ErrorCategory.SIGN_IN_REQUIRED),
            ("Unable to extract nsig parameter", ErrorCategory.EXTRACTOR_OUTDATED),
            ("Requested format is not available", ErrorCategory.FORMAT_UNAVAILABLE),
            ("HTTP Error 403: Forbidden", ErrorCategory.NETWORK_ERROR),
            ("HTTP Error 429: Too Many Requests", ErrorCategory.BOT_DETECTION),
            ("Connection reset by peer", ErrorCategory.NETWORK_ERROR),
            ("ffmpeg: conversion failed", ErrorCategory.FFMPEG_ERROR),
            ("Video not found: 404", ErrorCategory.NOT_FOUND),
            ("This is not a valid URL", ErrorCategory.INVALID_URL),
            ("Something random that does not match any regex", ErrorCategory.UNKNOWN),
        ],
    )
    def test_classify_categories(self, error_str: str, expected_category: ErrorCategory) -> None:
        classified = ErrorClassifier.classify(error_str, platform_name="YouTube")
        assert isinstance(classified, ClassifiedError)
        assert classified.category == expected_category
        assert isinstance(classified.user_message, str)
        assert len(classified.user_message) > 0

    def test_platform_specific_message(self) -> None:
        yt_err = ErrorClassifier.classify("This video is private", platform_name="YouTube")
        ig_err = ErrorClassifier.classify("Account is private", platform_name="Instagram")
        tt_err = ErrorClassifier.classify("private account", platform_name="TikTok")

        assert "YouTube" not in ig_err.user_message
        assert "Instagram" in ig_err.user_message
        assert "TikTok" in tt_err.user_message
        assert yt_err.category == ErrorCategory.PRIVATE_CONTENT
        assert ig_err.category == ErrorCategory.PRIVATE_CONTENT

    def test_cookie_recoverable_flag(self) -> None:
        bot_err = ErrorClassifier.classify("bot check required")
        assert bot_err.is_cookie_recoverable is True

        age_err = ErrorClassifier.classify("age-restricted video")
        assert age_err.is_cookie_recoverable is True

        net_err = ErrorClassifier.classify("connection timeout")
        assert net_err.is_cookie_recoverable is False

    def test_suggestion_presence(self) -> None:
        classified = ErrorClassifier.classify("bot check verification")
        assert classified.suggestion is not None
        assert "cookies" in classified.suggestion.lower() or "espera" in classified.suggestion.lower()

    def test_technical_detail_truncation(self) -> None:
        long_msg = "error: " + "A" * 500
        classified = ErrorClassifier.classify(long_msg)
        assert len(classified.technical_detail) <= 300
        assert classified.technical_detail.endswith("...")
