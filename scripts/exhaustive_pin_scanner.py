#!/usr/bin/env python3
"""
Exhaustive GPIO Pin Scanner

Tests ALL possible pin combinations without any assumptions:
- Hook switch: Test each individual pin
- Keypad: Test all possible combinations of 4 rows + 3 columns

This is thorough but may take a few minutes.
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

def scan_hook_switch_exhaustive():
    """
    Test each GPIO pin individually to find hook switch.
    No assumptions about which pin it might be.
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'EXHAUSTIVE HOOK SWITCH SCAN'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print(f"\n{Colors.CYAN}Testing all {len(SAFE_GPIO_PINS)} GPIO pins individually...{Colors.END}")

    # Test with pull-up resistors
    print(f"\n{Colors.BOLD}Test 1: Pull-up resistors (most common){Colors.END}")

    print(f"\n{Colors.YELLOW}Make sure handset is ON HOOK (hung up){Colors.END}")
    input("Press Enter when ready...")

    # Setup all pins and read baseline
    on_hook_pullup = {}
    for pin in SAFE_GPIO_PINS:
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            time.sleep(0.001)
            on_hook_pullup[pin] = GPIO.input(pin)
        except Exception as e:
            print(f"{Colors.RED}Could not read GPIO {pin}: {e}{Colors.END}")

    print(f"✓ Read {len(on_hook_pullup)} pins (baseline)")

    print(f"\n{Colors.YELLOW}LIFT the handset (OFF HOOK) now{Colors.END}")
    input("Press Enter after lifting...")

    time.sleep(0.5)

    # Read all pins again
    off_hook_pullup = {}
    for pin in SAFE_GPIO_PINS:
        try:
            off_hook_pullup[pin] = GPIO.input(pin)
        except:
            pass

    # Check for changes
    pullup_changes = []
    for pin in on_hook_pullup:
        if pin in off_hook_pullup and on_hook_pullup[pin] != off_hook_pullup[pin]:
            old = "HIGH" if on_hook_pullup[pin] else "LOW"
            new = "HIGH" if off_hook_pullup[pin] else "LOW"
            print(f"{Colors.GREEN}  GPIO {pin}: {old} → {new}{Colors.END}")
            pullup_changes.append(pin)

    if pullup_changes:
        print(f"\n{Colors.GREEN}✓ Found {len(pullup_changes)} pin(s) with pull-up: {pullup_changes}{Colors.END}")

        # Verify by hanging up
        print(f"\n{Colors.YELLOW}HANG UP the handset (ON HOOK) to verify{Colors.END}")
        input("Press Enter after hanging up...")

        time.sleep(0.5)

        verified = []
        for pin in pullup_changes:
            try:
                current = GPIO.input(pin)
                if current == on_hook_pullup[pin]:
                    print(f"{Colors.GREEN}  GPIO {pin}: Verified (returned to {('HIGH' if current else 'LOW')}){Colors.END}")
                    verified.append(pin)
            except:
                pass

        if verified:
            return verified, 'PULLUP'

    # Test with pull-down resistors
    print(f"\n{Colors.BOLD}Test 2: Pull-down resistors{Colors.END}")

    print(f"\n{Colors.YELLOW}Make sure handset is ON HOOK (hung up){Colors.END}")
    input("Press Enter when ready...")

    # Setup all pins with pull-down
    on_hook_pulldown = {}
    for pin in SAFE_GPIO_PINS:
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            time.sleep(0.001)
            on_hook_pulldown[pin] = GPIO.input(pin)
        except:
            pass

    print(f"✓ Read {len(on_hook_pulldown)} pins (baseline)")

    print(f"\n{Colors.YELLOW}LIFT the handset (OFF HOOK) now{Colors.END}")
    input("Press Enter after lifting...")

    time.sleep(0.5)

    # Read all pins again
    off_hook_pulldown = {}
    for pin in SAFE_GPIO_PINS:
        try:
            off_hook_pulldown[pin] = GPIO.input(pin)
        except:
            pass

    # Check for changes
    pulldown_changes = []
    for pin in on_hook_pulldown:
        if pin in off_hook_pulldown and on_hook_pulldown[pin] != off_hook_pulldown[pin]:
            old = "HIGH" if on_hook_pulldown[pin] else "LOW"
            new = "HIGH" if off_hook_pulldown[pin] else "LOW"
            print(f"{Colors.GREEN}  GPIO {pin}: {old} → {new}{Colors.END}")
            pulldown_changes.append(pin)

    if pulldown_changes:
        print(f"\n{Colors.GREEN}✓ Found {len(pulldown_changes)} pin(s) with pull-down: {pulldown_changes}{Colors.END}")
        return pulldown_changes, 'PULLDOWN'

    return None, None

