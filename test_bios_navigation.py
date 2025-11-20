#!/usr/bin/env python3
"""
Test BIOS navigation programmatically
"""
import logging
import queue
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from test_phone_tree import AudioPlayer, setup_bios_phone_tree

def test_bios_navigation():
    """Test BIOS menu navigation"""
    print("\n" + "="*60)
    print("BIOS NAVIGATION TEST")
    print("="*60 + "\n")

    # Create audio player in silent mode
    audio = AudioPlayer("audio_files", silent=True)

    # Build BIOS menu
    print("Building BIOS menu...")
    bios_menu = setup_bios_phone_tree(audio)
    print(f"✓ BIOS menu created with {len(bios_menu.options)} options\n")

    # Create input queue
    input_queue = queue.Queue()

    # Test 1: Navigate to Information Booth (option 1)
    print("TEST 1: Navigate to Information Booth System")
    print("-" * 60)
    input_queue.put('1')  # Select system 1

    # Run navigation with limited iterations
    iteration_count = [0]
    max_iterations = 50

    def hook_status():
        iteration_count[0] += 1
        has_input = not input_queue.empty()
        within_limit = iteration_count[0] < max_iterations
        return has_input or within_limit

    try:
        print("Starting navigation...")
        bios_menu.navigate(input_queue, hook_status, bios_menu)
        print(f"✓ Navigation completed after {iteration_count[0]} iterations\n")
    except Exception as e:
        print(f"✗ Navigation failed: {e}\n")
        import traceback
        traceback.print_exc()

    # Test 2: Navigate to option within Information Booth
    print("\nTEST 2: Navigate within Information Booth")
    print("-" * 60)
    input_queue = queue.Queue()
    input_queue.put('1')  # Select Information Booth
    input_queue.put('1')  # Select option 1 within Information Booth

    iteration_count[0] = 0

    try:
        print("Starting navigation...")
        bios_menu.navigate(input_queue, hook_status, bios_menu)
        print(f"✓ Navigation completed after {iteration_count[0]} iterations\n")
    except Exception as e:
        print(f"✗ Navigation failed: {e}\n")
        import traceback
        traceback.print_exc()

    print("="*60)
    print("✅ BIOS navigation tests complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_bios_navigation()
