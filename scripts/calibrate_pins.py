#!/usr/bin/env python3
"""
GPIO Pin Calibration Tool for Payphone

This tool automatically detects which GPIO pins are connected to:
- Hook switch (1 or 2 pins)
- Keypad matrix (4 rows + 3 columns)

Usage:
    sudo python3 calibrate_pins.py

The tool will guide you through the calibration process and save
the configuration to a file.
"""

import RPi.GPIO as GPIO
import time
import sys
import json
from collections import defaultdict

# Safe GPIO pins to test (avoiding special purpose pins)
# Excluded: GPIO 0,1 (ID EEPROM), GPIO 14,15 (UART), GPIO 28-31 (not available on most models)
SAFE_GPIO_PINS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]

# Keypad layout
KEYPAD_KEYS = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['*', '0', '#']
]

# Colors for output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def setup_gpio():
    """Initialize GPIO"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    print_success("GPIO initialized (BCM mode)")

def cleanup_gpio():
    """Cleanup all GPIO pins"""
    GPIO.cleanup()
    print_info("GPIO cleaned up")

def calibrate_hook_switch():
    """
    Calibrate hook switch by detecting which pin(s) change state
    when the handset is lifted/hung up.
    """
    print_header("Hook Switch Calibration")

    print_info("Setting up all GPIO pins as inputs with pull-up resistors...")

    # Setup all pins as inputs with pull-ups
    for pin in SAFE_GPIO_PINS:
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except Exception as e:
            print_warning(f"Could not setup GPIO {pin}: {e}")

    time.sleep(0.5)

    print_success("Reading initial pin states...")
    initial_states = {}
    for pin in SAFE_GPIO_PINS:
        try:
            initial_states[pin] = GPIO.input(pin)
        except:
            pass

    print(f"\n{Colors.BOLD}Current handset position: ON HOOK (handset down){Colors.END}")
    print(f"{Colors.YELLOW}Please LIFT the handset (off hook) and press Enter...{Colors.END}")
    input()

    time.sleep(0.3)

    # Read states after lifting
    off_hook_states = {}
    for pin in SAFE_GPIO_PINS:
        try:
            off_hook_states[pin] = GPIO.input(pin)
        except:
            pass

    # Find pins that changed
    changed_pins = []
    for pin in initial_states:
        if pin in off_hook_states and initial_states[pin] != off_hook_states[pin]:
            changed_pins.append(pin)
            print_success(f"GPIO {pin}: {initial_states[pin]} → {off_hook_states[pin]}")

    if not changed_pins:
        print_error("No pins detected! Check your wiring.")
        return None

    print(f"\n{Colors.YELLOW}Now HANG UP the handset (on hook) and press Enter...{Colors.END}")
    input()

    time.sleep(0.3)

    # Verify by hanging up
    on_hook_states = {}
    for pin in SAFE_GPIO_PINS:
        try:
            on_hook_states[pin] = GPIO.input(pin)
        except:
            pass

    # Verify pins changed back
    verified_pins = []
    for pin in changed_pins:
        if pin in on_hook_states and on_hook_states[pin] == initial_states[pin]:
            verified_pins.append(pin)
            print_success(f"GPIO {pin}: Verified (changed back to {on_hook_states[pin]})")

    if not verified_pins:
        print_error("Verification failed! No pins changed back.")
        return None

    print(f"\n{Colors.GREEN}{Colors.BOLD}Hook switch detected on pin(s): {verified_pins}{Colors.END}")

    # Determine configuration
    if len(verified_pins) == 1:
        print_info("Single-pin hook switch detected")
        return {
            'type': 'single',
            'pin': verified_pins[0],
            'active_state': 'LOW' if off_hook_states[verified_pins[0]] == 0 else 'HIGH'
        }
    else:
        print_info(f"Multi-pin hook switch detected ({len(verified_pins)} pins)")
        return {
            'type': 'multi',
            'pins': verified_pins,
            'states': {pin: off_hook_states[pin] for pin in verified_pins}
        }

def test_keypad_button(row_pins, col_pins, expected_key):
    """
    Test a single keypad button press and detect which row/col pins are active
    """
    print(f"\n{Colors.YELLOW}Press and HOLD the '{expected_key}' button, then press Enter...{Colors.END}")
    input()

    time.sleep(0.2)

    # Scan matrix
    detected_connections = []

    for row_idx, row_pin in enumerate(row_pins):
        GPIO.output(row_pin, GPIO.LOW)
        time.sleep(0.001)

        for col_idx, col_pin in enumerate(col_pins):
            if GPIO.input(col_pin) == GPIO.LOW:
                detected_connections.append((row_pin, col_pin, row_idx, col_idx))

        GPIO.output(row_pin, GPIO.HIGH)

    if detected_connections:
        row_pin, col_pin, row_idx, col_idx = detected_connections[0]
        actual_key = KEYPAD_KEYS[row_idx][col_idx]
        print_success(f"Detected: Row {row_idx} (GPIO {row_pin}) + Col {col_idx} (GPIO {col_pin}) = '{actual_key}'")
        return detected_connections[0]
    else:
        print_error(f"No connection detected for button '{expected_key}'")
        return None

def calibrate_keypad():
    """
    Calibrate keypad matrix by testing specific buttons (1, 5, 9, 0)
    to identify all row and column pins.
    """
    print_header("Keypad Matrix Calibration")

    print_info("We'll test 4 buttons to detect the matrix layout:")
    print("  • Button '1' (Row 0, Col 0)")
    print("  • Button '5' (Row 1, Col 1)")
    print("  • Button '9' (Row 2, Col 2)")
    print("  • Button '0' (Row 3, Col 1)")

    # Get available pins (excluding hook switch pins if we know them)
    available_pins = SAFE_GPIO_PINS.copy()

    print(f"\n{Colors.BOLD}Step 1: Initial Pin Scan{Colors.END}")
    print_info("We need to identify which pins are connected to the keypad...")

    # Setup all pins as inputs with pull-ups first
    for pin in available_pins:
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except:
            pass

    print(f"\n{Colors.YELLOW}Press and HOLD any key on the keypad, then press Enter...{Colors.END}")
    input()

    # Read baseline (no keys pressed)
    print_info("Release the key and wait...")
    time.sleep(1)
    baseline_states = {}
    for pin in available_pins:
        try:
            baseline_states[pin] = GPIO.input(pin)
        except:
            pass

    print(f"{Colors.YELLOW}Now press and HOLD any key again, then press Enter...{Colors.END}")
    input()

    time.sleep(0.2)
    active_states = {}
    for pin in available_pins:
        try:
            active_states[pin] = GPIO.input(pin)
        except:
            pass

    # Find pins that might be part of keypad
    potential_pins = []
    for pin in baseline_states:
        if pin in active_states:
            # Pins that are LOW when key is pressed might be columns
            if active_states[pin] == GPIO.LOW:
                potential_pins.append(pin)

    if not potential_pins:
        print_error("Could not detect any keypad pins! Check your wiring.")
        return None

    print_success(f"Found {len(potential_pins)} potential keypad pins: {potential_pins}")

    # Now we need to distinguish rows from columns
    # Rows are outputs, columns are inputs
    # Try different combinations

    print(f"\n{Colors.BOLD}Step 2: Detecting Row and Column Pins{Colors.END}")

    # Test with 4 rows and 3 columns assumption
    if len(potential_pins) < 7:
        print_error(f"Need at least 7 pins for 4x3 matrix, only found {len(potential_pins)}")
        # Try to proceed anyway

    # Strategy: Set some pins as outputs (rows), others as inputs (cols)
    # Standard keypad: 4 rows (outputs) + 3 columns (inputs)

    # We'll use a heuristic: test button '1' (row 0, col 0) to find one row and one column
    # Then expand from there

    print_info("Setting up test matrix configuration...")

    # Try assuming first N pins as rows, rest as columns
    test_configurations = []

    # Generate reasonable configurations
    for num_rows in [4, 3]:  # Try 4 rows first, then 3
        for num_cols in [3, 4]:  # Try 3 columns first, then 4
            if num_rows + num_cols <= len(potential_pins):
                test_configurations.append((num_rows, num_cols))

    # Try to find working configuration
    working_config = None

    for num_rows, num_cols in test_configurations:
        print_info(f"Testing {num_rows}x{num_cols} matrix configuration...")

        row_pins = potential_pins[:num_rows]
        col_pins = potential_pins[num_rows:num_rows+num_cols]

        # Setup rows as outputs (HIGH), columns as inputs (pull-up)
        for pin in row_pins:
            try:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)
            except:
                pass

        for pin in col_pins:
            try:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            except:
                pass

        time.sleep(0.1)

        # Test with button '1'
        result = test_keypad_button(row_pins, col_pins, '1')

        if result:
            working_config = {
                'row_pins': row_pins,
                'col_pins': col_pins
            }
            break

    if not working_config:
        print_error("Could not detect keypad matrix configuration!")
        return None

    row_pins = working_config['row_pins']
    col_pins = working_config['col_pins']

    print_success(f"Matrix detected: {len(row_pins)} rows × {len(col_pins)} columns")
    print_info(f"Row pins (outputs): {row_pins}")
    print_info(f"Column pins (inputs): {col_pins}")

    # Now test the other buttons to verify
    print(f"\n{Colors.BOLD}Step 3: Verification{Colors.END}")

    test_buttons = [('5', 1, 1), ('9', 2, 2), ('0', 3, 1)]

    for key, expected_row, expected_col in test_buttons:
        result = test_keypad_button(row_pins, col_pins, key)
        if result:
            _, _, detected_row, detected_col = result
            if detected_row == expected_row and detected_col == expected_col:
                print_success(f"Button '{key}' verified!")
            else:
                print_warning(f"Button '{key}' detected at different position")

    return {
        'row_pins': row_pins,
        'col_pins': col_pins
    }

def save_configuration(hook_config, keypad_config, output_file='pin_config.json'):
    """Save the detected configuration to a file"""
    config = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'hook_switch': hook_config,
        'keypad': keypad_config
    }

    with open(output_file, 'w') as f:
        json.dump(config, f, indent=2)

    print_success(f"Configuration saved to {output_file}")

    # Also create .env format
    env_lines = []
    env_lines.append("# Auto-calibrated pin configuration")
    env_lines.append(f"# Generated: {config['timestamp']}")
    env_lines.append("")

    if hook_config['type'] == 'single':
        env_lines.append(f"HOOK_SWITCH_PIN={hook_config['pin']}")
    else:
        env_lines.append(f"# Multi-pin hook switch detected: {hook_config['pins']}")
        env_lines.append(f"HOOK_SWITCH_PIN={hook_config['pins'][0]}  # Using first pin")

    if keypad_config:
        env_lines.append(f"KEYPAD_ROW_PINS={json.dumps(keypad_config['row_pins'])}")
        env_lines.append(f"KEYPAD_COL_PINS={json.dumps(keypad_config['col_pins'])}")

    env_file = output_file.replace('.json', '.env')
    with open(env_file, 'w') as f:
        f.write('\n'.join(env_lines))

    print_success(f"Environment config saved to {env_file}")

    return config

def main():
    print_header("Payphone GPIO Pin Calibration Tool")

    print(f"{Colors.BOLD}This tool will automatically detect your pin connections.{Colors.END}")
    print("Make sure your hardware is connected and ready.")
    print()
    input("Press Enter to start calibration...")

    try:
        setup_gpio()

        # Calibrate hook switch
        hook_config = calibrate_hook_switch()
        if not hook_config:
            print_error("Hook switch calibration failed!")
            return 1

        time.sleep(1)

        # Calibrate keypad
        keypad_config = calibrate_keypad()
        if not keypad_config:
            print_error("Keypad calibration failed!")
            return 1

        # Save configuration
        print_header("Calibration Complete")

        print(f"{Colors.GREEN}{Colors.BOLD}Successfully calibrated all pins!{Colors.END}\n")

        print(f"{Colors.BOLD}Hook Switch:{Colors.END}")
        if hook_config['type'] == 'single':
            print(f"  Pin: GPIO {hook_config['pin']}")
            print(f"  Active state: {hook_config['active_state']}")
        else:
            print(f"  Pins: {hook_config['pins']}")

        print(f"\n{Colors.BOLD}Keypad Matrix:{Colors.END}")
        print(f"  Row pins: {keypad_config['row_pins']}")
        print(f"  Col pins: {keypad_config['col_pins']}")

        # Save configuration
        config = save_configuration(hook_config, keypad_config)

        print(f"\n{Colors.CYAN}Next steps:{Colors.END}")
        print("1. Review the generated pin_config.json file")
        print("2. Update /etc/payphone/.env with the new pins")
        print("3. Restart the payphone service")

        return 0

    except KeyboardInterrupt:
        print("\n\nCalibration interrupted by user")
        return 1
    except Exception as e:
        print_error(f"Calibration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        cleanup_gpio()

if __name__ == "__main__":
    if GPIO.RPI_INFO['P1_REVISION'] == 0:
        print_error("This script must be run on a Raspberry Pi!")
        sys.exit(1)

    sys.exit(main())
