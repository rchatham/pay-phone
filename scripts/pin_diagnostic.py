#!/usr/bin/env python3
"""
GPIO Pin Diagnostic Tool

Shows the raw state of all GPIO pins before and after an action.
This helps identify which pins are actually connected to your hardware.
"""

import RPi.GPIO as GPIO
import time
import sys

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

def read_all_pins(mode='INPUT_PULLUP'):
    """Read all GPIO pins with specified mode"""
    states = {}

    for pin in SAFE_GPIO_PINS:
        try:
            if mode == 'INPUT_PULLUP':
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            elif mode == 'INPUT_PULLDOWN':
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            else:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)

            time.sleep(0.001)
            states[pin] = GPIO.input(pin)
        except Exception as e:
            states[pin] = f"Error: {e}"

    return states

def print_pin_states(states, title="Pin States"):
    """Print pin states in a readable format"""
    print(f"\n{Colors.BOLD}=== {title} ==={Colors.END}")
    print(f"{'GPIO':<6} {'State':<10} {'Binary':<10}")
    print("-" * 30)

    for pin in sorted(states.keys()):
        state = states[pin]
        if isinstance(state, int):
            state_str = "HIGH" if state == 1 else "LOW"
            color = Colors.GREEN if state == 1 else Colors.CYAN
            print(f"{color}GPIO{pin:<2} {state_str:<10} {state}{Colors.END}")
        else:
            print(f"{Colors.RED}GPIO{pin:<2} {state}{Colors.END}")

def compare_states(before, after):
    """Compare two pin state snapshots and show differences"""
    print(f"\n{Colors.BOLD}=== CHANGES DETECTED ==={Colors.END}")
    print(f"{'GPIO':<6} {'Before':<10} {'After':<10} {'Change':<10}")
    print("-" * 40)

    changes = []
    for pin in sorted(before.keys()):
        if pin in after and isinstance(before[pin], int) and isinstance(after[pin], int):
            if before[pin] != after[pin]:
                before_str = "HIGH" if before[pin] == 1 else "LOW"
                after_str = "HIGH" if after[pin] == 1 else "LOW"
                arrow = "→"
                changes.append(pin)
                print(f"{Colors.YELLOW}GPIO{pin:<2} {before_str:<10} {after_str:<10} {before_str} {arrow} {after_str}{Colors.END}")

    if not changes:
        print(f"{Colors.RED}No changes detected!{Colors.END}")
    else:
        print(f"\n{Colors.GREEN}{len(changes)} pin(s) changed: {changes}{Colors.END}")

    return changes

def test_hook_switch():
    """Diagnostic test for hook switch"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'Hook Switch Diagnostic Test'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print("\nWe'll test with different resistor configurations:")
    print("  1. Pull-up resistors (most common)")
    print("  2. Pull-down resistors")
    print("  3. No pull resistors")

    for test_mode in ['INPUT_PULLUP', 'INPUT_PULLDOWN', 'INPUT_FLOATING']:
        print(f"\n{Colors.BOLD}Testing with {test_mode}...{Colors.END}")

        print(f"\n{Colors.YELLOW}Current state: Handset should be ON HOOK (hung up){Colors.END}")
        input("Press Enter when ready...")

        on_hook_states = read_all_pins(test_mode)
        print_pin_states(on_hook_states, f"On Hook States ({test_mode})")

        print(f"\n{Colors.YELLOW}Action: LIFT the handset (OFF HOOK){Colors.END}")
        input("Press Enter after lifting...")

        time.sleep(0.3)
        off_hook_states = read_all_pins(test_mode)
        print_pin_states(off_hook_states, f"Off Hook States ({test_mode})")

        changes = compare_states(on_hook_states, off_hook_states)

        if changes:
            print(f"\n{Colors.GREEN}✓ Hook switch detected on pin(s): {changes}{Colors.END}")
            print(f"   Mode: {test_mode}")
            return changes, test_mode

        print(f"\n{Colors.RED}✗ No changes detected with {test_mode}{Colors.END}")

        print(f"\n{Colors.YELLOW}Action: HANG UP the handset (ON HOOK){Colors.END}")
        input("Press Enter to continue to next test...")

    return None, None

def test_keypad():
    """Diagnostic test for keypad"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'Keypad Diagnostic Test'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print("\n{Colors.YELLOW}Make sure NO keys are pressed{Colors.END}")
    input("Press Enter when ready...")

    baseline = read_all_pins('INPUT_PULLUP')
    print_pin_states(baseline, "Baseline (no keys pressed)")

    print(f"\n{Colors.YELLOW}Press and HOLD the '5' button on the keypad{Colors.END}")
    input("Press Enter while holding the button...")

    time.sleep(0.2)
    pressed = read_all_pins('INPUT_PULLUP')
    print_pin_states(pressed, "With button '5' pressed")

    changes = compare_states(baseline, pressed)

    if not changes:
        print(f"\n{Colors.RED}No keypad pins detected!{Colors.END}")
        print("\nPossible issues:")
        print("  1. Keypad not connected to GPIO pins")
        print("  2. Wiring problem")
        print("  3. Keypad requires different pull resistor configuration")
        return None

    print(f"\n{Colors.GREEN}Keypad activity detected on {len(changes)} pin(s)!{Colors.END}")

    # Test a few more buttons
    print("\nTesting additional buttons for matrix detection...")

    button_results = {}
    for button in ['1', '9', '0']:
        print(f"\n{Colors.YELLOW}Press and HOLD button '{button}'{Colors.END}")
        input("Press Enter while holding...")

        time.sleep(0.2)
        button_states = read_all_pins('INPUT_PULLUP')
        button_changes = compare_states(baseline, button_states)
        button_results[button] = button_changes

    return button_results

def main():
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'GPIO Pin Diagnostic Tool'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print("\nThis tool shows RAW pin states to help diagnose wiring issues.")
    print("It will show you exactly which pins change state when you")
    print("interact with your hardware.")

    input("\nPress Enter to start...")

    try:
        setup_gpio()
        print(f"{Colors.GREEN}✓ GPIO initialized{Colors.END}")

        # Test hook switch
        hook_pins, hook_mode = test_hook_switch()

        time.sleep(1)

        # Test keypad
        keypad_pins = test_keypad()

        # Summary
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{'DIAGNOSTIC SUMMARY'.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}")

        if hook_pins:
            print(f"\n{Colors.GREEN}Hook Switch:{Colors.END}")
            print(f"  Pins: {hook_pins}")
            print(f"  Mode: {hook_mode}")
        else:
            print(f"\n{Colors.RED}Hook Switch: NOT DETECTED{Colors.END}")
            print("  Check your wiring!")

        if keypad_pins:
            print(f"\n{Colors.GREEN}Keypad:{Colors.END}")
            all_keypad_pins = set()
            for button, pins in keypad_pins.items():
                all_keypad_pins.update(pins)
                print(f"  Button '{button}': {pins}")
            print(f"  All keypad pins: {sorted(all_keypad_pins)}")
        else:
            print(f"\n{Colors.RED}Keypad: NOT DETECTED{Colors.END}")
            print("  Check your wiring!")

        print()

    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
    finally:
        GPIO.cleanup()
        print(f"{Colors.CYAN}GPIO cleaned up{Colors.END}")

if __name__ == "__main__":
    main()
