#!/usr/bin/env python3
"""
Generate audio files for the payphone using OpenAI's TTS API.
"""
import os
from pathlib import Path
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

# Audio file definitions
AUDIO_FILES = {
    # Prompts
    "prompts/dial_tone.mp3": {
        "text": "[This would be a dial tone sound - skipping for now]",
        "skip": True  # We'll skip this one since it's a sound effect
    },
    "prompts/timeout.mp3": {
        "text": "Sorry, we didn't receive your selection. Returning to the main menu.",
        "voice": "alloy"
    },
    "prompts/invalid_option.mp3": {
        "text": "That's not a valid option. Please try again.",
        "voice": "alloy"
    },

    # Main menu
    "menu/main_menu.mp3": {
        "text": """Welcome to the payphone menu system.
        Press 1 for information services.
        Press 2 to hear a joke.
        Press 3 for music.""",
        "voice": "nova"
    },

    # Info submenu
    "menu/info_menu.mp3": {
        "text": """Information menu.
        Press 1 for weather information.
        Press 2 for time information.""",
        "voice": "nova"
    },

    # Leaf nodes
    "menu/weather_info.mp3": {
        "text": """The weather today is sunny with a high of 72 degrees.
        Perfect weather for using a payphone!
        Returning to main menu.""",
        "voice": "shimmer"
    },

    "menu/time_info.mp3": {
        "text": """The current time is... well, check your phone!
        Just kidding, this is a demonstration.
        Returning to main menu.""",
        "voice": "shimmer"
    },

    "menu/jokes.mp3": {
        "text": """Here's a joke: Why did the smartphone go to therapy?
        Because it had too many hang-ups!
        Get it? Hang-ups? Like a payphone?
        Returning to main menu.""",
        "voice": "echo"
    },

    "menu/music.mp3": {
        "text": """La la la, this is where music would play!
        Imagine your favorite hold music here.
        Returning to main menu.""",
        "voice": "fable"
    }
}

def generate_audio_file(filepath: str, text: str, voice: str = "alloy"):
    """Generate a single audio file using OpenAI TTS"""
    print(f"Generating: {filepath}")

    # Create directory if it doesn't exist
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    # Generate speech
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text
    )

    # Save to file
    response.stream_to_file(filepath)
    print(f"  ✓ Saved to {filepath}")

def main():
    """Generate all audio files"""
    print("=" * 60)
    print("Generating Payphone Audio Files with OpenAI TTS")
    print("=" * 60)
    print()

    # Create base directory
    audio_dir = Path("audio_files")
    audio_dir.mkdir(exist_ok=True)

    # Generate each file
    for relative_path, config in AUDIO_FILES.items():
        if config.get("skip"):
            print(f"Skipping: {relative_path} (sound effect)")
            continue

        filepath = audio_dir / relative_path
        voice = config.get("voice", "alloy")
        text = config["text"]

        try:
            generate_audio_file(str(filepath), text, voice)
        except Exception as e:
            print(f"  ✗ Error generating {relative_path}: {e}")

    print()
    print("=" * 60)
    print("Audio generation complete!")
    print("=" * 60)
    print()
    print(f"Files saved to: {audio_dir.absolute()}")
    print("\nAvailable voices used:")
    print("  - alloy (prompts)")
    print("  - nova (menus)")
    print("  - shimmer (info)")
    print("  - echo (jokes)")
    print("  - fable (music)")

if __name__ == "__main__":
    main()
