# Development Guide

Complete guide for developing, testing, and deploying the payphone system.

## Table of Contents

1. [Development Environment](#development-environment)
2. [Project Structure](#project-structure)
3. [Testing Strategy](#testing-strategy)
4. [Deployment Workflow](#deployment-workflow)
5. [Debugging](#debugging)
6. [Common Tasks](#common-tasks)

---

## Development Environment

### Local Setup (Mac/Linux)

Your local machine is for development and testing code that doesn't require hardware.

**Prerequisites:**
```bash
# Python 3.7+
python3 --version

# pip
pip3 --version

# 1Password CLI (for deployment)
op --version
```

**Install Dependencies:**
```bash
# Clone repository
git clone <repo-url> pay-phone
cd pay-phone

# Install Python packages
make install
# OR
pip3 install -r requirements.txt

# Verify installation
pytest --version
```

### Raspberry Pi Setup

The Pi is for hardware testing and production deployment.

See [SD_CARD_SETUP.md](SD_CARD_SETUP.md) for initial setup.

---

## Project Structure

```
pay-phone/
├── payphone/                    # Main Python package
│   ├── main.py                  # Entry point
│   ├── phone_system/            # Phone menu logic
│   │   ├── phone_tree.py        # Menu navigation
│   │   └── phone_action.py      # Action wrapper
│   ├── hardware/                # Hardware interfaces
│   │   ├── gpio_handler.py      # Base GPIO handler
│   │   ├── gpio_keypad.py       # Keypad scanning
│   │   ├── gpio_hook.py         # Hook switch
│   │   └── serial_handler.py    # Arduino serial
│   ├── audio/                   # Audio playback
│   │   └── handler.py           # Pygame-based audio
│   └── config/                  # Configuration
│       └── settings.py          # Environment settings
│
├── tests/                       # Test suite
│   ├── conftest.py              # Pytest fixtures
│   ├── unit/                    # Unit tests (local)
│   ├── integration/             # Integration tests
│   └── hardware/                # Hardware tests (Pi only)
│
├── scripts/                     # Utility scripts
│   ├── load_secrets.sh          # Load from 1Password
│   ├── deploy_to_pi.sh          # Deploy to Pi
│   ├── ssh_to_pi.sh             # SSH helper
│   ├── inject_secrets.sh        # Inject secrets to Pi
│   ├── sync_config.sh           # Sync config only
│   ├── run_remote_tests.sh      # Run tests on Pi
│   ├── setup_pi.sh              # Pi initial setup
│   ├── test_hardware.py         # Serial hardware test
│   └── test_hardware_gpio.py    # GPIO hardware test
│
├── docs/                        # Documentation
│   ├── DEVELOPMENT.md           # This file
│   ├── WALKTHROUGH.md           # Complete tutorial
│   ├── BEST_PRACTICES.md        # Best practices
│   ├── SD_CARD_SETUP.md         # SD card setup
│   ├── SECRETS_MANAGEMENT.md    # 1Password guide
│   ├── GPIO_WIRING.md           # GPIO wiring guide
│   ├── HARDWARE_SETUP.md        # Hardware setup
│   └── TROUBLESHOOTING.md       # Common issues
│
├── audio_files/                 # Audio files (gitignored)
│   ├── menu/                    # Menu prompts
│   ├── prompts/                 # System prompts
│   └── music/                   # Content audio
│
├── arduino/                     # Arduino firmware (optional)
│   └── payphone_controller/     # Arduino sketch
│
├── Makefile                     # Common commands
├── pytest.ini                   # Test configuration
├── requirements.txt             # Python dependencies
├── .env.template                # Environment template
└── .gitignore                   # Git ignore rules
```

---

## Testing Strategy

### Three Testing Levels

#### 1. Unit Tests (Local Machine)

Test individual components with mocked dependencies.

**Run locally:**
```bash
# All unit tests
make test
# OR
pytest tests/unit -v

# Specific test file
pytest tests/unit/test_phone_tree.py -v

# With coverage
make test-coverage

# Watch mode (auto-rerun on changes)
make test-watch  # Requires pytest-watch
```

**Writing unit tests:**
```python
# tests/unit/test_my_module.py
import pytest
from unittest.mock import Mock, patch

@pytest.mark.unit
def test_my_function():
    """Test description"""
    # Use fixtures from conftest.py
    # Mock hardware dependencies
    # Assert expected behavior
    pass
```

#### 2. Integration Tests (Local or Pi)

Test component interactions with minimal hardware mocking.

```bash
# Run integration tests
pytest tests/integration -v
make test-integration
```

#### 3. Hardware Tests (Raspberry Pi Only)

Test actual GPIO, audio, and serial hardware.

**Run on Pi:**
```bash
# SSH into Pi
make ssh

# Run all hardware tests
sudo pytest tests/hardware -v

# Run specific hardware tests
sudo pytest -m gpio      # GPIO tests
sudo pytest -m audio     # Audio tests
sudo pytest -m serial    # Serial tests
```

**Run remotely from local machine:**
```bash
# Load secrets first
source scripts/load_secrets.sh

# Run all hardware tests on Pi
make pi-test-hardware

# Run specific categories
make pi-test-gpio
make pi-test-unit
make pi-test-coverage
```

### Test Markers

Tests are marked for categorization:

```python
@pytest.mark.unit          # No hardware, fully mocked
@pytest.mark.integration   # Multiple components
@pytest.mark.hardware      # Requires actual hardware
@pytest.mark.gpio          # Requires GPIO pins
@pytest.mark.audio         # Requires audio hardware
@pytest.mark.serial        # Requires Arduino
@pytest.mark.slow          # Long-running tests
```

### Test Fixtures

Available fixtures (in `tests/conftest.py`):

```python
def test_example(mock_gpio, mock_pygame, mock_serial,
                 mock_input_queue, sample_phone_tree):
    """All fixtures auto-injected by pytest"""
    pass
```

---

## Deployment Workflow

### Quick Deployment

```bash
# 1. Load 1Password secrets (once per session)
source scripts/load_secrets.sh

# 2. Deploy code + inject secrets
make deploy

# 3. Check status
make pi-status

# 4. View logs
make pi-logs
```

### Step-by-Step Deployment

#### Step 1: Load Secrets

```bash
# Load from 1Password
source scripts/load_secrets.sh

# Verify loaded
echo $PI_HOST
echo $PI_USER
```

See [SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md) for setup.

#### Step 2: Test Locally

```bash
# Run unit tests
make test

# Run linters (if configured)
make lint

# Clean generated files
make clean
```

#### Step 3: Deploy

**Quick deploy (code only):**
```bash
make deploy
# OR
./scripts/deploy_to_pi.sh
```

**Full deploy (code + dependencies):**
```bash
make deploy-full
# OR
./scripts/deploy_to_pi.sh --full
```

**Deploy without restart:**
```bash
./scripts/deploy_to_pi.sh --no-restart
```

**Deploy without secrets:**
```bash
./scripts/deploy_to_pi.sh --skip-secrets
```

#### Step 4: Verify Deployment

```bash
# Check service status
make pi-status

# View logs (live)
make pi-logs

# SSH and inspect
make ssh
```

### Sync Only Configuration

Update secrets/environment without deploying code:

```bash
source scripts/load_secrets.sh

# Sync config
make sync-secrets
# OR
./scripts/sync_config.sh

# With service restart
./scripts/sync_config.sh --restart
```

---

## Debugging

### Local Debugging

**Running main.py locally (will fail without hardware):**
```bash
python3 -m payphone.main
# Error: No module named 'RPi.GPIO'
```

Use unit tests with mocks instead.

**Python debugger:**
```python
# Add to code
import pdb; pdb.set_trace()

# Or
breakpoint()  # Python 3.7+
```

### Remote Debugging (on Pi)

#### View Logs

```bash
# Live logs (from local machine)
make pi-logs

# SSH and view logs
make ssh
sudo journalctl -u payphone -f

# Last 50 lines
sudo journalctl -u payphone -n 50

# Logs with errors only
sudo journalctl -u payphone -p err

# Logs since boot
sudo journalctl -u payphone -b
```

#### Check Service Status

```bash
# From local machine
make pi-status

# On Pi
sudo systemctl status payphone.service

# Is running?
sudo systemctl is-active payphone.service
```

#### Run Manually (Not as Service)

```bash
# SSH to Pi
make ssh

# Stop service
sudo systemctl stop payphone.service

# Run manually to see output
cd ~/payphone
python3 -m payphone.main

# Press Ctrl+C to stop
# Restart service
sudo systemctl start payphone.service
```

#### Test Hardware

```bash
# GPIO hardware test
sudo python3 ~/payphone/scripts/test_hardware_gpio.py

# Serial hardware test
python3 ~/payphone/scripts/test_hardware.py

# Check GPIO permissions
groups  # Should include 'gpio'

# Check audio
aplay -l
speaker-test -t wav
```

### Common Issues

#### Import Errors

```python
# Error: ModuleNotFoundError: No module named 'payphone'
# Solution: Use -m flag
python3 -m payphone.main  # Correct
python3 payphone/main.py  # May fail
```

#### GPIO Permission Denied

```bash
# Error: RuntimeError: No access to /dev/mem
# Solution: Run with sudo or add user to gpio group
sudo python3 -m payphone.main

# OR (one-time setup)
sudo usermod -a -G gpio pi
# Log out and back in
```

#### Audio Not Working

```bash
# Check audio device
aplay -l

# Test audio
aplay /usr/share/sounds/alsa/Front_Center.wav

# Check ALSA config
cat /etc/asound.conf
cat ~/.asoundrc

# Check volume
alsamixer
```

#### Deployment Fails

```bash
# Test SSH connection
ssh pi@payphone.local

# Verify secrets loaded
echo $PI_HOST
echo $PI_USER

# Test with password
ssh pi@payphone.local  # Enter password manually

# Check rsync
which rsync
```

---

## Common Tasks

### Adding a New Menu Option

**1. Create audio file:**
```bash
# Add to audio_files/menu/
# Example: new_option.wav
```

**2. Update phone tree (in main.py):**
```python
def build_phone_tree():
    main_menu = PhoneTree(
        audio_file="menu/main.wav",
        options={
            '1': existing_option,
            '2': new_option,  # Add this
        }
    )

    new_option = PhoneTree(
        audio_file="menu/new_option.wav",
        action=new_option_action
    )

    return main_menu
```

**3. Define action (if needed):**
```python
def new_option_action():
    print("New option selected")
    # Do something
```

**4. Test locally:**
```python
# tests/unit/test_phone_tree.py
def test_new_option():
    tree = build_phone_tree()
    assert '2' in tree.options
```

**5. Deploy:**
```bash
make deploy
```

### Adding New Audio Files

```bash
# 1. Create/convert audio files (WAV format)
# Recommended: 44.1kHz, mono, 16-bit

# 2. Copy to Pi
scp audio_files/menu/new.wav pi@payphone.local:~/payphone/audio_files/menu/

# OR sync entire directory
make deploy  # Includes audio_files/
```

### Changing GPIO Pins

**1. Update environment variable:**
```bash
# On local machine in .env.template
KEYPAD_ROW_PINS=[5, 6, 13, 19]  # Change these
KEYPAD_COL_PINS=[26, 20, 21]
HOOK_SWITCH_PIN=17
```

**2. Update Pi configuration:**
```bash
source scripts/load_secrets.sh
make sync-secrets
```

**3. Restart service:**
```bash
make pi-restart
```

### Updating Dependencies

**1. Update requirements.txt:**
```bash
# Add new package
echo "newpackage>=1.0.0" >> requirements.txt
```

**2. Install locally:**
```bash
pip3 install newpackage
```

**3. Deploy to Pi with --full:**
```bash
make deploy-full
```

### Viewing Phone State

```bash
# SSH to Pi
make ssh

# Check environment variables
cat /etc/payphone/.env

# Check active processes
ps aux | grep python

# Check GPIO usage
# No built-in tool, use your test scripts
```

---

## Git Workflow

### Branch Strategy

```bash
# Main branch: stable, production-ready
git checkout master

# Feature branch
git checkout -b feature/new-menu-option

# Make changes, test locally
make test

# Commit
git add .
git commit -m "Add new menu option"

# Push
git push origin feature/new-menu-option

# Create pull request
# After review, merge to master
```

### Before Committing

```bash
# Run tests
make test

# Clean unnecessary files
make clean

# Check what's being committed
git status
git diff

# Verify no secrets
git diff | grep -i "password\|api_key\|secret"

# Commit
git commit -m "Descriptive message"
```

### .gitignore Verification

```bash
# These should NEVER be committed:
# .env (secrets)
# *.key, *.pem (SSH keys)
# __pycache__/ (Python cache)
# .coverage, htmlcov/ (test coverage)
# audio_files/*.wav, *.mp3 (large files)

# Verify ignored
git status --ignored
```

---

## Performance Tips

### Optimize Boot Time

```bash
# On Pi: disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon

# Reduce systemd timeout
sudo nano /etc/systemd/system.conf
# Set: DefaultTimeoutStartSec=30s
```

### Optimize Audio Latency

```bash
# Reduce buffer size in audio handler
# payphone/audio/handler.py
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
```

### Reduce Memory Usage

```bash
# On Pi: reduce GPU memory (headless)
sudo raspi-config
# Performance Options → GPU Memory → 16
```

---

## Next Steps

- **WALKTHROUGH.md**: Complete step-by-step tutorial
- **BEST_PRACTICES.md**: Code organization and safety guidelines
- **GPIO_WIRING.md**: Hardware wiring diagrams
- **TROUBLESHOOTING.md**: Common issues and solutions

---

## Quick Reference

### Essential Commands

```bash
# Local testing
make test                 # Run unit tests
make test-coverage        # Tests with coverage

# Deployment
source scripts/load_secrets.sh   # Load 1Password secrets
make deploy              # Deploy to Pi
make deploy-full         # Deploy with dependencies
make sync-secrets        # Sync config only

# Pi access
make ssh                 # SSH to Pi
make pi-status           # Service status
make pi-logs             # Live logs
make pi-restart          # Restart service

# Remote testing
make pi-test             # All tests on Pi
make pi-test-hardware    # Hardware tests only
make pi-test-gpio        # GPIO tests

# Help
make help                # Show all commands
```

### File Locations

**Local Machine:**
- Code: `~/Developer/pay-phone/`
- Secrets: 1Password (never on disk)
- Tests: `~/Developer/pay-phone/tests/`

**Raspberry Pi:**
- Code: `~/payphone/`
- Config: `/etc/payphone/.env`
- Logs: `/var/log/payphone/` or `journalctl`
- Audio: `~/payphone/audio_files/`
- Service: `/etc/systemd/system/payphone.service`

---

**See also:**
- [SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md) - 1Password workflow
- [SD_CARD_SETUP.md](SD_CARD_SETUP.md) - Initial Pi setup
- [WALKTHROUGH.md](WALKTHROUGH.md) - Complete tutorial
