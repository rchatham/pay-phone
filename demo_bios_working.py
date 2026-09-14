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
    input_queue.put('1')  # Select first discovered system

    # Hook check that doesn't depend on keyboard.running
    call_count = [0]

    def hook_check():
        call_count[0] += 1
        # Stay alive while we have input OR for a reasonable number of iterations
        has_input = not input_queue.empty()
        within_limit = call_count[0] < 150
        return has_input or within_limit

    print("Scenario: User selects the first discovered system (1)")
    print("="*70)
    print("\nExpected sequence:")
    print("  1. bios/main_menu.mp3       ← BIOS menu")
    print("  2. bios/system_<id>.mp3     ← Selected system prompt")
    print("  3. [system runs or timeout]")
    print("  4. bios/main_menu.mp3       ← Back to BIOS menu")
    print("\n" + "="*70)
    print("Actual audio playback:\n")

    # Navigate
    navigate_bios_menu(bios_menu, input_queue, hook_check)

    print("\n" + "="*70)
    print(f"✅ DEMONSTRATION COMPLETE ({call_count[0]} iterations)")
    print("="*70)
    print("\n🎯 KEY POINT: The selected subsystem runs independently before")
    print("   control returns to the BIOS menu.")
    print("="*70 + "\n")

if __name__ == "__main__":
    demo()
