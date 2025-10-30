#!/usr/bin/env python3
"""
Raw Pin State Monitor

Simply reads and displays the state of all pins.
No fancy logic - just shows you what's happening.
"""

import RPi.GPIO as GPIO
import time
import sys

# Your pins
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

def read_all_pins(mode='PULLUP'):
    """Read all pins with specified resistor mode"""
    states = {}

    for pin in PINS:
        try:
            if mode == 'PULLUP':
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            elif mode == 'PULLDOWN':
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            else:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)

            time.sleep(0.001)
            states[pin] = GPIO.input(pin)
        except Exception as e:
            states[pin] = f"ERROR: {e}"

    return states

def display_states(states, title):
    """Display pin states in a readable format"""
    print(f"\n{Colors.BOLD}{title}{Colors.END}")
    print(f"{'Pin':<10} {'State':<10}")
    print("-" * 20)

    for pin in sorted(PINS):
        state = states.get(pin)
        if isinstance(state, int):
            state_str = "HIGH (1)" if state == 1 else "LOW  (0)"
            color = Colors.GREEN if state == 1 else Colors.CYAN
        else:
            state_str = str(state)
            color = Colors.RED

        print(f"{color}GPIO {pin:<3}  {state_str}{Colors.END}")

def compare_states(before, after, show_low_pins=True):
    """Show which pins changed and optionally all LOW pins"""
    changes = []
    print(f"\n{Colors.BOLD}CHANGES:{Colors.END}")

    for pin in sorted(PINS):
        if pin in before and pin in after:
            if isinstance(before[pin], int) and isinstance(after[pin], int):
                if before[pin] != after[pin]:
                    old = "HIGH" if before[pin] else "LOW"
                    new = "HIGH" if after[pin] else "LOW"
                    print(f"{Colors.YELLOW}  GPIO {pin}: {old} → {new}{Colors.END}")
                    changes.append(pin)

    if not changes:
        print(f"  {Colors.RED}No pins changed state{Colors.END}")

    # Also show all pins that are currently LOW (for keypad detection)
    if show_low_pins:
        low_pins = []
        high_pins = []
        for pin in sorted(PINS):
            if pin in after and isinstance(after[pin], int):
                if after[pin] == 0:
                    low_pins.append(pin)
                else:
                    high_pins.append(pin)

        if low_pins or high_pins:
            print(f"\n{Colors.BOLD}CURRENT STATE:{Colors.END}")
            if low_pins:
                print(f"  {Colors.CYAN}LOW pins:  {low_pins}{Colors.END}")
            if high_pins:
                print(f"  {Colors.GREEN}HIGH pins: {high_pins}{Colors.END}")

    return changes

