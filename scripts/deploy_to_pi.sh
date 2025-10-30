#!/bin/bash
# =============================================================================
# Deploy Payphone to Raspberry Pi
# =============================================================================
# This script deploys the payphone codebase to a Raspberry Pi, including:
#   - Syncing source code
#   - Injecting secrets from 1Password
#   - Installing dependencies
#   - Restarting the service
#
# Usage:
#   # First time: load secrets from 1Password
#   source scripts/load_secrets.sh
#
#   # Deploy
#   ./scripts/deploy_to_pi.sh
#
#   # Options
#   ./scripts/deploy_to_pi.sh --no-restart    # Don't restart service after deploy
#   ./scripts/deploy_to_pi.sh --skip-secrets  # Skip secret injection
#   ./scripts/deploy_to_pi.sh --full          # Full deploy with dependencies
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse options
NO_RESTART=false
SKIP_SECRETS=false
FULL_DEPLOY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-restart)
            NO_RESTART=true
            shift
            ;;
        --skip-secrets)
            SKIP_SECRETS=true
            shift
            ;;
        --full)
            FULL_DEPLOY=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Deploying Payphone to Raspberry Pi${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# -----------------------------------------------------------------------------
# Check required environment variables
# -----------------------------------------------------------------------------

if [ -z "$PI_HOST" ] || [ -z "$PI_USER" ]; then
    echo -e "${RED}ERROR: PI_HOST and PI_USER must be set${NC}"
    echo "Load secrets first: source scripts/load_secrets.sh"
    exit 1
fi

echo -e "${GREEN}Target: ${PI_USER}@${PI_HOST}${NC}"
echo ""

# -----------------------------------------------------------------------------
# Build SSH/SCP commands
# -----------------------------------------------------------------------------

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

if [ -n "$PI_SSH_KEY_PATH" ] && [ -f "$PI_SSH_KEY_PATH" ]; then
    SSH_CMD="ssh -i $PI_SSH_KEY_PATH $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
    RSYNC_CMD="rsync -avz --delete -e 'ssh -i $PI_SSH_KEY_PATH $SSH_OPTS -p ${PI_PORT:-22}'"
elif [ -n "$PI_PASSWORD" ]; then
    if command -v sshpass &> /dev/null; then
        SSH_CMD="sshpass -p '$PI_PASSWORD' ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
        RSYNC_CMD="sshpass -p '$PI_PASSWORD' rsync -avz --delete -e 'ssh $SSH_OPTS -p ${PI_PORT:-22}'"
    else
        echo -e "${YELLOW}WARNING: sshpass not installed, will prompt for password${NC}"
        SSH_CMD="ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
        RSYNC_CMD="rsync -avz --delete -e 'ssh $SSH_OPTS -p ${PI_PORT:-22}'"
    fi
else
    SSH_CMD="ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
    RSYNC_CMD="rsync -avz --delete -e 'ssh $SSH_OPTS -p ${PI_PORT:-22}'"
fi

# -----------------------------------------------------------------------------
# Test connection
# -----------------------------------------------------------------------------

echo "1. Testing connection to Raspberry Pi..."

if ! $SSH_CMD "echo 'Connection successful'" &>/dev/null; then
    echo -e "${RED}ERROR: Cannot connect to Raspberry Pi${NC}"
    echo "Check your credentials and network connection"
    exit 1
fi

echo -e "${GREEN}✓ Connected successfully${NC}"
echo ""

# -----------------------------------------------------------------------------
# Create project directory on Pi
# -----------------------------------------------------------------------------

echo "2. Creating project directory..."

$SSH_CMD "mkdir -p ~/payphone"

echo -e "${GREEN}✓ Directory created${NC}"
echo ""

# -----------------------------------------------------------------------------
# Sync source code
# -----------------------------------------------------------------------------

echo "3. Syncing source code to Raspberry Pi..."

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

# Sync files (excluding .git, __pycache__, etc.)
eval $RSYNC_CMD \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='htmlcov' \
    --exclude='.coverage' \
    --exclude='.env' \
    --exclude='audio_files/*.wav' \
    --exclude='audio_files/*.mp3' \
    --exclude='venv' \
    --exclude='.venv' \
    ./ ${PI_USER}@${PI_HOST}:~/payphone/

echo -e "${GREEN}✓ Source code synced${NC}"
echo ""

# -----------------------------------------------------------------------------
# Install/update dependencies (if --full flag)
# -----------------------------------------------------------------------------

if [ "$FULL_DEPLOY" = true ]; then
    echo "4. Installing dependencies on Raspberry Pi..."

    $SSH_CMD "cd ~/payphone && pip3 install -r requirements.txt"

    echo -e "${GREEN}✓ Dependencies installed${NC}"
    echo ""
else
    echo "4. Skipping dependency installation (use --full to install)"
    echo ""
fi

# -----------------------------------------------------------------------------
# Inject secrets
# -----------------------------------------------------------------------------

if [ "$SKIP_SECRETS" = false ]; then
    echo "5. Injecting secrets to Raspberry Pi..."

    ./scripts/inject_secrets.sh

    echo ""
else
    echo "5. Skipping secret injection"
    echo ""
fi

# -----------------------------------------------------------------------------
# Create audio directories
# -----------------------------------------------------------------------------

echo "6. Setting up audio directories..."

$SSH_CMD "mkdir -p ~/payphone/audio_files/{menu,prompts,music}"

echo -e "${GREEN}✓ Audio directories created${NC}"
echo ""

# -----------------------------------------------------------------------------
# Create log directory
# -----------------------------------------------------------------------------

echo "7. Setting up log directory..."

$SSH_CMD "sudo mkdir -p /var/log/payphone && sudo chown ${PI_USER}:${PI_USER} /var/log/payphone"

echo -e "${GREEN}✓ Log directory created${NC}"
echo ""

# -----------------------------------------------------------------------------
# Set permissions
# -----------------------------------------------------------------------------

echo "8. Setting file permissions..."

$SSH_CMD "chmod +x ~/payphone/payphone/main.py"
$SSH_CMD "chmod +x ~/payphone/scripts/*.sh"

echo -e "${GREEN}✓ Permissions set${NC}"
echo ""

# -----------------------------------------------------------------------------
# Restart service (if not --no-restart)
# -----------------------------------------------------------------------------

if [ "$NO_RESTART" = false ]; then
    echo "9. Restarting payphone service..."

    # Check if service exists
    if $SSH_CMD "sudo systemctl list-unit-files | grep -q payphone.service"; then
        $SSH_CMD "sudo systemctl restart payphone.service"
        echo -e "${GREEN}✓ Service restarted${NC}"

        # Wait a moment and check status
        sleep 2
        if $SSH_CMD "sudo systemctl is-active --quiet payphone.service"; then
            echo -e "${GREEN}✓ Service is running${NC}"
        else
            echo -e "${YELLOW}⚠ Service may not be running${NC}"
            echo "Check status: ssh ${PI_USER}@${PI_HOST} 'sudo systemctl status payphone'"
        fi
    else
        echo -e "${YELLOW}⚠ Service not yet installed${NC}"
        echo "Run setup: ssh ${PI_USER}@${PI_HOST} 'cd ~/payphone && sudo ./scripts/setup_pi.sh'"
    fi
    echo ""
else
    echo "9. Skipping service restart"
    echo ""
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Deployed to: ${PI_USER}@${PI_HOST}:~/payphone"
echo ""
echo "Useful commands:"
echo "  SSH into Pi:        ./scripts/ssh_to_pi.sh"
echo "  Check status:       ssh ${PI_USER}@${PI_HOST} 'sudo systemctl status payphone'"
echo "  View logs:          ssh ${PI_USER}@${PI_HOST} 'sudo journalctl -u payphone -f'"
echo "  Run tests:          ./scripts/run_remote_tests.sh"
echo "  Restart service:    ssh ${PI_USER}@${PI_HOST} 'sudo systemctl restart payphone'"
echo ""
