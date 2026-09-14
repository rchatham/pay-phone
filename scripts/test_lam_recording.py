#!/usr/bin/env python3
"""Diagnostic recording test for the Leave a Message plugin."""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

from payphone.config.settings import Config
from plugins.LAM import record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test LAM microphone recording setup.")
    parser.add_argument("--seconds", type=int, default=3, help="Seconds to record")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("audio_files/lam_messages/test_lam_recording.wav"),
        help="Output WAV path",
    )
    parser.add_argument("--playback", action="store_true", help="Play the recording with aplay when available")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = Config()

    print("LAM recording diagnostic")
    print(f"ENABLE_RECORDING={config.ENABLE_RECORDING}")
    print(f"RECORDING_DEVICE={config.RECORDING_DEVICE!r}")
    print(f"RECORDING_SAMPLE_RATE={config.RECORDING_SAMPLE_RATE}")
    print(f"RECORDING_CHANNELS={config.RECORDING_CHANNELS}")
    print()

    print("Detected input devices:")
    try:
        for device in record.list_input_devices():
            print(
                f"  [{device['index']}] {device['name']} "
                f"inputs={device['max_input_channels']} default_rate={device['default_samplerate']}"
            )
    except Exception as exc:
        print(f"  ERROR: {exc}")
        raise SystemExit(1) from exc

    print()
    print(f"Recording {args.seconds} seconds to {args.output}...")
    try:
        record.init(
            preferred_device=config.RECORDING_DEVICE,
            preferred_samplerate=config.RECORDING_SAMPLE_RATE,
            preferred_channels=config.RECORDING_CHANNELS,
        )
        record.start_recording(args.output, timeout=0)
        time.sleep(args.seconds)
        record.stop_recording()
    except Exception as exc:
        try:
            record.cancel_recording()
        except Exception:
            pass
        print(f"Recording failed: {exc}")
        raise SystemExit(1) from exc

    size = args.output.stat().st_size if args.output.exists() else 0
    print(f"Saved {args.output} ({size} bytes)")
    if size == 0:
        raise SystemExit("Recording file is empty")

    if args.playback:
        print("Playing recording with aplay...")
        subprocess.run(["aplay", str(args.output)], check=True)


if __name__ == "__main__":
    main()
