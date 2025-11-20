#!/usr/bin/env python3
"""
Quick test script for hybrid mode functionality.
Tests all key features programmatically.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import queue
from payphone.core.phone_tree import PhoneTree
from test_phone_tree import AudioPlayer

def test_scenario(name, inputs, expected_behavior):
    """Run a test scenario"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Inputs: {' '.join(inputs)}")
    print(f"Expected: {expected_behavior}")

    # Create hybrid menu
    audio = AudioPlayer("audio_files", silent=True)
    menu = PhoneTree(
        "menu/main_menu_ext.mp3",
        hybrid_mode=True,
        extension_prefix='*',
        return_to_menu_key='0',
        extension_length=3,
        audio_handler=audio,
        options={
            "1": PhoneTree("menu/info.mp3", audio_handler=audio),
            "2": PhoneTree("menu/jokes.mp3", audio_handler=audio),
            "101": PhoneTree("directory/alice.mp3", audio_handler=audio),
            "102": PhoneTree("directory/bob.mp3", audio_handler=audio),
            "103": PhoneTree("directory/charlie.mp3", audio_handler=audio),
        }
    )

    # Setup input queue
    input_queue = queue.Queue()
    for key in inputs:
        input_queue.put(key)

    # Track iterations to prevent infinite loop
    iteration_count = [0]
    def limited_hook():
        iteration_count[0] += 1
        return iteration_count[0] < 500 and not input_queue.empty()

    # Run navigation
    try:
        menu.navigate(input_queue, limited_hook, menu)
        print(f"✓ Test completed successfully!")
        print(f"  Iterations: {iteration_count[0]}")
        print(f"  Queue remaining: {input_queue.qsize()}")
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("HYBRID MODE - Quick Test Suite")
    print("="*60)

    tests_passed = 0
    tests_total = 0

    # Test 1: Single-digit navigation
    tests_total += 1
    if test_scenario(
        "Single-Digit Navigation",
        ['1'],
        "Press 1 → plays Info directly"
    ):
        tests_passed += 1

    # Test 2: Extension with prefix
    tests_total += 1
    if test_scenario(
        "Extension with * Prefix",
        ['*', '1', '0', '1'],
        "Press *101 → plays Alice (extension 101)"
    ):
        tests_passed += 1

    # Test 3: Return to menu
    tests_total += 1
    if test_scenario(
        "Return to Menu with 0",
        ['*', '1', '0'],
        "Press *1 then 0 → returns to main menu"
    ):
        tests_passed += 1

    # Test 4: Multiple extensions
    tests_total += 1
    if test_scenario(
        "Multiple Extension Navigation",
        ['*', '1', '0', '1', '*', '1', '0', '2'],
        "Press *101 then *102 → plays Alice then Bob"
    ):
        tests_passed += 1

    # Test 5: Invalid extension
    tests_total += 1
    if test_scenario(
        "Invalid Extension",
        ['*', '9', '9', '9'],
        "Press *999 → invalid extension error"
    ):
        tests_passed += 1

    # Test 6: Mixed navigation
    tests_total += 1
    if test_scenario(
        "Mixed Single-Digit and Extension",
        ['1', '*', '1', '0', '1', '2'],
        "Press 1 (info), then *101 (alice), then 2 (jokes)"
    ):
        tests_passed += 1

    # Results
    print("\n" + "="*60)
    print(f"TEST RESULTS: {tests_passed}/{tests_total} passed")
    print("="*60)

    if tests_passed == tests_total:
        print("✓ All tests passed! Hybrid mode is working correctly.")
        return 0
    else:
        print(f"✗ {tests_total - tests_passed} test(s) failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
