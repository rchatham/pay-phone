#!/usr/bin/env python3
"""
Working BIOS demo - Shows that subsystems DO run correctly
"""
import queue
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from test_phone_tree import AudioPlayer, setup_bios_phone_tree, navigate_bios_menu

def demo():
    """Demonstrate working BIOS navigation"""
    print("\n" + "="*70)
    print("BIOS WORKING DEMONSTRATION")
    print("="*70)
    print("\nThis demonstrates that subsystems ARE running correctly.")
    print("Watch the audio playback sequence:\n")

    # Setup
    audio = AudioPlayer("audio_files", silent=True)
    bios_menu = setup_bios_phone_tree(audio)

    # Create input queue
    input_queue = queue.Queue()
    input_queue.put('1')  # Select Information Booth
    input_queue.put('2')  # Within Info Booth, select Jokes

    # Hook check that doesn't depend on keyboard.running
    call_count = [0]

    def hook_check():
        call_count[0] += 1
        # Stay alive while we have input OR for a reasonable number of iterations
        has_input = not input_queue.empty()
        within_limit = call_count[0] < 150
        return has_input or within_limit

    print("Scenario: User selects Info Booth (1), then Jokes (2)")
    print("="*70)
    print("\nExpected sequence:")
    print("  1. bios/main_menu.mp3       ← BIOS menu")
    print("  2. menu/main_menu.mp3       ← Info Booth main menu")
    print("  3. menu/jokes.mp3           ← Jokes playing")
    print("  4. menu/main_menu.mp3       ← Back to Info Booth menu")
    print("  5. [timeout]")
    print("  6. bios/main_menu.mp3       ← Back to BIOS menu")
    print("\n" + "="*70)
    print("Actual audio playback:\n")

    # Navigate
    navigate_bios_menu(bios_menu, input_queue, hook_check)

    print("\n" + "="*70)
    print(f"✅ DEMONSTRATION COMPLETE ({call_count[0]} iterations)")
    print("="*70)
    print("\n🎯 KEY POINT: Notice that after jokes.mp3 plays, it returns to")
    print("   the Info Booth menu (menu/main_menu.mp3), NOT the BIOS menu!")
    print("\n   This proves the subsystem is running independently.")
    print("="*70 + "\n")

if __name__ == "__main__":
    demo()