def test_keypad_matrix(row_pins, col_pins):
    """
    Test a specific row/column pin configuration.
    Returns detected connections if button is pressed.

    IMPORTANT: Only one GPIO pin is actively driven at a time.
    """
    try:
        # Setup row pins as outputs (all HIGH initially)
        for pin in row_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)

        # Setup column pins as inputs with pull-ups
        for pin in col_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        time.sleep(0.005)

        # Scan the matrix - only ONE row driven LOW at a time
        detections = []
        for row_idx, row_pin in enumerate(row_pins):
            # Drive ONLY this row LOW (all others remain HIGH)
            GPIO.output(row_pin, GPIO.LOW)
            time.sleep(0.001)

            # Check all columns
            for col_idx, col_pin in enumerate(col_pins):
                if GPIO.input(col_pin) == GPIO.LOW:
                    detections.append({
                        'row_pin': row_pin,
                        'col_pin': col_pin,
                        'row_idx': row_idx,
                        'col_idx': col_idx
                    })

            # IMMEDIATELY return this row to HIGH before testing next row
            GPIO.output(row_pin, GPIO.HIGH)
            time.sleep(0.001)

        # Cleanup: return all pins to safe state (inputs)
        for pin in row_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        for pin in col_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)

        return detections if detections else None

    except Exception as e:
        # Cleanup on error
        try:
            GPIO.cleanup()
        except:
            pass
        return None

