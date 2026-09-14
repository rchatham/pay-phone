"""Shared audio recording backend for message-capturing phone systems (TDTM, LAM).

Both plugins use this module as their single sounddevice/soundfile backing so
that device selection, availability checks, and stream lifecycle handling are
identical everywhere.

WARNING: This module uses global state for recording management (is_recording,
filename, file, stream). This is necessary because sounddevice callbacks require
access to these variables. The module is NOT thread-safe - only one recording
can be active at a time.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Conditional imports for recording hardware
try:
    import sounddevice as sd
    import soundfile as sf
    import numpy  # Make sure NumPy is loaded before it is used in the callback
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
device: int | None = None
channels = 1


def _check_recording_available() -> None:
    """Raise if recording hardware dependencies are missing."""
    if not _RECORDING_AVAILABLE:
        details = _IMPORT_ERROR or "sounddevice and soundfile are required for recording."
        raise RuntimeError(f"Recording not available. {details}")


def _normalize_device(device_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": int(device_info["index"]),
        "name": str(device_info["name"]),
        "max_input_channels": int(device_info.get("max_input_channels", 0)),
        "default_samplerate": int(device_info.get("default_samplerate", 44100)),
    }


def list_input_devices() -> list[dict[str, Any]]:
    """Return detected input-capable audio devices."""
    _check_recording_available()

    try:
        devices = sd.query_devices()
    except Exception as exc:
        raise RuntimeError(f"Could not query audio input devices: {exc}") from exc

    return [
        _normalize_device(dict(device_info))
        for device_info in devices
        if int(device_info.get("max_input_channels", 0)) > 0
    ]


def _parse_preferred_device(preferred_device: str | int | None) -> str | int | None:
    if preferred_device is None:
        return None
    if isinstance(preferred_device, int):
        return preferred_device
    preferred = preferred_device.strip()
    if not preferred:
        return None
    if preferred.isdigit():
        return int(preferred)
    return preferred.lower()


def _select_input_device(preferred_device: str | int | None) -> dict[str, Any]:
    parsed_device = _parse_preferred_device(preferred_device)
    devices = list_input_devices()
    if not devices:
        raise RuntimeError("No audio input devices found")

    if isinstance(parsed_device, int):
        for audio_device in devices:
            if audio_device["index"] == parsed_device:
                return audio_device
        raise RuntimeError(f"Configured input device index {parsed_device} was not found. Available: {devices}")

    if isinstance(parsed_device, str):
        for audio_device in devices:
            if parsed_device in audio_device["name"].lower():
                return audio_device
        raise RuntimeError(f"Configured input device '{preferred_device}' was not found. Available: {devices}")

    default_device = sd.query_devices(kind="input")
    default_index = int(default_device["index"])
    for audio_device in devices:
        if audio_device["index"] == default_index:
            return audio_device

    raise RuntimeError(f"Default input device is not input-capable. Default: {default_device}. Available: {devices}")


def init(
    preferred_device: str | int | None = None,
    preferred_samplerate: int = 44100,
    preferred_channels: int = 1,
) -> None:
    """Initialize recording from explicit config and detected input devices."""
    _check_recording_available()

    global samplerate, device, channels
    try:
        audio_device = _select_input_device(preferred_device)
        if preferred_channels > audio_device["max_input_channels"]:
            raise RuntimeError(
                f"Configured {preferred_channels} recording channels, but device "
                f"{audio_device['index']} supports {audio_device['max_input_channels']}"
            )

        device = audio_device["index"]
        samplerate = int(preferred_samplerate or audio_device["default_samplerate"])
        channels = int(preferred_channels)
        logger.info(
            "Initialized recording device=%s samplerate=%s channels=%s",
            device,
            samplerate,
            channels,
        )
    except Exception as exc:
        try:
            devices = list_input_devices()
        except Exception as list_exc:
            devices = [{"error": str(list_exc)}]
        logger.error(
            "Record init failed with RECORDING_DEVICE=%r samplerate=%r channels=%r available_devices=%s error=%s",
            preferred_device,
            preferred_samplerate,
            preferred_channels,
            devices,
            exc,
        )
        raise


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


def cancel_recording(delete_file: Optional[Callable[[Path], None]] = None) -> None:
    """Cancel the current recording and remove the partial output file.

    ``delete_file`` is an optional plugin-provided deletion callback (for example
    TDTM's filehandling helper); when absent the partial file is unlinked.
    """
    if not _RECORDING_AVAILABLE:
        return

    global is_recording, filename
    if stream is not None:
        stream.stop()
    is_recording = False
    close_file()
    close_stream()

    if filename is not None:
        if delete_file is not None:
            delete_file(filename)
        elif filename.exists():
            filename.unlink()
        filename = None


def finish_recording() -> None:
    if not _RECORDING_AVAILABLE:
        return

    global is_recording
    if stream is not None:
        stream.stop()
    is_recording = False
    close_file()
    close_stream()


def stop_recording() -> None:
    """Alias for finish_recording()."""
    finish_recording()


def restart_recording() -> None:
    """Truncate the output file and reset the timeout clock for a redo."""
    global file, start_time
    file.truncate(0)
    start_time = int(time.time())


def start_recording(
    target_filename: str | Path,
    timeout: int = 180,
    timeout_callback: Optional[Callable[[], None]] = None,
) -> None:
    """Start recording audio to a WAV file."""
    _check_recording_available()

    global is_recording, filename, file, stream, start_time
    is_recording = True
    filename = Path(target_filename)
    filename.parent.mkdir(parents=True, exist_ok=True)

    def callback(indata, frames, time_info, status):
        # Called from a separate thread for each audio block.
        del frames, time_info
        if not is_recording:
            return
        if timeout and int(time.time()) - start_time >= timeout:
            stream.stop()
            if timeout_callback is not None:
                timeout_callback()
            return
        if status:
            logger.warning("Recording callback status: %s", status)
        file.write(indata.copy())

    file = sf.SoundFile(str(filename), mode="w", samplerate=int(samplerate), channels=channels)
    stream = sd.InputStream(callback=callback, samplerate=int(samplerate), channels=channels, device=device)
    start_time = int(time.time())
    stream.start()
