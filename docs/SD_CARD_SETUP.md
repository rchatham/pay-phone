# SD Card Setup Guide

Complete guide for preparing an SD card for your Raspberry Pi payphone system.

## Overview

This guide covers:
1. Downloading and flashing Raspberry Pi OS
2. Configuring headless access (no monitor/keyboard needed)
3. First boot and initial setup
4. Installing the payphone software

## Prerequisites

### Hardware
- **Raspberry Pi 3 or 4** (Pi Zero W also supported but slower)
- **MicroSD card**: 16GB minimum, 32GB recommended, Class 10
- **SD card reader** for your computer
- **Power supply**: Official Raspberry Pi power supply recommended
  - Pi 3: 5V/2.5A
  - Pi 4: 5V/3A (USB-C)
- **Network access**: WiFi or Ethernet cable

### Software (on your computer)
- **Raspberry Pi Imager**: [Download here](https://www.raspberrypi.com/software/)
- **Text editor**: For editing configuration files
- **SSH client**: Terminal (Mac/Linux) or PuTTY (Windows)

---

## Step 1: Download Raspberry Pi OS

### Recommended: Raspberry Pi OS Lite (64-bit)

**Why Lite?**
- Smaller image size (~500MB vs 4GB+)
- Faster boot times
- Lower resource usage
- No desktop environment (not needed for headless operation)
- More storage for audio files

**Download:**
1. Open [Raspberry Pi OS Downloads](https://www.raspberrypi.com/software/operating-systems/)
2. Download **"Raspberry Pi OS Lite (64-bit)"**
3. OR use Raspberry Pi Imager (recommended)

---

## Step 2: Flash SD Card with Raspberry Pi Imager

### Using Raspberry Pi Imager (Recommended)

1. **Install Raspberry Pi Imager**
   - Mac: `brew install --cask raspberry-pi-imager`
   - Or download from: https://www.raspberrypi.com/software/

2. **Launch Imager**
   ```bash
   open /Applications/Raspberry\ Pi\ Imager.app
   ```

3. **Configure Image**
   - **Raspberry Pi Device**: Choose your model (Pi 3, Pi 4, etc.)
   - **Operating System**:
     - Choose OS → Raspberry Pi OS (other) → **Raspberry Pi OS Lite (64-bit)**
   - **Storage**: Select your SD card

4. **Advanced Settings** (IMPORTANT - Click the gear icon ⚙️)

   **General Tab:**
   - ✅ **Set hostname**: `payphone.local` (or your preferred name)
   - ✅ **Set username and password**
     - Username: `pi` (default) or custom
     - Password: Choose a strong password
   - ✅ **Configure wireless LAN**
     - SSID: Your WiFi network name
     - Password: Your WiFi password
     - Country: Your country code (e.g., US)
   - ✅ **Set locale settings**
     - Time zone: Your timezone
     - Keyboard layout: Your layout

   **Services Tab:**
   - ✅ **Enable SSH**
     - Select "Use password authentication"
     - OR "Allow public-key authentication only" (if you have SSH keys)

5. **Write Image**
   - Click **"Write"**
   - Confirm when prompted (this will erase the SD card)
   - Wait for write and verification (5-10 minutes)

6. **Eject SD Card**
   - Imager will notify when complete
   - Safely eject the SD card

---

## Step 3: Manual Configuration (Alternative to Imager Settings)

If you didn't use Raspberry Pi Imager's advanced settings, configure manually:

### 3a. Enable SSH

After flashing, the SD card will have a `boot` partition visible on your computer.

**Create empty SSH file:**
```bash
# Mac/Linux
touch /Volumes/boot/ssh

# Windows (in boot drive)
type nul > D:\ssh
```

### 3b. Configure WiFi

Create `wpa_supplicant.conf` in the boot partition:

```bash
# Mac/Linux
nano /Volumes/boot/wpa_supplicant.conf
```

**File contents:**
```
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="YOUR_WIFI_NAME"
    psk="YOUR_WIFI_PASSWORD"
    key_mgmt=WPA-PSK
}
```

Replace:
- `US` with your country code
- `YOUR_WIFI_NAME` with your WiFi SSID
- `YOUR_WIFI_PASSWORD` with your WiFi password

**Save and eject the SD card.**

---

## Step 4: First Boot

1. **Insert SD card** into Raspberry Pi
2. **Connect power** (use official power supply)
3. **Wait 1-2 minutes** for initial boot
4. **LED indicators:**
   - Red LED: Power
   - Green LED: Activity (should blink during boot)

### Find Your Raspberry Pi on the Network

**Method 1: Hostname (if configured)**
```bash
ping payphone.local
# or
ping raspberrypi.local  # Default hostname
```

**Method 2: IP Scanner**
```bash
# Mac (install with: brew install arp-scan)
sudo arp-scan --localnet | grep -i raspberry

# Linux
sudo nmap -sn 192.168.1.0/24 | grep -i raspberry

# Any OS - check your router's admin page
```

---

## Step 5: Initial SSH Connection

### Connect via SSH

```bash
# Using hostname (preferred)
ssh pi@payphone.local

# Or using IP address
ssh pi@192.168.1.XXX
```

**First connection:**
- You'll see a warning about authenticity - type `yes`
- Enter the password you set (or default: `raspberry`)

**You should see:**
```
Linux payphone 6.1.0-rpi7-rpi-v8 #1 SMP PREEMPT Debian 1:6.1.63-1+rpt1 (2023-11-24) aarch64
...
pi@payphone:~ $
```

---

## Step 6: Update System

Always update before installing software:

```bash
# Update package lists
sudo apt-get update

# Upgrade installed packages
sudo apt-get upgrade -y

# Reboot
sudo reboot
```

Wait 1 minute, then reconnect via SSH.

---

## Step 7: Configure Raspberry Pi

### Run raspi-config

```bash
sudo raspi-config
```

**Recommended settings:**

1. **System Options → Password** (if not already set)
2. **System Options → Hostname** (if not already set)
3. **Localisation Options → Timezone**
4. **Localisation Options → WLAN Country** (required for WiFi)
5. **Interface Options:**
   - ✅ **I2C**: Enable (for future I2C devices)
   - ✅ **SPI**: Enable (for future SPI devices)
6. **Performance Options → GPU Memory**: 16 MB (minimal for headless)
7. **Advanced Options → Expand Filesystem** (auto-expands on first boot, but verify)

**Finish and reboot when prompted.**

---

## Step 8: Install Payphone Software

### Option A: Automated Setup (Recommended)

```bash
# SSH into Pi
ssh pi@payphone.local

# Clone repository (or copy via deployment script)
cd ~
git clone https://github.com/yourusername/pay-phone.git payphone
cd payphone

# Run setup script
chmod +x scripts/setup_pi.sh
sudo ./scripts/setup_pi.sh
```

The setup script will:
- Install all dependencies
- Configure audio
- Setup systemd service
- Configure GPIO permissions

### Option B: Deploy from Local Machine

From your development computer:

```bash
# In your local payphone repository
source scripts/load_secrets.sh
make deploy-full
```

This will:
- Copy code to Pi
- Inject secrets
- Install dependencies
- Configure service

---

## Step 9: Configure Audio Hardware

### For Audio Injector Sound Card

The setup script handles this, but verify:

```bash
# Check if audio overlay is loaded
grep audioinjector /boot/config.txt

# Test audio devices
aplay -l
# Should show: card 1: audioinjector

# Test playback (if you have audio files)
aplay /usr/share/sounds/alsa/Front_Center.wav
```

### For USB Sound Card

```bash
# List audio devices
aplay -l

# Set default in ~/.asoundrc
cat > ~/.asoundrc << EOF
pcm.!default {
    type hw
    card 1
}
ctl.!default {
    type hw
    card 1
}
EOF
```

---

## Step 10: Verify Installation

```bash
# Check service status
sudo systemctl status payphone.service

# View logs
sudo journalctl -u payphone -f

# Test GPIO (if using GPIO mode)
python3 ~/payphone/scripts/test_hardware_gpio.py

# Test serial (if using Arduino mode)
python3 ~/payphone/scripts/test_hardware.py
```

---

## Troubleshooting

### Can't Find Raspberry Pi on Network

1. **Check router DHCP leases** (admin panel)
2. **Connect monitor and keyboard temporarily**
3. **Verify WiFi credentials** in wpa_supplicant.conf
4. **Try Ethernet cable** instead of WiFi
5. **Check power supply** (red LED should be solid)

### Can't SSH - Connection Refused

```bash
# Verify SSH file exists on boot partition
ls /Volumes/boot/ssh  # Mac/Linux

# Or re-create it and reboot Pi
```

### WiFi Not Working

```bash
# Check WiFi status
sudo iwconfig

# Check wpa_supplicant
sudo cat /etc/wpa_supplicant/wpa_supplicant.conf

# Manually connect
sudo wpa_cli -i wlan0 reconfigure

# Check country code is set
sudo raspi-config
# Localisation Options → WLAN Country
```

### Audio Not Working

```bash
# Check audio devices
aplay -l

# Verify config.txt
sudo cat /boot/config.txt | grep audio

# Check ALSA config
cat ~/.asoundrc
```

### Service Won't Start

```bash
# Check logs
sudo journalctl -u payphone -n 50

# Check file permissions
ls -la ~/payphone/payphone/main.py

# Test manually
cd ~/payphone
python3 -m payphone.main
```

---

## Next Steps

1. ✅ **SD card prepared and Pi running**
2. ✅ **SSH access working**
3. ✅ **Payphone software installed**
4. → **Wire up hardware** (see docs/GPIO_WIRING.md)
5. → **Add audio files** (see docs/BEST_PRACTICES.md)
6. → **Configure phone menu** (see docs/DEVELOPMENT.md)
7. → **Test complete system** (see docs/WALKTHROUGH.md)

---

## Quick Reference

### Default Credentials
- **Username**: pi (or custom)
- **Default Password**: raspberry (CHANGE THIS!)

### Network
- **Hostname**: payphone.local (or raspberrypi.local)
- **SSH Port**: 22
- **IP**: Check router or `hostname -I` on Pi

### Useful Commands
```bash
# SSH connect
ssh pi@payphone.local

# Copy files to Pi
scp file.py pi@payphone.local:~/payphone/

# Reboot
sudo reboot

# Shutdown
sudo shutdown -h now

# View logs
sudo journalctl -u payphone -f

# Restart service
sudo systemctl restart payphone.service
```

---

## Additional Resources

- [Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/)
- [SSH Configuration](https://www.raspberrypi.com/documentation/computers/remote-access.html#ssh)
- [WiFi Setup](https://www.raspberrypi.com/documentation/computers/configuration.html#wireless-networking)
- [GPIO Documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio)

---

**Next:** See [DEVELOPMENT.md](DEVELOPMENT.md) for deployment and development workflow.
