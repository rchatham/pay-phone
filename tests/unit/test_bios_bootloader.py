"""Hardware-free tests for the BIOS bootloader launch path.

Reproduces the concern that ``BIOSBootloader.launch_system`` built the chosen
system with ``system_class(self.config)``, giving it fresh, never-started
handlers (an empty input queue) and ``phone_on_hook=True``, so its menu exited
immediately while keypresses kept flowing into the BIOS's own queue.

Fixtures come from tests/conftest.py: ``mock_payphone_system`` is a real
``BIOSBootloader`` with stub handlers whose scan path holds ``fake-line``.
"""

import json
from unittest.mock import Mock

import pytest

from payphone.bios import BIOSBootloader
from payphone.core.phone_tree import PhoneTree
from payphone.core.system import PhoneSystemBase


@pytest.fixture
def no_sleep(monkeypatch):
    """PhoneTree pauses between menus; skip the waits."""
    monkeypatch.setattr("payphone.core.phone_tree.time.sleep", lambda seconds: None)


def pick_up(bios: BIOSBootloader) -> None:
    """Simulate the handset being lifted without starting the call thread."""
    bios.hook_status_changed(off_hook=True)
    assert bios.phone_on_hook is False
    assert bios.in_bios_menu is True
    # Pickup starts the BIOS menu call; later assertions care about the launch call.
    bios.start_call.assert_called_once()
    bios.start_call.reset_mock()


# ---------------------------------------------------------------------------
# BIOS menu construction
# ---------------------------------------------------------------------------

def test_setup_phone_tree_lists_discovered_systems(mock_payphone_system):
    menu = mock_payphone_system.setup_phone_tree()

    assert isinstance(menu, PhoneTree)
    assert list(menu.options) == ["1"]
    assert menu.options["1"].audio_file == "bios/system_fake-line.mp3"
    available = mock_payphone_system.bios_config.get("available_systems")
    assert [system["id"] for system in available] == ["fake-line"]


# ---------------------------------------------------------------------------
# launch_system: handler sharing
# ---------------------------------------------------------------------------

def test_launch_system_shares_bios_handlers_and_hook_state(mock_payphone_system):
    bios = mock_payphone_system
    pick_up(bios)

    assert bios.launch_system("fake-line") is True

    launched = bios.current_system
    assert launched is not None
    assert bios.current_system_id == "fake-line"
    assert bios.in_bios_menu is False
    assert bios.bios_config.get_last_system() == "fake-line"

    # The launched system must listen to the keypad the BIOS already owns...
    assert launched.hardware_handler is bios.hardware_handler
    assert launched.hardware_handler.input_queue is bios.hardware_handler.input_queue
    assert launched.audio_handler is bios.audio_handler
    # ...and know the handset is already lifted, or navigate() exits at once.
    assert launched.phone_on_hook is False
    assert launched.running is True

    bios.start_long_press_monitor.assert_called_once()
    bios.start_call.assert_called_once()


def test_launched_system_receives_keypresses_from_bios_queue(mock_payphone_system, no_sleep):
    bios = mock_payphone_system
    pick_up(bios)
    bios.launch_system("fake-line")
    launched = bios.current_system

    # Caller presses 1 on the physical keypad: it lands in the BIOS's queue.
    bios.hardware_handler.press("1")

    # The BIOS call thread delegates to the launched system.
    bios._call_handler()

    assert launched.seen == [("1", "off-hook")]
    assert bios.hardware_handler.input_queue.empty()


def test_launch_system_injects_handlers_when_constructor_accepts_them(mock_payphone_system):
    bios = mock_payphone_system
    pick_up(bios)
    bios.system_manager.discover_systems()
    system_class = bios.system_manager.load_system("fake-line")
    constructed = []
    original_init = system_class.__init__

    def spy_init(self, *args, **kwargs):
        constructed.append(kwargs)
        original_init(self, *args, **kwargs)

    system_class.__init__ = spy_init
    try:
        assert bios.launch_system("fake-line") is True
    finally:
        system_class.__init__ = original_init

    assert constructed == [{"hardware_handler": bios.hardware_handler, "audio_handler": bios.audio_handler}]


def test_launch_system_falls_back_to_attribute_assignment(mock_payphone_system, fake_system_dir):
    """Systems with a config-only constructor still end up on the BIOS handlers."""
    legacy_dir = fake_system_dir / "legacy-line"
    legacy_dir.mkdir()
    (legacy_dir / "system.py").write_text(
        "from payphone.core.phone_tree import PhoneTree\n"
        "from payphone.core.system import PhoneSystemBase\n"
        "class LegacyLine(PhoneSystemBase):\n"
        "    def __init__(self, config=None):\n"
        "        super().__init__(config)\n"
        "        self.constructed_with_own_handlers = self.hardware_handler\n"
        "    def setup_phone_tree(self):\n"
        "        return PhoneTree('legacy/menu.mp3', audio_handler=self.audio_handler)\n"
    )
    bios = mock_payphone_system
    bios.system_manager.discover_systems()
    pick_up(bios)

    assert bios.launch_system("legacy-line") is True

    launched = bios.current_system
    assert launched.constructed_with_own_handlers is not bios.hardware_handler
    assert launched.hardware_handler is bios.hardware_handler
    assert launched.audio_handler is bios.audio_handler
    assert launched.phone_on_hook is False


# ---------------------------------------------------------------------------
# BIOS menu -> launch handoff and hang-up
# ---------------------------------------------------------------------------

def test_bios_menu_selection_launches_system_and_stops_bios_navigation(mock_payphone_system, no_sleep):
    bios = mock_payphone_system
    pick_up(bios)
    bios.hardware_handler.press("1")

    # The BIOS call thread: navigate the BIOS menu; option 1 launches fake-line.
    bios._call_handler()

    assert bios.current_system_id == "fake-line"
    assert bios.in_bios_menu is False
    bios.start_call.assert_called_once()
    # The BIOS menu must not keep consuming keypresses meant for the launched system.
    bios.hardware_handler.press("1")
    assert bios.hardware_handler.input_queue.qsize() == 1


def test_hang_up_puts_launched_system_on_hook(mock_payphone_system):
    bios = mock_payphone_system
    pick_up(bios)
    bios.launch_system("fake-line")
    launched = bios.current_system
    bios.current_call = None

    bios.hook_status_changed(off_hook=False)

    assert bios.phone_on_hook is True
    assert bios.current_system is None
    assert launched.running is False
    assert launched.phone_on_hook is True, "the delegated navigate() polls phone_on_hook, not running"


def test_pickup_enters_bios_menu_by_default(mock_payphone_system):
    bios = mock_payphone_system

    bios.hook_status_changed(off_hook=True)

    assert bios.in_bios_menu is True
    bios.start_call.assert_called_once()


# ---------------------------------------------------------------------------
# PAYPHONE_LEGACY_MODE keeps constructing systems without the BIOS
# ---------------------------------------------------------------------------

def test_legacy_mode_constructs_system_without_bios(tmp_path, monkeypatch, hardware_free_phone_systems, fake_system_dir):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".bios_config.json").write_text(json.dumps({"scan_paths": [str(fake_system_dir)]}))
    from payphone import main as payphone_main

    system = payphone_main._load_legacy_system("fake-line")()

    assert isinstance(system, PhoneSystemBase)
    assert not isinstance(system, BIOSBootloader)
    assert system.phone_on_hook is True
    assert system.hardware_handler.input_queue.empty()
