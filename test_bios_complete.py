#!/usr/bin/env python3
"""
Complete BIOS simulation - Shows full navigation flow
"""
import logging
import queue
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from test_phone_tree import AudioPlayer, setup_bios_phone_tree, navigate_bios_menu

def simulate_keypresses(input_queue, keys, delay=0.5):
    """Simulate keypresses with delay"""
    for key in keys:
        print(f"  >>> User presses: {key}")
        input_queue.put(key)
        time.sleep(delay)

def run_simulation():
    """Run complete BIOS simulation"""
    print("\n" + "="*70)
    print("COMPLETE BIOS SIMULATION")
    print("="*70)
    print("\nThis simulates the full BIOS experience:")
    print("  1. Phone picked up")
    print("  2. BIOS menu plays")
    print("  3. User selects a system")
    print("  4. System launches and user navigates")
    print("="*70 + "\n")

    # Create audio player in NON-silent mode to see what plays
    print("Initializing audio player (silent=False to see audio events)...")
    audio = AudioPlayer("audio_files", silent=True)

    # Build BIOS menu
    print("Building BIOS menu...")
    bios_menu = setup_bios_phone_tree(audio)
    print(f"✓ BIOS menu created with {len(bios_menu.options)} options")
    print()

    # List available systems
    print("Available systems in BIOS menu:")
    for digit, tree in bios_menu.options.items():
        print(f"  Press '{digit}' to select a system")
    print()

    # ===================================================================
    # SCENARIO 1: Navigate to Information Booth, then into Info submenu
    # ===================================================================
    print("="*70)
    print("SCENARIO 1: Navigate to Information Booth System")
    print("="*70)
    print("\nSimulation:")
    print("  1. BIOS menu plays")
    print("  2. User presses '1' (Information Booth)")
    print("  3. Information Booth main menu plays")
    print("  4. User presses '1' (Information submenu)")
    print("  5. Information submenu plays")
    print()

    input_queue = queue.Queue()

    # Prepare inputs
    keys_to_press = ['1', '1']  # Select system 1, then option 1 within it

    print("Starting navigation with simulated keypresses...")
    print("-" * 70)

    # Track navigation
    call_count = [0]
    max_calls = 100
    key_index = [0]

    def hook_check():
        """Simulate hook status and inject keypresses"""
        call_count[0] += 1

        # Inject keys at intervals
        if call_count[0] % 20 == 10 and key_index[0] < len(keys_to_press):
            key = keys_to_press[key_index[0]]
            print(f"\n>>> KEYPRESS: {key}\n")
            input_queue.put(key)
            key_index[0] += 1

        # Continue until max calls or all keys pressed
        return call_count[0] < max_calls

    try:
        # Use custom BIOS navigation that properly switches main_menu
        navigate_bios_menu(bios_menu, input_queue, hook_check)
        print("-" * 70)
        print(f"✓ Scenario 1 completed after {call_count[0]} iterations")
        print(f"  Keys pressed: {keys_to_press[:key_index[0]]}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

    # ===================================================================
    # SCENARIO 2: Navigate to TDTM System
    # ===================================================================
    print("\n" + "="*70)
    print("SCENARIO 2: Navigate to TDTM System")
    print("="*70)
    print("\nSimulation:")
    print("  1. BIOS menu plays")
    print("  2. User presses '2' (TDTM System)")
    print("  3. TDTM system launches (placeholder in simulator)")
    print()

    input_queue = queue.Queue()
    keys_to_press = ['2']

    print("Starting navigation with simulated keypresses...")
    print("-" * 70)

    call_count[0] = 0
    key_index[0] = 0

    try:
        # Use custom BIOS navigation
        navigate_bios_menu(bios_menu, input_queue, hook_check)
        print("-" * 70)
        print(f"✓ Scenario 2 completed after {call_count[0]} iterations")
        print(f"  Keys pressed: {keys_to_press[:key_index[0]]}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

    # ===================================================================
    # SUMMARY
    # ===================================================================
    print("\n" + "="*70)
    print("SIMULATION SUMMARY")
    print("="*70)
    print("\n✅ BIOS simulation complete!")
    print("\nWhat you should see:")
    print("  - BIOS menu plays first")
    print("  - Pressing '1' navigates to Information Booth system")
    print("  - Information Booth has its own multi-level menu")
    print("  - Pressing '2' navigates to TDTM system")
    print("\nOn real hardware (Raspberry Pi):")
    print("  - Hold hook for 3 seconds → BIOS menu")
    print("  - Press * for 5 seconds → Return to BIOS")
    print("  - Both systems will work fully")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_simulation()
