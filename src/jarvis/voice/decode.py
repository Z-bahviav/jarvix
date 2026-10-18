"""Decode uploaded/browser audio for Whisper (PyAV compatibility shim)."""

from __future__ import annotations

import gc
import io
import itertools
from typing import BinaryIO, Union

import av
import numpy as np


def _open_av_input(input_file: Union[str, BinaryIO], mode: str = "r"):
    """PyAV 19 removed metadata_errors; faster-whisper still passes it on older pins."""
    try:
        return av.open(input_file, mode=mode, metadata_errors="ignore")
    except TypeError:
        return av.open(input_file, mode=mode)


def decode_audio_file(
    input_file: Union[str, BinaryIO],
    sampling_rate: int = 16000,
) -> np.ndarray:
    resampler = av.audio.resampler.AudioResampler(
        format="s16",
        layout="mono",
        rate=sampling_rate,
    )

    raw_buffer = io.BytesIO()
    dtype = None

    with _open_av_input(input_file, mode="r") as container:
        frames = container.decode(audio=0)
        frames = _ignore_invalid_frames(frames)
        frames = _group_frames(frames, 500000)
        frames = _resample_frames(frames, resampler)

        for frame in frames:
            array = frame.to_ndarray()
            dtype = array.dtype
            raw_buffer.write(array)

    del resampler
    gc.collect()

    if dtype is None:
        return np.zeros((0,), dtype=np.float32)

    audio = np.frombuffer(raw_buffer.getbuffer(), dtype=dtype)
    return (audio.astype(np.float32) / 32768.0).astype(np.float32)


def _ignore_invalid_frames(frames):
    iterator = iter(frames)
    while True:
        try:
            yield next(iterator)
        except StopIteration:
            break
        except av.error.InvalidDataError:
            continue


def _group_frames(frames, num_samples=None):
    fifo = av.audio.fifo.AudioFifo()
    for frame in frames:
        frame.pts = None
        fifo.write(frame)
        if num_samples is not None and fifo.samples >= num_samples:
            yield fifo.read()
    if fifo.samples > 0:
        yield fifo.read()


def _resample_frames(frames, resampler):
    for frame in itertools.chain(frames, [None]):
        yield from resampler.resample(frame)
