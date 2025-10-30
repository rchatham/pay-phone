# Quick Start Guide

Get your payphone system running in 30 minutes!

## Prerequisites

- ✅ Raspberry Pi 3/4 with power supply
- ✅ MicroSD card (16GB+, Class 10)
- ✅ 4x3 matrix keypad
- ✅ Phone handset with speaker/mic
- ✅ Audio interface (Audio Injector or USB sound card)
- ✅ Mac/Linux computer for development
- ✅ 1Password account

## Phase 1: Local Setup (10 minutes)

```bash
# 1. Navigate to project
cd ~/Developer/pay-phone

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install pytest pytest-cov pygame numpy

# 4. Run tests
pytest tests/unit -v

# ✅ 14+ tests should pass
```

## Phase 2: 1Password Setup (5 minutes)

```bash
# 1. Install 1Password CLI (if not already)
brew install --cask 1password-cli

# 2. Sign in
eval $(op signin)

# 3. Create item in 1Password app:
#    - Item name: "Payphone-Pi"
#    - Vault: Personal
#    - Fields:
#      username: pi
#      password: [your password]
#      host: payphone.local
#      port: 22

# 4. Test loading
source scripts/load_secrets.sh
echo $PI_HOST  # Should show: payphone.local
```

## Phase 3: Raspberry Pi Setup (15 minutes)

```bash
# 1. Flash SD card with Raspberry Pi Imager
#    - OS: Raspberry Pi OS Lite (64-bit)
#    - Configure: hostname (payphone.local), user (pi), WiFi, SSH

# 2. Boot Pi and wait 2 minutes

# 3. Connect and update
ssh pi@payphone.local
sudo apt-get update && sudo apt-get upgrade -y
sudo reboot

# 4. Wait 1 minute, reconnect

# 5. Run setup (from local machine)
scp scripts/setup_pi.sh pi@payphone.local:~/
ssh pi@payphone.local
chmod +x setup_pi.sh
sudo ./setup_pi.sh
# Choose: GPIO mode (1)
sudo reboot
```

## Phase 4: First Deployment (5 minutes)

```bash
# On local machine

# 1. Load secrets
source scripts/load_secrets.sh

# 2. Deploy
make deploy-full

# 3. Check status
make pi-status
make pi-logs

# ✅ Service should be running
```

## Phase 5: Wire Hardware & Test

Follow detailed wiring in `docs/GPIO_WIRING.md`:

```
Keypad:
  Rows → GPIO 5, 6, 13, 19
  Cols → GPIO 26, 20, 21

Hook Switch:
  → GPIO 17 + GND

Audio:
  Audio Injector → GPIO pins 1-26
  Handset → 3.5mm jack
```

Test:
```bash
make ssh
sudo python3 ~/payphone/scripts/test_hardware_gpio.py
# Press keys, toggle hook switch

speaker-test -t wav -c 1
# Should hear audio through handset
```

## Daily Workflow

```bash
# Morning (once per session)
source scripts/load_secrets.sh

# Development cycle
1. Edit code locally
2. make test                    # Test locally
3. make deploy                  # Deploy to Pi
4. make pi-logs                 # Monitor
5. Test on hardware
6. Repeat!

# Common commands
make help                       # Show all commands
make ssh                        # SSH to Pi
make pi-status                  # Check service
make pi-restart                 # Restart service
make sync-secrets               # Update config only
```

## Troubleshooting

**Can't connect to Pi:**
```bash
ping payphone.local
# Or check router for Pi's IP address
```

**Tests failing locally:**
```bash
source venv/bin/activate
pip install pytest pytest-cov pygame numpy
make test
```

**Service won't start on Pi:**
```bash
make pi-logs                    # View errors
make ssh
sudo systemctl status payphone
python3 -m payphone.main        # Run manually to see errors
```

**Audio not working:**
```bash
make ssh
aplay -l                        # List audio devices
speaker-test -t wav -c 1        # Test playback
alsamixer                       # Adjust volume
```

## Next Steps

1. **Add audio files:** See `docs/BEST_PRACTICES.md` → Audio Management
2. **Customize menus:** Edit `payphone/main.py` → `build_phone_tree()`
3. **Add features:** See `docs/WALKTHROUGH.md` → Part 11: Advanced Features
4. **Monitor system:** `make pi-logs`

## Documentation

Start here:
- 📖 **docs/WALKTHROUGH.md** - Complete tutorial with all details
- 🛠️ **docs/DEVELOPMENT.md** - Development workflow
- ✨ **docs/BEST_PRACTICES.md** - Best practices
- 💿 **docs/SD_CARD_SETUP.md** - Detailed Pi setup
- 🔐 **docs/SECRETS_MANAGEMENT.md** - 1Password details

## Support

- Check logs: `make pi-logs`
- See docs: `docs/TROUBLESHOOTING.md`
- Run tests: `make test` (local) or `make pi-test-hardware` (Pi)

---

**You're all set!** 🎉

The system is production-ready. Follow the phases above to get running, then iterate using the daily workflow. All commands are in the Makefile (`make help`).
