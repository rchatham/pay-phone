"""BIOSBootloader pickup routing, legacy auto-launch and hang-up key handling.

The gesture under test: hold a routed key while the phone is hung up and lift
the handset with it still pressed.

Uses the ``mock_payphone_system`` fixture from tests/conftest.py: a real
``BIOSBootloader`` with stub handlers, ``start_call`` and
``start_long_press_monitor`` replaced by Mocks, and one discoverable system,
``fake-line``. ``hardware_handler.hold(key)`` queues the key's press and opens
a hold; ``release(key)`` ends it. ``bios._clock`` is a controllable clock that
also stamps the holds.
"""

import json
import time
from queue import Queue
from unittest.mock import Mock

import pytest

from payphone.bios import BIOSBootloader
from payphone.bios import bootloader as bootloader_module


class FakeClock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def bios(mock_payphone_system):
    mock_payphone_system._clock = FakeClock()
    return mock_payphone_system


def set_bios(bios, **values):
    for key, value in values.items():
        bios.bios_config.set(key, value)


def hold(bios, key):
    bios.hardware_handler.hold(key, at=bios._clock.now)


def release(bios, key):
    bios.hardware_handler.release(key, at=bios._clock.now)


def lift(bios):
    bios.hook_status_changed(off_hook=True)


def write_theme(tmp_path, theme: dict):
    pack = tmp_path / "theme-pack"
    (pack / "theme").mkdir(parents=True)
    (pack / "theme" / "theme.json").write_text(json.dumps(theme))
    return str(pack)


def assert_bios_menu(bios):
    assert bios.in_bios_menu is True
    assert bios.current_system is None
    bios.start_call.assert_called_once()


# ---------------------------------------------------------------------------
# Routing on lift
# ---------------------------------------------------------------------------

def test_routed_key_held_while_lifting_launches_its_system(bios):
    set_bios(bios, pickup_routes={"9": "fake-line"})
    hold(bios, "9")
    bios._clock.now += 1.5  # still holding 9 as the handset comes up

    lift(bios)

    assert bios.current_system_id == "fake-line"
    assert bios.in_bios_menu is False
    assert bios.current_system.phone_on_hook is False
    bios.start_call.assert_called_once()
    assert bios.hardware_handler.input_queue.empty(), "the held key's press must not reach the system"


def test_key_released_just_before_the_lift_is_noticed_still_routes(bios):
    """The hook switch debounce reports the lift a moment after it happens."""
    set_bios(bios, pickup_routes={"9": "fake-line"})
    hold(bios, "9")
    bios._clock.now += 1.0
    release(bios, "9")
    bios._clock.now += 0.2

    lift(bios)

    assert bios.current_system_id == "fake-line"


def test_key_tapped_and_released_before_lifting_is_a_normal_pickup(bios):
    set_bios(bios, pickup_routes={"9": "fake-line"})
    hold(bios, "9")
    bios._clock.now += 0.2
    release(bios, "9")
    bios._clock.now += 3.0

    lift(bios)

    assert_bios_menu(bios)
    assert bios.hardware_handler.input_queue.empty(), "the tapped 9 must not select menu option 9"


def test_pickup_route_launch_does_not_replace_last_system(bios):
    """An art phone with auto-launch keeps its art piece for the next caller."""
    set_bios(bios, pickup_routes={"9": "fake-line"}, last_system="art-piece")
    hold(bios, "9")

    lift(bios)

    assert bios.current_system_id == "fake-line"
    assert bios.bios_config.get_last_system() == "art-piece"


def test_routes_come_from_the_theme_when_bios_config_has_none(bios, tmp_path):
    set_bios(bios, theme_path=write_theme(tmp_path, {"pickup_routes": {"9": "fake-line"}}))
    hold(bios, "9")

    lift(bios)

    assert bios.current_system_id == "fake-line"


def test_bios_config_routes_override_the_theme(bios, tmp_path):
    set_bios(bios, theme_path=write_theme(tmp_path, {"pickup_routes": {"9": "fake-line"}}), pickup_routes={})
    hold(bios, "9")

    lift(bios)

    assert_bios_menu(bios)


def test_release_grace_from_bios_config_is_used(bios):
    set_bios(bios, pickup_routes={"9": "fake-line"}, pickup_route_release_grace_seconds=0.1)
    hold(bios, "9")
    release(bios, "9")
    bios._clock.now += 0.3

    lift(bios)

    assert_bios_menu(bios)


def test_release_grace_from_the_theme_is_used(bios, tmp_path):
    theme = {"pickup_routes": {"9": "fake-line"}, "pickup_route_release_grace_seconds": 5}
    set_bios(bios, theme_path=write_theme(tmp_path, theme))
    hold(bios, "9")
    release(bios, "9")
    bios._clock.now += 3.0

    lift(bios)

    assert bios.current_system_id == "fake-line"


def test_route_to_a_missing_system_falls_back_to_normal_pickup(bios):
    set_bios(bios, pickup_routes={"9": "no-such-system"})
    hold(bios, "9")

    lift(bios)

    assert_bios_menu(bios)


