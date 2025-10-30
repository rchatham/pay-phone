#!/usr/bin/env python3
"""
Pin Connectivity Tester

Tests connectivity between pins by:
1. Driving one pin HIGH (output)
2. Reading all other pins (inputs with pull-down)
3. Any pin that reads HIGH is connected to the driven pin

This shows which pins are physically connected through switches/buttons.
"""

import RPi.GPIO as GPIO
import time
import sys
import os
import re
from collections import defaultdict

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
        # (pull-down ensures they read LOW unless connected to driven pin)
        for pin in test_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        time.sleep(0.01)  # Let signals stabilize

        # Read all test pins
        connected = []
        for pin in test_pins:
            state = GPIO.input(pin)
            if state == GPIO.HIGH:
                connected.append(pin)

        # Cleanup - return driven pin to safe state
        GPIO.output(driven_pin, GPIO.LOW)
        GPIO.setup(driven_pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        for pin in test_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)

        return connected

    except Exception as e:
        print(f"{Colors.RED}Error testing pin {driven_pin}: {e}{Colors.END}")
        return []

def test_hook_switch():
    """
    Test hook switch by finding which pins are connected when handset is lifted.
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'HOOK SWITCH CONNECTIVITY TEST'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print(f"\n{Colors.YELLOW}Step 1: Handset ON HOOK (hung up){Colors.END}")
    input("Press Enter when ready...")

    print("\nTesting pin connectivity (handset on hook)...")
    on_hook_connections = {}

    for driven_pin in PINS:
        test_pins = [p for p in PINS if p != driven_pin]
        connected = test_pin_connectivity(driven_pin, test_pins)
        if connected:
            on_hook_connections[driven_pin] = connected
            print(f"  GPIO {driven_pin} → {connected}")

    if not on_hook_connections:
        print(f"  {Colors.CYAN}No connections detected (expected when on hook){Colors.END}")

    print(f"\n{Colors.YELLOW}Step 2: LIFT the handset (OFF HOOK){Colors.END}")
    input("Press Enter after lifting...")

    print("\nTesting pin connectivity (handset off hook)...")
    off_hook_connections = {}

    for driven_pin in PINS:
        test_pins = [p for p in PINS if p != driven_pin]
        connected = test_pin_connectivity(driven_pin, test_pins)
        if connected:
            off_hook_connections[driven_pin] = connected
            print(f"  {Colors.GREEN}GPIO {driven_pin} → {connected}{Colors.END}")

    # Find NEW connections (connections that appeared when handset lifted)
    new_connections = {}
    for pin, connections in off_hook_connections.items():
        if pin not in on_hook_connections:
            new_connections[pin] = connections
        else:
            new_pins = [c for c in connections if c not in on_hook_connections[pin]]
            if new_pins:
                new_connections[pin] = new_pins

    print(f"\n{Colors.BOLD}Analysis:{Colors.END}")
    if new_connections:
        print(f"{Colors.GREEN}New connections when handset lifted:{Colors.END}")
        for pin, connections in new_connections.items():
            print(f"  GPIO {pin} ↔ {connections}")

        # The hook switch likely connects these pins
        all_hook_pins = set()
        for pin, connections in new_connections.items():
            all_hook_pins.add(pin)
            all_hook_pins.update(connections)

        print(f"\n{Colors.GREEN}✓ Hook switch involves pins: {sorted(all_hook_pins)}{Colors.END}")

        # If it's a simple 2-pin switch, we expect one pair
        if len(all_hook_pins) == 2:
            print(f"{Colors.GREEN}✓ Simple 2-pin hook switch detected!{Colors.END}")
        else:
            print(f"{Colors.YELLOW}Note: {len(all_hook_pins)} pins involved (unusual for hook switch){Colors.END}")

        return sorted(all_hook_pins)
    else:
        print(f"{Colors.RED}No new connections detected!{Colors.END}")
        return None

def test_keypad_button(button_name, test_pins):
    """
    Test which pins are connected when a specific button is pressed.
    """
    print(f"\n{Colors.YELLOW}Press and HOLD button '{button_name}'{Colors.END}")
    input("Press Enter while holding...")

    connections = {}

    for driven_pin in test_pins:
        other_pins = [p for p in test_pins if p != driven_pin]
        connected = test_pin_connectivity(driven_pin, other_pins)
        if connected:
            connections[driven_pin] = connected

    return connections

def test_keypad(test_pins):
    """
    Test keypad by pressing specific buttons and detecting connections.
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'KEYPAD CONNECTIVITY TEST'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print("\nWe'll test buttons 2, 4, 6, 8, and 0 to map the matrix.")
    print(f"Testing with {len(test_pins)} pins: {test_pins}")
    print("\nButton mapping strategy:")
    print("  - Buttons 2, 8, 0 share column 1")
    print("  - Buttons 4, 6 share row 1")
    print("  - This allows us to identify all rows and columns")

    button_tests = {
        '2': None,
        '4': None,
        '6': None,
        '8': None,
        '0': None
    }

    for button in ['2', '4', '6', '8', '0']:
        connections = test_keypad_button(button, test_pins)
        button_tests[button] = connections

        if connections:
            print(f"{Colors.GREEN}Button '{button}' connections:{Colors.END}")
            for pin, conn in connections.items():
                print(f"  GPIO {pin} ↔ {conn}")
        else:
            print(f"{Colors.RED}Button '{button}': No connections detected!{Colors.END}")

    # Analyze results
    print(f"\n{Colors.BOLD}Analysis:{Colors.END}")

    # Extract all involved pins
    all_keypad_pins = set()
    for button, connections in button_tests.items():
        if connections:
            for pin, conn in connections.items():
                all_keypad_pins.add(pin)
                all_keypad_pins.update(conn)

    print(f"Total pins involved in keypad: {sorted(all_keypad_pins)}")

    # For a 4x3 matrix, each button press should connect exactly one row to one column
    # So we should see connections like: pin_A ↔ [pin_B]

    # Try to deduce rows and columns
    print(f"\n{Colors.CYAN}Deducing matrix structure...{Colors.END}")

    # Count how many buttons each pin participates in
    pin_button_count = {}
    for button, connections in button_tests.items():
        if connections:
            for pin, conn in connections.items():
                pin_button_count[pin] = pin_button_count.get(pin, 0) + 1
                for c in conn:
                    pin_button_count[c] = pin_button_count.get(c, 0) + 1

    # Pins used in multiple buttons are likely rows or columns
    # Rows: used in 3 buttons (3 columns)
    # Columns: used in 4 buttons (4 rows)
    potential_rows = [pin for pin, count in pin_button_count.items() if count >= 2]
    potential_cols = [pin for pin, count in pin_button_count.items() if count >= 2]

    print(f"Pins appearing in multiple button presses: {sorted(set(potential_rows))}")

    # Show detailed button connections
    print(f"\n{Colors.BOLD}Button Connection Details:{Colors.END}")
    keypad_keys = [
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9'],
        ['*', '0', '#']
    ]

    expected_positions = {
        '2': (0, 1),  # row 0, col 1
        '4': (1, 0),  # row 1, col 0
        '6': (1, 2),  # row 1, col 2
        '8': (2, 1),  # row 2, col 1
        '0': (3, 1),  # row 3, col 1
    }

    for button, connections in button_tests.items():
        if connections:
            row, col = expected_positions[button]
            print(f"\nButton '{button}' (expected: row {row}, col {col}):")
            for pin, conn in connections.items():
                print(f"  GPIO {pin} connects to {conn}")

    return button_tests

