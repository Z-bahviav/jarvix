import av

from jarvis.voice.decode import _open_av_input


def test_open_av_input_accepts_pyav19() -> None:
    if int(av.__version__.split(".", 1)[0]) < 19:
        return
    container = _open_av_input("/etc/hosts", mode="r")
    container.close()
