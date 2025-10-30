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
    mock

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

# Create audio configuration
sudo tee /etc/asound.conf > /dev/null <<EOF
pcm.!default {
    type hw
    card 1
}
ctl.!default {
    type hw
    card 1
}
EOF

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
echo "3. Add audio files to:"
echo "   ~/payphone/audio_files/"
echo ""
echo "4. Deploy configuration from your local machine:"
echo "   make deploy"
echo ""
echo "5. Enable and start service:"
echo "   sudo systemctl enable payphone.service"
echo "   sudo systemctl start payphone.service"
echo ""
echo "6. Check status:"
echo "   sudo systemctl status payphone.service"
echo ""
echo -e "${YELLOW}IMPORTANT: Reboot required for audio changes to take effect${NC}"
echo "   sudo reboot"
echo ""