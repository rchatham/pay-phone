# Complete Command Reference

Quick reference for all commands in the payphone project.

## Local Testing

```bash
# Activate virtual environment (ALWAYS FIRST)
source venv/bin/activate

# Run all unit tests
make test
pytest tests/unit -v

# Run specific test file
pytest tests/unit/test_phone_tree.py -v

# Run tests with coverage
make test-coverage
pytest --cov=payphone --cov-report=html

# View coverage report
open htmlcov/index.html

# Run specific test by name
pytest tests/unit/test_phone_tree.py::TestPhoneTreeBasics::test_create_simple_tree -v

# Clean generated files
make clean

# Install dependencies
make install
pip install -r requirements.txt
```

## 1Password & Secrets

```bash
# Sign in to 1Password
eval $(op signin)

# Check if signed in
op whoami

# Load secrets (REQUIRED before deployment)
source scripts/load_secrets.sh

# Verify secrets loaded
echo $PI_HOST
echo $PI_USER
echo $PI_PASSWORD

# Show all loaded variables
env | grep PI_
```

## Deployment

```bash
# ALWAYS load secrets first!
source scripts/load_secrets.sh

# Quick deploy (code only, no dependencies)
make deploy
./scripts/deploy_to_pi.sh

# Full deploy (code + dependencies)
make deploy-full
./scripts/deploy_to_pi.sh --full

# Deploy without restarting service
./scripts/deploy_to_pi.sh --no-restart

# Deploy without updating secrets
./scripts/deploy_to_pi.sh --skip-secrets

# Sync only configuration/secrets
make sync-secrets
./scripts/sync_config.sh

# Sync config and restart service
./scripts/sync_config.sh --restart
```

## Raspberry Pi Access

```bash
# SSH to Pi (with loaded secrets)
make ssh
./scripts/ssh_to_pi.sh

# Run command on Pi
./scripts/ssh_to_pi.sh "ls -la ~/payphone"

# Copy file to Pi
scp myfile.txt pi@payphone.local:~/payphone/

# Copy file from Pi
scp pi@payphone.local:~/payphone/myfile.txt ./
```

## Service Management

```bash
# Check service status
make pi-status
./scripts/ssh_to_pi.sh "sudo systemctl status payphone"

# View live logs
make pi-logs
./scripts/ssh_to_pi.sh "sudo journalctl -u payphone -f"

# View last 50 log lines
./scripts/ssh_to_pi.sh "sudo journalctl -u payphone -n 50"

# Restart service
make pi-restart
./scripts/ssh_to_pi.sh "sudo systemctl restart payphone"

# Stop service
make pi-stop
./scripts/ssh_to_pi.sh "sudo systemctl stop payphone"

# Enable auto-start on boot
./scripts/ssh_to_pi.sh "sudo systemctl enable payphone"

# Disable auto-start
./scripts/ssh_to_pi.sh "sudo systemctl disable payphone"
```

## Remote Testing

```bash
# Run all tests on Pi
make pi-test
./scripts/run_remote_tests.sh

# Run only unit tests
make pi-test-unit
./scripts/run_remote_tests.sh --unit

# Run hardware tests (GPIO, audio)
make pi-test-hardware
./scripts/run_remote_tests.sh --hardware

# Run GPIO-specific tests
make pi-test-gpio
./scripts/run_remote_tests.sh --gpio

# Run audio-specific tests
./scripts/run_remote_tests.sh --audio

# Run with coverage
make pi-test-coverage
./scripts/run_remote_tests.sh --coverage
```

## Hardware Testing (On Pi)

```bash
# SSH to Pi first
make ssh

# Test GPIO keypad
sudo python3 ~/payphone/scripts/test_hardware_gpio.py

# Test serial/Arduino
python3 ~/payphone/scripts/test_hardware.py

# Test audio output
speaker-test -t wav -c 1

# List audio devices
aplay -l

# Test audio recording
arecord -d 5 -f cd test.wav
aplay test.wav

# Adjust volume
alsamixer

# Check GPIO groups
groups

# Check system resources
htop
free -h
df -h

# Check temperature
vcgencmd measure_temp

# Run manual test
cd ~/payphone
python3 -m payphone.main
```

## Git Operations

