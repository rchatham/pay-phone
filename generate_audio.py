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
    },

    # Extension mode prompts
    "prompts/invalid_extension.mp3": {
        "text": "I'm sorry, that extension is not valid. Please try again.",
        "voice": "alloy"
    },

    # Extension mode main menu
    "menu/main_menu_ext.mp3": {
        "text": """Welcome to the company directory.
        Press 1 for the employee directory.
        Press 2 for departments.
        Press 3 for general information.""",
        "voice": "nova"
    },

    # Directory menu
    "menu/directory.mp3": {
        "text": """Employee directory. Please dial the three-digit extension of the person you wish to reach.
        Extension 101 for Alice, 102 for Bob, 103 for Charlie, or 104 for Diana.""",
        "voice": "nova"
    },

    # Departments menu
    "menu/departments.mp3": {
        "text": """Department directory. Dial 10 for Sales, 20 for Support, or 30 for Engineering. Press pound when finished.""",
        "voice": "nova"
    },

    # General info
    "menu/info.mp3": {
        "text": """Company information. Our office hours are Monday through Friday, 9 AM to 5 PM Pacific Time.
        For technical support, please press 2 from the main menu and dial extension 20.
        Returning to main menu.""",
        "voice": "shimmer"
    },

    # Directory entries (employees)
    "directory/alice.mp3": {
        "text": """You have reached Alice Smith in Marketing.
        I'm currently away from my desk. Please leave a message after the tone, or press pound to return to the directory.
        Returning to main menu.""",
        "voice": "shimmer"
    },

    "directory/bob.mp3": {
        "text": """You have reached Bob Johnson in Engineering.
        I'm not available right now. Please leave your name and number, and I'll get back to you as soon as possible.
        Returning to main menu.""",
        "voice": "onyx"
    },

    "directory/charlie.mp3": {
        "text": """You have reached Charlie Davis in Sales.
        Thank you for calling! I'm either on another call or away from my desk. Please leave a detailed message and I'll return your call.
        Returning to main menu.""",
        "voice": "echo"
    },

    "directory/diana.mp3": {
        "text": """You have reached Diana Martinez in Human Resources.
        I'm currently unavailable. If this is regarding employment verification, please press 0 to reach the main desk. Otherwise, please leave a message.
        Returning to main menu.""",
        "voice": "nova"
    },

    # Department messages
    "departments/sales.mp3": {
        "text": """You have reached the Sales department.
        Our sales team is available Monday through Friday, 9 AM to 6 PM.
        For immediate assistance, please call our main line. For all other inquiries, please leave a message.
        Returning to main menu.""",
        "voice": "echo"
    },

    "departments/support.mp3": {
        "text": """You have reached Technical Support.
        For 24/7 support, please visit our website or use our chat system.
        For non-urgent matters, please leave a detailed message including your contact information and a description of your issue.
        Returning to main menu.""",
        "voice": "onyx"
    },

    "departments/engineering.mp3": {
        "text": """You have reached the Engineering department.
        For technical inquiries, please email engineering@company.com.
        For urgent production issues, please contact the on-call engineer through the main desk.
        Returning to main menu.""",
        "voice": "onyx"
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
    print("  - nova (menus, Diana)")
    print("  - shimmer (info, Alice)")
    print("  - echo (jokes, Charlie, Sales)")
    print("  - onyx (Bob, Support, Engineering)")
    print("  - fable (music)")
    print("\nExtension mode files generated:")
    print("  - prompts/invalid_extension.mp3")
    print("  - menu/main_menu_ext.mp3, directory.mp3, departments.mp3, info.mp3")
    print("  - directory/alice.mp3, bob.mp3, charlie.mp3, diana.mp3")
    print("  - departments/sales.mp3, support.mp3, engineering.mp3")

if __name__ == "__main__":
    main()
