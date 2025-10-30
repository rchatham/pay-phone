#!/usr/bin/env python3
"""
Test Keypad Integration

Tests the actual keypad with the configured pins to verify buttons work.
"""

import sys
import os
import time
import queue

# Add project to path
sys.path.insert(0, '/home/pi/payphone')

from dotenv import load_dotenv
load_dotenv()

import RPi.GPIO as GPIO
from payphone.config.settings import Config
from payphone.hardware.gpio_keypad import GPIOKeypad

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def main():
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'Keypad Integration Test'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print(f"\n{Colors.CYAN}Configuration:{Colors.END}")
    print(f"  ROW pins: {Config.KEYPAD_ROW_PINS}")
    print(f"  COL pins: {Config.KEYPAD_COL_PINS}")
    print(f"  Matrix: {len(Config.KEYPAD_ROW_PINS)}x{len(Config.KEYPAD_COL_PINS)}")

    # Create input queue
    input_queue = queue.Queue()

    try:
        # Initialize keypad
        print(f"\n{Colors.CYAN}Initializing keypad...{Colors.END}")
        keypad = GPIOKeypad(Config.KEYPAD_ROW_PINS, Config.KEYPAD_COL_PINS, input_queue)
        keypad.setup()
        print(f"{Colors.GREEN}✓ Keypad initialized{Colors.END}")

        print(f"\n{Colors.BOLD}Available buttons (based on 3x3 configuration):{Colors.END}")
        if len(Config.KEYPAD_ROW_PINS) == 3:
            print("  Row 1: 4, 5, 6")
            print("  Row 2: 7, 8, 9")
            print("  Row 3: *, 0, #")
        else:
            print("  Row 0: 1, 2, 3")
            print("  Row 1: 4, 5, 6")
            print("  Row 2: 7, 8, 9")
            print("  Row 3: *, 0, #")

        print(f"\n{Colors.YELLOW}Press buttons on the keypad...{Colors.END}")
        print("Press Ctrl+C to stop\n")

        # Start scanning
        keypad.start()

        # Monitor for keypresses
        buttons_pressed = []
        while True:
            if not input_queue.empty():
                key = input_queue.get()
                buttons_pressed.append(key)
                print(f"{Colors.GREEN}Button pressed: {key}{Colors.END}")

                # Summary after each press
                if len(buttons_pressed) > 0:
                    print(f"  Total buttons tested: {len(set(buttons_pressed))}")
                    print(f"  Buttons working: {sorted(set(buttons_pressed))}")

            time.sleep(0.1)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.CYAN}Test stopped{Colors.END}")

        if buttons_pressed:
            print(f"\n{Colors.BOLD}Test Results:{Colors.END}")
            print(f"  Total presses: {len(buttons_pressed)}")
            print(f"  Unique buttons: {len(set(buttons_pressed))}")
            print(f"  Working buttons: {sorted(set(buttons_pressed))}")

            # Expected buttons for 3x3 configuration
            if len(Config.KEYPAD_ROW_PINS) == 3:
                expected = {'4', '5', '6', '7', '8', '9', '*', '0', '#'}
                working = set(buttons_pressed)
                missing = expected - working

                if len(working) == len(expected):
                    print(f"\n{Colors.GREEN}✓ All 9 buttons working perfectly!{Colors.END}")
                elif len(working) >= 6:
                    print(f"\n{Colors.YELLOW}✓ Most buttons working ({len(working)}/9){Colors.END}")
                    if missing:
                        print(f"  Missing buttons: {sorted(missing)}")
                else:
                    print(f"\n{Colors.RED}⚠ Only {len(working)}/9 buttons working{Colors.END}")
                    if missing:
                        print(f"  Missing buttons: {sorted(missing)}")
        else:
            print(f"\n{Colors.RED}No buttons detected!{Colors.END}")
            print("Possible issues:")
            print("  1. Wiring not connected properly")
            print("  2. Wrong pin configuration")
            print("  3. Hardware fault")

    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()

    finally:
        try:
            keypad.stop()
        except:
            pass
        GPIO.cleanup()
        print(f"\n{Colors.CYAN}GPIO cleaned up{Colors.END}")

if __name__ == "__main__":
    main()
