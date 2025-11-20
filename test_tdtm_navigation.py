#!/usr/bin/env python3
"""
Test TDTM navigation from BIOS
"""
import queue
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from test_phone_tree import AudioPlayer, setup_bios_phone_tree, navigate_bios_menu

def test_tdtm():
    """Test navigating to TDTM system"""
    print("\n" + "="*70)
    print("TDTM NAVIGATION TEST")
    print("="*70)
    print("\nThis tests navigating from BIOS to TDTM system\n")

    # Setup
    audio = AudioPlayer("audio_files", silent=True)
    bios_menu = setup_bios_phone_tree(audio)

    # Create input queue
    input_queue = queue.Queue()
    input_queue.put('2')  # Select TDTM
    input_queue.put('9')  # Within TDTM, press 9 for random recording

    # Hook check
    call_count = [0]

    def hook_check():
        call_count[0] += 1
        return call_count[0] < 150

    print("Scenario: Select TDTM (2), then press 9 for random recording")
    print("="*70)
    print("\nExpected sequence:")
    print("  1. bios/main_menu.mp3")
    print("  2. user-instructions/abbey-combined-intro.wav  ← TDTM welcome")
    print("  3. [TDTM plays random recording]")
    print("  4. user-instructions/abbey-combined-intro.wav  ← Back to TDTM menu")
    print("  5. [timeout]")
    print("  6. bios/main_menu.mp3                         ← Back to BIOS")
    print("\n" + "="*70)
    print("Actual audio playback:\n")

    # Navigate
    navigate_bios_menu(bios_menu, input_queue, hook_check)

    print("\n" + "="*70)
    print(f"✅ TEST COMPLETE ({call_count[0]} iterations)")
    print("="*70)
    print("\n🎯 If you saw TDTM's welcome message, it's working!")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_tdtm()
