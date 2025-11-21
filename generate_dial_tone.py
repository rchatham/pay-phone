#!/usr/bin/env python3
"""
Generate a standard North American dial tone (350 Hz + 440 Hz)
"""
import numpy as np
import wave
import struct
import os

# Audio parameters
duration = 5.0  # seconds
sample_rate = 44100  # Hz
freq1 = 350  # Hz - lower frequency
freq2 = 440  # Hz - upper frequency
amplitude = 0.3  # Reduce amplitude to prevent clipping

# Generate time array
t = np.linspace(0, duration, int(sample_rate * duration), False)

# Generate two sine waves and mix them
tone1 = amplitude * np.sin(2 * np.pi * freq1 * t)
tone2 = amplitude * np.sin(2 * np.pi * freq2 * t)
dial_tone = tone1 + tone2

# Normalize to prevent clipping
dial_tone = dial_tone / np.max(np.abs(dial_tone)) * 0.9

# Convert to 16-bit PCM
audio_data = (dial_tone * 32767).astype(np.int16)

# Save as WAV first
wav_path = "audio_files/prompts/dial_tone.wav"
with wave.open(wav_path, 'w') as wav_file:
    # Set parameters: nchannels, sampwidth, framerate, nframes, comptype, compname
    wav_file.setnchannels(1)  # Mono
    wav_file.setsampwidth(2)  # 2 bytes (16-bit)
    wav_file.setframerate(sample_rate)
    wav_file.writeframes(audio_data.tobytes())
print(f"Generated WAV file: {wav_path}")

# Convert to MP3 using ffmpeg
try:
    import subprocess

    mp3_path = "audio_files/prompts/dial_tone.mp3"
    result = subprocess.run([
        'ffmpeg', '-i', wav_path,
        '-codec:a', 'libmp3lame',
        '-b:a', '192k',
        mp3_path, '-y'
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Converted to MP3: {mp3_path}")
        # Remove WAV file
        os.remove(wav_path)
        print("Removed temporary WAV file")
    else:
        print(f"ffmpeg conversion failed: {result.stderr}")
        print("Keeping WAV file")

except FileNotFoundError:
    print("ffmpeg not available, keeping WAV file")
    print("To convert to MP3, install ffmpeg: brew install ffmpeg")
