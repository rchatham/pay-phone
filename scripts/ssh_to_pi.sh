#!/bin/bash
# =============================================================================
# SSH to Raspberry Pi
# =============================================================================
# Quick SSH access to your Raspberry Pi using credentials from 1Password
#
# Usage:
#   # Load credentials first
#   source scripts/load_secrets.sh
#
#   # Connect
#   ./scripts/ssh_to_pi.sh
#
#   # Or run a command directly
#   ./scripts/ssh_to_pi.sh "ls -la ~/payphone"
#   ./scripts/ssh_to_pi.sh "sudo systemctl status payphone"
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Check required environment variables
# -----------------------------------------------------------------------------

if [ -z "$PI_HOST" ] || [ -z "$PI_USER" ]; then
    echo -e "${RED}ERROR: PI_HOST and PI_USER must be set${NC}"
    echo "Load secrets first: source scripts/load_secrets.sh"
    exit 1
fi

# -----------------------------------------------------------------------------
# Build SSH command
# -----------------------------------------------------------------------------

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

if [ -n "$PI_SSH_KEY_PATH" ] && [ -f "$PI_SSH_KEY_PATH" ]; then
    # Use SSH key
    SSH_CMD="ssh -i $PI_SSH_KEY_PATH $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
elif [ -n "$PI_PASSWORD" ]; then
    # Use password (with sshpass if available)
    if command -v sshpass &> /dev/null; then
        SSH_CMD="sshpass -p '$PI_PASSWORD' ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
    else
        echo -e "${YELLOW}WARNING: sshpass not installed, will prompt for password${NC}"
        SSH_CMD="ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
    fi
else
    # No credentials, will prompt
    SSH_CMD="ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
fi

# -----------------------------------------------------------------------------
# Connect
# -----------------------------------------------------------------------------

if [ $# -gt 0 ]; then
    # Run command and exit
    echo -e "${GREEN}Running on ${PI_USER}@${PI_HOST}: $@${NC}"
    $SSH_CMD "$@"
else
    # Interactive session
    echo -e "${GREEN}Connecting to ${PI_USER}@${PI_HOST}...${NC}"
    echo -e "${YELLOW}Tip: Exit with 'exit' or Ctrl+D${NC}"
    echo ""
    $SSH_CMD
fi
