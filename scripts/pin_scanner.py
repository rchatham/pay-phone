#!/usr/bin/env python3
"""
Active GPIO Pin Scanner

This tool actively drives GPIO pins to detect keypad matrix connections.
For keypad detection, it tries different combinations of:
- Some pins as outputs (rows) driving LOW
- Other pins as inputs (columns) with pull-ups

When you press a button, it creates a connection between a row and column.
"""

import RPi.GPIO as GPIO
import time
import sys
from itertools import combinations

# Safe GPIO pins to test
SAFE_GPIO_PINS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]

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

def cleanup_gpio():
    GPIO.cleanup()

def scan_for_hook_switch():
    """
    Scan for hook switch by reading all pins as inputs with pull-ups
    and detecting which ones change when handset is lifted.
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'HOOK SWITCH SCAN'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print("\nSetting up all pins as inputs with pull-up resistors...")

    # Setup all pins as inputs with pull-ups
    for pin in SAFE_GPIO_PINS:
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except Exception as e:
            print(f"{Colors.RED}Warning: Could not setup GPIO {pin}: {e}{Colors.END}")

    time.sleep(0.5)

    print(f"\n{Colors.YELLOW}Step 1: Make sure handset is ON HOOK (hung up){Colors.END}")
    input("Press Enter when ready...")

    # Read initial states
    on_hook = {}
    for pin in SAFE_GPIO_PINS:
        try:
            on_hook[pin] = GPIO.input(pin)
        except:
            pass

    print(f"✓ Read {len(on_hook)} pins (baseline)")

    print(f"\n{Colors.YELLOW}Step 2: LIFT the handset (OFF HOOK){Colors.END}")
    input("Press Enter after lifting...")

    time.sleep(0.3)

    # Read states while off hook
    off_hook = {}
    for pin in SAFE_GPIO_PINS:
        try:
            off_hook[pin] = GPIO.input(pin)
        except:
            pass

    # Find changes
    changes = []
    print(f"\n{Colors.CYAN}Checking for changes...{Colors.END}")
    for pin in on_hook:
        if pin in off_hook and on_hook[pin] != off_hook[pin]:
            old = "HIGH" if on_hook[pin] else "LOW"
            new = "HIGH" if off_hook[pin] else "LOW"
            print(f"{Colors.GREEN}  GPIO {pin}: {old} → {new}{Colors.END}")
            changes.append(pin)

    if not changes:
        print(f"{Colors.RED}  No pins changed state!{Colors.END}")
        print(f"\n{Colors.YELLOW}This could mean:{Colors.END}")
        print("  1. Hook switch is not connected to any GPIO pins")
        print("  2. Hook switch needs different resistor configuration")
        print("  3. Physical wiring issue")

        # Try with pull-down
        print(f"\n{Colors.CYAN}Trying with PULL-DOWN resistors...{Colors.END}")

        for pin in SAFE_GPIO_PINS:
            try:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            except:
                pass

        time.sleep(0.3)

        pulldown_states = {}
        for pin in SAFE_GPIO_PINS:
            try:
                pulldown_states[pin] = GPIO.input(pin)
            except:
                pass

        for pin in off_hook:
            if pin in pulldown_states and off_hook[pin] != pulldown_states[pin]:
                old = "HIGH" if off_hook[pin] else "LOW"
                new = "HIGH" if pulldown_states[pin] else "LOW"
                print(f"{Colors.GREEN}  GPIO {pin}: {old} → {new} (with pull-down){Colors.END}")
                changes.append(pin)

    return changes

def scan_for_keypad_active():
    """
    Active keypad scanning: Try different combinations of pins as
    outputs (rows) vs inputs (columns) and detect button presses.
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'KEYPAD ACTIVE SCAN'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print("\nThis will actively scan for keypad matrix connections.")
    print("A 4x3 keypad needs 4 output pins (rows) + 3 input pins (columns).")
    print("\nWe'll test different pin combinations...")

    # We'll try a smart approach: test common configurations
    # Standard keypad matrix: 4 rows (outputs) + 3 columns (inputs)

    print(f"\n{Colors.YELLOW}Step 1: Make sure NO keys are pressed{Colors.END}")
    input("Press Enter when ready...")

    # Try different 4-row + 3-col combinations from available pins
    num_rows = 4
    num_cols = 3
    test_count = 0
    max_tests = 20  # Limit tests to avoid taking forever

    print(f"\nTesting pin combinations (this may take a minute)...")

    # Generate reasonable test combinations
    # We'll slide a window through the pins
    for start_idx in range(len(SAFE_GPIO_PINS) - (num_rows + num_cols) + 1):
        if test_count >= max_tests:
            break

        row_pins = SAFE_GPIO_PINS[start_idx:start_idx + num_rows]
        col_pins = SAFE_GPIO_PINS[start_idx + num_rows:start_idx + num_rows + num_cols]

        test_count += 1

        if test_count % 5 == 1:
            print(f"  Testing configuration {test_count}...")
            print(f"    Rows: {row_pins}")
            print(f"    Cols: {col_pins}")

        # Setup pins
        try:
            for pin in row_pins:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)

            for pin in col_pins:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            time.sleep(0.01)

            # Scan matrix while user might be pressing a button
            detected = []

            for row_idx, row_pin in enumerate(row_pins):
                GPIO.output(row_pin, GPIO.LOW)
                time.sleep(0.001)

                for col_idx, col_pin in enumerate(col_pins):
                    if GPIO.input(col_pin) == GPIO.LOW:
                        detected.append((row_pin, col_pin, row_idx, col_idx))

                GPIO.output(row_pin, GPIO.HIGH)

            # Reset to HIGH
            for pin in row_pins:
                GPIO.output(pin, GPIO.HIGH)

        except Exception as e:
            continue

    print(f"\n{Colors.YELLOW}Step 2: Press and HOLD button '5' on the keypad{Colors.END}")
    input("Press Enter while holding the button...")

    # Now do a comprehensive scan with all tested configurations
    print(f"\n{Colors.CYAN}Scanning all configurations...{Colors.END}")

    detected_configs = []

    for start_idx in range(len(SAFE_GPIO_PINS) - (num_rows + num_cols) + 1):
        row_pins = SAFE_GPIO_PINS[start_idx:start_idx + num_rows]
        col_pins = SAFE_GPIO_PINS[start_idx + num_rows:start_idx + num_rows + num_cols]

        # Setup pins
        try:
            for pin in row_pins:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)

            for pin in col_pins:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            time.sleep(0.01)

            # Scan matrix
            detected = []

            for row_idx, row_pin in enumerate(row_pins):
                GPIO.output(row_pin, GPIO.LOW)
                time.sleep(0.001)

                for col_idx, col_pin in enumerate(col_pins):
                    if GPIO.input(col_pin) == GPIO.LOW:
                        detected.append((row_pin, col_pin, row_idx, col_idx))

                GPIO.output(row_pin, GPIO.HIGH)

            if detected:
                print(f"\n{Colors.GREEN}✓ DETECTED CONNECTION!{Colors.END}")
                print(f"  Row pins: {row_pins}")
                print(f"  Col pins: {col_pins}")
                print(f"  Connections: {detected}")

                # Expected position for '5' button: row 1, col 1
                for row_pin, col_pin, row_idx, col_idx in detected:
                    keypad_keys = [
                        ['1', '2', '3'],
                        ['4', '5', '6'],
                        ['7', '8', '9'],
                        ['*', '0', '#']
                    ]
                    key = keypad_keys[row_idx][col_idx] if row_idx < 4 and col_idx < 3 else '?'
                    print(f"  Row {row_idx} (GPIO {row_pin}) + Col {col_idx} (GPIO {col_pin}) = Button '{key}'")

                detected_configs.append({
                    'row_pins': row_pins,
                    'col_pins': col_pins,
                    'connections': detected
                })

        except Exception as e:
            continue

    if detected_configs:
        print(f"\n{Colors.GREEN}Found {len(detected_configs)} working configuration(s)!{Colors.END}")
        return detected_configs[0]  # Return the first working config
    else:
        print(f"\n{Colors.RED}No keypad detected!{Colors.END}")
        return None

