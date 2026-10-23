"""
Pytest configuration and shared fixtures for payphone tests

This file provides hardware-free fixtures so the suite runs on any machine:

- Stub handlers (``StubAudioHandler``, ``StubHardwareHandler``) that record what
  a phone system does instead of touching pygame, GPIO or a serial port.
- ``hardware_free_phone_systems`` makes every ``PhoneSystemBase`` subclass build
  those stubs, so real systems (including the BIOS bootloader) can be
  constructed and driven in tests.
- ``mock_gpio`` / ``mock_pygame`` fake the RPi.GPIO and pygame modules for the
  low-level hardware classes.
"""

import sys
import types
from pathlib import Path
from queue import Queue
from unittest.mock import Mock, patch

import pytest


# ============================================================================
# Hardware Availability Checks
# ============================================================================

def is_raspberry_pi():
    """Check if running on a Raspberry Pi"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            return 'Raspberry Pi' in f.read()
    except FileNotFoundError:
        return False


def has_gpio():
    """Check if RPi.GPIO is available"""
    try:
        import RPi.GPIO
        return True
    except (ImportError, RuntimeError):
        return False


def has_pygame():
    """Check if pygame is available"""
    try:
        import pygame
        return True
    except ImportError:
        return False


# ============================================================================
# Skip Markers
# ============================================================================

requires_gpio = pytest.mark.skipif(
    not has_gpio(),
    reason="Requires RPi.GPIO library and Raspberry Pi hardware"
)

requires_pygame = pytest.mark.skipif(
    not has_pygame(),
    reason="Requires pygame library"
)

requires_pi = pytest.mark.skipif(
    not is_raspberry_pi(),
    reason="Requires Raspberry Pi hardware"
)


# ============================================================================
# Stub Handlers (what a phone system talks to instead of real hardware)
# ============================================================================

class StubAudioHandler:
    """Records playback requests; never plays anything."""

    def __init__(self):
        self.played_files = []
        self.played_tones = []
        self.stopped = False

    def play_file(self, filename, blocking=True):
        self.played_files.append((filename, blocking))
        return True

    def play_dtmf_tone(self, key):
        self.played_tones.append(key)
        return True

    def is_playing(self):
        return False

    def stop(self):
        self.stopped = True


class StubHardwareHandler:
    """Keypad/hook handler with a real input queue and no hardware."""

    def __init__(self):
        self.input_queue = Queue()
        self.hook_callback = None
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True
        return True

    def stop(self):
        self.stopped = True

    def set_hook_callback(self, callback):
        self.hook_callback = callback

    def press(self, *keys):
        """Simulate keypad presses."""
        for key in keys:
            self.input_queue.put(key)


# ============================================================================
# Mock Hardware Modules
# ============================================================================

@pytest.fixture
def mock_gpio(monkeypatch):
    """Fake RPi.GPIO module so the GPIO classes import and run off-Pi."""
    gpio = Mock(name="RPi.GPIO")
    gpio.BCM = 11
    gpio.IN = 1
    gpio.OUT = 0
    gpio.PUD_UP = 22
    gpio.PUD_DOWN = 21
    gpio.RISING = 31
    gpio.FALLING = 32
    gpio.BOTH = 33
    gpio.HIGH = 1
    gpio.LOW = 0
    gpio.input = Mock(return_value=1)

    rpi = types.ModuleType("RPi")
    rpi.GPIO = gpio
    monkeypatch.setitem(sys.modules, "RPi", rpi)
    monkeypatch.setitem(sys.modules, "RPi.GPIO", gpio)

    # Modules that already bound `GPIO` at import time get the fake too.
    for module_name in ("payphone.hardware.gpio_keypad", "payphone.hardware.gpio_hook"):
        module = sys.modules.get(module_name)
        if module is not None:
            monkeypatch.setattr(module, "GPIO", gpio)

    yield gpio


@pytest.fixture
def mock_pygame():
    """Mock pygame inside payphone.audio.handler so AudioHandler needs no audio device."""
    with patch('payphone.audio.handler.pygame') as mock_pg:
        mock_pg.error = Exception
        mock_pg.mixer.music.get_busy = Mock(return_value=False)
        mock_sound = Mock()
        mock_pg.mixer.Sound = Mock(return_value=mock_sound)
        yield mock_pg


@pytest.fixture
def mock_serial():
    """Mock serial.Serial for testing without Arduino"""
    with patch('serial.Serial') as mock:
        serial_instance = Mock()
        serial_instance.is_open = True
        serial_instance.readline = Mock(return_value=b'READY\n')
        serial_instance.write = Mock()
        serial_instance.close = Mock()
        serial_instance.in_waiting = 0
        mock.return_value = serial_instance
        yield serial_instance


@pytest.fixture
def mock_input_queue():
    """Input queue for keypad events"""
    return Queue()


@pytest.fixture
def mock_hook_callback():
    """Mock callback function for hook state changes"""
    return Mock()


# ============================================================================
# Hardware Handler Fixtures
# ============================================================================

@pytest.fixture
def mock_gpio_keypad(mock_gpio, mock_input_queue):
    """Real GPIOKeypad bound to the fake GPIO module (scanning thread not started)."""
    from payphone.hardware.gpio_keypad import GPIOKeypad
    keypad = GPIOKeypad(
        row_pins=[5, 6, 13, 19],
        col_pins=[26, 20, 21],
        input_queue=mock_input_queue,
    )
    yield keypad
    keypad.running = False


@pytest.fixture
def mock_gpio_hook(mock_gpio, mock_hook_callback):
    """Real GPIOHookSwitch bound to the fake GPIO module."""
    from payphone.hardware.gpio_hook import GPIOHookSwitch
    hook = GPIOHookSwitch(hook_pin=17, callback=mock_hook_callback)
    yield hook
    hook.running = False


@pytest.fixture
def mock_audio_handler(mock_pygame, tmp_path):
    """Real AudioHandler over mocked pygame with a temporary audio directory."""
    audio_dir = tmp_path / "audio_files"
    for sub in ("menu", "prompts", "music"):
        (audio_dir / sub).mkdir(parents=True)

    from payphone.audio.handler import AudioHandler
    return AudioHandler(audio_dir=str(audio_dir))


# ============================================================================
# Phone System Fixtures
# ============================================================================

@pytest.fixture
def hardware_free_phone_systems(monkeypatch):
    """Make PhoneSystemBase build stub handlers instead of pygame/GPIO/serial.

    Patches the factories ``PhoneSystemBase.__init__`` calls, so the real
    constructor (including handler injection) still runs.
    """
    import payphone.core.system as system_module

    monkeypatch.setattr(system_module.Config, "USE_GPIO", False)
    monkeypatch.setattr(system_module, "AudioHandler", lambda audio_dir: StubAudioHandler())
    monkeypatch.setattr(system_module, "SerialHandler", lambda port, baudrate: StubHardwareHandler())
    monkeypatch.setattr(system_module, "GPIOHandler", lambda **kwargs: StubHardwareHandler())
    monkeypatch.setattr(system_module.PhoneSystemBase, "_init_tts", lambda self: None)
    return system_module


FAKE_SYSTEM_SOURCE = '''
from payphone.core.phone_tree import PhoneTree
from payphone.core.system import PhoneSystemBase


class FakeLineSystem(PhoneSystemBase):
    """Tiny system used to exercise the BIOS launch path."""

    @staticmethod
    def get_metadata():
        return {"name": "Fake Line", "description": "test system", "version": "0.1"}

    def setup_phone_tree(self) -> PhoneTree:
        self.seen = []
        one = PhoneTree("fake/one.mp3", audio_handler=self.audio_handler, action=self._on_one)
        return PhoneTree(
            "fake/menu.mp3",
            audio_handler=self.audio_handler,
            options={"1": one},
            timeout=2,
        )

    def _on_one(self):
        self.seen.append(("1", "off-hook" if not self.phone_on_hook else "on-hook"))
        # Hang up so navigation ends.
        self.phone_on_hook = True
        return True
'''


@pytest.fixture
def fake_system_dir(tmp_path):
    """A scan path containing one discoverable system, ``fake-line``."""
    systems_dir = tmp_path / "systems"
    (systems_dir / "fake-line").mkdir(parents=True)
    (systems_dir / "fake-line" / "system.py").write_text(FAKE_SYSTEM_SOURCE)
    return systems_dir


@pytest.fixture
def mock_payphone_system(tmp_path, monkeypatch, hardware_free_phone_systems, fake_system_dir):
    """The real entry-point system (BIOSBootloader) with stub handlers.

    Runs in ``tmp_path`` so ``.bios_config.json`` is written there, with the
    scan path pointing at ``fake_system_dir``. Calls that would spawn threads
    (``start_call``, ``start_long_press_monitor``) are replaced with Mocks; drive
    ``_call_handler()`` directly instead.
    """
    import json

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".bios_config.json").write_text(json.dumps({"scan_paths": [str(fake_system_dir)]}))

    from payphone.bios import BIOSBootloader
    from payphone.config.settings import Config

    system = BIOSBootloader(Config())
    system.start_call = Mock(name="start_call")
    system.start_long_press_monitor = Mock(name="start_long_press_monitor")
    return system


@pytest.fixture
def mock_phone_action():
    """Mock phone action callback"""
    return Mock(return_value=None)


@pytest.fixture
def sample_phone_tree(mock_phone_action):
    """Create a sample phone tree for testing"""
    from payphone.phone_system.phone_tree import PhoneTree

    # payphone.phone_system.PhoneTree builds a real (pygame) AudioHandler unless given one.
    audio = StubAudioHandler()

    # Create a simple menu structure:
    # Main Menu (1: Weather, 2: Time, 3: Music)
    main_menu = PhoneTree(
        audio_file="menu/main.wav",
        timeout=30,
        audio_handler=audio,
    )

    weather_menu = PhoneTree(
        audio_file="menu/weather.wav",
        action=mock_phone_action,
        timeout=10,
        audio_handler=audio,
    )

    time_menu = PhoneTree(
        audio_file="menu/time.wav",
        action=mock_phone_action,
        timeout=10,
        audio_handler=audio,
    )

    music_menu = PhoneTree(
        audio_file="menu/music.wav",
        options={
            '1': PhoneTree(audio_file="music/song1.wav", action=mock_phone_action, audio_handler=audio),
            '2': PhoneTree(audio_file="music/song2.wav", action=mock_phone_action, audio_handler=audio),
        },
        timeout=20,
        audio_handler=audio,
    )

    main_menu.options = {
        '1': weather_menu,
        '2': time_menu,
        '3': music_menu
    }

    return main_menu


# ============================================================================
# Temporary File Fixtures
# ============================================================================

@pytest.fixture
def temp_audio_dir(tmp_path):
    """Create temporary audio directory structure"""
    audio_dir = tmp_path / "audio_files"
    audio_dir.mkdir()
    (audio_dir / "menu").mkdir()
    (audio_dir / "prompts").mkdir()
    (audio_dir / "music").mkdir()

    # Create dummy audio files
    (audio_dir / "prompts" / "dial_tone.wav").touch()
    (audio_dir / "prompts" / "timeout.wav").touch()
    (audio_dir / "menu" / "main.wav").touch()

    return audio_dir


@pytest.fixture
def temp_config_file(tmp_path):
    """Create temporary configuration file"""
    config_file = tmp_path / ".env"
    config_file.write_text("""
USE_GPIO=true
SERIAL_PORT=/dev/ttyUSB0
BAUDRATE=9600
KEYPAD_ROW_PINS=[5, 6, 13, 19]
KEYPAD_COL_PINS=[26, 20, 21]
HOOK_SWITCH_PIN=17
AUDIO_DIR=audio_files
SAMPLE_RATE=44100
MENU_TIMEOUT=30
ENABLE_RECORDING=false
ENABLE_CELLULAR=false
""")
    return config_file
