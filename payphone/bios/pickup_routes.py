"""
Pickup routes: hold a key while lifting the handset to choose what starts.

An installation maps keypad keys to phone system ids, for example
``{"9": "bm-network"}``. Hold 9 while the phone is hung up, lift the handset
with 9 still pressed, and ``bm-network`` launches directly. Lifting without a
routed key held gives the normal pickup (BIOS menu or auto-launch).

The keypad layer records when each key went down and when it was released
(:class:`payphone.hardware.key_hold.KeyHold`). On lift the BIOS passes those
records to :func:`match_pickup_route`.

This module is pure (no threads, no clocks, no hardware) so the matching rules
can be unit-tested with hand-built timestamps.
"""

from typing import Any, Dict, Mapping, Optional, Sequence

from ..hardware.key_hold import KeyHold

#: Keys a keypad can produce. A route is one of these.
KEYPAD_KEYS = frozenset("0123456789*#")

#: How long before the lift is noticed a key may have been released and still
#: count as "held while lifting", when nothing configures it. The hook switch
#: is debounced, so the lift is noticed 0.1-0.2 s after it physically happens.
DEFAULT_RELEASE_GRACE_SECONDS = 0.75


def match_pickup_route(
    holds: Sequence[KeyHold],
    now: float,
    routes: Mapping[str, str],
    grace_s: float,
) -> Optional[str]:
    """Pick the system to launch from the keys held when the handset was lifted.

    Args:
        holds: Each key's most recent press, oldest press first. A hold has
            ``key``, ``down_at`` and ``up_at`` (None while the key is still
            down). Includes keys released long ago.
        now: When the lift was noticed, on the same clock as the holds.
        routes: Key -> system id, e.g. ``{"9": "bm-network"}``. Already
            validated by :func:`normalize_routes` (single keypad keys).
        grace_s: A key released at most this many seconds before ``now`` still
            counts as held while lifting. 0 means it must still be down.

    Returns:
        The system id to launch, or None for a normal pickup.

    Policy (pinned by tests/unit/test_pickup_routes.py):
        - A hold counts if the key is still down, or was released within
          ``grace_s`` of the lift.
        - One key decides: the key held last. A key still down beats a
          released one; among released keys the latest release wins.
        - If the deciding key has no route, it is a normal pickup. A routed
          key released just before it does not count: the caller's finger had
          moved on.
        - Key mashing needs no special case: only the last key matters.
    """
    counted = [hold for hold in holds if hold.up_at is None or now - hold.up_at <= grace_s]
    if not counted:
        return None
    deciding = max(counted, key=lambda hold: (hold.up_at is None, hold.up_at or 0.0, hold.down_at))
    return routes.get(deciding.key)


def normalize_routes(raw: Any) -> Dict[str, str]:
    """Validate a ``pickup_routes`` value from .bios_config.json or theme.json.

    Invalid entries are dropped rather than raising, so a typo in a config file
    cannot stop the phone from booting.

    Args:
        raw: The decoded JSON value; expected to be an object of
            ``{"<key>": "<system id>"}``.

    Returns:
        Only the entries whose key is a single keypad key and whose value is a
        non-empty string. A route is a key you hold, so sequences like "42"
        are not routes.
    """
    if not isinstance(raw, Mapping):
        return {}
    routes: Dict[str, str] = {}
    for key, system_id in raw.items():
        if not isinstance(key, str) or not isinstance(system_id, str):
            continue
        key = key.strip()
        system_id = system_id.strip()
        if key in KEYPAD_KEYS and system_id:
            routes[key] = system_id
    return routes
