"""Validated Booth snapshots and safe state-local media references."""
from __future__ import annotations

import copy
import json
import logging
import math
import re
from pathlib import Path
from typing import Callable, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from payphone.config.persistence import atomic_write_json, state_directory

logger = logging.getLogger(__name__)
MAX_JSON_BYTES = 65536
MAX_AUDIO_BYTES = 32 * 1024 * 1024
SERVICES = ("weather", "time", "jokes", "music")
MEDIA_NAME = re.compile(r"[a-zA-Z0-9_-]{1,80}\.wav\Z")


class AdminCapability(Protocol):
    def require_authorized(self) -> None: ...

    def protected_commit(self, replace: Callable[[], None]) -> None: ...


def default_content() -> dict:
    """Return an independent default snapshot; do not write it automatically."""
    return {
        "version": 1,
        "services": {name: True for name in SERVICES},
        "weather": {"latitude": 40.7128, "longitude": -74.0060, "units": "celsius"},
        "timezone": "local",
        "music": "sample.wav",
        "categories": [{"slot": "4", "label": "Community information", "label_audio": None,
                        "messages": [{"slot": "1", "label": "Welcome", "label_audio": None,
                                      "text": "Welcome to the information booth. Ask the operator to add local information.",
                                      "audio": None}]}],
    }


def safe_media_path(root: Path, name: str, *, must_exist: bool = True) -> Path:
    """Accept only simple WAV names and reject symlinks, including escaped roots."""
    if not isinstance(name, str) or not MEDIA_NAME.fullmatch(name):
        raise ValueError("Audio must be a simple WAV filename")
    if root.is_symlink():
        raise ValueError("Audio directory must not be a symlink")
    target = root / name
    if target.is_symlink() or target.resolve().parent != root.resolve():
        raise ValueError("Unsafe audio reference")
    if must_exist and (not target.is_file() or not 44 <= target.stat().st_size <= MAX_AUDIO_BYTES):
        raise ValueError("Audio is missing, empty, or too large")
    return target


def _keys(value: object, expected: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("Invalid configuration fields")
    return value


def _text(value: object, maximum: int, *, empty: bool = False) -> None:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise ValueError("Invalid text length")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError("Control characters are not allowed")


def validate_content(data: object, media_root: Path) -> dict:
    """Strict bounded schema, unique keypad slots, valid timezone and media."""
    data = _keys(data, {"version", "services", "weather", "timezone", "music", "categories"})
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("Unsupported Booth schema version")
    services = _keys(data["services"], set(SERVICES))
    if any(type(enabled) is not bool for enabled in services.values()):
        raise ValueError("Service switches must be booleans")
    weather = _keys(data["weather"], {"latitude", "longitude", "units"})
    for key, bound in (("latitude", 90), ("longitude", 180)):
        number = weather[key]
        if type(number) not in (int, float) or not math.isfinite(number) or abs(number) > bound:
            raise ValueError("Invalid weather coordinates")
    if weather["units"] not in ("celsius", "fahrenheit"):
        raise ValueError("Invalid weather units")
    _text(data["timezone"], 100)
    if data["timezone"] != "local":
        try:
            ZoneInfo(data["timezone"])
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
    if data["music"] is not None:
        # The generated sample may not exist until the setup script has run.
        safe_media_path(media_root, data["music"], must_exist=data["music"] != "sample.wav")
    categories = data["categories"]
    if not isinstance(categories, list) or len(categories) > 6:
        raise ValueError("At most six categories are allowed")
    category_slots: set[str] = set()
    for category in categories:
        _keys(category, {"slot", "label", "label_audio", "messages"})
        slot = category["slot"]
        if not isinstance(slot, str) or slot not in "456789" or len(slot) != 1 or slot in category_slots:
            raise ValueError("Category slots must be unique digits 4 through 9")
        category_slots.add(slot)
        _text(category["label"], 100)
        if category["label_audio"] is not None:
            safe_media_path(media_root, category["label_audio"])
        messages = category["messages"]
        if not isinstance(messages, list) or len(messages) > 9:
            raise ValueError("At most nine messages per category are allowed")
        message_slots: set[str] = set()
        for message in messages:
            _keys(message, {"slot", "label", "label_audio", "text", "audio"})
            slot = message["slot"]
            if not isinstance(slot, str) or len(slot) != 1 or slot not in "123456789" or slot in message_slots:
                raise ValueError("Message slots must be unique digits 1 through 9")
            message_slots.add(slot)
            _text(message["label"], 100)
            _text(message["text"], 4000, empty=True)
            for key in ("label_audio", "audio"):
                if message[key] is not None:
                    safe_media_path(media_root, message[key])
            if not message["text"].strip() and message["audio"] is None:
                raise ValueError("A message needs text or recorded audio")
    if len(json.dumps(data).encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("Booth configuration is too large")
    return copy.deepcopy(data)


class ContentStore:
    """Retain last valid content on corrupt external edits; explicit atomic saves."""
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = Path(directory) if directory is not None else state_directory()
        self.path = self.directory / "information_booth.json"
        self.media_root = self.directory / "information_booth_audio"
        self.snapshot = default_content()
        self.reload_error: str | None = None
        self.reload()

    def reload(self) -> dict:
        self.reload_error = None
        try:
            with self.path.open("rb") as source:
                raw = source.read(MAX_JSON_BYTES + 1)
            if len(raw) > MAX_JSON_BYTES:
                raise ValueError("Booth configuration is too large")
            self.snapshot = validate_content(json.loads(raw), self.media_root)
        except FileNotFoundError:
            # Initial absence is normal; removal after loading does not reset content.
            pass
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            self.reload_error = str(exc)
            logger.warning("Booth configuration rejected; retaining last valid content: %s", exc)
        return copy.deepcopy(self.snapshot)

    def references_audio(self, name: str) -> bool:
        """Conservatively keep media if a failed save may have replaced the JSON.

        A directory fsync can fail after atomic replacement. Never delete a file
        referenced by that new JSON just because the writer reported an exception.
        """
        try:
            with self.path.open("rb") as source:
                raw = source.read(MAX_JSON_BYTES + 1)
            if len(raw) > MAX_JSON_BYTES:
                return True
            data = json.loads(raw)
        except FileNotFoundError:
            return False
        except (OSError, ValueError, RecursionError):
            return True

        def contains(value: object) -> bool:
            if isinstance(value, dict):
                return any(contains(item) for item in value.values())
            if isinstance(value, list):
                return any(contains(item) for item in value)
            return value == name

        try:
            return contains(data)
        except RecursionError:
            return True

    def save(self, candidate: dict, admin: AdminCapability) -> None:
        validated = validate_content(candidate, self.media_root)
        admin.require_authorized()  # Early UX check; staging can still be cancelled.
        atomic_write_json(self.path, validated, commit=admin.protected_commit)
        self.snapshot = validated
        self.reload_error = None