```bash
# Check status
git status

# View changes
git diff

# Add files
git add .

# Commit
git commit -m "Description of changes"

# Push
git push origin master

# Pull latest
git pull origin master

# Create branch
git checkout -b feature/my-feature

# Switch branch
git checkout master

# View commit history
git log --oneline -10

# Check for secrets (BEFORE committing)
git diff | grep -i "password\|api_key\|secret"
```

## Makefile Commands

```bash
# Show all available commands
make help

# Local Development
make install              # Install dependencies
make test                 # Run unit tests
make test-coverage        # Tests with coverage
make clean                # Clean generated files

# Secrets Management
make setup-secrets        # Show 1Password setup instructions
make load-secrets         # Reminder to source load_secrets.sh

# Raspberry Pi - Deployment
make deploy               # Deploy code to Pi
make deploy-full          # Full deployment with dependencies
make sync-secrets         # Sync only configuration

# Raspberry Pi - Access
make ssh                  # SSH to Pi
make pi-status            # Check service status
make pi-logs              # View live logs
make pi-restart           # Restart service
make pi-stop              # Stop service

# Raspberry Pi - Testing
make pi-test              # Run all tests on Pi
make pi-test-unit         # Unit tests on Pi
make pi-test-hardware     # Hardware tests on Pi
make pi-test-gpio         # GPIO tests on Pi
make pi-test-coverage     # Tests with coverage on Pi

# Documentation
make docs                 # Show documentation list
make quickstart           # Show quick start guide
```

## Documentation

```bash
# View documentation
cat QUICK_START.md
cat docs/WALKTHROUGH.md
cat docs/DEVELOPMENT.md
cat docs/BEST_PRACTICES.md
cat docs/SD_CARD_SETUP.md
cat docs/SECRETS_MANAGEMENT.md
cat docs/GPIO_WIRING.md
cat docs/TROUBLESHOOTING.md

# Open in browser/editor
open QUICK_START.md
open docs/WALKTHROUGH.md
```

## Development Workflow

```bash
# === Morning Routine ===

# 1. Navigate to project
cd ~/Developer/pay-phone

# 2. Activate virtual environment
source venv/bin/activate

# 3. Load secrets (if deploying)
source scripts/load_secrets.sh

# 4. Pull latest changes (if team project)
git pull origin master


# === Development Cycle ===

# 1. Make code changes
vim payphone/main.py

# 2. Run local tests
make test

# 3. Deploy to Pi
make deploy

# 4. Monitor logs
make pi-logs

# 5. Test on hardware
# (Pick up handset, press keys)

# 6. Make adjustments
# (Repeat steps 1-5)

# 7. Commit when ready
git add .
git commit -m "Implement feature X"
git push


# === Troubleshooting ===

# Service not starting
make pi-logs
make ssh
sudo systemctl status payphone
python3 -m payphone.main

# Tests failing
make test
pytest tests/unit -v

# Can't connect to Pi
ping payphone.local
ssh pi@<IP_ADDRESS>

# Audio issues
make ssh
aplay -l
speaker-test -t wav -c 1
alsamixer
```

## Quick Commands

```bash
# Most common commands (90% of usage):

source venv/bin/activate      # Start local session
source scripts/load_secrets.sh # Load 1Password secrets
make test                      # Test locally
make deploy                    # Deploy to Pi
make pi-logs                   # Monitor Pi
make ssh                       # SSH to Pi
make pi-restart                # Restart service
make help                      # Show all commands
```

## Environment Variables

```bash
# Set in .env or export manually:

# Hardware
export USE_GPIO=true
export KEYPAD_ROW_PINS='[5, 6, 13, 19]'
export KEYPAD_COL_PINS='[26, 20, 21]'
export HOOK_SWITCH_PIN=17

# Audio
export AUDIO_DIR=audio_files
export SAMPLE_RATE=44100

# Pi Access (from 1Password)
export PI_HOST=payphone.local
export PI_USER=pi
export PI_PASSWORD=<from-1password>
export PI_PORT=22

# API Keys (from 1Password)
export OPENAI_API_KEY=<from-1password>
export TWILIO_ACCOUNT_SID=<from-1password>
```

## Tips

```bash
# Use tab completion
make d<TAB>  # expands to make deploy

# Chain commands
source venv/bin/activate && make test && make deploy

# Background processes
make pi-logs &  # Run in background

# Search command history
history | grep deploy

# Rerun last command
!!

# Rerun command starting with 'make'
!make
```

---

**Save this file** for quick reference! All commands are also available via `make help`.
