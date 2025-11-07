#!/usr/bin/env python3
import logging
import signal
import sys
import queue
import threading
import time
import os
import subprocess
import pygame
from .hardware.serial_handler import SerialHandler
from .hardware.gpio_handler import GPIOHandler
from .phone_system.phone_tree import PhoneTree
from .audio.handler import AudioHandler
from .config.settings import Config

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

class PayphoneSystem:
    def __init__(self):
        self.config = Config()
        self.audio_handler = AudioHandler(self.config.AUDIO_DIR)
        self.phone_on_hook = True
        self.running = True
        self.current_call = None
        
        # Initialize hardware handler based on config
        if self.config.USE_GPIO:
            logger.info("Using GPIO mode (direct Raspberry Pi connection)")
            self.hardware_handler = GPIOHandler(
                keypad_rows=self.config.KEYPAD_ROW_PINS,
                keypad_cols=self.config.KEYPAD_COL_PINS,
                hook_pin=self.config.HOOK_SWITCH_PIN
            )
        else:
            logger.info("Using Serial mode (Arduino connection)")
            self.hardware_handler = SerialHandler(
                port=self.config.SERIAL_PORT,
                baudrate=self.config.BAUDRATE
            )
        
    def setup_phone_tree(self) -> PhoneTree:
        """Build the phone menu tree"""
        # Reuse the same audio handler for all nodes to avoid multiple pygame inits
        audio = self.audio_handler

        # Leaf nodes
        weather = PhoneTree("menu/weather_info.mp3", audio_handler=audio)
        time_info = PhoneTree("menu/time_info.mp3", audio_handler=audio)

        # Branch nodes
        info_menu = PhoneTree(
            "menu/info_menu.mp3",
            audio_handler=audio,
            options={
                "1": weather,
                "2": time_info
            }
        )

        # Root menu
        main_menu = PhoneTree(
            "menu/main_menu.mp3",
            audio_handler=audio,
            options={
                "1": info_menu,
                "2": PhoneTree("menu/jokes.mp3", audio_handler=audio),
                "3": PhoneTree("menu/music.mp3", audio_handler=audio)
            }
        )

        return main_menu
        
    def hook_status_changed(self, off_hook: bool):
        """Handle hook switch changes"""
        self.phone_on_hook = not off_hook
        
        if off_hook:
            logger.info("Phone picked up")
            self.start_call()
        else:
            logger.info("Phone hung up")
            self.end_call()
            
    def start_call(self):
        """Start a new call session"""
        self.audio_handler.play_file("prompts/dial_tone.mp3", blocking=False)
        time.sleep(1)
        self.audio_handler.stop()
        
        # Start navigation in new thread
        self.current_call = threading.Thread(
            target=self._call_handler
        )
        self.current_call.start()
        
    def _call_handler(self):
        """Handle the call navigation"""
        main_menu = self.setup_phone_tree()
        main_menu.navigate(
            self.hardware_handler.input_queue,
            lambda: not self.phone_on_hook,
            main_menu
        )
        
    def end_call(self):
        """End current call"""
        self.audio_handler.stop()
        # Clear input queue
        while not self.hardware_handler.input_queue.empty():
            self.hardware_handler.input_queue.get()

        # Wait for call thread to finish
        if self.current_call and self.current_call.is_alive():
            self.current_call.join(timeout=2.0)

    def run(self):
        """Main application loop"""
        # Setup hardware communication
        self.hardware_handler.set_hook_callback(self.hook_status_changed)
        if not self.hardware_handler.start():
            logger.error("Failed to start hardware communication")
            return

        logger.info("Payphone system started")

        # Keep running until interrupted
        try:
            while self.running:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        """Cleanup and shutdown"""
        logger.info("Shutting down...")
        self.running = False

        # Signal phone is on hook to exit navigation loops
        self.phone_on_hook = True

        # Stop audio playback
        self.audio_handler.stop()

        # Wait for call thread to finish
        if self.current_call and self.current_call.is_alive():
            logger.info("Waiting for call thread to finish...")
            self.current_call.join(timeout=3.0)
            if self.current_call.is_alive():
                logger.warning("Call thread did not exit cleanly")

        # Stop hardware and cleanup
        self.hardware_handler.stop()

        # Quit pygame last (after all threads are stopped)
        pygame.quit()
        logger.info("Shutdown complete")
        
def main():
    # Kill any existing payphone instances before starting
    _kill_existing_instances()

    system = PayphoneSystem()

    # Setup signal handlers with logging
    def signal_handler(signum, frame):
        logger.warning(f"Received signal {signum} ({signal.Signals(signum).name})")
        system.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    system.run()

if __name__ == "__main__":
    main()