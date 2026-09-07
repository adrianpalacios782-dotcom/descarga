from src.domain.value_objects.audio_preset import AudioPreset


def test_audio_preset_enum_values():
    assert AudioPreset.MP3_320K.value == "mp3_320k"
    assert AudioPreset.MP3_192K.value == "mp3_192k"
    assert AudioPreset.M4A_AAC.value == "m4a_aac"
    assert AudioPreset.FLAC.value == "flac"
    assert AudioPreset.WAV.value == "wav"
    assert AudioPreset.OPUS.value == "opus"


def test_audio_preset_properties():
    mp3 = AudioPreset.MP3_320K
    assert mp3.extension == "mp3"
    assert mp3.ffmpeg_codec == "libmp3lame"
    assert mp3.bitrate == "320k"
    assert "320 kbps" in mp3.display_name

    flac = AudioPreset.FLAC
    assert flac.extension == "flac"
    assert flac.ffmpeg_codec == "flac"
    assert flac.bitrate is None
    assert "Lossless" in flac.display_name


def test_audio_preset_from_string():
    assert AudioPreset.from_string("mp3_320k") == AudioPreset.MP3_320K
    assert AudioPreset.from_string("FLAC") == AudioPreset.FLAC
    assert AudioPreset.from_string("wav") == AudioPreset.WAV
    assert AudioPreset.from_string("unknown") == AudioPreset.MP3_320K