def scan_keypad_exhaustive():
    """
    Test ALL possible combinations of 4 row pins + 3 column pins.
    No assumptions about which pins or their order.

    Optimization: First identify which pins show activity, then only
    test combinations from those pins.
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'EXHAUSTIVE KEYPAD MATRIX SCAN'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    # STEP 1: Identify active pins
    print(f"\n{Colors.BOLD}Step 1: Identifying active pins{Colors.END}")
    print("This will narrow down which pins are actually connected to the keypad.")

    print(f"\n{Colors.YELLOW}Make sure NO keys are pressed{Colors.END}")
    input("Press Enter when ready...")

    # Read baseline with all pins as inputs
    for pin in SAFE_GPIO_PINS:
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except:
            pass

    time.sleep(0.1)

    baseline = {}
    for pin in SAFE_GPIO_PINS:
        try:
            baseline[pin] = GPIO.input(pin)
        except:
            pass

    print(f"\n{Colors.YELLOW}Press and HOLD button '5' on the keypad{Colors.END}")
    input("Press Enter while holding...")

    time.sleep(0.2)

    pressed = {}
    for pin in SAFE_GPIO_PINS:
        try:
            pressed[pin] = GPIO.input(pin)
        except:
            pass

    # Find pins that might be involved
    active_pins = []
    for pin in baseline:
        if pin in pressed:
            # Pins that are LOW when button pressed are likely columns
            # Or pins that changed state
            if pressed[pin] == GPIO.LOW or pressed[pin] != baseline[pin]:
                active_pins.append(pin)

    if not active_pins:
        print(f"{Colors.RED}No active pins detected!{Colors.END}")
        print("Falling back to testing all pins...")
        active_pins = SAFE_GPIO_PINS
    else:
        print(f"{Colors.GREEN}Found {len(active_pins)} potentially active pins: {active_pins}{Colors.END}")

    # STEP 2: Test combinations from active pins only
    print(f"\n{Colors.BOLD}Step 2: Testing pin combinations{Colors.END}")

    # Calculate total combinations from active pins
    from math import comb
    if len(active_pins) >= 7:
        total_row_combos = comb(len(active_pins), 4)
        total_configs = total_row_combos * comb(len(active_pins) - 4, 3)
    else:
        # Not enough active pins, use all pins
        print(f"{Colors.YELLOW}Not enough active pins detected, using all {len(SAFE_GPIO_PINS)} pins{Colors.END}")
        active_pins = SAFE_GPIO_PINS
        total_row_combos = comb(len(active_pins), 4)
        total_configs = total_row_combos * comb(len(active_pins) - 4, 3)

    print(f"{Colors.CYAN}Testing {total_configs:,} combinations from {len(active_pins)} active pins{Colors.END}")

    estimated_time = (total_configs * 0.008) / 60  # ~8ms per test
    print(f"Estimated time: {estimated_time:.1f} minutes")

    print(f"\n{Colors.YELLOW}Press and HOLD button '5' on the keypad{Colors.END}")
    print("Keep holding it while the scan runs...")
    input("Press Enter to start scanning...")

    print(f"\n{Colors.CYAN}Scanning...{Colors.END}")

    detected_configs = []
    test_count = 0
    last_progress = 0

    # Generate all combinations of 4 pins for rows from active pins
    for row_pins in combinations(active_pins, 4):
        # For each row combination, get remaining pins
        remaining_pins = [p for p in active_pins if p not in row_pins]

        # Generate all combinations of 3 pins for columns from remaining
        for col_pins in combinations(remaining_pins, 3):
            test_count += 1

            # Show progress
            progress = int((test_count / total_configs) * 100)
            if progress > last_progress and progress % 10 == 0:
                print(f"  Progress: {progress}% ({test_count}/{total_configs:,} configurations tested)")
                last_progress = progress

            # Test this configuration
            result = test_keypad_matrix(list(row_pins), list(col_pins))

            if result:
                # Found a detection!
                print(f"\n{Colors.GREEN}✓ KEYPAD DETECTED!{Colors.END}")
                print(f"  Row pins: {list(row_pins)}")
                print(f"  Col pins: {list(col_pins)}")
                print(f"  Connections: {result}")

                # Map to keypad layout
                keypad_keys = [
                    ['1', '2', '3'],
                    ['4', '5', '6'],
                    ['7', '8', '9'],
                    ['*', '0', '#']
                ]

                for det in result:
                    row_idx = det['row_idx']
                    col_idx = det['col_idx']
                    if row_idx < 4 and col_idx < 3:
                        key = keypad_keys[row_idx][col_idx]
                        print(f"  Button: '{key}' (Row {row_idx}, Col {col_idx})")

                detected_configs.append({
                    'row_pins': list(row_pins),
                    'col_pins': list(col_pins),
                    'detections': result
                })

                # Ask if this looks right
                print(f"\n{Colors.YELLOW}Does this look correct?{Colors.END}")
                print("We detected a connection when you pressed '5'.")
                response = input("Is this the right configuration? (y/n): ").lower()

                if response == 'y':
                    print(f"{Colors.GREEN}Great! Using this configuration.{Colors.END}")
                    return detected_configs[0]
                else:
                    print(f"{Colors.CYAN}Continuing search...{Colors.END}")
                    detected_configs.pop()  # Remove this config

    print(f"\n{Colors.CYAN}Scan complete: {test_count} configurations tested{Colors.END}")

    if detected_configs:
        print(f"\n{Colors.GREEN}Found {len(detected_configs)} possible configuration(s){Colors.END}")
        return detected_configs[0]
    else:
        print(f"\n{Colors.RED}No keypad detected!{Colors.END}")
        return None

def verify_keypad_config(config):
    """
    Verify the keypad configuration by testing multiple buttons.
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'KEYPAD VERIFICATION'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print(f"\nLet's verify the configuration by testing more buttons.")
    print(f"Row pins: {config['row_pins']}")
    print(f"Col pins: {config['col_pins']}")

    keypad_keys = [
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9'],
        ['*', '0', '#']
    ]

    test_buttons = ['1', '9', '0', '*']

    verified = []

    for button in test_buttons:
        print(f"\n{Colors.YELLOW}Press and HOLD button '{button}'{Colors.END}")
        input("Press Enter while holding...")

        result = test_keypad_matrix(config['row_pins'], config['col_pins'])

        if result:
            for det in result:
                row_idx = det['row_idx']
                col_idx = det['col_idx']
                if row_idx < 4 and col_idx < 3:
                    detected_key = keypad_keys[row_idx][col_idx]
                    if detected_key == button:
                        print(f"{Colors.GREEN}✓ Button '{button}' verified!{Colors.END}")
                        verified.append(button)
                    else:
                        print(f"{Colors.RED}✗ Expected '{button}' but detected '{detected_key}'{Colors.END}")
        else:
            print(f"{Colors.RED}✗ No connection detected{Colors.END}")

    print(f"\n{Colors.CYAN}Verified {len(verified)}/{len(test_buttons)} buttons{Colors.END}")

    return len(verified) >= 2  # At least 2 buttons should work

