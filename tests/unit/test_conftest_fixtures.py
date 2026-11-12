"""Smoke tests: every shared fixture in tests/conftest.py constructs a real object off-Pi."""

from queue import Queue

from payphone.bios import BIOSBootloader
from tests.conftest import StubAudioHandler, StubHardwareHandler


def test_mock_gpio_hook_is_a_real_hook_switch(mock_gpio_hook, mock_hook_callback):
    assert mock_gpio_hook.hook_pins == [17]
    assert mock_gpio_hook.mode == "1pin"
    assert mock_gpio_hook.callback is mock_hook_callback


def test_mock_gpio_keypad_is_a_real_keypad(mock_gpio_keypad, mock_input_queue):
    assert mock_gpio_keypad.input_queue is mock_input_queue
    assert mock_gpio_keypad.row_pins == [5, 6, 13, 19]


def test_mock_audio_handler_uses_mocked_pygame(mock_audio_handler, mock_pygame):
    mock_pygame.mixer.init.assert_called_once()
    assert mock_audio_handler.audio_dir.endswith("audio_files")


def test_mock_payphone_system_is_a_hardware_free_bios(mock_payphone_system, fake_system_dir):
    assert isinstance(mock_payphone_system, BIOSBootloader)
    assert isinstance(mock_payphone_system.audio_handler, StubAudioHandler)
    assert isinstance(mock_payphone_system.hardware_handler, StubHardwareHandler)
    assert isinstance(mock_payphone_system.hardware_handler.input_queue, Queue)
    assert mock_payphone_system.bios_config.get_scan_paths() == [str(fake_system_dir)]
    assert "fake-line" in mock_payphone_system.system_manager.discover_systems()


def test_sample_phone_tree(sample_phone_tree):
    assert set(sample_phone_tree.options) == {"1", "2", "3"}
