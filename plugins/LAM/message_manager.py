"""Message storage helpers for the Leave a Message plugin."""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Optional


class MessageManager:
    """Manage sequential caller message files."""

    def __init__(self, audio_dir: str = "audio_files", messages_subdir: str = "lam_messages") -> None:
        self.audio_dir = Path(audio_dir)
        self.messages_subdir = messages_subdir
        self.messages_dir = self.audio_dir / messages_subdir
        self.messages_dir.mkdir(parents=True, exist_ok=True)

    def list_all(self) -> list[Path]:
        """Return all visible WAV messages in chronological filename order."""
        if not self.messages_dir.exists():
            return []

        return sorted(
            path for path in self.messages_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".wav" and not path.name.startswith(".")
        )

    def total_count(self) -> int:
        """Return the number of saved messages."""
        return len(self.list_all())

    def get_random(self) -> Optional[Path]:
        """Return a random saved message, if any exist."""
        messages = self.list_all()
        if not messages:
            return None
        return random.choice(messages)

    def filename_for_next(self) -> Path:
        """Return the next sequential message filename."""
        return self.messages_dir / f"{self.total_count() + 1:03d}.wav"

    def relative_audio_path(self, path: Path) -> str:
        """Return a path suitable for AudioHandler.play_file()."""
        return os.path.join(self.messages_subdir, path.name)

    def delete_file(self, path: Path) -> None:
        """Delete a message file if it exists."""
        if path.exists():
            path.unlink()
