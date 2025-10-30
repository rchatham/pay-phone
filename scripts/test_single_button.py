#!/usr/bin/env python3
"""
Test Single Button - Non-Interactive

Tests which pins are connected when you're holding a button.
Run this while holding a button down.

Usage: python3 test_single_button.py [button_name]
Example: python3 test_single_button.py 2
"""

import RPi.GPIO as GPIO
import time
import sys

# Your connected pins
PINS = [17, 18, 27, 22, 23, 24, 25, 5, 6, 12, 13, 16, 19, 20, 21]

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

def test_pin_connectivity(driven_pin, test_pins):
    """
    Drive one pin HIGH and see which other pins read HIGH.
    Returns list of pins that are connected.
    """
    try:
        # Set driven pin as OUTPUT and drive HIGH
        GPIO.setup(driven_pin, GPIO.OUT)
        GPIO.output(driven_pin, GPIO.HIGH)

        # Set all test pins as INPUT with pull-down
        for pin in test_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        time.sleep(0.01)

        # Read all test pins
        connected = []
        for pin in test_pins:
            state = GPIO.input(pin)
            if state == GPIO.HIGH:
                connected.append(pin)

        # Cleanup
        GPIO.output(driven_pin, GPIO.LOW)
        GPIO.setup(driven_pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        for pin in test_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)

        return connected

    except Exception as e:
        return []

def main():
    button_name = sys.argv[1] if len(sys.argv) > 1 else "unknown"

    print(f"{Colors.BOLD}Test Single Button - {button_name}{Colors.END}")
    print(f"\nHOLD BUTTON '{button_name}' DOWN NOW!")
    print("Testing will start in 3 seconds...")
    time.sleep(3)

    try:
        setup_gpio()

        print(f"\n{Colors.CYAN}Testing connectivity with button '{button_name}' held down...{Colors.END}\n")

        connections = {}

        # Test each pin as a driver
        for driven_pin in PINS:
            test_pins = [p for p in PINS if p != driven_pin]
            connected = test_pin_connectivity(driven_pin, test_pins)
            if connected:
                connections[driven_pin] = connected
                print(f"  {Colors.GREEN}GPIO {driven_pin} → {connected}{Colors.END}")

        if not connections:
            print(f"{Colors.RED}No connections detected!{Colors.END}")
            print("Possible issues:")
            print("  1. Button not pressed/held during test")
            print("  2. Button is broken")
            print("  3. Wiring issue")
        else:
            print(f"\n{Colors.BOLD}Summary:{Colors.END}")
            print(f"Button '{button_name}' connections:")

            # Extract all involved pins
            all_pins = set()
            for pin, conn in connections.items():
                all_pins.add(pin)
                all_pins.update(conn)

            print(f"  Pins involved: {sorted(all_pins)}")

            # Show bidirectional connections
            for pin, conn in connections.items():
                for c in conn:
                    print(f"  GPIO {pin} ↔ GPIO {c}")

    except KeyboardInterrupt:
        print("\n\nInterrupted")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