def analyze_keypad_matrix(button_tests):
    """
    Analyze button connections to deduce row and column pins.

    Strategy for buttons 2, 4, 6, 8, 0:
    - Buttons 2, 8, 0 share column 1 (common pin = col 1)
    - Buttons 4, 6 share row 1 (common pin = row 1)
    - Button 2's unique pin = row 0
    - Button 8's unique pin = row 2
    - Button 0's unique pin = row 3
    - Button 4's unique pin = col 0
    - Button 6's unique pin = col 2

    Returns (row_pins, col_pins) or (None, None) if unable to determine.
    """
    # Extract connections as pairs (button connects pin_a to pin_b)
    button_connections = {}
    for button, connections in button_tests.items():
        if connections:
            # Each button should connect exactly 2 pins (one row, one col)
            pins_involved = set()
            for pin, conn_list in connections.items():
                pins_involved.add(pin)
                pins_involved.update(conn_list)

            if len(pins_involved) == 2:
                button_connections[button] = tuple(sorted(pins_involved))

    if not button_connections:
        return None, None

    row_pins = {}  # row_num -> pin
    col_pins = {}  # col_num -> pin

    # Step 1: Find column 1 (common to buttons 2, 8, 0)
    if '2' in button_connections and '8' in button_connections and '0' in button_connections:
        pins_2 = set(button_connections['2'])
        pins_8 = set(button_connections['8'])
        pins_0 = set(button_connections['0'])

        # Common pin is column 1
        common_280 = pins_2 & pins_8 & pins_0
        if len(common_280) == 1:
            col_pins[1] = list(common_280)[0]

            # Unique pins from these buttons are rows
            row_pins[0] = list(pins_2 - common_280)[0]  # Button 2's other pin
            row_pins[2] = list(pins_8 - common_280)[0]  # Button 8's other pin
            row_pins[3] = list(pins_0 - common_280)[0]  # Button 0's other pin

    # Step 2: Find row 1 (common to buttons 4, 6)
    if '4' in button_connections and '6' in button_connections:
        pins_4 = set(button_connections['4'])
        pins_6 = set(button_connections['6'])

        # Common pin is row 1
        common_46 = pins_4 & pins_6
        if len(common_46) == 1:
            row_pins[1] = list(common_46)[0]

            # Unique pins from these buttons are columns
            col_pins[0] = list(pins_4 - common_46)[0]  # Button 4's other pin
            col_pins[2] = list(pins_6 - common_46)[0]  # Button 6's other pin

    # Build ordered lists
    if row_pins and col_pins:
        row_list = [row_pins.get(i) for i in sorted(row_pins.keys())]
        col_list = [col_pins.get(i) for i in sorted(col_pins.keys())]

        # Remove any None values (missing rows/cols)
        row_list = [r for r in row_list if r is not None]
        col_list = [c for c in col_list if c is not None]

        return row_list, col_list

    return None, None

