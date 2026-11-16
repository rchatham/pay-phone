"""Held-key tracking: the pure tracker, the GPIO scan loop and the serial protocol."""

import time

import pytest

from payphone.hardware.key_hold import KeyHold, KeyHoldTracker


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


# ---------------------------------------------------------------------------
# KeyHoldTracker
# ---------------------------------------------------------------------------

def test_key_down_then_up_records_one_hold():
    tracker = KeyHoldTracker()
    tracker.key_down("9", at=10.0)
    assert tracker.snapshot() == [KeyHold("9", 10.0, None)]
    assert tracker.snapshot()[0].is_down

    tracker.key_up("9", at=12.5)

    assert tracker.snapshot() == [KeyHold("9", 10.0, 12.5)]
    assert not tracker.snapshot()[0].is_down


def test_snapshot_keeps_each_keys_latest_hold_oldest_first():
    tracker = KeyHoldTracker()
    tracker.key_down("1", at=1.0)
    tracker.key_up("1", at=1.2)
    tracker.key_down("9", at=5.0)
    tracker.key_down("1", at=8.0)  # pressed again much later: a new hold

    assert tracker.snapshot() == [KeyHold("9", 5.0, None), KeyHold("1", 8.0, None)]


def test_contact_bounce_continues_the_same_hold():
    tracker = KeyHoldTracker(rejoin_s=0.05)
    tracker.key_down("9", at=10.0)
    tracker.key_up("9", at=10.50)
    tracker.key_down("9", at=10.52)  # bounced: still the same press

    assert tracker.snapshot() == [KeyHold("9", 10.0, None)]


def test_repeated_down_and_stray_up_are_ignored():
    tracker = KeyHoldTracker()
    tracker.key_up("5", at=1.0)  # never went down
    tracker.key_down("9", at=2.0)
    tracker.key_down("9", at=3.0)  # already down

    assert tracker.snapshot() == [KeyHold("9", 2.0, None)]


def test_release_all_ends_open_holds_only():
    tracker = KeyHoldTracker()
    tracker.key_down("1", at=1.0)
    tracker.key_up("1", at=2.0)
    tracker.key_down("9", at=3.0)

    tracker.release_all(at=4.0)

    assert tracker.snapshot() == [KeyHold("1", 1.0, 2.0), KeyHold("9", 3.0, 4.0)]


def test_timestamps_default_to_the_monotonic_clock():
    tracker = KeyHoldTracker()
    before = time.monotonic()
    tracker.key_down("9")
    tracker.key_up("9")
    hold, = tracker.snapshot()
    assert before <= hold.down_at <= hold.up_at <= time.monotonic()


# ---------------------------------------------------------------------------
# GPIO keypad scan loop
# ---------------------------------------------------------------------------

def test_gpio_scan_loop_tracks_hold_and_release(mock_gpio_keypad, mock_input_queue):
    keypad = mock_gpio_keypad
    state = {"key": None}
    keypad.scan_keypad = lambda: state["key"]
    keypad.start()
    try:
        state["key"] = "9"
        assert wait_for(lambda: any(h.key == "9" and h.is_down for h in keypad.hold_tracker.snapshot()))
        assert mock_input_queue.get(timeout=1.0) == "9", "the press is still queued as before"

        time.sleep(0.1)  # held: no repeat events
        assert mock_input_queue.empty()

        state["key"] = None
        assert wait_for(lambda: all(not h.is_down for h in keypad.hold_tracker.snapshot()))
        hold, = keypad.hold_tracker.snapshot()
        assert hold.key == "9" and hold.up_at > hold.down_at
    finally:
        keypad.stop()


def test_gpio_hold_is_tracked_even_when_the_press_is_debounced(mock_gpio_keypad, mock_input_queue):
    """A second key inside the 0.3 s press debounce is not queued, but its hold is real."""
    keypad = mock_gpio_keypad
    state = {"key": None}
    keypad.scan_keypad = lambda: state["key"]
    keypad.start()
    try:
        state["key"] = "1"
        assert mock_input_queue.get(timeout=1.0) == "1"
        state["key"] = "9"  # rolled straight onto 9

        assert wait_for(lambda: any(h.key == "9" and h.is_down for h in keypad.hold_tracker.snapshot()))
        assert any(h.key == "1" and not h.is_down for h in keypad.hold_tracker.snapshot())
    finally:
        keypad.stop()


def test_gpio_stop_releases_held_keys(mock_gpio_keypad):
    keypad = mock_gpio_keypad
    keypad.hold_tracker.key_down("9")

    keypad.stop()

    assert not keypad.hold_tracker.snapshot()[0].is_down


def test_gpio_handler_exposes_key_holds(mock_gpio_keypad):
    from payphone.hardware.gpio_handler import GPIOHandler

    # __new__ skips __init__, which refuses to run without real RPi.GPIO.
    handler = GPIOHandler.__new__(GPIOHandler)
    handler.keypad = mock_gpio_keypad
    mock_gpio_keypad.hold_tracker.key_down("9", at=1.0)

    assert handler.key_holds() == [KeyHold("9", 1.0, None)]


# ---------------------------------------------------------------------------
# Serial (Arduino) protocol
# ---------------------------------------------------------------------------

@pytest.fixture
def serial_handler(monkeypatch):
    """A SerialHandler that never opens a port; lines are fed to _process_data."""
    from payphone.hardware import serial_handler as serial_module

    # The constructor only needs pyserial to exist; nothing here connects.
    monkeypatch.setattr(serial_module, "_SERIAL_AVAILABLE", True)
    return serial_module.SerialHandler(port="/dev/null")


def test_old_firmware_cannot_report_holds(serial_handler):
    serial_handler._process_data("READY")
    serial_handler._process_data("KEY:9")

    assert serial_handler.input_queue.get_nowait() == "9"
    assert serial_handler.key_holds() is None, "without KEYUP a key would look held forever"


def test_features_line_enables_hold_reporting(serial_handler):
    serial_handler._process_data("READY")
    serial_handler._process_data("FEATURES:KEYUP")
    serial_handler._process_data("KEY:9")

    hold, = serial_handler.key_holds()
    assert hold.key == "9" and hold.is_down

    serial_handler._process_data("KEYUP:9")

    hold, = serial_handler.key_holds()
    assert not hold.is_down
    assert serial_handler.input_queue.qsize() == 1, "KEYUP must not queue a keypress"


def test_first_keyup_enables_hold_reporting_if_features_line_was_missed(serial_handler):
    serial_handler._process_data("KEY:5")
    assert serial_handler.key_holds() is None

    serial_handler._process_data("KEYUP:5")

    hold, = serial_handler.key_holds()
    assert hold.key == "5" and not hold.is_down
