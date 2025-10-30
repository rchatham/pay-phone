#!/bin/bash
# =============================================================================
# Sync Configuration to Raspberry Pi
# =============================================================================
# Syncs only the configuration/secrets to the Raspberry Pi without deploying
# code. Useful for updating API keys or settings without a full deployment.
#
# Usage:
#   # Load secrets from 1Password
#   source scripts/load_secrets.sh
#
#   # Sync configuration
#   ./scripts/sync_config.sh
#
#   # Options
#   ./scripts/sync_config.sh --restart    # Restart service after sync
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse options
RESTART_SERVICE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --restart)
            RESTART_SERVICE=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Syncing Configuration to Raspberry Pi${NC}"
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
# Inject secrets
# -----------------------------------------------------------------------------

echo "Syncing configuration..."

./scripts/inject_secrets.sh

# -----------------------------------------------------------------------------
# Restart service if requested
# -----------------------------------------------------------------------------

if [ "$RESTART_SERVICE" = true ]; then
    echo ""
    echo "Restarting payphone service..."

    # Build SSH command
    SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

    if [ -n "$PI_SSH_KEY_PATH" ] && [ -f "$PI_SSH_KEY_PATH" ]; then
        SSH_CMD="ssh -i $PI_SSH_KEY_PATH $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
    elif [ -n "$PI_PASSWORD" ]; then
        if command -v sshpass &> /dev/null; then
            SSH_CMD="sshpass -p '$PI_PASSWORD' ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
        else
            SSH_CMD="ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
        fi
    else
        SSH_CMD="ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
    fi

    $SSH_CMD "sudo systemctl restart payphone.service"
    echo -e "${GREEN}✓ Service restarted${NC}"

    # Check status
    sleep 2
    if $SSH_CMD "sudo systemctl is-active --quiet payphone.service"; then
        echo -e "${GREEN}✓ Service is running${NC}"
    else
        echo -e "${YELLOW}⚠ Service may not be running${NC}"
        echo "Check status: ./scripts/ssh_to_pi.sh 'sudo systemctl status payphone'"
    fi
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Configuration synced successfully!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Configuration file: /etc/payphone/.env on ${PI_HOST}"
echo ""

if [ "$RESTART_SERVICE" = false ]; then
    echo "Note: Service not restarted. Restart to apply changes:"
    echo "  ./scripts/sync_config.sh --restart"
    echo "  OR"
    echo "  ./scripts/ssh_to_pi.sh 'sudo systemctl restart payphone'"
    echo ""
fi
