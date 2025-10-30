"""
Pytest configuration and shared fixtures for payphone tests

This file provides mock fixtures for hardware components, allowing
tests to run on any system without requiring Raspberry Pi hardware.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from queue import Queue
import tempfile
import os


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
# Mock Hardware Fixtures
# ============================================================================

@pytest.fixture
def mock_gpio():
    """Mock RPi.GPIO module for testing without hardware"""
    with patch('RPi.GPIO') as mock:
        mock.BCM = 11
        mock.IN = 1
        mock.OUT = 0
        mock.PUD_UP = 22
        mock.PUD_DOWN = 21
        mock.RISING = 31
        mock.FALLING = 32
        mock.BOTH = 33
        mock.setmode = Mock()
        mock.setup = Mock()
        mock.input = Mock(return_value=1)
        mock.output = Mock()
        mock.cleanup = Mock()
        mock.add_event_detect = Mock()
        mock.remove_event_detect = Mock()
        yield mock


@pytest.fixture
def mock_pygame():
    """Mock pygame module for testing without audio hardware"""
    with patch('pygame') as mock_pg:
        # Mock mixer
        mock_mixer = Mock()
        mock_mixer.init = Mock()
        mock_mixer.quit = Mock()
        mock_mixer.music.load = Mock()
        mock_mixer.music.play = Mock()
        mock_mixer.music.stop = Mock()
        mock_mixer.music.get_busy = Mock(return_value=False)
        mock_pg.mixer = mock_mixer

        # Mock Sound
        mock_sound = Mock()
        mock_sound.play = Mock()
        mock_sound.stop = Mock()
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
    """Mock input queue for keypad events"""
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
    """Mock GPIO keypad handler"""
    with patch('payphone.hardware.gpio_keypad.GPIO', mock_gpio):
        from payphone.hardware.gpio_keypad import GPIOKeypad
        keypad = GPIOKeypad(
            input_queue=mock_input_queue,
            row_pins=[5, 6, 13, 19],
            col_pins=[26, 20, 21]
        )
        # Don't actually start scanning thread in tests
        keypad.start_scanning = Mock()
        keypad.stop_scanning = Mock()
        yield keypad


@pytest.fixture
def mock_gpio_hook(mock_gpio, mock_hook_callback):
    """Mock GPIO hook switch handler"""
    with patch('payphone.hardware.gpio_hook.GPIO', mock_gpio):
        from payphone.hardware.gpio_hook import GPIOHookSwitch
        hook = GPIOHookSwitch(
            callback=mock_hook_callback,
            pin=17
        )
        yield hook


@pytest.fixture
def mock_audio_handler(mock_pygame, tmp_path):
    """Mock audio handler with temporary audio directory"""
    audio_dir = tmp_path / "audio_files"
    audio_dir.mkdir()
    (audio_dir / "menu").mkdir()
    (audio_dir / "prompts").mkdir()
    (audio_dir / "music").mkdir()

    with patch('payphone.audio.handler.pygame', mock_pygame):
        from payphone.audio.handler import AudioHandler
        handler = AudioHandler(audio_dir=str(audio_dir))
        yield handler


# ============================================================================
# Phone System Fixtures
# ============================================================================

@pytest.fixture
def mock_phone_action():
    """Mock phone action callback"""
    return Mock(return_value=None)


@pytest.fixture
def sample_phone_tree(mock_phone_action):
    """Create a sample phone tree for testing"""
    from payphone.phone_system.phone_tree import PhoneTree

    # Create a simple menu structure:
    # Main Menu (1: Weather, 2: Time, 3: Music)
    main_menu = PhoneTree(
        audio_file="menu/main.wav",
        timeout=30
    )

    weather_menu = PhoneTree(
        audio_file="menu/weather.wav",
        action=mock_phone_action,
        timeout=10
    )

    time_menu = PhoneTree(
        audio_file="menu/time.wav",
        action=mock_phone_action,
        timeout=10
    )

    music_menu = PhoneTree(
        audio_file="menu/music.wav",
        options={
            '1': PhoneTree(audio_file="music/song1.wav", action=mock_phone_action),
            '2': PhoneTree(audio_file="music/song2.wav", action=mock_phone_action),
        },
        timeout=20
    )

    main_menu.options = {
        '1': weather_menu,
        '2': time_menu,
        '3': music_menu
    }

    return main_menu


@pytest.fixture
def mock_payphone_system(mock_gpio, mock_pygame, tmp_path):
    """Mock complete payphone system"""
    with patch.dict('os.environ', {
        'USE_GPIO': 'true',
        'AUDIO_DIR': str(tmp_path / 'audio_files'),
        'MENU_TIMEOUT': '30'
    }):
        with patch('payphone.main.GPIO', mock_gpio), \
             patch('payphone.main.pygame', mock_pygame):
            from payphone.main import PayphoneSystem
            system = PayphoneSystem()
            # Don't actually run the system
            system.run = Mock()
            yield system


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


# ============================================================================
# Cleanup
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Automatically cleanup after each test"""
    yield
    # Any cleanup code here
