#!/usr/bin/env python3
"""
Simple Pin State Viewer

Shows the raw state of all your pins in real-time.
This helps diagnose wiring issues.
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

def read_pins_multiple_times(num_reads=5):
    """
    Read each pin multiple times to detect stability.
    Returns dict with pin -> most common state
    """
    pin_readings = {pin: [] for pin in PINS}

    for _ in range(num_reads):
        for pin in PINS:
            try:
                state = GPIO.input(pin)
                pin_readings[pin].append(state)
            except:
                pin_readings[pin].append(None)
        time.sleep(0.01)

    # Get most common state for each pin
    stable_states = {}
    for pin, readings in pin_readings.items():
        if readings and readings[0] is not None:
            # Check if stable (all same)
            if len(set(readings)) == 1:
                stable_states[pin] = ('STABLE', readings[0])
            else:
                # Count HIGH vs LOW
                high_count = readings.count(1)
                low_count = readings.count(0)
                most_common = 1 if high_count > low_count else 0
                stable_states[pin] = ('UNSTABLE', most_common)
        else:
            stable_states[pin] = ('ERROR', None)

    return stable_states

def main():
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{'Simple Pin State Viewer'.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    print(f"\nThis will show you the actual state of each pin.")
    print(f"Testing {len(PINS)} pins: {PINS}")

    try:
        setup_gpio()

        # Test with pull-up resistors
        print(f"\n{Colors.BOLD}=== PULL-UP RESISTORS ==={Colors.END}")

        print("\nSetting up all pins as inputs with PULL-UP...")
        for pin in PINS:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        time.sleep(0.5)

        print(f"\n{Colors.YELLOW}Handset should be ON HOOK (hung up){Colors.END}")
        input("Press Enter to read pin states...")

        on_hook = read_pins_multiple_times(5)

        print(f"\n{'Pin':<8} {'Stability':<12} {'State':<8}")
        print("-" * 30)
        for pin in sorted(PINS):
            stability, state = on_hook[pin]
            if state is not None:
                state_str = "HIGH" if state == 1 else "LOW"
                if stability == 'STABLE':
                    color = Colors.GREEN
                else:
                    color = Colors.YELLOW
                print(f"{color}GPIO {pin:<3} {stability:<12} {state_str}{Colors.END}")
            else:
                print(f"{Colors.RED}GPIO {pin:<3} ERROR{Colors.END}")

        print(f"\n{Colors.YELLOW}Now LIFT the handset (OFF HOOK){Colors.END}")
        input("Press Enter to read pin states...")

        time.sleep(0.5)

        off_hook = read_pins_multiple_times(5)

        print(f"\n{'Pin':<8} {'Stability':<12} {'State':<8} {'Changed?':<10}")
        print("-" * 45)

        changed_pins = []
        for pin in sorted(PINS):
            stability, state = off_hook[pin]
            if state is not None and pin in on_hook:
                state_str = "HIGH" if state == 1 else "LOW"
                old_state = on_hook[pin][1]

                if old_state is not None and old_state != state:
                    changed_pins.append(pin)
                    change_str = f"{'HIGH' if old_state else 'LOW'} → {'HIGH' if state else 'LOW'}"
                    color = Colors.RED
                else:
                    change_str = "No"
                    color = Colors.GREEN if stability == 'STABLE' else Colors.YELLOW

                print(f"{color}GPIO {pin:<3} {stability:<12} {state_str:<8} {change_str}{Colors.END}")
            else:
                print(f"{Colors.RED}GPIO {pin:<3} ERROR{Colors.END}")

        print(f"\n{Colors.BOLD}Summary:{Colors.END}")
        print(f"  Pins that changed: {changed_pins if changed_pins else 'NONE'}")
        print(f"  Total changed: {len(changed_pins)}")

        # Check if too many pins changed
        if len(changed_pins) > 2:
            print(f"\n{Colors.RED}⚠ WARNING: Too many pins changed!{Colors.END}")
            print("This suggests:")
            print("  1. Multiple pins are electrically connected together")
            print("  2. Wiring issue (short circuit)")
            print("  3. Ground/power rail issue")
            print("\nLet's check which pins are actually different...")

            # Show actual voltage levels
            print(f"\n{Colors.CYAN}Detailed state comparison:{Colors.END}")
            for pin in sorted(PINS):
                if pin in on_hook and pin in off_hook:
                    on_state = on_hook[pin][1]
                    off_state = off_hook[pin][1]
                    if on_state is not None and off_state is not None:
                        on_str = "HIGH(1)" if on_state else "LOW(0)"
                        off_str = "HIGH(1)" if off_state else "LOW(0)"
                        if on_state != off_state:
                            print(f"  {Colors.RED}GPIO {pin}: {on_str} → {off_str}{Colors.END}")
                        else:
                            print(f"  GPIO {pin}: {on_str} (no change)")

        elif len(changed_pins) == 0:
            print(f"\n{Colors.RED}⚠ No pins changed!{Colors.END}")
            print("Possible issues:")
            print("  1. Hook switch not connected to any of these pins")
            print("  2. Hook switch is broken")
            print("  3. Need to use pull-down instead of pull-up")

            # Try pull-down
            print(f"\n{Colors.BOLD}Let's try PULL-DOWN resistors...{Colors.END}")
            print(f"\n{Colors.YELLOW}HANG UP the handset first{Colors.END}")
            input("Press Enter when ready...")

            for pin in PINS:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            time.sleep(0.5)

            on_hook_pd = read_pins_multiple_times(5)

            print(f"\n{Colors.YELLOW}Now LIFT the handset{Colors.END}")
            input("Press Enter...")

            time.sleep(0.5)

            off_hook_pd = read_pins_multiple_times(5)

            print(f"\n{'Pin':<8} {'On Hook':<12} {'Off Hook':<12} {'Changed?':<10}")
            print("-" * 50)

            pd_changed = []
            for pin in sorted(PINS):
                if pin in on_hook_pd and pin in off_hook_pd:
                    on_state = on_hook_pd[pin][1]
                    off_state = off_hook_pd[pin][1]
                    if on_state is not None and off_state is not None:
                        on_str = "HIGH" if on_state else "LOW"
                        off_str = "HIGH" if off_state else "LOW"
                        if on_state != off_state:
                            pd_changed.append(pin)
                            print(f"{Colors.RED}GPIO {pin:<3} {on_str:<12} {off_str:<12} YES{Colors.END}")
                        else:
                            print(f"GPIO {pin:<3} {on_str:<12} {off_str:<12} No")

            if pd_changed:
                print(f"\n{Colors.GREEN}✓ Found with pull-down: {pd_changed}{Colors.END}")
            else:
                print(f"\n{Colors.RED}Still no pins detected{Colors.END}")

        else:
            print(f"\n{Colors.GREEN}✓ This looks correct!{Colors.END}")
            print(f"Hook switch appears to be on: {changed_pins}")

    except KeyboardInterrupt:
        print("\n\nInterrupted")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
    finally:
        GPIO.cleanup()
        print(f"\n{Colors.CYAN}GPIO cleaned up{Colors.END}")

if __name__ == "__main__":
    main()
