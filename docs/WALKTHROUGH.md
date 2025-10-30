# Complete Walkthrough: Building Your Payphone System

A step-by-step tutorial from zero to a working payphone system. Follow along to build your own interactive payphone!

## What We'll Build

By the end of this walkthrough, you'll have:
- A Raspberry Pi running your payphone software
- A 4x3 keypad for user input
- Audio playback through a phone handset
- An interactive menu system
- A secure, repeatable deployment process

**Time Required**: 2-4 hours (first time)

---

## Prerequisites

### Hardware Checklist

- [ ] Raspberry Pi 3 or 4 (Pi Zero W also works but slower)
- [ ] MicroSD card (16GB minimum, Class 10)
- [ ] Power supply for Pi
- [ ] 4x3 matrix keypad
- [ ] Phone handset with working speaker and microphone
- [ ] Audio interface (Audio Injector or USB sound card)
- [ ] Hookswitch or button (to detect handset on/off hook)
- [ ] Breadboard and jumper wires (for prototyping)
- [ ] Optionally: Arduino Nano (for serial mode)

### Software/Accounts

- [ ] Mac or Linux computer for development
- [ ] 1Password account (for credential management)
- [ ] Git installed
- [ ] Python 3.7+ installed

### Skills Needed

- Basic command line usage
- Basic Python knowledge (helpful but not required)
- Willingness to learn!

---

## Part 1: Local Development Setup

### Step 1: Clone Repository

```bash
# Create project directory
cd ~/Developer  # Or your preferred location

# Clone repository
git clone <your-repo-url> pay-phone
cd pay-phone

# Explore structure
ls -la
```

**What you should see:**
```
pay-phone/
├── payphone/          # Python source code
├── tests/             # Test suite
├── scripts/           # Deployment scripts
├── docs/              # Documentation
├── Makefile           # Common commands
├── requirements.txt   # Python dependencies
└── README.md          # Project overview
```

### Step 2: Install Python Dependencies

```bash
# Install dependencies
make install

# OR manually
pip3 install -r requirements.txt

# Verify installation
pytest --version
# Should output: pytest 6.x.x or higher
```

### Step 3: Run Local Tests

```bash
# Run unit tests (no hardware needed)
make test

# You should see output like:
# tests/unit/test_phone_tree.py::TestPhoneTreeBasics::test_create_simple_tree PASSED
# tests/unit/test_phone_tree.py::TestPhoneTreeBasics::test_create_tree_with_options PASSED
# ...
# ==================== X passed in X.XXs ====================
```

**Congratulations!** Your local development environment is set up.

---

## Part 2: Raspberry Pi Setup

### Step 4: Prepare SD Card

Follow [SD_CARD_SETUP.md](SD_CARD_SETUP.md) to:
1. Flash Raspberry Pi OS Lite to SD card
2. Configure WiFi and SSH (headless mode)
3. First boot and connect

**Quick version:**
```bash
# 1. Download and install Raspberry Pi Imager
open https://www.raspberrypi.com/software/

# 2. Flash SD card with:
#    - OS: Raspberry Pi OS Lite (64-bit)
#    - Hostname: payphone.local
#    - Username: pi
#    - Password: [your password]
#    - WiFi: [your network]
#    - SSH: enabled

# 3. Insert SD card into Pi and power on

# 4. Wait 1-2 minutes, then test connection
ping payphone.local
```

### Step 5: First SSH Connection

```bash
# Connect to Pi
ssh pi@payphone.local

# You'll see:
# Linux payphone 6.1.0-rpi7-rpi-v8 ...
# pi@payphone:~ $

# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Reboot
sudo reboot

# Wait 1 minute, reconnect
ssh pi@payphone.local
```

### Step 6: Run Automated Setup

```bash
# On Pi, create project directory
mkdir -p ~/payphone
cd ~/payphone

# Copy setup script from local machine
# (On your local machine)
scp scripts/setup_pi.sh pi@payphone.local:~/payphone/

# Back on Pi, run setup
chmod +x setup_pi.sh
sudo ./setup_pi.sh

# Follow prompts:
# - Select hardware mode: GPIO (1)
# - Wait for installation to complete

# Reboot for audio changes
sudo reboot
```

