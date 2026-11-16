#!/bin/bash
# =============================================================================
# Automated Raspberry Pi setup script for payphone project
# =============================================================================
# Supports: Raspberry Pi Zero W, Pi 3, Pi 4
# Configures: GPIO/Serial, Audio, Systemd service, Permissions
#
# Usage:
#   sudo ./scripts/setup_pi.sh
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Payphone Raspberry Pi Setup ===${NC}"
echo ""

# Detect Raspberry Pi model
PI_MODEL=$(cat /proc/cpuinfo | grep "Model" | cut -d ':' -f2 | xargs)
echo -e "${GREEN}Detected: ${PI_MODEL}${NC}"
echo ""

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-pygame \
    python3-serial \
    python3-numpy \
    python3-rpi.gpio \
    alsa-utils \
    portaudio19-dev \
    libsndfile1 \
    mpg321 \
    git \
    arduino \
    arduino-mk \
    build-essential

# Install Python packages
echo "Installing Python packages..."
pip3 install --user --break-system-packages \
    pyserial \
    pygame \
    RPi.GPIO \
    pytest \
    pytest-cov \
    mock \
    sounddevice \
    soundfile

# Configure audio for Audio Injector
echo "Configuring audio..."
if grep -q "dtoverlay=audioinjector-wm8731-audio" /boot/config.txt; then
    echo "Audio Injector already configured"
else
    echo "dtoverlay=audioinjector-wm8731-audio" | sudo tee -a /boot/config.txt
    echo "Audio Injector configured - reboot required"
fi

# Disable onboard audio
sudo sed -i 's/dtparam=audio=on/#dtparam=audio=on/g' /boot/config.txt

# Create audio configuration.
# dmix (playback) and dsnoop (capture) let several programs open the card at
# once: pygame plays prompts while baresip (VoIP) plays and records the call,
# and LAM can record. `plug` on top converts each program's rate/channels.
# Override for other cards, e.g. a mono USB dongle on card 2:
#   AUDIO_CARD=2 AUDIO_CAPTURE_CHANNELS=1 ./scripts/setup_pi.sh
AUDIO_CARD=${AUDIO_CARD:-1}
AUDIO_RATE=${AUDIO_RATE:-48000}
AUDIO_PLAYBACK_CHANNELS=${AUDIO_PLAYBACK_CHANNELS:-2}
AUDIO_CAPTURE_CHANNELS=${AUDIO_CAPTURE_CHANNELS:-2}

if [ -f /etc/asound.conf ] && ! grep -q "payphone_dmix" /etc/asound.conf; then
    sudo cp /etc/asound.conf "/etc/asound.conf.bak.$(date +%Y%m%d%H%M%S)"
    echo "Backed up previous /etc/asound.conf"
fi

sudo tee /etc/asound.conf > /dev/null <<EOF
# Written by scripts/setup_pi.sh: shared access to sound card ${AUDIO_CARD}.
pcm.payphone_dmix {
    type dmix
    ipc_key 1024
    ipc_perm 0660
    ipc_gid audio
    slave {
        pcm "hw:${AUDIO_CARD},0"
        rate ${AUDIO_RATE}
        channels ${AUDIO_PLAYBACK_CHANNELS}
        period_size 1024
        buffer_size 4096
    }
}
pcm.payphone_dsnoop {
    type dsnoop
    ipc_key 1025
    ipc_perm 0660
    ipc_gid audio
    slave {
        pcm "hw:${AUDIO_CARD},0"
        rate ${AUDIO_RATE}
        channels ${AUDIO_CAPTURE_CHANNELS}
        period_size 1024
        buffer_size 4096
    }
}
pcm.payphone_duplex {
    type asym
    playback.pcm "payphone_dmix"
    capture.pcm "payphone_dsnoop"
}
pcm.!default {
    type plug
    slave.pcm "payphone_duplex"
}
ctl.!default {
    type hw
    card ${AUDIO_CARD}
}
EOF
echo "Audio: card ${AUDIO_CARD} shared via dmix/dsnoop at ${AUDIO_RATE} Hz"

# Ask user about hardware mode
echo "Select hardware mode:"
echo "1) GPIO (Direct Raspberry Pi connection)"
echo "2) Serial (Arduino connection)"
read -p "Enter choice (1 or 2): " mode_choice

if [ "$mode_choice" = "2" ]; then
    # Setup Arduino CLI
    if ! command -v arduino-cli &> /dev/null; then
        echo "Installing Arduino CLI..."
        curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
        sudo mv bin/arduino-cli /usr/local/bin/
    fi

    # Configure Arduino
    arduino-cli core update-index
    arduino-cli core install arduino:avr
    
    # Set environment variable
    echo "export USE_GPIO=false" >> ~/.bashrc
else
    echo "GPIO mode selected - no Arduino required"
    # Set environment variable
    echo "export USE_GPIO=true" >> ~/.bashrc
    
    # Enable GPIO permissions for pi user
    sudo usermod -a -G gpio pi
fi

# Create configuration directory
echo -e "${BLUE}Creating configuration directory...${NC}"
sudo mkdir -p /etc/payphone
sudo chown ${USER}:${USER} /etc/payphone

