#!/bin/bash
# =============================================================================
# Load Secrets from 1Password CLI
# =============================================================================
# This script loads secrets from 1Password on your LOCAL MACHINE and exports
# them as environment variables for use in deployment scripts.
#
# Usage:
#   source scripts/load_secrets.sh
#
# Requirements:
#   - 1Password CLI (op) installed and authenticated
#   - Payphone secrets stored in 1Password
#
# Setup:
#   1. Install 1Password CLI: https://developer.1password.com/docs/cli/get-started/
#   2. Sign in: op signin
#   3. Create items in 1Password for your secrets
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Loading secrets from 1Password...${NC}"

# -----------------------------------------------------------------------------
# Check 1Password CLI is installed and authenticated
# -----------------------------------------------------------------------------

if ! command -v op &> /dev/null; then
    echo -e "${RED}ERROR: 1Password CLI (op) is not installed${NC}"
    echo "Install it from: https://developer.1password.com/docs/cli/get-started/"
    return 1
fi

if ! op whoami &> /dev/null; then
    echo -e "${YELLOW}WARNING: Not signed in to 1Password${NC}"
    echo "Sign in with: eval \$(op signin)"
    return 1
fi

echo -e "${GREEN}✓ 1Password CLI authenticated${NC}"

# -----------------------------------------------------------------------------
# Load Raspberry Pi SSH Credentials
# -----------------------------------------------------------------------------

echo "Loading Raspberry Pi SSH credentials..."

# Update these references to match your 1Password structure
# Format: op://vault/item/field
export PI_HOST=$(op read "op://Personal/Payphone-Pi/host" 2>/dev/null || echo "raspberrypi.local")
export PI_PORT=$(op read "op://Personal/Payphone-Pi/port" 2>/dev/null || echo "22")
export PI_USER=$(op read "op://Personal/Payphone-Pi/username" 2>/dev/null || echo "pi")
export PI_PASSWORD=$(op read "op://Personal/Payphone-Pi/password" 2>/dev/null || echo "")

# SSH Key (optional)
PI_SSH_KEY_REFERENCE="op://Personal/Payphone-Pi/ssh_private_key"
if op item get "Payphone-Pi" --vault Personal &>/dev/null; then
    # Save SSH key to temp file if it exists
    export PI_SSH_KEY_PATH="/tmp/payphone_ssh_key"
    op read "$PI_SSH_KEY_REFERENCE" > "$PI_SSH_KEY_PATH" 2>/dev/null || true
    if [ -f "$PI_SSH_KEY_PATH" ]; then
        chmod 600 "$PI_SSH_KEY_PATH"
        echo -e "${GREEN}✓ SSH key loaded${NC}"
    fi
fi

if [ -n "$PI_USER" ] && [ -n "$PI_HOST" ]; then
    echo -e "${GREEN}✓ Raspberry Pi credentials loaded${NC}"
    echo "  Host: $PI_USER@$PI_HOST:$PI_PORT"
else
    echo -e "${YELLOW}⚠ No Pi credentials found in 1Password${NC}"
    echo "  Create an item named 'Payphone-Pi' in your Personal vault with:"
    echo "    - username: pi"
    echo "    - password: your_pi_password"
    echo "    - host: raspberrypi.local"
    echo "    - port: 22"
fi

# -----------------------------------------------------------------------------
# Load Future API Keys (Optional - create these items as needed)
# -----------------------------------------------------------------------------

echo "Loading API keys..."

# OpenAI API Key (for AI features)
export OPENAI_API_KEY=$(op read "op://Personal/Payphone-APIs/OpenAI/api_key" 2>/dev/null || echo "")
[ -n "$OPENAI_API_KEY" ] && echo -e "${GREEN}✓ OpenAI API key loaded${NC}"

# Twilio API (for telephony features)
export TWILIO_ACCOUNT_SID=$(op read "op://Personal/Payphone-APIs/Twilio/account_sid" 2>/dev/null || echo "")
export TWILIO_AUTH_TOKEN=$(op read "op://Personal/Payphone-APIs/Twilio/auth_token" 2>/dev/null || echo "")
export TWILIO_PHONE_NUMBER=$(op read "op://Personal/Payphone-APIs/Twilio/phone_number" 2>/dev/null || echo "")
[ -n "$TWILIO_ACCOUNT_SID" ] && echo -e "${GREEN}✓ Twilio API credentials loaded${NC}"

# Weather API
export WEATHER_API_KEY=$(op read "op://Personal/Payphone-APIs/Weather/api_key" 2>/dev/null || echo "")
[ -n "$WEATHER_API_KEY" ] && echo -e "${GREEN}✓ Weather API key loaded${NC}"

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Secrets loaded successfully!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Loaded environment variables:"
echo "  PI_HOST: ${PI_HOST}"
echo "  PI_USER: ${PI_USER}"
echo "  PI_PORT: ${PI_PORT}"
[ -n "$PI_PASSWORD" ] && echo "  PI_PASSWORD: ****"
[ -f "$PI_SSH_KEY_PATH" ] && echo "  PI_SSH_KEY_PATH: ${PI_SSH_KEY_PATH}"
[ -n "$OPENAI_API_KEY" ] && echo "  OPENAI_API_KEY: ****"
[ -n "$TWILIO_ACCOUNT_SID" ] && echo "  TWILIO_ACCOUNT_SID: ****"
[ -n "$WEATHER_API_KEY" ] && echo "  WEATHER_API_KEY: ****"
echo ""
echo "You can now run deployment scripts:"
echo "  ./scripts/deploy_to_pi.sh"
echo "  ./scripts/ssh_to_pi.sh"
echo "  ./scripts/sync_config.sh"
echo ""
