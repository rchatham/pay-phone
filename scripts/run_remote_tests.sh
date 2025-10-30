#!/bin/bash
# =============================================================================
# Run Tests on Raspberry Pi
# =============================================================================
# Execute tests remotely on the Raspberry Pi, including hardware tests that
# require actual GPIO/audio hardware.
#
# Usage:
#   # Load credentials first
#   source scripts/load_secrets.sh
#
#   # Run all tests
#   ./scripts/run_remote_tests.sh
#
#   # Run specific test categories
#   ./scripts/run_remote_tests.sh --unit        # Unit tests only
#   ./scripts/run_remote_tests.sh --hardware    # Hardware tests only
#   ./scripts/run_remote_tests.sh --gpio        # GPIO tests only
#   ./scripts/run_remote_tests.sh --audio       # Audio tests only
#
#   # Run with coverage
#   ./scripts/run_remote_tests.sh --coverage
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
TEST_MARKER=""
WITH_COVERAGE=false

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            TEST_MARKER="-m unit"
            shift
            ;;
        --hardware)
            TEST_MARKER="-m hardware"
            shift
            ;;
        --gpio)
            TEST_MARKER="-m gpio"
            shift
            ;;
        --audio)
            TEST_MARKER="-m audio"
            shift
            ;;
        --integration)
            TEST_MARKER="-m integration"
            shift
            ;;
        --coverage)
            WITH_COVERAGE=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--unit|--hardware|--gpio|--audio|--integration] [--coverage]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Running Tests on Raspberry Pi${NC}"
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

# -----------------------------------------------------------------------------
# Build SSH command
# -----------------------------------------------------------------------------

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

if [ -n "$PI_SSH_KEY_PATH" ] && [ -f "$PI_SSH_KEY_PATH" ]; then
    SSH_CMD="ssh -i $PI_SSH_KEY_PATH $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
elif [ -n "$PI_PASSWORD" ]; then
    if command -v sshpass &> /dev/null; then
        SSH_CMD="sshpass -p '$PI_PASSWORD' ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
    else
        echo -e "${YELLOW}WARNING: sshpass not installed, will prompt for password${NC}"
        SSH_CMD="ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
    fi
else
    SSH_CMD="ssh $SSH_OPTS -p ${PI_PORT:-22} ${PI_USER}@${PI_HOST}"
fi

# -----------------------------------------------------------------------------
# Test connection
# -----------------------------------------------------------------------------

echo "Connecting to ${PI_USER}@${PI_HOST}..."

if ! $SSH_CMD "echo 'Connected'" &>/dev/null; then
    echo -e "${RED}ERROR: Cannot connect to Raspberry Pi${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Connected${NC}"
echo ""

# -----------------------------------------------------------------------------
# Build pytest command
# -----------------------------------------------------------------------------

PYTEST_CMD="cd ~/payphone && python3 -m pytest"

if [ -n "$TEST_MARKER" ]; then
    PYTEST_CMD="$PYTEST_CMD $TEST_MARKER"
fi

if [ "$WITH_COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=payphone --cov-report=term-missing"
fi

PYTEST_CMD="$PYTEST_CMD -v"

# -----------------------------------------------------------------------------
# Ensure pytest is installed
# -----------------------------------------------------------------------------

echo "Checking test dependencies..."

if ! $SSH_CMD "python3 -m pytest --version" &>/dev/null; then
    echo -e "${YELLOW}pytest not found, installing test dependencies...${NC}"
    $SSH_CMD "cd ~/payphone && pip3 install -r requirements.txt"
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ pytest available${NC}"
fi

echo ""

# -----------------------------------------------------------------------------
# Run tests
# -----------------------------------------------------------------------------

echo -e "${BLUE}Running tests...${NC}"
echo -e "${YELLOW}Command: $PYTEST_CMD${NC}"
echo ""

# Run tests and capture exit code
set +e
$SSH_CMD "$PYTEST_CMD"
TEST_EXIT_CODE=$?
set -e

echo ""

# -----------------------------------------------------------------------------
# Download coverage report if generated
# -----------------------------------------------------------------------------

if [ "$WITH_COVERAGE" = true ] && [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "Downloading coverage report..."

    # Build SCP command
    if [ -n "$PI_SSH_KEY_PATH" ] && [ -f "$PI_SSH_KEY_PATH" ]; then
        SCP_CMD="scp -i $PI_SSH_KEY_PATH $SSH_OPTS -P ${PI_PORT:-22}"
    elif [ -n "$PI_PASSWORD" ] && command -v sshpass &> /dev/null; then
        SCP_CMD="sshpass -p '$PI_PASSWORD' scp $SSH_OPTS -P ${PI_PORT:-22}"
    else
        SCP_CMD="scp $SSH_OPTS -P ${PI_PORT:-22}"
    fi

    # Download .coverage file if it exists
    if $SSH_CMD "[ -f ~/payphone/.coverage ]"; then
        $SCP_CMD "${PI_USER}@${PI_HOST}:~/payphone/.coverage" .coverage.pi
        echo -e "${GREEN}✓ Coverage data downloaded to .coverage.pi${NC}"
        echo "  View with: coverage report --data-file=.coverage.pi"
    fi
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

echo -e "${BLUE}================================================${NC}"

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo -e "${RED}Tests failed (exit code: $TEST_EXIT_CODE)${NC}"
fi

echo -e "${BLUE}================================================${NC}"
echo ""

exit $TEST_EXIT_CODE