**What this did:**
- Installed all dependencies
- Configured audio hardware
- Created systemd service
- Set up directory structure
- Configured GPIO permissions

---

## Part 3: 1Password & Secrets Management

### Step 7: Install 1Password CLI

**On your local machine:**

```bash
# Mac
brew install --cask 1password-cli

# Verify
op --version
```

### Step 8: Create 1Password Items

**1. Sign in to 1Password:**
```bash
eval $(op signin)
```

**2. Create Raspberry Pi credentials:**

Open 1Password app:
- Create new item: "Payphone-Pi"
- Vault: Personal
- Type: Login
- Fields:
  - username: `pi`
  - password: [your Pi password]
  - host: `payphone.local`
  - port: `22`

**3. Test loading secrets:**

```bash
# In your local pay-phone directory
source scripts/load_secrets.sh

# You should see:
# ✓ 1Password CLI authenticated
# ✓ Raspberry Pi credentials loaded
#   Host: pi@payphone.local:22

# Verify environment variables
echo $PI_HOST
# Output: payphone.local

echo $PI_USER
# Output: pi
```

**Troubleshooting:**
- If "Not signed in", run: `eval $(op signin)`
- If item not found, verify item name is exactly "Payphone-Pi"
- See [SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md) for details

---

## Part 4: First Deployment

### Step 9: Deploy Code to Raspberry Pi

```bash
# In your local pay-phone directory

# Load secrets (if not already loaded)
source scripts/load_secrets.sh

# Deploy with full dependency installation
make deploy-full

# You should see:
# ================================================
# Deploying Payphone to Raspberry Pi
# ================================================
# Target: pi@payphone.local
#
# 1. Testing connection to Raspberry Pi...
# ✓ Connected successfully
#
# 2. Creating project directory...
# ✓ Directory created
#
# 3. Syncing source code to Raspberry Pi...
# [rsync output...]
# ✓ Source code synced
#
# 4. Installing dependencies on Raspberry Pi...
# ✓ Dependencies installed
#
# 5. Injecting secrets to Raspberry Pi...
# ✓ Configuration uploaded
#
# ...
#
# ================================================
# Deployment complete!
# ================================================
```

### Step 10: Verify Deployment

```bash
# Check service status
make pi-status

# You should see:
# ● payphone.service - Payphone Interactive System
#    Loaded: loaded (/etc/systemd/system/payphone.service; disabled; ...)
#    Active: inactive (dead)

# Service is installed but not running yet (no hardware wired)
```

**Congratulations!** Your code is now on the Raspberry Pi.

---

## Part 5: Hardware Wiring

### Step 11: Wire the Keypad

**IMPORTANT**: Make sure Pi is powered OFF while wiring!

Follow [GPIO_WIRING.md](GPIO_WIRING.md) for detailed diagrams.

**Quick reference (GPIO mode):**

```
Keypad Rows → Pi GPIO Outputs:
Row 1 → GPIO 5  (Pin 29)
Row 2 → GPIO 6  (Pin 31)
Row 3 → GPIO 13 (Pin 33)
Row 4 → GPIO 19 (Pin 35)

Keypad Columns → Pi GPIO Inputs:
Col 1 → GPIO 26 (Pin 37)
Col 2 → GPIO 20 (Pin 38)
Col 3 → GPIO 21 (Pin 40)

Note: Use 220Ω resistors in series with row outputs for protection
```

**Keypad Layout:**
```
1  2  3
4  5  6
7  8  9
*  0  #
```

### Step 12: Wire the Hook Switch

```
Hook Switch → GPIO 17 (Pin 11)
Hook Switch → Ground (Pin 9)

Hook closed (on-hook) = HIGH (3.3V via pull-up)
Hook open (off-hook) = LOW (0V, grounded)
```

### Step 13: Wire Audio Interface

**For Audio Injector Sound Card:**

