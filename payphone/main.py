#!/usr/bin/env python3
import logging
import signal
import sys
import os
import subprocess
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def _kill_existing_instances():
    """Kill any existing payphone instances and stop systemd service before starting"""
    try:
        # First, check if systemd service is running and stop it
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'payphone.service'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip() == 'active':
                print("Payphone systemd service is running. Stopping it...")
                stop_result = subprocess.run(
                    ['sudo', 'systemctl', 'stop', 'payphone.service'],
                    capture_output=True,
                    text=True
                )

                if stop_result.returncode == 0:
                    print("✓ Systemd service stopped")
                    time.sleep(1)  # Give service time to stop
                else:
                    print(f"⚠ Warning: Could not stop systemd service: {stop_result.stderr}")
                    print("  You may need to run: sudo systemctl stop payphone.service")
        except FileNotFoundError:
            # systemctl not available (not running on systemd)
            pass

        # Get current PID
        current_pid = os.getpid()

        # Find all remaining payphone.main processes
        result = subprocess.run(
            ['pgrep', '-f', 'payphone.main'],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            killed_any = False

            for pid_str in pids:
                try:
                    pid = int(pid_str)

                    # Don't kill ourselves
                    if pid == current_pid:
                        continue

                    # Kill the existing instance
                    print(f"Found remaining payphone instance (PID {pid}), stopping it...")
                    os.kill(pid, signal.SIGTERM)
                    killed_any = True

                    # Wait a bit for graceful shutdown
                    time.sleep(0.5)

                    # Force kill if still running
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Already dead

                except (ValueError, ProcessLookupError):
                    pass
                except Exception as e:
                    logger.warning(f"Failed to kill PID {pid}: {e}")

            if killed_any:
                print("✓ Previous instances stopped")
                time.sleep(1)  # Give system time to release resources

    except FileNotFoundError:
        # pgrep not available, skip check
        logger.debug("pgrep command not available")
    except Exception as e:
        logger.warning(f"Failed to check for existing instances: {e}")

# Import the BIOS bootloader system
# This will handle launching other phone systems
try:
    from payphone.bios import BIOSBootloader as PhoneSystem
except ImportError:
    # Fallback to direct import
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from payphone.bios import BIOSBootloader as PhoneSystem

# Legacy mode: Allow direct system launch via environment variable
# Set PAYPHONE_LEGACY_MODE=information_booth to bypass BIOS
legacy_mode = os.environ.get('PAYPHONE_LEGACY_MODE')

if legacy_mode:
    logger.info(f"Legacy mode enabled: {legacy_mode}")
    try:
        from phone_systems import InformationBoothSystem as LegacyPhoneSystem
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from phone_systems import InformationBoothSystem as LegacyPhoneSystem

def main():
    # Kill any existing payphone instances before starting
    _kill_existing_instances()

    # Create and run the phone system
    if legacy_mode:
        logger.info("Running in legacy mode (bypassing BIOS)")
        system = LegacyPhoneSystem()
    else:
        logger.info("Running with BIOS bootloader")
        system = PhoneSystem()

    # Setup signal handlers with logging
    def signal_handler(signum, frame):
        logger.warning(f"Received signal {signum} ({signal.Signals(signum).name})")
        system.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    system.run()

if __name__ == "__main__":
    main()