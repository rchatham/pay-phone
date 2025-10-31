#!/usr/bin/env python3
"""
Local phone tree simulator for testing without hardware.
Uses keyboard input and computer speakers.
"""
import pygame
import logging
import os
import sys
import queue
import threading
import time

# Add payphone to path
sys.path.insert(0, os.path.dirname(__file__))

from payphone.phone_system.phone_tree import PhoneTree

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AudioPlayer:
    """Simple audio player using pygame"""
    def __init__(self, audio_dir="audio_files"):
        self.audio_dir = audio_dir
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        logger.info(f"Audio initialized with directory: {audio_dir}")

    def play_file(self, filename, blocking=True):
        """Play an audio file"""
        filepath = os.path.join(self.audio_dir, filename)
        if not os.path.exists(filepath):
            logger.warning(f"Audio file not found: {filepath}")
            logger.info(f"[WOULD PLAY: {filename}]")
            return False

        try:
            logger.info(f"Playing: {filename}")
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()

            if blocking:
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
            return True
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            return False

    def stop(self):
        """Stop current playback"""
        pygame.mixer.music.stop()

class KeyboardInput:
    """Simulate keypad input via keyboard"""
    def __init__(self):
        self.input_queue = queue.Queue()
        self.running = True
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()

    def _input_loop(self):
        """Thread to read keyboard input"""
        logger.info("Keyboard input ready. Type keys and press Enter (or 'q' to quit)")
        while self.running:
            try:
                key = input("> ")
                if key.lower() == 'q':
                    logger.info("Quit requested")
                    self.running = False
                    break
                elif key in '0123456789*#':
                    self.input_queue.put(key)
                    logger.info(f"Key pressed: {key}")
                else:
                    logger.warning(f"Invalid key: {key} (use 0-9, *, or #)")
            except EOFError:
                break
            except KeyboardInterrupt:
                self.running = False
                break

def setup_phone_tree(audio_player: AudioPlayer) -> PhoneTree:
    """Build the phone menu tree"""
    # Leaf nodes
    weather = PhoneTree("menu/weather_info.mp3", audio_handler=audio_player)
    time_info = PhoneTree("menu/time_info.mp3", audio_handler=audio_player)

    # Branch nodes
    info_menu = PhoneTree(
        "menu/info_menu.mp3",
        audio_handler=audio_player,
        options={
            "1": weather,
            "2": time_info
        }
    )

    # Root menu
    main_menu = PhoneTree(
        "menu/main_menu.mp3",
        audio_handler=audio_player,
        options={
            "1": info_menu,
            "2": PhoneTree("menu/jokes.mp3", audio_handler=audio_player),
            "3": PhoneTree("menu/music.mp3", audio_handler=audio_player)
        }
    )

    return main_menu

def main():
    """Run the phone tree simulator"""
    print("\n" + "="*60)
    print("PAYPHONE SIMULATOR - Local Testing Mode")
    print("="*60)
    print("\nInstructions:")
    print("  - Type a number (0-9) and press Enter to simulate keypad")
    print("  - Type 'q' to quit")
    print("  - Audio files will play if they exist")
    print("="*60 + "\n")

    # Initialize components
    audio_player = AudioPlayer("audio_files")
    keyboard = KeyboardInput()
    phone_tree = setup_phone_tree(audio_player)

    # Simulate dial tone
    logger.info("Phone picked up - playing dial tone")
    audio_player.play_file("prompts/dial_tone.mp3", blocking=False)
    time.sleep(1)
    audio_player.stop()

    # Start navigation
    logger.info("Starting phone tree navigation...")
    print("\n[Phone tree ready for input]\n")

    try:
        # Navigate the tree
        phone_tree.navigate(
            keyboard.input_queue,
            lambda: keyboard.running,  # Check if still running
            phone_tree  # Root menu to return to
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        keyboard.running = False
        pygame.quit()
        print("\n" + "="*60)
        print("Simulator ended. Goodbye!")
        print("="*60 + "\n")

if __name__ == "__main__":
    main()