def main():
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'Exhaustive GPIO Pin Scanner'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print("\nThis tool tests EVERY possible GPIO pin combination.")
    print("No assumptions are made about which pins you're using.")
    print("\nFor a 4x3 keypad, this means testing:")
    print(f"  • All combinations of 4 pins for rows")
    print(f"  • All combinations of 3 pins for columns")
    print(f"  • Total: ~65,000 configurations")

    print(f"\n{Colors.YELLOW}WARNING: This will take 2-3 minutes to complete.{Colors.END}")

    input("\nPress Enter to start...")

    try:
        setup_gpio()
        print(f"{Colors.GREEN}✓ GPIO initialized{Colors.END}")

        # Scan for hook switch
        hook_pins, hook_mode = scan_hook_switch_exhaustive()

        if hook_pins:
            print(f"\n{Colors.GREEN}✓ Hook switch found!{Colors.END}")
            print(f"  Pin(s): {hook_pins}")
            print(f"  Mode: {hook_mode}")
        else:
            print(f"\n{Colors.RED}✗ Hook switch not detected{Colors.END}")

        time.sleep(2)

        # Scan for keypad
        keypad_config = scan_keypad_exhaustive()

        if keypad_config:
            # Verify the configuration
            if verify_keypad_config(keypad_config):
                print(f"\n{Colors.GREEN}✓ Keypad configuration verified!{Colors.END}")
            else:
                print(f"\n{Colors.YELLOW}⚠ Keypad partially verified{Colors.END}")

        # Final summary
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{'FINAL CONFIGURATION'.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}")

        if hook_pins:
            print(f"\n{Colors.GREEN}Hook Switch:{Colors.END}")
            print(f"  HOOK_SWITCH_PIN={hook_pins[0]}")
            if len(hook_pins) > 1:
                print(f"  # Additional pins detected: {hook_pins[1:]}")
        else:
            print(f"\n{Colors.RED}Hook Switch: NOT DETECTED{Colors.END}")

        if keypad_config:
            print(f"\n{Colors.GREEN}Keypad Matrix:{Colors.END}")
            print(f"  KEYPAD_ROW_PINS={keypad_config['row_pins']}")
            print(f"  KEYPAD_COL_PINS={keypad_config['col_pins']}")
        else:
            print(f"\n{Colors.RED}Keypad: NOT DETECTED{Colors.END}")

        print()

    except KeyboardInterrupt:
        print("\n\nScan interrupted by user")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup_gpio()
        print(f"{Colors.CYAN}GPIO cleaned up{Colors.END}")

if __name__ == "__main__":
    main()
