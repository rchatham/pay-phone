#!/usr/bin/env python3
"""
Targeted GPIO Pin Scanner

User knows which pins are connected, but not which is which.
Tests only the specified pins to identify:
- Hook switch (1-2 pins)
- Keypad rows (4 pins)
- Keypad columns (3 pins)
"""

import RPi.GPIO as GPIO
import time
import sys
from itertools import combinations

# User-specified pins that are connected
CONNECTED_PINS = [17, 18, 27, 22, 23, 24, 25, 5, 6, 12, 13, 16, 19, 20, 21]

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

def test_hook_switch_pins():
    """
    Test each connected pin individually to find hook switch.
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'HOOK SWITCH DETECTION'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print(f"\nTesting {len(CONNECTED_PINS)} pins: {CONNECTED_PINS}")

    # Test with pull-up resistors (most common)
    print(f"\n{Colors.BOLD}Setting up pins with pull-up resistors...{Colors.END}")

    print(f"\n{Colors.YELLOW}Step 1: Make sure handset is ON HOOK (hung up){Colors.END}")
    input("Press Enter when ready...")

    # Setup all pins as inputs with pull-ups
    for pin in CONNECTED_PINS:
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except Exception as e:
            print(f"{Colors.RED}Error setting up GPIO {pin}: {e}{Colors.END}")

    time.sleep(0.5)

    # Read baseline
    on_hook = {}
    for pin in CONNECTED_PINS:
        try:
            state = GPIO.input(pin)
            on_hook[pin] = state
            print(f"  GPIO {pin}: {'HIGH' if state else 'LOW'}")
        except Exception as e:
            print(f"{Colors.RED}  GPIO {pin}: Error - {e}{Colors.END}")

    print(f"\n{Colors.YELLOW}Step 2: LIFT the handset (OFF HOOK){Colors.END}")
    input("Press Enter after lifting...")

    time.sleep(0.5)

    # Read off-hook states
    off_hook = {}
    print("\nReading pin states...")
    for pin in CONNECTED_PINS:
        try:
            state = GPIO.input(pin)
            off_hook[pin] = state
            if pin in on_hook and on_hook[pin] != state:
                old = 'HIGH' if on_hook[pin] else 'LOW'
                new = 'HIGH' if state else 'LOW'
                print(f"  {Colors.GREEN}GPIO {pin}: {old} → {new} (CHANGED!){Colors.END}")
            else:
                print(f"  GPIO {pin}: {'HIGH' if state else 'LOW'} (no change)")
        except:
            pass

    # Find pins that changed
    changed_pins = []
    for pin in on_hook:
        if pin in off_hook and on_hook[pin] != off_hook[pin]:
            changed_pins.append(pin)

    if changed_pins:
        print(f"\n{Colors.GREEN}✓ Found {len(changed_pins)} pin(s) that changed: {changed_pins}{Colors.END}")

        # Verify by hanging up
        print(f"\n{Colors.YELLOW}Step 3: HANG UP the handset (ON HOOK) to verify{Colors.END}")
        input("Press Enter after hanging up...")

        time.sleep(0.5)

        verified = []
        for pin in changed_pins:
            try:
                state = GPIO.input(pin)
                if state == on_hook[pin]:
                    print(f"  {Colors.GREEN}GPIO {pin}: Verified (returned to original state){Colors.END}")
                    verified.append(pin)
                else:
                    print(f"  {Colors.RED}GPIO {pin}: Did not return to original state{Colors.END}")
            except:
                pass

        return verified
    else:
        print(f"\n{Colors.RED}No pins changed when lifting handset!{Colors.END}")
        print("\nTrying with pull-down resistors...")

        # Try pull-down
        for pin in CONNECTED_PINS:
            try:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            except:
                pass

        time.sleep(0.5)

        print(f"\n{Colors.YELLOW}LIFT the handset (OFF HOOK) again{Colors.END}")
        input("Press Enter after lifting...")

        pulldown_states = {}
        for pin in CONNECTED_PINS:
            try:
                state = GPIO.input(pin)
                pulldown_states[pin] = state
                if pin in off_hook and off_hook[pin] != state:
                    old = 'HIGH' if off_hook[pin] else 'LOW'
                    new = 'HIGH' if state else 'LOW'
                    print(f"  {Colors.GREEN}GPIO {pin}: {old} → {new} (CHANGED with pull-down!){Colors.END}")
                    changed_pins.append(pin)
            except:
                pass

        return changed_pins if changed_pins else None

def test_keypad_matrix(row_pins, col_pins):
    """
    Test a specific row/column configuration.
    Only one pin driven at a time.
    """
    try:
        # Setup row pins as outputs (HIGH)
        for pin in row_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)

        # Setup column pins as inputs with pull-ups
        for pin in col_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        time.sleep(0.005)

        # Scan matrix - only ONE row driven LOW at a time
        detections = []
        for row_idx, row_pin in enumerate(row_pins):
            # Drive this row LOW (all others stay HIGH)
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

            # Return row to HIGH immediately
            GPIO.output(row_pin, GPIO.HIGH)
            time.sleep(0.001)

        # Cleanup - return to safe state
        for pin in row_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        for pin in col_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)

        return detections if detections else None

    except Exception as e:
        # Cleanup on error
        try:
            for pin in row_pins + col_pins:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        except:
            pass
        return None

def test_keypad_configuration(remaining_pins):
    """
    Test all combinations of 4 rows + 3 columns from remaining pins.
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'KEYPAD MATRIX DETECTION'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print(f"\nTesting {len(remaining_pins)} remaining pins: {remaining_pins}")

    from math import comb
    num_4_combos = comb(len(remaining_pins), 4)
    total_tests = num_4_combos * comb(len(remaining_pins) - 4, 3)

    print(f"Total configurations to test: {total_tests:,}")

    print(f"\n{Colors.YELLOW}Press and HOLD button '5' on the keypad{Colors.END}")
    print("Keep holding it during the entire scan...")
    input("Press Enter to start scanning...")

    keypad_keys = [
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9'],
        ['*', '0', '#']
    ]

    print(f"\n{Colors.CYAN}Scanning...{Colors.END}")

    test_count = 0
    last_progress = 0

    # Test all combinations
    for row_pins in combinations(remaining_pins, 4):
        remaining_for_cols = [p for p in remaining_pins if p not in row_pins]

        for col_pins in combinations(remaining_for_cols, 3):
            test_count += 1

            # Progress update
            progress = int((test_count / total_tests) * 100)
            if progress > last_progress and progress % 10 == 0:
                print(f"  {progress}% ({test_count}/{total_tests:,} configurations)")
                last_progress = progress

            # Test this configuration
            result = test_keypad_matrix(list(row_pins), list(col_pins))

            if result:
                print(f"\n{Colors.GREEN}✓ KEYPAD DETECTED!{Colors.END}")
                print(f"  Row pins: {list(row_pins)}")
                print(f"  Col pins: {list(col_pins)}")

                # Show what was detected
                for det in result:
                    r = det['row_idx']
                    c = det['col_idx']
                    key = keypad_keys[r][c] if r < 4 and c < 3 else '?'
                    print(f"  Button '{key}': Row {r} (GPIO {det['row_pin']}) + Col {c} (GPIO {det['col_pin']})")

                # Check if '5' was detected (row 1, col 1)
                detected_5 = any(d['row_idx'] == 1 and d['col_idx'] == 1 for d in result)

                if detected_5:
                    print(f"\n{Colors.GREEN}✓ Button '5' correctly detected!{Colors.END}")
                    return {
                        'row_pins': list(row_pins),
                        'col_pins': list(col_pins),
                        'detections': result
                    }
                else:
                    print(f"{Colors.YELLOW}Note: This detected a button, but not '5'. Continuing search...{Colors.END}")

    print(f"\n{Colors.RED}No working keypad configuration found!{Colors.END}")
    return None