def test_matcher_error_falls_back_to_normal_pickup(bios, monkeypatch):
    def broken(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(bootloader_module, "match_pickup_route", broken)
    set_bios(bios, pickup_routes={"9": "fake-line"})
    hold(bios, "9")

    lift(bios)

    assert_bios_menu(bios)
    assert bios.hardware_handler.input_queue.empty()


def test_keys_pressed_on_hook_do_not_leak_into_the_bios_menu(bios):
    """Before pickup routes, a 1 pressed while hung up selected menu option 1."""
    bios.hardware_handler.press("1", "2")

    lift(bios)

    assert_bios_menu(bios)
    assert bios.hardware_handler.input_queue.empty()


def test_handler_that_cannot_report_holds_gets_a_normal_pickup(bios, caplog):
    """E.g. Arduino firmware without KEYUP, or a custom handler."""
    bios.hardware_handler.key_holds = lambda: None
    set_bios(bios, pickup_routes={"9": "fake-line"})
    bios.hardware_handler.press("9")

    with caplog.at_level("WARNING"):
        lift(bios)

    assert_bios_menu(bios)
    assert "cannot report held keys" in caplog.text
    assert bios.hardware_handler.input_queue.empty()


def test_bare_mock_handler_is_treated_as_unable_to_report_holds(bios):
    bios.hardware_handler = Mock(input_queue=Queue())
    set_bios(bios, pickup_routes={"9": "fake-line"})

    lift(bios)

    assert_bios_menu(bios)


# ---------------------------------------------------------------------------
# Legacy auto-launch
# ---------------------------------------------------------------------------

def test_auto_launch_without_hold_window_goes_straight_to_last_system(bios, monkeypatch):
    sleeps = []
    monkeypatch.setattr(bootloader_module.time, "sleep", sleeps.append)
    set_bios(bios, auto_launch=True, always_show_menu_on_pickup=False,
             bios_enter_hold_seconds=0.0, last_system="fake-line")
    bios.hook_hold_threshold = 0.0

    lift(bios)

    assert bios.current_system_id == "fake-line"
    assert bios.in_bios_menu is False
    assert sleeps == [], "no hold wait when bios_enter_hold_seconds is 0"


def test_pickup_route_beats_auto_launch(bios):
    set_bios(bios, auto_launch=True, always_show_menu_on_pickup=False,
             last_system="art-piece", pickup_routes={"9": "fake-line"})
    bios.hook_hold_threshold = 0.0
    hold(bios, "9")

    lift(bios)

    assert bios.current_system_id == "fake-line"


def test_auto_launch_with_hold_window_still_enters_bios_when_held(bios):
    """Unchanged legacy behaviour: still lifted after the hold window -> BIOS."""
    set_bios(bios, auto_launch=True, always_show_menu_on_pickup=False, last_system="fake-line")
    bios.hook_hold_threshold = 0.05

    lift(bios)

    assert_bios_menu(bios)


# ---------------------------------------------------------------------------
# Hang-up: the long-press monitor must stop reading keys
# ---------------------------------------------------------------------------

def test_hang_up_stops_the_long_press_monitor(mock_payphone_system):
    bios = mock_payphone_system
    bios.hook_status_changed(off_hook=True)
    bios.launch_system("fake-line")
    BIOSBootloader.start_long_press_monitor(bios)  # the real thread
    monitor = bios.long_press_monitor_thread
    assert monitor.is_alive()
    bios.current_call = None

    bios.hook_status_changed(off_hook=False)

    assert not monitor.is_alive()
    bios.hardware_handler.press("9")
    time.sleep(0.3)
    assert bios.hardware_handler.input_queue.qsize() == 1, "nothing may read keys while on hook"


def test_hang_up_during_star_hold_does_not_reopen_the_bios(mock_payphone_system):
    bios = mock_payphone_system
    bios.hook_status_changed(off_hook=True)
    bios.launch_system("fake-line")
    bios.start_call.reset_mock()
    bios.long_press_threshold = 2.0
    BIOSBootloader.start_long_press_monitor(bios)
    monitor = bios.long_press_monitor_thread
    bios.hardware_handler.press("*")
    deadline = time.monotonic() + 2.0
    while bios.star_key_press_start is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert bios.star_key_press_start is not None, "monitor should be timing the * hold"
    bios.current_call = None

    started = time.monotonic()
    bios.hook_status_changed(off_hook=False)

    assert not monitor.is_alive()
    assert time.monotonic() - started < 1.0
    time.sleep(0.2)
    bios.start_call.assert_not_called()
    assert bios.in_bios_menu is False


def test_keys_left_from_a_call_are_dropped_at_the_next_lift(bios):
    lift(bios)
    bios.hardware_handler.press("7")  # pressed during the call, never consumed
    bios.current_call = None
    bios.hook_status_changed(off_hook=False)
    bios.start_call.reset_mock()

    lift(bios)

    assert_bios_menu(bios)
    assert bios.hardware_handler.input_queue.empty()


# ---------------------------------------------------------------------------
# Settings resolution
# ---------------------------------------------------------------------------

def test_route_settings_default_to_no_routes_and_default_grace(bios):
    routes, grace = bios._pickup_route_settings()
    assert routes == {}
    assert grace == bootloader_module.DEFAULT_RELEASE_GRACE_SECONDS


@pytest.mark.parametrize("bad_grace", ["soon", -1])
def test_unusable_grace_falls_back_to_default(bios, bad_grace):
    set_bios(bios, pickup_route_release_grace_seconds=bad_grace)
    assert bios._pickup_route_settings()[1] == bootloader_module.DEFAULT_RELEASE_GRACE_SECONDS


def test_zero_grace_is_allowed(bios):
    set_bios(bios, pickup_route_release_grace_seconds=0)
    assert bios._pickup_route_settings()[1] == 0.0


def test_invalid_route_entries_are_dropped(bios):
    set_bios(bios, pickup_routes={"9": "fake-line", "x": "bad", "1": "", "42": "sequence"})
    assert bios._pickup_route_settings()[0] == {"9": "fake-line"}