```
1. Insert Audio Injector onto GPIO header (pins 1-26)
2. Connect handset to Audio Injector 3.5mm jack:
   - Tip: Speaker + (Yellow wire)
   - Ring: Speaker - (Black wire)
   - Sleeve: Microphone (Green wire + Red wire)
```

**For USB Sound Card:**

```
1. Plug USB sound card into Pi USB port
2. Use TRRS adapter for handset connection
3. Configure ALSA (see SD_CARD_SETUP.md)
```

### Step 14: Test Hardware

```bash
# SSH to Pi
make ssh

# Test keypad (GPIO mode)
sudo python3 ~/payphone/scripts/test_hardware_gpio.py

# Expected output:
# Testing GPIO Keypad...
# Press keys on keypad (Ctrl+C to exit)
# [Press key 1]
# Key detected: 1
# [Press key 5]
# Key detected: 5
# ...

# Press Ctrl+C to exit

# Test audio
speaker-test -t wav -c 1

# You should hear test tones through the handset speaker
# Press Ctrl+C to stop
```

**If tests fail**, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Part 6: Adding Audio Files

### Step 15: Create Audio Files

**You need at least these audio files:**

1. **menu/main.wav** - Main menu prompt
2. **prompts/dial_tone.wav** - Dial tone
3. **prompts/timeout.wav** - Timeout message
4. **prompts/goodbye.wav** - Goodbye message

**Create or download audio files**, then convert to correct format:

```bash
# On your local machine
cd pay-phone/audio_files

# Create directories
mkdir -p menu prompts music

# Convert audio files to WAV format
ffmpeg -i input.mp3 -ar 44100 -ac 1 -sample_fmt s16 menu/main.wav

# Example main menu (use text-to-speech or record yourself):
# "Thank you for calling. Press 1 for the weather,
#  press 2 for the time, or press 3 for music."
```

**Quick start: Generate with text-to-speech:**

```bash
# Mac (using built-in say command)
say "Press 1 for option 1, Press 2 for option 2" -o temp.aiff
ffmpeg -i temp.aiff -ar 44100 -ac 1 menu/main.wav
rm temp.aiff

# OR use online TTS services:
# - https://ttsmaker.com
# - https://www.naturalreaders.com
# - https://cloud.google.com/text-to-speech
```

### Step 16: Copy Audio Files to Pi

```bash
# On your local machine, in pay-phone directory

# Copy audio files during deployment
make deploy

# OR manually copy audio directory
scp -r audio_files/* pi@payphone.local:~/payphone/audio_files/

# Verify files on Pi
make ssh
ls -lh ~/payphone/audio_files/menu/
ls -lh ~/payphone/audio_files/prompts/
```

---

## Part 7: Configure Phone Menu

### Step 17: Customize Menu Structure

**Edit `payphone/main.py` to define your menu:**

```python
def build_phone_tree():
    """Build the phone menu tree structure"""

    # Main menu
    main_menu = PhoneTree(
        audio_file="menu/main.wav",
        options={
            '1': weather_menu,
            '2': time_menu,
            '3': music_menu,
        },
        timeout=30
    )

    # Weather submenu
    weather_menu = PhoneTree(
        audio_file="menu/weather.wav",
        action=get_weather,
        timeout=10
    )

    # Time submenu
    time_menu = PhoneTree(
        audio_file="menu/time.wav",
        action=get_time,
        timeout=10
    )

    # Music submenu
    music_menu = PhoneTree(
        audio_file="menu/music.wav",
        options={
            '1': PhoneTree("music/song1.wav", action=play_song_1),
            '2': PhoneTree("music/song2.wav", action=play_song_2),
        },
        timeout=20
    )

    return main_menu

# Define action functions
def get_weather():
    print("Playing weather information")
    # Add weather API integration here

def get_time():
    print("Playing current time")
    # Add time announcement here

def play_song_1():
    print("Playing song 1")

def play_song_2():
    print("Playing song 2")
```

**Deploy changes:**

```bash
# On local machine
make deploy

# OR just sync code (faster, no full deployment)
source scripts/load_secrets.sh
./scripts/deploy_to_pi.sh --no-restart
make pi-restart
```

---

