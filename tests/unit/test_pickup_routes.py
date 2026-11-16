"""Tests for the pure pickup-route matcher and route validation.

The gesture: hold a routed key while the phone is hung up, and lift the handset
with it still pressed. ``NOW`` is the moment the lift is noticed, ``GRACE`` the
configured ``pickup_route_release_grace_seconds``.

The first group pins behaviour any sensible policy must have. The "policy"
group pins the chosen policy: the key held last decides. Change those
expectations together with ``match_pickup_route`` if the policy changes.
"""

import pytest

from payphone.bios.pickup_routes import (
    DEFAULT_RELEASE_GRACE_SECONDS,
    match_pickup_route,
    normalize_routes,
)
from payphone.hardware.key_hold import KeyHold

NOW = 1000.0
GRACE = 0.75
ROUTES = {"9": "bm-network"}


def held(key, pressed_ago=1.0):
    """A key that went down ``pressed_ago`` seconds before the lift and is still down."""
    return KeyHold(key, NOW - pressed_ago, None)


def released(key, released_ago, pressed_ago=None):
    """A key released ``released_ago`` seconds before the lift."""
    pressed_ago = released_ago + 0.5 if pressed_ago is None else pressed_ago
    return KeyHold(key, NOW - pressed_ago, NOW - released_ago)


# ---------------------------------------------------------------------------
# Behaviour every policy must have
# ---------------------------------------------------------------------------

def test_no_keys_is_a_normal_pickup():
    assert match_pickup_route([], NOW, ROUTES, GRACE) is None


def test_no_routes_is_a_normal_pickup():
    assert match_pickup_route([held("9")], NOW, {}, GRACE) is None


def test_routed_key_still_held_at_lift_matches():
    assert match_pickup_route([held("9")], NOW, ROUTES, GRACE) == "bm-network"


def test_key_held_for_a_long_time_still_matches():
    assert match_pickup_route([held("9", pressed_ago=30.0)], NOW, ROUTES, GRACE) == "bm-network"


def test_key_released_within_grace_counts_as_held():
    """Let go of 9 as the handset came up; the hook debounce noticed 0.2 s later."""
    assert match_pickup_route([released("9", 0.2)], NOW, ROUTES, GRACE) == "bm-network"


def test_key_released_exactly_grace_ago_still_counts():
    assert match_pickup_route([released("9", GRACE)], NOW, ROUTES, GRACE) == "bm-network"


def test_key_tapped_and_released_before_the_lift_is_a_normal_pickup():
    """Pressing 9 and letting go, then lifting 2 s later, is not the gesture."""
    assert match_pickup_route([released("9", 2.0)], NOW, ROUTES, GRACE) is None


def test_zero_grace_requires_the_key_to_be_down():
    assert match_pickup_route([released("9", 0.1)], NOW, ROUTES, 0.0) is None
    assert match_pickup_route([held("9")], NOW, ROUTES, 0.0) == "bm-network"


def test_unrouted_key_held_is_a_normal_pickup():
    assert match_pickup_route([held("5")], NOW, ROUTES, GRACE) is None


def test_old_releases_of_other_keys_do_not_block_the_route():
    holds = [released("1", 60.0), released("2", 30.0), held("9")]
    assert match_pickup_route(holds, NOW, ROUTES, GRACE) == "bm-network"


def test_each_routed_key_goes_to_its_own_system():
    routes = {"9": "bm-network", "0": "operator-console"}
    assert match_pickup_route([held("0")], NOW, routes, GRACE) == "operator-console"
    assert match_pickup_route([held("9")], NOW, routes, GRACE) == "bm-network"


def test_holds_are_not_modified():
    holds = [released("1", 60.0), held("9")]
    before = list(holds)
    match_pickup_route(holds, NOW, ROUTES, GRACE)
    assert holds == before


# ---------------------------------------------------------------------------
# Policy: the key held last decides
# ---------------------------------------------------------------------------

def test_policy_still_held_key_beats_a_just_released_one():
    routes = {"9": "bm-network", "0": "operator-console"}
    holds = [released("0", 0.2), held("9", pressed_ago=0.1)]
    assert match_pickup_route(holds, NOW, routes, GRACE) == "bm-network"


def test_policy_latest_release_decides_when_nothing_is_still_down():
    routes = {"9": "bm-network", "0": "operator-console"}
    holds = [released("0", 0.4), released("9", 0.1)]
    assert match_pickup_route(holds, NOW, routes, GRACE) == "bm-network"


def test_policy_unrouted_key_held_last_means_normal_pickup():
    """9 was let go and 5 is the key under the finger at lift: not the gesture.

    A "any routed key within grace wins" policy would return bm-network here.
    """
    holds = [released("9", 0.3), held("5", pressed_ago=0.2)]
    assert match_pickup_route(holds, NOW, ROUTES, GRACE) is None


# ---------------------------------------------------------------------------
# normalize_routes
# ---------------------------------------------------------------------------

def test_default_grace_covers_hook_debounce_but_not_a_tap():
    assert 0.3 <= DEFAULT_RELEASE_GRACE_SECONDS <= 1.5


@pytest.mark.parametrize("raw", [None, [], "9", 9, {"": "bm-network"}, {"9": ""}, {"42": "two-keys"}])
def test_normalize_routes_rejects_unusable_values(raw):
    assert normalize_routes(raw) == {}


def test_normalize_routes_keeps_valid_entries_and_drops_bad_ones():
    raw = {"9": "bm-network", " * ": " operator ", "a": "bad-key", "1": 5, "99": "sequence"}
    assert normalize_routes(raw) == {"9": "bm-network", "*": "operator"}
