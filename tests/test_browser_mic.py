from jarvis.ui.browser_mic import parse_mic_event


def test_parse_mic_event_dict() -> None:
    assert parse_mic_event({"action": "start"})["action"] == "start"


def test_parse_mic_event_tuple() -> None:
    assert parse_mic_event(({"action": "stop"},))["action"] == "stop"
