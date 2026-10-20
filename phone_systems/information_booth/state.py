"""Process-local Booth data, independent of per-call hardware/audio/capabilities."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from payphone.config.persistence import state_directory

from .content import ContentStore
from .services import WeatherService


@dataclass(frozen=True)
class BoothState:
    store: ContentStore
    weather: WeatherService


# SystemManager re-executes system.py on discovery. Keep this registry in an
# ordinary imported module so fresh classes/pickups still see the last valid data.
# Never retain a system, runtime, session, handler or authorization callback here.
_STATES: dict[Path, BoothState] = {}
_STATE_LOCK = threading.Lock()


def state_for_directory(directory: Path | None = None) -> BoothState:
    """Retain content/weather for each resolved deployment directory until exit."""
    root = (Path(directory) if directory is not None else state_directory()).resolve()
    with _STATE_LOCK:
        if root not in _STATES:
            _STATES[root] = BoothState(ContentStore(root), WeatherService())
        return _STATES[root]
