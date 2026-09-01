#!/usr/bin/env python3
"""Run the Information Booth example outside the BIOS default scan path."""

from __future__ import annotations

import signal
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from system import InformationBoothSystem


def main() -> None:
    """Run the example phone system directly."""
    system = InformationBoothSystem()

    def signal_handler(signum, frame):
        system.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    system.run()


if __name__ == "__main__":
    main()