def update_env_file(hook_pins, row_pins, col_pins, env_path='/home/pi/payphone/.env'):
    """
    Update the .env file with the discovered pin configuration.
    """
    print(f"\n{Colors.BOLD}Updating configuration file...{Colors.END}")

    # Read existing .env file
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            content = f.read()
    else:
        print(f"{Colors.YELLOW}Warning: {env_path} not found, will create new file{Colors.END}")
        content = ""

    # Update hook switch pins
    if hook_pins:
        if len(hook_pins) == 1:
            # Single pin (connected to GND)
            hook_pin = hook_pins[0]
            # Remove old HOOK_SWITCH_PINS if exists
            content = re.sub(r'HOOK_SWITCH_PINS=\[.*?\]\n?', '', content)
            if re.search(r'HOOK_SWITCH_PIN=', content):
                content = re.sub(r'HOOK_SWITCH_PIN=\d+', f'HOOK_SWITCH_PIN={hook_pin}', content)
            else:
                content += f"\nHOOK_SWITCH_PIN={hook_pin}\n"
            print(f"  {Colors.GREEN}✓ Hook switch pin: {hook_pin} (other pin connected to GND){Colors.END}")
        elif len(hook_pins) == 2:
            # Two GPIO pins (not using GND)
            hook_json = str(hook_pins).replace("'", "")
            # Remove old HOOK_SWITCH_PIN if exists
            content = re.sub(r'HOOK_SWITCH_PIN=\d+\n?', '', content)
            if re.search(r'HOOK_SWITCH_PINS=', content):
                content = re.sub(r'HOOK_SWITCH_PINS=\[.*?\]', f'HOOK_SWITCH_PINS={hook_json}', content)
            else:
                content += f"\nHOOK_SWITCH_PINS={hook_json}\n"
            print(f"  {Colors.GREEN}✓ Hook switch pins: {hook_pins} (2-pin GPIO configuration){Colors.END}")

    # Update keypad row pins
    if row_pins:
        row_json = str(row_pins).replace("'", "")
        if re.search(r'KEYPAD_ROW_PINS=', content):
            content = re.sub(r'KEYPAD_ROW_PINS=\[.*?\]', f'KEYPAD_ROW_PINS={row_json}', content)
        else:
            content += f"\nKEYPAD_ROW_PINS={row_json}\n"
        print(f"  {Colors.GREEN}✓ Keypad rows: {row_pins}{Colors.END}")

    # Update keypad column pins
    if col_pins:
        col_json = str(col_pins).replace("'", "")
        if re.search(r'KEYPAD_COL_PINS=', content):
            content = re.sub(r'KEYPAD_COL_PINS=\[.*?\]', f'KEYPAD_COL_PINS={col_json}', content)
        else:
            content += f"\nKEYPAD_COL_PINS={col_json}\n"
        print(f"  {Colors.GREEN}✓ Keypad columns: {col_pins}{Colors.END}")

    # Write back to file
    try:
        with open(env_path, 'w') as f:
            f.write(content)
        print(f"\n{Colors.GREEN}✓ Configuration updated in {env_path}{Colors.END}")
        return True
    except Exception as e:
        print(f"\n{Colors.RED}✗ Failed to update {env_path}: {e}{Colors.END}")
        return False

