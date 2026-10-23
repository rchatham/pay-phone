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