## Part 8: Start the System

### Step 18: Enable and Start Service

```bash
# Enable service to start on boot
make ssh
sudo systemctl enable payphone.service

# Start service
sudo systemctl start payphone.service

# Check status
sudo systemctl status payphone.service

# You should see:
# ● payphone.service - Payphone Interactive System
#    Loaded: loaded (...)
#    Active: active (running) since ...
#    ...
```

### Step 19: Test the Complete System

**On the Raspberry Pi:**

1. **Pick up handset** (open hook switch)
   - Should hear dial tone

2. **Press key 1**
   - Should play menu/main.wav
   - Menu should navigate to option 1

3. **Press key 2**
   - Should play menu/main.wav
   - Menu should navigate to option 2

4. **Hang up handset** (close hook switch)
   - System should reset
   - Ready for next call

### Step 20: Monitor Logs

**In real-time (from local machine):**

```bash
make pi-logs

# You'll see live output:
# Dec 01 10:30:45 payphone python3[1234]: Starting payphone system...
# Dec 01 10:30:46 payphone python3[1234]: GPIO mode enabled
# Dec 01 10:30:46 payphone python3[1234]: Audio handler initialized
# Dec 01 10:30:47 payphone python3[1234]: Waiting for off-hook event...
# [Pick up handset]
# Dec 01 10:31:00 payphone python3[1234]: Hook: OFF (call started)
# Dec 01 10:31:00 payphone python3[1234]: Playing dial tone
# [Press key 1]
# Dec 01 10:31:05 payphone python3[1234]: Key pressed: 1
# Dec 01 10:31:05 payphone python3[1234]: Navigating to menu option 1
# ...

# Press Ctrl+C to exit log view
```

---

## Part 9: Debugging & Troubleshooting

### Common Issues & Solutions

#### Issue: "No audio output"

```bash
# Check audio device
make ssh
aplay -l

# Test audio
speaker-test -t wav -c 1

# Check volume
alsamixer
# Use arrow keys to adjust, press ESC to exit

# Verify audio files exist
ls -lh ~/payphone/audio_files/menu/
```

#### Issue: "Keypad not responding"

```bash
# Test keypad manually
make ssh
sudo python3 ~/payphone/scripts/test_hardware_gpio.py

# Check GPIO permissions
groups  # Should include 'gpio'

# If not, add to group
sudo usermod -a -G gpio pi
# Log out and back in

# Check pin configuration
cat /etc/payphone/.env | grep PIN
```

#### Issue: "Service won't start"

```bash
# Check service status
make pi-status

# View error logs
make pi-logs

# Common errors:
# - "No module named 'RPi.GPIO'" → Run: make deploy-full
# - "Permission denied" → Check GPIO permissions
# - "Audio file not found" → Copy audio files
# - "Config file missing" → Run: make sync-secrets

# Try running manually to see errors
make ssh
sudo systemctl stop payphone.service
cd ~/payphone
python3 -m payphone.main
# Watch for error messages

# Restart service
sudo systemctl start payphone.service
```

#### Issue: "Deployment fails"

```bash
# Test connection
ssh pi@payphone.local

# Check secrets loaded
echo $PI_HOST  # Should output: payphone.local
echo $PI_USER  # Should output: pi

# If empty, reload secrets
source scripts/load_secrets.sh

# Try deployment again
make deploy
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more solutions.

---

## Part 10: Making Changes

### Typical Development Cycle

```bash
# 1. Make code changes locally
nano payphone/main.py

# 2. Test locally (if possible)
make test

# 3. Load secrets (if new terminal)
source scripts/load_secrets.sh

# 4. Deploy to Pi
make deploy

# 5. Check status
make pi-status

# 6. Monitor logs
make pi-logs

# 7. Test on hardware

# 8. Iterate!
```

### Adding a New Menu Option

**Example: Add a "jokes" menu**

**1. Create audio file:**
```bash
# Record or generate audio
say "Press 1 to hear a joke, Press 2 for another joke" -o temp.aiff
ffmpeg -i temp.aiff -ar 44100 -ac 1 audio_files/menu/jokes.wav