def verify_keypad(config):
    """
    Verify keypad by testing additional buttons.
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'KEYPAD VERIFICATION'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    keypad_keys = [
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9'],
        ['*', '0', '#']
    ]

    test_buttons = ['1', '9', '0']
    verified = []

    for button in test_buttons:
        print(f"\n{Colors.YELLOW}Press and HOLD button '{button}'{Colors.END}")
        input("Press Enter while holding...")

        result = test_keypad_matrix(config['row_pins'], config['col_pins'])

        if result:
            for det in result:
                r = det['row_idx']
                c = det['col_idx']
                detected_key = keypad_keys[r][c] if r < 4 and c < 3 else '?'
                if detected_key == button:
                    print(f"  {Colors.GREEN}✓ Button '{button}' verified!{Colors.END}")
                    verified.append(button)
                else:
                    print(f"  {Colors.YELLOW}Detected '{detected_key}' instead of '{button}'{Colors.END}")

    print(f"\n{Colors.CYAN}Verified {len(verified)}/{len(test_buttons)} buttons{Colors.END}")
    return len(verified) >= 2

def main():
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'Targeted GPIO Pin Scanner'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print(f"\n{Colors.CYAN}Testing these {len(CONNECTED_PINS)} pins:{Colors.END}")
    print(f"  {CONNECTED_PINS}")

    input("\nPress Enter to start...")

    try:
        setup_gpio()
        print(f"{Colors.GREEN}✓ GPIO initialized{Colors.END}")

        # Step 1: Find hook switch
        hook_pins = test_hook_switch_pins()

        if hook_pins:
            print(f"\n{Colors.GREEN}✓ Hook switch found on: {hook_pins}{Colors.END}")
            remaining_pins = [p for p in CONNECTED_PINS if p not in hook_pins]
        else:
            print(f"\n{Colors.RED}✗ Hook switch not detected{Colors.END}")
            print("Continuing with keypad detection using all pins...")
            remaining_pins = CONNECTED_PINS

        time.sleep(1)

        # Step 2: Find keypad
        if len(remaining_pins) >= 7:
            keypad_config = test_keypad_configuration(remaining_pins)

            if keypad_config:
                # Verify
                if verify_keypad(keypad_config):
                    print(f"\n{Colors.GREEN}✓ Keypad verified!{Colors.END}")
            else:
                keypad_config = None
        else:
            print(f"\n{Colors.RED}Not enough remaining pins for keypad (need 7, have {len(remaining_pins)}){Colors.END}")
            keypad_config = None

        # Final results
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{'FINAL CONFIGURATION'.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}")

        if hook_pins:
            print(f"\n{Colors.GREEN}Hook Switch:{Colors.END}")
            print(f"  HOOK_SWITCH_PIN={hook_pins[0]}")
            if len(hook_pins) > 1:
                print(f"  # Note: Multiple pins detected: {hook_pins}")
        else:
            print(f"\n{Colors.RED}Hook Switch: NOT DETECTED{Colors.END}")

        if keypad_config:
            print(f"\n{Colors.GREEN}Keypad Matrix:{Colors.END}")
            print(f"  KEYPAD_ROW_PINS={keypad_config['row_pins']}")
            print(f"  KEYPAD_COL_PINS={keypad_config['col_pins']}")

            # Save to file
            with open('detected_pins.txt', 'w') as f:
                f.write("# Auto-detected pin configuration\n")
                f.write(f"HOOK_SWITCH_PIN={hook_pins[0] if hook_pins else 'NOT_DETECTED'}\n")
                f.write(f"KEYPAD_ROW_PINS={keypad_config['row_pins']}\n")
                f.write(f"KEYPAD_COL_PINS={keypad_config['col_pins']}\n")

            print(f"\n{Colors.CYAN}✓ Configuration saved to detected_pins.txt{Colors.END}")
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
