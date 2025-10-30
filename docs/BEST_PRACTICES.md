# Best Practices

Guidelines for code organization, hardware safety, audio management, and system reliability.

## Table of Contents

1. [Code Organization](#code-organization)
2. [Hardware Safety](#hardware-safety)
3. [Audio Management](#audio-management)
4. [Testing Practices](#testing-practices)
5. [Security Practices](#security-practices)
6. [Phone Menu Design](#phone-menu-design)
7. [Error Handling](#error-handling)
8. [Performance Optimization](#performance-optimization)

---

## Code Organization

### Module Structure

**Keep modules focused and single-purpose:**

```python
# Good: Focused module
# payphone/hardware/gpio_keypad.py
class GPIOKeypad:
    """Handles 4x3 matrix keypad scanning via GPIO"""
    def __init__(self, input_queue, row_pins, col_pins):
        pass

# Bad: Too many responsibilities
class HardwareManager:
    """Handles keypad, hook, audio, and serial"""  # Too much!
    pass
```

### Import Organization

```python
# Standard library imports
import os
import sys
from queue import Queue

# Third-party imports
import pygame
import RPi.GPIO as GPIO

# Local application imports
from payphone.audio.handler import AudioHandler
from payphone.config.settings import Settings
```

### Constants

```python
# payphone/config/constants.py
# Define constants in a central location

# GPIO Pin Assignments
DEFAULT_ROW_PINS = [5, 6, 13, 19]
DEFAULT_COL_PINS = [26, 20, 21]
DEFAULT_HOOK_PIN = 17

# Timing
DEBOUNCE_TIME = 300  # milliseconds
DEFAULT_TIMEOUT = 30  # seconds

# Audio
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CHANNELS = 1
```

### Configuration

**Use environment variables for configuration:**

```python
# payphone/config/settings.py
import os

class Settings:
    @staticmethod
    def get_gpio_mode():
        return os.getenv('USE_GPIO', 'true').lower() == 'true'

    @staticmethod
    def get_keypad_rows():
        import json
        return json.loads(os.getenv('KEYPAD_ROW_PINS', '[5,6,13,19]'))
```

**Don't hardcode configuration:**

```python
# Bad
hook_pin = 17  # What if I need to change this?

# Good
hook_pin = Settings.get_hook_pin()
```

### Error Messages

**Make error messages actionable:**

```python
# Bad
raise ValueError("Invalid pin")

# Good
raise ValueError(
    f"Invalid GPIO pin {pin}. "
    f"Pin must be in range 2-27 for Raspberry Pi GPIO. "
    f"See docs/GPIO_WIRING.md for valid pins."
)
```

---

## Hardware Safety

### GPIO Voltage Levels

**CRITICAL**: Raspberry Pi GPIO is **3.3V logic**. Do NOT apply 5V!

```python
# Always use proper level shifting for 5V devices
# OR use 3.3V-tolerant components

# Raspberry Pi GPIO pins:
# - Output: 3.3V max
# - Input: 3.3V max (will be damaged by 5V!)
# - Current: 16mA max per pin
```

### GPIO Best Practices

**1. Always cleanup GPIO:**

```python
import RPi.GPIO as GPIO

try:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    # ... do work ...
finally:
    GPIO.cleanup()  # Always cleanup!
```

**2. Use pull-up/pull-down resistors:**

```python
# For switches/buttons, always specify pull resistor
GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Good
GPIO.setup(pin, GPIO.IN)  # Bad - floating input!
```

**3. Debounce inputs:**

```python
# Hardware debouncing
last_press_time = 0
DEBOUNCE_MS = 300

def on_key_press(key):
    global last_press_time
    now = time.time() * 1000
    if now - last_press_time < DEBOUNCE_MS:
        return  # Ignore bounce
    last_press_time = now
    # Process key press
```

**4. Protect against shorts:**

```python
# Use resistors on all outputs
# - 220Ω to 1kΩ in series with outputs
# - Limits current if pin shorts to ground

# Never directly connect:
# - GPIO output to GPIO output
# - GPIO output to ground (without resistor)
# - GPIO output to 3.3V/5V (without resistor)
```

### Keypad Wiring Safety

```
Raspberry Pi (3.3V)          4x3 Keypad Matrix
--------------------         ------------------
GPIO 5  (Row 0) ----+----------- Row 1 pin
GPIO 6  (Row 1) ----+----------- Row 2 pin
GPIO 13 (Row 2) ----+----------- Row 3 pin
GPIO 19 (Row 3) ----+----------- Row 4 pin
                    |
                   [220Ω resistor]  <- IMPORTANT
                    |
GPIO 26 (Col 0) ----+----------- Col 1 pin
GPIO 20 (Col 1) ----+----------- Col 2 pin
GPIO 21 (Col 2) ----+----------- Col 3 pin

All column pins: INPUT with PULL_DOWN
All row pins: OUTPUT
```

### Audio Hardware Safety

**TRRS Jack Connections (3.5mm):**

```
Tip:    Left audio (Yellow wire from handset)
Ring 1: Right audio (or ground for mono)
Ring 2: Ground (Black wire from handset)
Sleeve: Microphone (Green wire from handset)
```

**Electret Microphone Bias:**
- Requires 1.5-3.3V bias voltage
- Audio Injector provides bias on mic pin
- Check your sound card specs!

---

## Audio Management

### Audio File Requirements

**Format:**
- **Container**: WAV (uncompressed)
- **Sample Rate**: 44100 Hz (CD quality)
- **Bit Depth**: 16-bit
- **Channels**: Mono (1 channel)

**Why WAV?**
- No decoding overhead
- Predictable playback timing
- Low CPU usage on Pi Zero

### Converting Audio Files

```bash
# Using ffmpeg
ffmpeg -i input.mp3 -ar 44100 -ac 1 -sample_fmt s16 output.wav

# Using sox
sox input.mp3 -r 44100 -c 1 -b 16 output.wav
```

### Audio Organization

```
audio_files/
├── menu/              # Menu prompts
│   ├── main.wav       # "Press 1 for weather, 2 for time..."
│   ├── weather.wav    # "Current weather is..."
│   └── time.wav       # "The time is..."
│
├── prompts/           # System prompts
│   ├── dial_tone.wav  # Continuous tone
│   ├── timeout.wav    # "Your call timed out"
│   ├── invalid.wav    # "Invalid selection"
│   └── goodbye.wav    # "Thank you for calling"
│
└── music/             # Content audio (long files)
    ├── song1.wav
    └── song2.wav
```

### Audio File Naming

**Use descriptive, lowercase names with underscores:**

```bash
# Good
menu_main.wav
prompt_timeout.wav
music_jazz_1.wav

# Bad
MainMenu.wav
1.wav
audio-file.wav
```

### Audio Playback Best Practices

**1. Preload short sounds:**

```python
# Load frequently used sounds once
class AudioHandler:
    def __init__(self):
        self.dial_tone = pygame.mixer.Sound("prompts/dial_tone.wav")
        self.timeout = pygame.mixer.Sound("prompts/timeout.wav")

    def play_dial_tone(self):
        self.dial_tone.play(loops=-1)  # Loop indefinitely
```

**2. Stream long audio:**

```python
# Stream long music files
pygame.mixer.music.load("music/long_song.wav")
pygame.mixer.music.play()
```

**3. Stop audio before starting new:**

```python
def play_file(self, filename):
    # Stop any playing audio first
    pygame.mixer.music.stop()
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()
```

### Audio Volume

**Adjust volume in code:**

```python
# Set master volume (0.0 to 1.0)
pygame.mixer.music.set_volume(0.8)

# Set individual sound volume
sound = pygame.mixer.Sound("file.wav")
sound.set_volume(0.5)
```

**Adjust system volume on Pi:**

```bash
# Using alsamixer (interactive)
alsamixer

# Using amixer (command line)
amixer set Master 80%

# Save settings
sudo alsactl store
```

---

## Testing Practices

### Test-Driven Development

**Write tests first:**

```python
# 1. Write test
def test_keypad_detects_key_press():
    keypad = GPIOKeypad(queue, rows, cols)
    # Simulate key press
    # Assert key detected

# 2. Write code to make test pass
class GPIOKeypad:
    def detect_key(self):
        # Implementation
        pass

# 3. Refactor
```

### Test Isolation

**Tests should be independent:**

```python
# Bad - tests depend on each other
def test_init():
    global keypad
    keypad = GPIOKeypad(...)

def test_scan():
    keypad.scan()  # Uses global from previous test

# Good - each test is self-contained
def test_scan(mock_gpio):
    keypad = GPIOKeypad(...)
    keypad.scan()
```

### Mock External Dependencies

```python
@pytest.mark.unit
@patch('payphone.hardware.gpio_keypad.GPIO')
def test_keypad_without_hardware(mock_gpio):
    """Test runs on any system without GPIO"""
    mock_gpio.input.return_value = 1
    keypad = GPIOKeypad(Queue(), [5,6], [26,20])
    # Test logic without actual GPIO
```

### Hardware Test Safety

**Always check before running hardware tests:**

```python
# tests/hardware/test_gpio_keypad.py
import pytest

@pytest.mark.hardware
@pytest.mark.gpio
def test_real_keypad():
    """Test with actual GPIO hardware - Pi only!"""
    if not is_raspberry_pi():
        pytest.skip("Requires Raspberry Pi")

    # Safe to use real GPIO here
    keypad = GPIOKeypad(...)
```

---

## Security Practices

### Never Commit Secrets

```bash
# Check before committing
git status
git diff

# Search for secrets
git diff | grep -i "password\|api.key\|secret\|token"

# Use pre-commit hooks
# .git/hooks/pre-commit
#!/bin/bash
if git diff --cached | grep -i "password\|api_key"; then
    echo "ERROR: Possible secret in commit"
    exit 1
fi
```

### Use 1Password for All Secrets

```bash
# Good - secret in 1Password
export API_KEY=$(op read "op://Personal/Payphone-APIs/OpenAI/api_key")

# Bad - secret in shell history
export API_KEY="sk-1234567890abcdef"
```

### Secure File Permissions on Pi

```bash
# Configuration file with secrets
sudo chmod 600 /etc/payphone/.env
sudo chown pi:pi /etc/payphone/.env

# SSH keys
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub

# Scripts
chmod +x scripts/*.sh
chmod 755 scripts/*.py
```

### Sanitize Logs

```python
import logging

# Don't log secrets
logging.info(f"API key: {api_key}")  # BAD!

# Log only non-sensitive info
logging.info("API key loaded successfully")  # Good

# Mask secrets
def mask_secret(s):
    if len(s) > 8:
        return s[:4] + "****" + s[-4:]
    return "****"

logging.info(f"Using API key: {mask_secret(api_key)}")
```

---

## Phone Menu Design

### Keep Menus Simple

**2-4 options per menu level:**

```python
# Good
main_menu = PhoneTree("menu/main.wav", options={
    '1': weather,
    '2': time,
    '3': music
})

# Bad - too many options
main_menu = PhoneTree("menu/main.wav", options={
    '1': opt1, '2': opt2, '3': opt3, '4': opt4,
    '5': opt5, '6': opt6, '7': opt7, '8': opt8,
    '9': opt9, '0': opt0, '*': star, '#': pound
})  # Users will forget options!
```

### Use Consistent Key Mapping

```
1-3: Primary options
4-6: Secondary options
7-9: Advanced options
0: Help / Repeat menu
*: Go back
#: Confirm / Submit
```

### Provide Timeouts

```python
# Always set reasonable timeouts
menu = PhoneTree(
    audio_file="menu/main.wav",
    timeout=30,  # 30 seconds
    options=...
)

# Shorter timeout for simple yes/no
confirm = PhoneTree(
    audio_file="menu/confirm.wav",
    timeout=10,  # 10 seconds
    options={'1': yes, '2': no}
)
```

### Audio Prompts Should Be Clear

**Good prompts:**
- "Press 1 for weather, 2 for time, or 3 for music"
- "To confirm, press 1. To cancel, press 2"
- "Enter your 4-digit code, then press pound"

**Bad prompts:**
- "Select an option" (which options?)
- "Press a key" (which key?)
- [Long story before options]

### Allow Easy Exit

```python
# Always provide way to return to main menu
def build_phone_tree():
    main = PhoneTree("menu/main.wav", options={...})
    submenu = PhoneTree("menu/sub.wav", options={
        '1': action1,
        '2': action2,
        '*': main  # Back to main menu
    })
    return main
```

---

## Error Handling

### Handle All Failure Modes

```python
def play_audio_file(filename):
    try:
        if not os.path.exists(filename):
            logging.error(f"Audio file not found: {filename}")
            # Fallback: play error tone
            self.play_error_tone()
            return False

        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        return True

    except pygame.error as e:
        logging.error(f"Pygame error: {e}")
        return False

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False
```

### Graceful Degradation

```python
# Try hardware, fall back to mock if unavailable
try:
    import RPi.GPIO as GPIO
    USE_REAL_GPIO = True
except (ImportError, RuntimeError):
    import Mock
    GPIO = Mock()
    USE_REAL_GPIO = False
    logging.warning("GPIO not available, using mock")
```

### User-Friendly Error Messages

```python
# Bad
print("Error code 0x42")

# Good
logging.error(
    "Failed to initialize keypad. "
    "Check GPIO pin configuration in /etc/payphone/.env. "
    "See docs/GPIO_WIRING.md for correct wiring."
)
```

### Retry Logic

```python
def connect_with_retry(max_attempts=3):
    for attempt in range(max_attempts):
        try:
            connection = establish_connection()
            return connection
        except ConnectionError:
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                raise
```

---

## Performance Optimization

### Raspberry Pi Zero Optimization

**The Pi Zero is slow - optimize carefully:**

```python
# Good - load once
class AudioHandler:
    def __init__(self):
        self.sounds = {
            'tone': pygame.mixer.Sound("tone.wav"),
            'beep': pygame.mixer.Sound("beep.wav"),
        }

# Bad - load every time
def play_tone(self):
    sound = pygame.mixer.Sound("tone.wav")  # Slow!
    sound.play()
```

### Minimize Imports

```python
# Good - import only what you need
from queue import Queue

# Bad - imports entire module
import queue
```

### Use Generators for Large Data

```python
# Good - lazy evaluation
def read_large_file():
    with open('large.txt') as f:
        for line in f:
            yield line.strip()

# Bad - loads entire file into memory
def read_large_file():
    with open('large.txt') as f:
        return [line.strip() for line in f]
```

### Profile Code

```python
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()

    # Code to profile
    my_function()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumtime')
    stats.print_stats(20)  # Top 20
```

### Monitor System Resources

```bash
# CPU usage
top

# Memory usage
free -h

# Disk usage
df -h

# Raspberry Pi temperature
vcgencmd measure_temp
```

---

## Documentation

### Code Comments

```python
# Good comments explain WHY, not WHAT

# Bad - obvious
i += 1  # Increment i

# Good - explains rationale
time.sleep(0.3)  # 300ms debounce prevents double-press on mechanical switches

# Bad - redundant with function name
def get_temperature():
    """Gets the temperature"""  # Useless
    pass

# Good - explains usage and edge cases
def get_temperature():
    """
    Returns current temperature in Celsius from DHT22 sensor.

    Returns None if sensor read fails (e.g., not connected, timeout).
    Sensor updates every 2 seconds, so cached values may be returned.
    """
    pass
```

### Keep README Updated

```markdown
# README.md should include:
- Project overview (what does it do?)
- Hardware requirements
- Quick start (5 minute setup)
- Link to full documentation
- License
```

---

## Quick Checklist

Before deploying to production:

- [ ] All tests passing (`make test`)
- [ ] No secrets in code or version control
- [ ] GPIO pins documented and correct
- [ ] Audio files present and correct format
- [ ] Timeouts configured appropriately
- [ ] Error handling for all hardware operations
- [ ] Logging configured (not too verbose, not too quiet)
- [ ] Service configured to restart on failure
- [ ] Documentation updated
- [ ] Tested on actual hardware

---

**See also:**
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development workflow
- [GPIO_WIRING.md](GPIO_WIRING.md) - Hardware wiring guide
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