say "Why did the chicken cross the road?" -o temp.aiff
ffmpeg -i temp.aiff -ar 44100 -ac 1 audio_files/menu/joke1.wav
```

**2. Update menu structure in main.py:**
```python
def build_phone_tree():
    main_menu = PhoneTree(
        audio_file="menu/main.wav",
        options={
            '1': weather_menu,
            '2': time_menu,
            '3': music_menu,
            '4': jokes_menu,  # NEW
        }
    )

    jokes_menu = PhoneTree(
        audio_file="menu/jokes.wav",
        options={
            '1': PhoneTree("menu/joke1.wav", action=tell_joke_1),
            '2': PhoneTree("menu/joke2.wav", action=tell_joke_2),
        }
    )

    return main_menu

def tell_joke_1():
    print("Telling joke 1")

def tell_joke_2():
    print("Telling joke 2")
```

**3. Deploy:**
```bash
make deploy
make pi-restart
```

**4. Test:**
Pick up handset → Press 4 → Press 1

---

## Part 11: Advanced Features

### Adding API Integration

**Example: Real weather data**

**1. Get API key (e.g., OpenWeatherMap):**
- Sign up at openweathermap.org
- Get API key

**2. Add to 1Password:**
- Open "Payphone-APIs" item
- Add section: "Weather"
- Add field: api_key = [your key]

**3. Update code:**
```python
import os
import requests

def get_weather():
    api_key = os.getenv('WEATHER_API_KEY')
    if not api_key:
        print("No weather API key configured")
        return

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q=London&appid={api_key}&units=metric"
        response = requests.get(url, timeout=5)
        data = response.json()

        temp = data['main']['temp']
        desc = data['weather'][0]['description']

        # Use TTS to speak weather
        speak_text(f"The weather is {desc} with a temperature of {temp} degrees")

    except Exception as e:
        print(f"Weather API error: {e}")
```

**4. Deploy with new secrets:**
```bash
source scripts/load_secrets.sh
make sync-secrets
make deploy
```

### Adding Voice Recording

**Enable recording in config:**

```bash
# Local machine - edit .env.template
ENABLE_RECORDING=true

# Deploy updated config
source scripts/load_secrets.sh
make sync-secrets
make pi-restart
```

**Use in code:**
```python
from payphone.audio.handler import AudioHandler

def record_message():
    audio = AudioHandler()
    audio.record_audio("recordings/message.wav", duration=30)
    print("Message recorded")
```

---

## Part 12: Production Deployment

### Making it Permanent

**1. Enable auto-start:**
```bash
make ssh
sudo systemctl enable payphone.service
```

**2. Set up log rotation:**
```bash
sudo nano /etc/logrotate.d/payphone

# Add:
/var/log/payphone/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

**3. Configure watchdog (auto-restart on crash):**
The systemd service already has `Restart=always` configured.

**4. Mount hardware permanently:**
- Move from breadboard to permanent enclosure
- Solder connections or use reliable terminal blocks
- Secure Raspberry Pi and components
- Add power backup (optional UPS)

---

## Congratulations!

You've successfully built a complete interactive payphone system!

### What You've Learned

✅ Raspberry Pi setup and configuration
✅ GPIO hardware interfacing
✅ Audio playback on embedded systems
✅ Python development and testing
✅ Secure credential management with 1Password
✅ Remote deployment and debugging
✅ Systemd service configuration
✅ Building interactive menu systems

### Next Steps

- **Customize your menus** - Add your own content and personality
- **Add more features** - Weather, news, jokes, games, AI chat
- **Improve the enclosure** - Build or restore a vintage payphone case
- **Share your project** - Document your build and share online!

### Resources

- **Documentation**: See all docs in `docs/` directory
- **Examples**: Check example code in repository
- **Community**: [Add your community links]
- **Issues**: Report bugs on GitHub

### Need Help?

- Read [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review [DEVELOPMENT.md](DEVELOPMENT.md)
- Check [BEST_PRACTICES.md](BEST_PRACTICES.md)
- Ask in discussions/issues

---

**Happy building! 📞**
