#!/usr/bin/env python3
"""
Interactive BIOS test - Shows what audio would play at each step
"""
import sys
from pathlib import Path
import queue

sys.path.insert(0, str(Path(__file__).parent))

from test_phone_tree import AudioPlayer, setup_bios_phone_tree, navigate_bios_menu

def interactive_test():
    """Interactive test showing audio playback"""
    print("\n" + "="*70)
    print("INTERACTIVE BIOS TEST")
    print("="*70)
    print("\nThis test shows you what audio plays at each step.")
    print("Type keys and see what happens!\n")

    # Create audio player NOT in silent mode
    print("Creating audio player (non-silent to actually hear audio)...")
    audio = AudioPlayer("audio_files", silent=False)

    # Build BIOS menu
    print("Building BIOS menu...")
    bios_menu = setup_bios_phone_tree(audio)
    print(f"✓ BIOS menu ready with {len(bios_menu.options)} systems\n")

    # Show menu structure
    print("Available systems:")
    for digit, tree in bios_menu.options.items():
        print(f"  Press '{digit}' → {tree.audio_file}")
    print()

    # Manual step-by-step navigation
    print("="*70)
    print("STEP-BY-STEP TEST")
    print("="*70)
    print()

    # Step 1: Play BIOS menu
    print("STEP 1: Playing BIOS menu...")
    audio.play_file(bios_menu.audio_file, blocking=False)
    input("  → Audio should be playing. Press Enter when done...")
    audio.stop()
    print()

    # Step 2: Simulate selecting option 1
    print("STEP 2: User selects option '1' (Information Booth)")
    system_1 = bios_menu.options['1']
    print(f"  → System 1 audio file: {system_1.audio_file}")
    print(f"  → System 1 has {len(system_1.options) if system_1.options else 0} options")
    if system_1.options:
        print(f"  → System 1 options: {list(system_1.options.keys())}")
    print()

    print("  Playing Information Booth menu...")
    audio.play_file(system_1.audio_file, blocking=False)
    input("  → Audio should be playing. Press Enter when done...")
    audio.stop()
    print()

    # Step 3: Navigate within system
    if system_1.options and '1' in system_1.options:
        print("STEP 3: User selects option '1' within Information Booth")
        subsystem = system_1.options['1']
        print(f"  → Subsystem audio file: {subsystem.audio_file}")
        print()

        print("  Playing Info submenu...")
        audio.play_file(subsystem.audio_file, blocking=False)
        input("  → Audio should be playing. Press Enter when done...")
        audio.stop()
        print()

        print("STEP 4: Submenu ends, should return to Information Booth menu")
        print(f"  → Would return to: {system_1.audio_file}")
        print()

    # Now test automated navigation
    print("="*70)
    print("AUTOMATED NAVIGATION TEST")
    print("="*70)
    print("\nNow let's test the actual navigate_bios_menu() function")
    print("This will auto-play: BIOS → Info Booth → Info Submenu")
    print()

    input("Press Enter to start automated test...")

    # Create input queue
    input_queue = queue.Queue()
    input_queue.put('1')  # Select Info Booth
    input_queue.put('1')  # Select Info submenu

    call_count = [0]

    def hook_check():
        call_count[0] += 1
        return call_count[0] < 100 and not input_queue.empty()

    print("\nRunning navigate_bios_menu()...\n")
    navigate_bios_menu(bios_menu, input_queue, hook_check)

    print(f"\n✓ Navigation completed ({call_count[0]} calls)")
    print()

    print("="*70)
    print("TEST COMPLETE")
    print("="*70)
    print("\nDid you hear:")
    print("  1. BIOS menu audio?")
    print("  2. Information Booth menu audio?")
    print("  3. Info submenu audio?")
    print()
    print("If not, check:")
    print("  - Are audio files present?")
    print("  - Is your speaker/audio working?")
    print("  - Try running with silent=True to see logs instead")
    print("="*70 + "\n")

if __name__ == "__main__":
    interactive_test()
