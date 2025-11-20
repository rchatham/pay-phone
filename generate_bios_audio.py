#!/usr/bin/env python3
"""
Generate audio files for BIOS menu using text-to-speech.

Creates:
- bios/main_menu.mp3
- bios/system_information_booth.mp3
- bios/system_tdtm.mp3 (if TDTM discovered)
- prompts/invalid_extension.mp3
- prompts/no_systems.mp3
"""

import os
import sys
from pathlib import Path

# Try importing TTS libraries
try:
    from gtts import gTTS
    TTS_ENGINE = "gtts"
    print("Using Google TTS (gTTS)")
except ImportError:
    try:
        import pyttsx3
        TTS_ENGINE = "pyttsx3"
        print("Using pyttsx3")
    except ImportError:
        print("ERROR: No TTS library available!")
        print("Install one with:")
        print("  pip install gtts")
        print("  OR")
        print("  pip install pyttsx3")
        sys.exit(1)

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from payphone.bios.system_manager import SystemManager


def generate_with_gtts(text: str, output_path: str):
    """Generate audio using Google TTS"""
    tts = gTTS(text=text, lang='en', slow=False)
    # gTTS outputs mp3 directly
    tts.save(output_path)
    print(f"✓ Generated: {output_path}")


def generate_with_pyttsx3(text: str, output_path: str):
    """Generate audio using pyttsx3"""
    engine = pyttsx3.init()

    # Set properties
    engine.setProperty('rate', 150)  # Speed
    engine.setProperty('volume', 0.9)  # Volume

    # pyttsx3 saves as WAV, we need to convert or just save as WAV
    if output_path.endswith('.mp3'):
        wav_path = output_path.replace('.mp3', '.wav')
        engine.save_to_file(text, wav_path)
        engine.runAndWait()
        print(f"✓ Generated: {wav_path} (pyttsx3 outputs WAV, not MP3)")
    else:
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        print(f"✓ Generated: {output_path}")


def generate_audio(text: str, output_path: str):
    """Generate audio file using available TTS engine"""
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if TTS_ENGINE == "gtts":
        generate_with_gtts(text, output_path)
    else:
        generate_with_pyttsx3(text, output_path)


def main():
    print("\n" + "="*60)
    print("BIOS Audio File Generator")
    print("="*60 + "\n")

    audio_dir = Path("audio_files")

    # Discover available systems
    print("Discovering phone systems...")
    manager = SystemManager(scan_paths=["./phone_systems", "../TDTM"])
    systems = manager.discover_systems()

    print(f"Found {len(systems)} systems:")
    for system_id, info in systems.items():
        print(f"  - {info.name} (id={system_id})")
    print()

    # Generate main menu
    if systems:
        menu_text = "Welcome to payphone BIOS. "
        for idx, (system_id, info) in enumerate(systems.items(), start=1):
            menu_text += f"Press {idx} for {info.name}. "

        generate_audio(
            menu_text,
            str(audio_dir / "bios" / "main_menu.mp3")
        )
    else:
        print("⚠️  No systems found, generating error message only")
        generate_audio(
            "No phone systems found. Please check configuration.",
            str(audio_dir / "prompts" / "no_systems.mp3")
        )

    # Generate individual system audio files
    for system_id, info in systems.items():
        generate_audio(
            info.name,
            str(audio_dir / "bios" / f"system_{system_id}.mp3")
        )

    # Generate error messages
    generate_audio(
        "Invalid extension. Please try again.",
        str(audio_dir / "prompts" / "invalid_extension.mp3")
    )

    generate_audio(
        "No phone systems found. Please check configuration.",
        str(audio_dir / "prompts" / "no_systems.mp3")
    )

    print("\n" + "="*60)
    print(f"✅ Generated {2 + len(systems) * 2} audio files")
    print("="*60 + "\n")

    print("Files created:")
    print(f"  - audio_files/bios/main_menu.mp3")
    for system_id in systems.keys():
        print(f"  - audio_files/bios/system_{system_id}.mp3")
    print(f"  - audio_files/prompts/invalid_extension.mp3")
    print(f"  - audio_files/prompts/no_systems.mp3")
    print()


if __name__ == "__main__":
    main()
