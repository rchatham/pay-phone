#!/usr/bin/env python3
"""
Test DTMF tones locally by playing each one in sequence.
"""
import pygame
import time
import os
from pathlib import Path

def test_dtmf_tones():
    """Play all DTMF tones in sequence to test them."""

    # Initialize pygame mixer
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

    # Define the tone files in keypad order
    tones = [
        ('1', '1.wav'),
        ('2', '2.wav'),
        ('3', '3.wav'),
        ('4', '4.wav'),
        ('5', '5.wav'),
        ('6', '6.wav'),
        ('7', '7.wav'),
        ('8', '8.wav'),
        ('9', '9.wav'),
        ('*', 'star.wav'),
        ('0', '0.wav'),
        ('#', 'pound.wav'),
    ]

    dtmf_dir = Path("audio_files/dtmf")

    if not dtmf_dir.exists():
        print(f"Error: DTMF directory not found: {dtmf_dir}")
        print("Run generate_dtmf_tones.py first to create the tones.")
        return

    print("Testing DTMF tones...")
    print("Playing each button in keypad order:")
    print()
    print("  1  2  3")
    print("  4  5  6")
    print("  7  8  9")
    print("  *  0  #")
    print()

    for key, filename in tones:
        filepath = dtmf_dir / filename

        if not filepath.exists():
            print(f"✗ Missing: {key} ({filename})")
            continue

        print(f"▶ Playing {key}...", end='', flush=True)

        try:
            sound = pygame.mixer.Sound(str(filepath))
            sound.play()

            # Wait for sound to finish
            while pygame.mixer.get_busy():
                time.sleep(0.01)

            print(" ✓")

            # Brief pause between tones
            time.sleep(0.3)

        except Exception as e:
            print(f" ✗ Error: {e}")

    print()
    print("✓ Test complete!")

    pygame.quit()

if __name__ == "__main__":
    test_dtmf_tones()