def test_with_mode(mode_name, resistor_mode):
    """Test hook switch and keypad with a specific resistor configuration"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{f'Testing with {mode_name}'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    # Hook switch test
    print(f"\n{Colors.CYAN}=== Hook Switch Test ==={Colors.END}")
    print(f"\n{Colors.YELLOW}Handset should be ON HOOK (hung up){Colors.END}")
    input("Press Enter to read pins...")

    on_hook = read_all_pins(resistor_mode)
    display_states(on_hook, "On Hook State")

    print(f"\n{Colors.YELLOW}LIFT the handset (OFF HOOK){Colors.END}")
    input("Press Enter to read pins...")

    off_hook = read_all_pins(resistor_mode)
    display_states(off_hook, "Off Hook State")

    hook_changes = compare_states(on_hook, off_hook)

    if hook_changes:
        print(f"\n{Colors.GREEN}✓ Hook switch detected on: {hook_changes}{Colors.END}")
    else:
        print(f"\n{Colors.RED}✗ No hook switch detected{Colors.END}")

    # Keypad test - test multiple buttons
    print(f"\n{Colors.CYAN}=== Keypad Test ==={Colors.END}")
    print(f"\n{Colors.YELLOW}Make sure NO buttons are pressed{Colors.END}")
    input("Press Enter to read baseline...")

    baseline = read_all_pins(resistor_mode)
    display_states(baseline, "Baseline (no buttons)")

    # Test buttons: 1, 2, 4, 5, 9, 0
    # This will show us:
    #   1 (row 0, col 0) - row 0 + col 0
    #   2 (row 0, col 1) - row 0 + col 1
    #   4 (row 1, col 0) - row 1 + col 0
    #   5 (row 1, col 1) - row 1 + col 1
    #   9 (row 2, col 2) - row 2 + col 2
    #   0 (row 3, col 1) - row 3 + col 1

    test_buttons = ['1', '2', '4', '5', '9', '0']
    button_results = {}

    for button in test_buttons:
        print(f"\n{Colors.YELLOW}Press and HOLD button '{button}'{Colors.END}")
        input("Press Enter while holding...")

        button_pressed = read_all_pins(resistor_mode)
        display_states(button_pressed, f"Button '{button}' Pressed")

        changes = compare_states(baseline, button_pressed, show_low_pins=True)

        # Store both changes and LOW pins for analysis
        low_pins_when_pressed = [p for p in PINS if p in button_pressed and button_pressed[p] == 0]
        button_results[button] = {
            'changes': changes,
            'low_pins': low_pins_when_pressed
        }

        if changes:
            print(f"\n{Colors.GREEN}✓ Button '{button}' - {len(changes)} pin(s) changed{Colors.END}")
        else:
            print(f"\n{Colors.YELLOW}Note: Button '{button}' - No changes, but {len(low_pins_when_pressed)} pin(s) are LOW{Colors.END}")

    return hook_changes, button_results

def main():
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'Raw Pin State Monitor'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print(f"\nThis tool shows RAW pin states with no processing.")
    print(f"Testing {len(PINS)} pins: {PINS}")
    print("\nWe'll test with different resistor configurations:")
    print("  1. Pull-up resistors (pins default to HIGH)")
    print("  2. Pull-down resistors (pins default to LOW)")
    print("  3. Floating (no resistors - may be unstable)")

    input("\nPress Enter to start...")

    try:
        setup_gpio()
        print(f"{Colors.GREEN}✓ GPIO initialized{Colors.END}")

        results = {}

        # Test with pull-up
        hook_pullup, button_pullup = test_with_mode("PULL-UP RESISTORS", "PULLUP")
        results['pullup'] = {'hook': hook_pullup, 'button': button_pullup}

        time.sleep(1)

        # Test with pull-down
        hook_pulldown, button_pulldown = test_with_mode("PULL-DOWN RESISTORS", "PULLDOWN")
        results['pulldown'] = {'hook': hook_pulldown, 'button': button_pulldown}

        # Summary
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{'SUMMARY'.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}")

        print(f"\n{Colors.CYAN}Pull-up resistors:{Colors.END}")
        print(f"  Hook switch: {results['pullup']['hook'] if results['pullup']['hook'] else 'Not detected'}")
        print(f"  Keypad buttons:")
        for button, data in results['pullup']['button'].items():
            changes = data['changes']
            low_pins = data['low_pins']
            status = f"Changes: {changes}, LOW pins: {low_pins}" if changes or low_pins else "Not detected"
            print(f"    Button '{button}': {status}")

        print(f"\n{Colors.CYAN}Pull-down resistors:{Colors.END}")
        print(f"  Hook switch: {results['pulldown']['hook'] if results['pulldown']['hook'] else 'Not detected'}")
        print(f"  Keypad buttons:")
        for button, data in results['pulldown']['button'].items():
            changes = data['changes']
            low_pins = data['low_pins']
            status = f"Changes: {changes}, LOW pins: {low_pins}" if changes or low_pins else "Not detected"
            print(f"    Button '{button}': {status}")

        # Diagnosis
        print(f"\n{Colors.BOLD}Diagnosis:{Colors.END}")

        # Check if anything was detected
        pullup_detected = results['pullup']['hook'] or any(
            data['changes'] or data['low_pins'] for data in results['pullup']['button'].values()
        )
        pulldown_detected = results['pulldown']['hook'] or any(
            data['changes'] or data['low_pins'] for data in results['pulldown']['button'].values()
        )

        if not pullup_detected and not pulldown_detected:
            print(f"{Colors.RED}No changes detected with any configuration!{Colors.END}")
            print("\nPossible issues:")
            print("  1. Hardware not actually connected to these GPIO pins")
            print("  2. Wiring problem (loose connections)")
            print("  3. Hardware fault (broken switches)")
            print("  4. Wrong pins specified")
            print("\nRecommendation: Double-check physical wiring")
        else:
            print(f"{Colors.GREEN}Some changes detected - configuration is working!{Colors.END}")

            # Analyze button patterns
            print(f"\n{Colors.CYAN}Button Analysis:{Colors.END}")

            # Use whichever mode detected buttons
            button_data = results['pullup']['button'] if pullup_detected else results['pulldown']['button']
            working_buttons = [btn for btn, data in button_data.items() if data['changes'] or data['low_pins']]

            if working_buttons:
                print(f"  Working buttons: {working_buttons}")

                # Check if we can identify row/column pins
                print(f"\n  Keypad matrix analysis:")
                for btn in ['1', '2', '4', '5', '9', '0']:
                    data = button_data.get(btn)
                    if data:
                        changes = data['changes']
                        low_pins = data['low_pins']
                        print(f"    Button {btn}: Changes={changes}, LOW={low_pins}")

                # Find common pins - use low_pins for comparison
                btn1_pins = set(button_data.get('1', {}).get('low_pins', []))
                btn2_pins = set(button_data.get('2', {}).get('low_pins', []))
                btn4_pins = set(button_data.get('4', {}).get('low_pins', []))
                btn5_pins = set(button_data.get('5', {}).get('low_pins', []))

                if btn1_pins and btn2_pins:
                    common_1_2 = btn1_pins & btn2_pins
                    if common_1_2:
                        print(f"\n  {Colors.YELLOW}Pins shared by buttons 1 and 2: {common_1_2}{Colors.END}")
                        print(f"    → These are likely ROW 0 pins (both buttons in row 0)")

                if btn1_pins and btn4_pins:
                    common_1_4 = btn1_pins & btn4_pins
                    if common_1_4:
                        print(f"  {Colors.YELLOW}Pins shared by buttons 1 and 4: {common_1_4}{Colors.END}")
                        print(f"    → These are likely COLUMN 0 pins (both buttons in column 0)")

                if btn2_pins and btn5_pins:
                    common_2_5 = btn2_pins & btn5_pins
                    if common_2_5:
                        print(f"  {Colors.YELLOW}Pins shared by buttons 2 and 5: {common_2_5}{Colors.END}")
                        print(f"    → These are likely COLUMN 1 pins (both buttons in column 1)")

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
    finally:
        GPIO.cleanup()
        print(f"\n{Colors.CYAN}GPIO cleaned up{Colors.END}")

if __name__ == "__main__":
    main()
