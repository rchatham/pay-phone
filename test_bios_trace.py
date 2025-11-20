#!/usr/bin/env python3
"""
Trace BIOS navigation step-by-step to see what's happening
"""
import logging
import queue
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

from test_phone_tree import AudioPlayer, setup_bios_phone_tree
from payphone.core.phone_tree import PhoneTree

def trace_navigation():
    """Manually trace through navigation to see what happens"""
    print("\n" + "="*70)
    print("BIOS NAVIGATION TRACE")
    print("="*70 + "\n")

    # Setup
    audio = AudioPlayer("audio_files", silent=True)
    bios_menu = setup_bios_phone_tree(audio)

    print("BIOS Menu Structure:")
    print(f"  Audio: {bios_menu.audio_file}")
    print(f"  Options: {list(bios_menu.options.keys())}")
    print()

    # Get system 1
    system_1 = bios_menu.options['1']
    print("System 1 (Information Booth):")
    print(f"  Audio: {system_1.audio_file}")
    print(f"  Options: {list(system_1.options.keys()) if system_1.options else 'None'}")
    print()

    # Manually simulate what navigate_bios_menu does
    print("="*70)
    print("SIMULATING navigate_bios_menu() behavior:")
    print("="*70 + "\n")

    # Create queue and add input
    input_queue = queue.Queue()
    input_queue.put('1')  # User selects system 1
    input_queue.put('1')  # User selects option 1 within system

    call_count = [0]
    max_calls = 50

    def hook_check():
        call_count[0] += 1
        return call_count[0] < max_calls

    print("Step 1: Playing BIOS menu...")
    audio.play_file(bios_menu.audio_file, blocking=False)
    print(f"  → Played: {bios_menu.audio_file}")
    audio.stop()
    print()

    print("Step 2: Getting input from queue...")
    digit = input_queue.get(timeout=0.1)
    print(f"  → Got digit: {digit}")
    print()

    print("Step 3: Checking if digit is valid option...")
    if digit in bios_menu.options:
        print(f"  → Yes, '{digit}' is valid")
        system_tree = bios_menu.options[digit]
        print(f"  → system_tree.audio_file = {system_tree.audio_file}")
        print(f"  → system_tree.options = {list(system_tree.options.keys()) if system_tree.options else 'None'}")
        print()

        print("Step 4: Calling system_tree.navigate(queue, hook, system_tree)...")
        print("  → This should:")
        print("     a) Play the system's main menu")
        print("     b) Wait for input")
        print("     c) Navigate within the system")
        print()

        # Call navigate
        print("  → Executing navigate()...")
        try:
            system_tree.navigate(input_queue, hook_check, system_tree)
            print(f"  → Navigate completed after {call_count[0]} calls")
        except Exception as e:
            print(f"  → ERROR: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"  → No, '{digit}' is NOT valid")

    print()
    print("="*70)
    print("EXPECTED AUDIO SEQUENCE:")
    print("="*70)
    print("1. bios/main_menu.mp3       (BIOS menu)")
    print("2. menu/main_menu.mp3       (Info Booth menu)")
    print("3. menu/info_menu.mp3       (Info submenu)")
    print("4. menu/main_menu.mp3       (Back to Info Booth)")
    print("="*70 + "\n")

if __name__ == "__main__":
    trace_navigation()
