#!/usr/bin/env python3
"""Generate an original, short sine-wave melody using only the Python stdlib."""
from __future__ import annotations

import argparse
import math
import os
import struct
import sys
import tempfile
import wave
from pathlib import Path


def generate_sample(destination: Path) -> None:
    """Atomically generate 8 seconds of original mono PCM music, no downloads."""
    if destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("Refusing a symlink audio destination")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    rate = 16000
    # Original two-phrase miniature, not a recording or adaptation of a song.
    notes = (261.63, 329.63, 392.00, 293.66, 349.23, 440.00, 392.00, 329.63,
             293.66, 392.00, 349.23, 261.63, 329.63, 293.66, 246.94, 261.63)
    fd, name = tempfile.mkstemp(prefix=".sample-", suffix=".wav", dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        with wave.open(str(temporary), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            for frequency in notes:
                frames = bytearray()
                count = rate // 2
                for sample in range(count):
                    moment = sample / rate
                    envelope = min(1.0, moment / 0.02, (0.5 - moment) / 0.07)
                    signal = math.sin(2 * math.pi * frequency * moment)
                    signal += 0.2 * math.sin(4 * math.pi * frequency * moment)
                    frames.extend(struct.pack("<h", int(7000 * envelope * signal)))
                output.writeframes(frames)
        with temporary.open("rb") as source:
            os.fsync(source.fileno())
        os.replace(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Output WAV; defaults to the Booth state audio directory")
    arguments = parser.parse_args()
    destination = arguments.output
    if destination is None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from payphone.config.persistence import state_directory
        root = state_directory()
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination = root / "information_booth_audio" / "sample.wav"
    generate_sample(destination)
    print(f"Generated original music: {destination}")


if __name__ == "__main__":
    main()