def main():
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'Active GPIO Pin Scanner'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print("\nThis tool actively drives GPIO pins to detect your hardware.")
    print("It will try different configurations to find working connections.")

    input("\nPress Enter to start scanning...")

    try:
        setup_gpio()
        print(f"{Colors.GREEN}✓ GPIO initialized{Colors.END}")

        # Scan for hook switch
        hook_pins = scan_for_hook_switch()

        if hook_pins:
            print(f"\n{Colors.GREEN}✓ Hook switch found on pin(s): {hook_pins}{Colors.END}")
        else:
            print(f"\n{Colors.RED}✗ Hook switch not detected{Colors.END}")

        time.sleep(1)

        # Scan for keypad
        keypad_config = scan_for_keypad_active()

        # Summary
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{'SCAN RESULTS'.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}")

        if hook_pins:
            print(f"\n{Colors.GREEN}Hook Switch:{Colors.END}")
            print(f"  Pin(s): {hook_pins}")
            print(f"\nAdd to configuration:")
            print(f"  HOOK_SWITCH_PIN={hook_pins[0]}")
        else:
            print(f"\n{Colors.RED}Hook Switch: NOT DETECTED{Colors.END}")

        if keypad_config:
            print(f"\n{Colors.GREEN}Keypad Matrix:{Colors.END}")
            print(f"  Row pins: {keypad_config['row_pins']}")
            print(f"  Col pins: {keypad_config['col_pins']}")
            print(f"\nAdd to configuration:")
            print(f"  KEYPAD_ROW_PINS={keypad_config['row_pins']}")
            print(f"  KEYPAD_COL_PINS={keypad_config['col_pins']}")
        else:
            print(f"\n{Colors.RED}Keypad: NOT DETECTED{Colors.END}")

        print()

    except KeyboardInterrupt:
        print("\n\nScan interrupted")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup_gpio()
        print(f"{Colors.CYAN}GPIO cleaned up{Colors.END}")

if __name__ == "__main__":
    main()