def main():
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'Pin Connectivity Tester'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print(f"\n{Colors.CYAN}This tool tests which pins are electrically connected{Colors.END}")
    print(f"when you interact with the hardware (lift handset, press buttons).")
    print(f"\nTesting {len(PINS)} pins: {PINS}")

    input("\nPress Enter to start...")

    try:
        setup_gpio()
        print(f"{Colors.GREEN}✓ GPIO initialized{Colors.END}")

        # Test hook switch
        hook_pins = test_hook_switch()

        time.sleep(1)

        # Remove hook switch pins from keypad test
        if hook_pins:
            remaining_pins = [p for p in PINS if p not in hook_pins]
            print(f"\n{Colors.CYAN}Testing keypad with remaining pins: {remaining_pins}{Colors.END}")
        else:
            remaining_pins = PINS

        # Test keypad
        button_tests = test_keypad(remaining_pins)

        # Analyze keypad matrix
        row_pins = None
        col_pins = None
        if button_tests:
            print(f"\n{Colors.CYAN}Analyzing keypad matrix...{Colors.END}")
            row_pins, col_pins = analyze_keypad_matrix(button_tests)

        # Final summary
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{'SUMMARY'.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}")

        if hook_pins:
            print(f"\n{Colors.GREEN}Hook Switch:{Colors.END}")
            print(f"  Pins: {hook_pins}")
            if len(hook_pins) == 1:
                print(f"  Configuration: HOOK_SWITCH_PIN={hook_pins[0]}")
                print(f"  Type: Single pin (other side connected to GND)")
            elif len(hook_pins) == 2:
                print(f"  Configuration: HOOK_SWITCH_PINS={hook_pins}")
                print(f"  Type: 2-pin GPIO (pins connect/disconnect on hook change)")
            else:
                print(f"  {Colors.YELLOW}Warning: Unusual number of pins ({len(hook_pins)}){Colors.END}")

        if row_pins and col_pins:
            print(f"\n{Colors.GREEN}Keypad Matrix:{Colors.END}")
            print(f"  Row pins: {row_pins}")
            print(f"  Column pins: {col_pins}")
            print(f"  Matrix size: {len(row_pins)}x{len(col_pins)}")
        elif button_tests:
            print(f"\n{Colors.YELLOW}Keypad:{Colors.END}")
            print(f"  Could not automatically determine row/column mapping")
            print(f"  Review the button connection details above")

        # Ask user if they want to update .env file
        if hook_pins or (row_pins and col_pins):
            print(f"\n{Colors.BOLD}Configuration ready to save!{Colors.END}")
            response = input(f"{Colors.YELLOW}Update .env file with this configuration? (y/n): {Colors.END}").strip().lower()

            if response == 'y':
                update_env_file(hook_pins, row_pins, col_pins)
            else:
                print(f"{Colors.CYAN}Configuration not saved. You can manually update .env later.{Colors.END}")

        print()

    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
    finally:
        GPIO.cleanup()
        print(f"{Colors.CYAN}GPIO cleaned up{Colors.END}")

if __name__ == "__main__":
    main()
