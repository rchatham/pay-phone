"""Audio recording support for the Leave a Message plugin."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

try:
    import sounddevice as sd
    import soundfile as sf
    import numpy  # noqa: F401 - loaded before callback uses sounddevice buffers
    _RECORDING_AVAILABLE = True
    _IMPORT_ERROR: Optional[str] = None
except ImportError as exc:
    sd = None
    sf = None
    _RECORDING_AVAILABLE = False
    _IMPORT_ERROR = str(exc)


is_recording = False
filename: Optional[Path] = None
file = None
stream = None
start_time = int(time.time())

samplerate = 44100
device = 1
channels = 1


def _check_recording_available() -> None:
    if not _RECORDING_AVAILABLE:
        details = _IMPORT_ERROR or "sounddevice and soundfile are required for recording."
        raise RuntimeError(f"Recording not available. {details}")


def init() -> None:
    """Initialize input device defaults from the first available input device."""
    _check_recording_available()

    global samplerate, device, channels
    audio_device = sd.query_devices(kind="input")
    device = audio_device["index"]
    samplerate = audio_device["default_samplerate"]
    channels = audio_device["max_input_channels"]


def close_file() -> None:
    global file
    if file is not None:
        file.close()
        file = None


def close_stream() -> None:
    global stream
    if stream is not None:
        stream.close()
        stream = None


def cancel_recording() -> None:
    global is_recording, filename
    if not _RECORDING_AVAILABLE:
        return

    if stream is not None:
        stream.stop()
    is_recording = False
    close_file()
    close_stream()

    if filename is not None and filename.exists():
        filename.unlink()
    filename = None


def finish_recording() -> None:
    global is_recording
    if not _RECORDING_AVAILABLE:
        return

    if stream is not None:
        stream.stop()
    is_recording = False
    close_file()
    close_stream()


def stop_recording() -> None:
    """Alias for finish_recording()."""
    finish_recording()


def start_recording(
    target_filename: Path,
    timeout: int = 180,
    timeout_callback: Optional[Callable[[], None]] = None,
) -> None:
    """Start recording audio to a WAV file."""
    _check_recording_available()

    global is_recording, filename, file, stream, start_time
    is_recording = True
    filename = target_filename
    filename.parent.mkdir(parents=True, exist_ok=True)

    def callback(indata, frames, time_info, status):
        del frames, time_info
        elapsed_time = int(time.time()) - start_time
        if not is_recording:
            return
        if timeout and elapsed_time >= timeout:
            if timeout_callback is not None:
                timeout_callback()
            raise sd.CallbackStop()
        if status:
            print(status)
        file.write(indata.copy())

    file = sf.SoundFile(str(filename), mode="w", samplerate=int(samplerate), channels=channels)
    stream = sd.InputStream(callback=callback, samplerate=int(samplerate), channels=channels, device=device)
    start_time = int(time.time())
    stream.start()
