import pytest
from src.domain.exceptions.domain_exceptions import InvalidParameterError
from src.domain.value_objects.time_range import TimeRange


def test_time_range_valid_creation():
    tr = TimeRange(start_seconds=10.0, end_seconds=30.0)
    assert tr.start_seconds == 10.0
    assert tr.end_seconds == 30.0


def test_time_range_negative_start_raises_error():
    with pytest.raises(InvalidParameterError):
        TimeRange(start_seconds=-5.0, end_seconds=10.0)


def test_time_range_end_less_than_start_raises_error():
    with pytest.raises(InvalidParameterError):
        TimeRange(start_seconds=20.0, end_seconds=10.0)


def test_time_range_parse_timestamp_seconds():
    assert TimeRange.parse_timestamp("45") == 45.0
    assert TimeRange.parse_timestamp("45.5") == 45.5


def test_time_range_parse_timestamp_minutes_seconds():
    assert TimeRange.parse_timestamp("01:30") == 90.0
    assert TimeRange.parse_timestamp("02:00") == 120.0


def test_time_range_parse_timestamp_hours_minutes_seconds():
    assert TimeRange.parse_timestamp("01:00:00") == 3600.0
    assert TimeRange.parse_timestamp("01:01:30") == 3690.0


def test_time_range_parse_invalid_format_raises_error():
    with pytest.raises(InvalidParameterError):
        TimeRange.parse_timestamp("invalid:time:format:extra")


def test_time_range_from_strings():
    tr = TimeRange.from_strings("01:00", "02:30")
    assert tr.start_seconds == 60.0
    assert tr.end_seconds == 150.0


def test_time_range_to_ytdlp_section():
    tr = TimeRange(start_seconds=65.0, end_seconds=130.0)
    section = tr.to_ytdlp_section()
    assert section == "*00:01:05-00:02:10"

    tr_open = TimeRange(start_seconds=60.0, end_seconds=None)
    assert tr_open.to_ytdlp_section() == "*00:01:00-inf"


def test_time_range_duration_calculation():
    tr = TimeRange(start_seconds=15.5, end_seconds=45.5)
    assert tr.duration == 30.0

    tr_open = TimeRange(start_seconds=10.0, end_seconds=None)
    assert tr_open.duration is None


def test_time_range_to_section_spec_and_format_range():
    tr = TimeRange(start_seconds=85.0, end_seconds=220.0)
    assert tr.to_section_spec() == "*00:01:25-00:03:40"
    assert tr.format_range() == "00:01:25 - 00:03:40"

    tr_frac = TimeRange(start_seconds=10.5, end_seconds=20.25)
    assert tr_frac.to_section_spec() == "*00:00:10.500-00:00:20.250"

    tr_open = TimeRange(start_seconds=90.0, end_seconds=None)
    assert tr_open.to_section_spec() == "*00:01:30-inf"
    assert tr_open.format_range() == "00:01:30 - Fin"

