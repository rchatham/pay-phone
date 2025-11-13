#!/usr/bin/env python3
"""
Generate DTMF (Dual-Tone Multi-Frequency) tones for each keypad button.

DTMF tones are composed of two simultaneous frequencies:
- Row frequency (low)
- Column frequency (high)
"""
import numpy as np
import wave
import os
from pathlib import Path

# DTMF frequency table
DTMF_FREQUENCIES = {
    '1': (697, 1209),
    '2': (697, 1336),
    '3': (697, 1477),
    '4': (770, 1209),
    '5': (770, 1336),
    '6': (770, 1477),
    '7': (852, 1209),
    '8': (852, 1336),
    '9': (852, 1477),
    '*': (941, 1209),
    '0': (941, 1336),
    '#': (941, 1477),
}

def generate_dtmf_tone(freq1: int, freq2: int, duration: float = 0.15, sample_rate: int = 44100) -> np.ndarray:
    """
    Generate a DTMF tone by combining two frequencies.

    Args:
        freq1: Low frequency (row)
        freq2: High frequency (column)
        duration: Duration in seconds (default 0.15s for crisp tone)
        sample_rate: Sample rate in Hz

    Returns:
        Audio samples as numpy array
    """
    t = np.linspace(0, duration, int(sample_rate * duration), False)

    # Generate both frequency components
    tone1 = np.sin(2 * np.pi * freq1 * t)
    tone2 = np.sin(2 * np.pi * freq2 * t)

    # Combine the tones (equal amplitude)
    combined = (tone1 + tone2) / 2.0

    # Apply fade in/out to prevent clicks
    fade_samples = int(0.005 * sample_rate)  # 5ms fade
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)

    combined[:fade_samples] *= fade_in
    combined[-fade_samples:] *= fade_out

    # Convert to 16-bit PCM
    audio = np.int16(combined * 32767)

    return audio

def save_wav(filename: str, audio: np.ndarray, sample_rate: int = 44100):
    """Save audio data to WAV file."""
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio.tobytes())

def main():
    # Create output directory
    output_dir = Path("audio_files/dtmf")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating DTMF tones...")

    for key, (freq1, freq2) in DTMF_FREQUENCIES.items():
        # Generate tone
        audio = generate_dtmf_tone(freq1, freq2)

        # Create filename (handle special characters)
        if key == '*':
            filename = 'star.wav'
        elif key == '#':
            filename = 'pound.wav'
        else:
            filename = f'{key}.wav'

        filepath = output_dir / filename

        # Save as WAV
        save_wav(str(filepath), audio)
        print(f"✓ Generated {key}: {freq1}Hz + {freq2}Hz -> {filepath}")

    print("\n✓ All DTMF tones generated successfully!")
    print(f"Output directory: {output_dir.absolute()}")
    print("\nNote: WAV files generated. Convert to MP3 if needed:")
    print("  for f in audio_files/dtmf/*.wav; do")
    print("    ffmpeg -i \"$f\" -acodec libmp3lame -b:a 128k \"${f%.wav}.mp3\"")
    print("  done")

if __name__ == "__main__":
    main()
