from jarvis.ui.live_voice import parse_live_voice_event, speech_api_language


def test_parse_live_voice_interim() -> None:
    ev = parse_live_voice_event({"action": "interim", "text": "hello"})
    assert ev["text"] == "hello"


def test_parse_live_voice_warn() -> None:
    ev = parse_live_voice_event({"action": "warn", "message": "network"})
    assert ev["action"] == "warn"


def test_speech_api_language() -> None:
    assert speech_api_language("en") == "en-US"
    assert speech_api_language("en-GB") == "en-GB"
