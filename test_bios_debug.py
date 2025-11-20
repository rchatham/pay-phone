#!/usr/bin/env python3
"""
Debug BIOS navigation to see what's actually playing
"""
import logging
import queue
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s'
)

from test_phone_tree import AudioPlayer, setup_bios_phone_tree, navigate_bios_menu

def test_with_detailed_logging():
    """Test with detailed logging to see exactly what's happening"""
    print("\n" + "="*70)
    print("BIOS DEBUG TEST - Detailed Navigation Trace")
    print("="*70 + "\n")

    # Create audio player (NOT silent to see all audio events)
    print("Creating audio player (silent=True to see logs clearly)...")
    audio = AudioPlayer("audio_files", silent=True)

    # Build BIOS menu
    print("Building BIOS menu...")
    bios_menu = setup_bios_phone_tree(audio)
    print(f"✓ BIOS menu created")
    print(f"  Audio file: {bios_menu.audio_file}")
    print(f"  Options: {list(bios_menu.options.keys())}")
    print()

    # Check what each option points to
    for digit, tree in bios_menu.options.items():
        print(f"Option '{digit}':")
        print(f"  Audio: {tree.audio_file}")
        print(f"  Has options: {len(tree.options) if tree.options else 0}")
        if tree.options:
            print(f"  Suboptions: {list(tree.options.keys())}")
        print()

    # Create input queue with test inputs
    input_queue = queue.Queue()

    print("="*70)
    print("TEST: Select system 1, then navigate within it")
    print("="*70)
    print("Inputs: '1' (select Info Booth), then '1' (select Info submenu)")
    print()

    # Add inputs
    input_queue.put('1')  # Select system 1
    input_queue.put('1')  # Navigate within system

    # Track calls
    call_count = [0]
    max_calls = 100

    def hook_check():
        call_count[0] += 1
        # Continue while we have input or haven't exceeded max
        has_input = not input_queue.empty()
        within_limit = call_count[0] < max_calls

        if call_count[0] % 10 == 0:
            print(f"[Call {call_count[0]}] Queue empty: {input_queue.empty()}")

        return has_input or within_limit

    print("Starting navigation...\n")
    print("-" * 70)

    try:
        navigate_bios_menu(bios_menu, input_queue, hook_check)
        print("-" * 70)
        print(f"\n✓ Navigation completed after {call_count[0]} calls")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*70)
    print("Expected audio sequence:")
    print("  1. bios/main_menu.mp3       (BIOS menu)")
    print("  2. menu/main_menu.mp3       (Info Booth main menu)")
    print("  3. menu/info_menu.mp3       (Info submenu)")
    print("  4. menu/main_menu.mp3       (Back to Info Booth menu)")
    print("  5. bios/main_menu.mp3       (Back to BIOS after timeout)")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_with_detailed_logging()