# Create systemd service
echo -e "${BLUE}Creating systemd service...${NC}"
sudo tee /etc/systemd/system/payphone.service > /dev/null <<EOF
[Unit]
Description=Payphone Interactive System
After=network.target sound.target

[Service]
Type=simple
User=${USER}
Group=${USER}
WorkingDirectory=/home/${USER}/payphone
Environment="PYTHONPATH=/home/${USER}/payphone"
EnvironmentFile=-/etc/payphone/.env
ExecStart=/usr/bin/python3 -m payphone.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Create service override directory for environment file
sudo mkdir -p /etc/systemd/system/payphone.service.d

# Optional: baresip SIP client for VoIP calls (payphone/voip/).
# Answer the prompt, or set INSTALL_BARESIP=yes|no to skip it.
if [ -z "$INSTALL_BARESIP" ]; then
    read -p "Install baresip for VoIP (SIP) calls? (y/N): " baresip_choice
    case "$baresip_choice" in [Yy]*) INSTALL_BARESIP=yes ;; *) INSTALL_BARESIP=no ;; esac
fi

if [ "$INSTALL_BARESIP" = "yes" ]; then
    echo -e "${BLUE}Installing baresip...${NC}"
    # baresip-core has the ALSA, G.711, account, menu, ctrl_tcp and mwi modules
    # without the GTK/video dependencies of the full `baresip` package.
    sudo apt-get install -y baresip-core || sudo apt-get install -y baresip

    BARESIP_DIR=/home/${USER}/payphone/.baresip
    mkdir -p "$BARESIP_DIR"
    chmod 700 "$BARESIP_DIR"

    # The config is rendered from VOIP_* in /etc/payphone/.env before every
    # start, so `make deploy` (inject_secrets.sh) + restart applies new settings.
    # ctrl_tcp listens on 127.0.0.1:4444 only; payphone connects to it.
    sudo tee /etc/systemd/system/baresip.service > /dev/null <<EOF
[Unit]
Description=baresip SIP client for the payphone (controlled over ctrl_tcp)
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
Group=${USER}
SupplementaryGroups=audio
WorkingDirectory=/home/${USER}/payphone
Environment="PYTHONPATH=/home/${USER}/payphone"
EnvironmentFile=-/etc/payphone/.env
ExecStartPre=/usr/bin/python3 -m payphone.voip.account --config-dir ${BARESIP_DIR}
ExecStart=/usr/bin/baresip -f ${BARESIP_DIR}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
    echo -e "${GREEN}✓ baresip installed; baresip.service created (not enabled yet)${NC}"
fi

# Create directories
echo -e "${BLUE}Creating project directories...${NC}"
mkdir -p ~/payphone/audio_files/{menu,prompts,music}
mkdir -p ~/payphone/logs
sudo mkdir -p /var/log/payphone
sudo chown ${USER}:${USER} /var/log/payphone

# Set permissions
if [ -d ~/payphone/scripts ]; then
    chmod +x ~/payphone/scripts/*.sh 2>/dev/null || true
    chmod +x ~/payphone/scripts/*.py 2>/dev/null || true
fi

# Reload systemd
echo -e "${BLUE}Reloading systemd...${NC}"
sudo systemctl daemon-reload

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""

if [ "$mode_choice" = "2" ]; then
    echo "1. Upload Arduino sketch:"
    echo "   arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:nano arduino/payphone_controller"
    echo ""
    echo "2. Run hardware tests:"
    echo "   python3 ~/payphone/scripts/test_hardware.py"
else
    echo "1. Wire your payphone according to:"
    echo "   docs/GPIO_WIRING.md"
    echo ""
    echo "2. Run hardware tests:"
    echo "   sudo python3 ~/payphone/scripts/test_hardware_gpio.py"
fi

echo ""
echo "3. Check microphone input and LAM recording:"
echo "   arecord -l"
echo "   arecord -D default --format S16_LE -V mono --rate 44100 -c1 test.wav"
echo "   aplay -D default test.wav"
echo "   (use the 'default' device: hw:${AUDIO_CARD},0 is held by dmix/dsnoop)"
echo "   ENABLE_RECORDING=true RECORDING_DEVICE=0 python3 ~/payphone/scripts/test_lam_recording.py"
echo ""
echo "4. Add audio files to:"
echo "   ~/payphone/audio_files/"
echo ""
echo "5. Deploy configuration from your local machine:"
echo "   make deploy"
echo ""
echo "6. Enable and start service:"
echo "   sudo systemctl enable payphone.service"
echo "   sudo systemctl start payphone.service"
echo ""
echo "7. Check status:"
echo "   sudo systemctl status payphone.service"
echo ""

if [ "$INSTALL_BARESIP" = "yes" ]; then
    echo "8. VoIP: set VOIP_SIP_URI / VOIP_PASSWORD (1Password item Payphone-VoIP,"
    echo "   see docs/SECRETS_MANAGEMENT.md), run 'make deploy', then:"
    echo "   sudo systemctl enable --now baresip.service"
    echo "   journalctl -u baresip -f      # look for a successful REGISTER"
    echo ""
fi
echo -e "${YELLOW}IMPORTANT: Reboot required for audio changes to take effect${NC}"
echo "   sudo reboot"
echo ""