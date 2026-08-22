"""Tests del Value Object SemanticVersion (versionado SemVer estricto)."""
import dataclasses

import pytest

from src.domain.exceptions.domain_exceptions import InvalidUpdateInfoError
from src.domain.value_objects.semantic_version import SemanticVersion


class TestSemanticVersionParse:

    def test_parse_valid_plain(self):
        v = SemanticVersion.parse("1.2.3")
        assert (v.major, v.minor, v.patch) == (1, 2, 3)

    def test_parse_valid_with_lowercase_v_prefix(self):
        v = SemanticVersion.parse("v10.0.1")
        assert (v.major, v.minor, v.patch) == (10, 0, 1)

    def test_parse_valid_with_uppercase_v_prefix(self):
        assert SemanticVersion.parse("V2.0.1").as_tuple() == (2, 0, 1)

    @pytest.mark.parametrize("raw", [
        "abc",
        "not-a-version",
        "1.0",
        "1",
        "1.0.0.0",
        "",
        "   ",
        None,
        "-1.0.0",
        "01.0.0",
        "1.0.0-beta",
        "1.x.y",
        123,
        ("1", "0", "0"),
    ])
    def test_parse_rejects_invalid_formats(self, raw):
        with pytest.raises(InvalidUpdateInfoError):
            SemanticVersion.parse(raw)


class TestSemanticVersionOrdering:

    def test_equal_versions(self):
        assert SemanticVersion.parse("1.0.0") == SemanticVersion.parse("v1.0.0")

    def test_patch_greater(self):
        assert SemanticVersion.parse("1.0.1") > SemanticVersion.parse("1.0.0")

    def test_minor_greater_beats_patch(self):
        assert SemanticVersion.parse("1.1.0") > SemanticVersion.parse("1.0.99")

    def test_major_dominates(self):
        assert SemanticVersion.parse("2.0.0") > SemanticVersion.parse("1.99.99")

    def test_less_than(self):
        assert SemanticVersion.parse("0.9.0") < SemanticVersion.parse("1.0.0")

    def test_le_and_ge(self):
        a = SemanticVersion.parse("1.0.0")
        assert a <= SemanticVersion.parse("1.0.0")
        assert a >= SemanticVersion.parse("1.0.0")
        assert a <= SemanticVersion.parse("1.0.1")
        assert a >= SemanticVersion.parse("0.9.9")

    def test_str_roundtrip(self):
        assert str(SemanticVersion(3, 14, 159)) == "3.14.159"


class TestSemanticVersionImmutability:

    def test_frozen_dataclass(self):
        v = SemanticVersion(1, 0, 0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.major = 5

    def test_negative_components_rejected_in_constructor(self):
        with pytest.raises(InvalidUpdateInfoError):
            SemanticVersion(major=-1, minor=0, patch=0)
