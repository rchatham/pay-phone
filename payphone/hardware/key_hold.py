"""
Track which keypad keys are physically held down, and when they were released.

The input queue only carries key-down events. Pickup routes need more: "was 9
still held when the handset was lifted?". Hardware handlers feed a
:class:`KeyHoldTracker` with key-down / key-up transitions and expose its
snapshot as ``key_holds()``.

Pure Python (no GPIO or serial imports) so it can be used and tested anywhere.
"""

import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class KeyHold:
    """One key's most recent press.

    Attributes:
        key: Keypad character, e.g. ``"9"``.
        down_at: When it went down (``time.monotonic()`` seconds).
        up_at: When it was released, or None while it is still held.
    """

    key: str
    down_at: float
    up_at: Optional[float] = None

    @property
    def is_down(self) -> bool:
        return self.up_at is None


class KeyHoldTracker:
    """Thread-safe record of each key's latest hold.

    The keypad scanning thread writes; the hook callback thread reads.
    """

    def __init__(self, rejoin_s: float = 0.05) -> None:
        """
        Args:
            rejoin_s: A key that goes down again within this many seconds of
                its release continues the same hold. Absorbs contact bounce,
                so a bouncing switch does not look like many short presses.
        """
        self.rejoin_s = rejoin_s
        self._holds: Dict[str, KeyHold] = {}
        self._lock = threading.Lock()

    def key_down(self, key: str, at: Optional[float] = None) -> None:
        """Record that ``key`` went down."""
        at = time.monotonic() if at is None else at
        with self._lock:
            previous = self._holds.get(key)
            if previous is not None and previous.up_at is None:
                return  # already down
            if previous is not None and at - previous.up_at <= self.rejoin_s:
                self._holds[key] = KeyHold(key, previous.down_at, None)
            else:
                self._holds[key] = KeyHold(key, at, None)

    def key_up(self, key: str, at: Optional[float] = None) -> None:
        """Record that ``key`` was released. Ignored if it was not down."""
        at = time.monotonic() if at is None else at
        with self._lock:
            previous = self._holds.get(key)
            if previous is not None and previous.up_at is None:
                self._holds[key] = KeyHold(key, previous.down_at, at)

    def release_all(self, at: Optional[float] = None) -> None:
        """Mark every held key released (e.g. when scanning stops)."""
        at = time.monotonic() if at is None else at
        with self._lock:
            for key, hold in self._holds.items():
                if hold.up_at is None:
                    self._holds[key] = KeyHold(key, hold.down_at, at)

    def snapshot(self) -> List[KeyHold]:
        """Each key's latest hold, oldest press first."""
        with self._lock:
            return sorted(self._holds.values(), key=lambda hold: hold.down_at)
