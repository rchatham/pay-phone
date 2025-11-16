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

from payphone.core.phone_tree import PhoneTree

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AudioPlayer:
    """Simple audio player using pygame - matches AudioHandler interface"""
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

    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        try:
            return pygame.mixer.music.get_busy()
        except:
            return False

    def play_dtmf_tone(self, key: str) -> bool:
        """Play DTMF tone for a keypad button press"""
        filename_map = {
            '0': '0.wav', '1': '1.wav', '2': '2.wav', '3': '3.wav',
            '4': '4.wav', '5': '5.wav', '6': '6.wav', '7': '7.wav',
            '8': '8.wav', '9': '9.wav', '*': 'star.wav', '#': 'pound.wav',
        }

        if key not in filename_map:
            return False

        dtmf_file = os.path.join(self.audio_dir, 'dtmf', filename_map[key])

        if not os.path.exists(dtmf_file):
            logger.debug(f"DTMF tone file not found: {dtmf_file}")
            return False

        try:
            sound = pygame.mixer.Sound(dtmf_file)
            sound.play()
            logger.info(f"♪ DTMF tone: {key}")
            return True
        except Exception as e:
            logger.error(f"Error playing DTMF tone for {key}: {e}")
            return False

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
                    # Play DTMF tone if audio player is available
                    if hasattr(self, 'audio_player') and self.audio_player:
                        self.audio_player.play_dtmf_tone(key)

                    self.input_queue.put(key)
                    logger.info(f"Key pressed: {key}")
                else:
                    logger.warning(f"Invalid key: {key} (use 0-9, *, or #)")
            except EOFError:
                break
            except KeyboardInterrupt:
                self.running = False
                break

    def set_audio_player(self, audio_player):
        """Set audio player for DTMF tones"""
        self.audio_player = audio_player

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
    keyboard.set_audio_player(audio_player)  # Enable DTMF tones on keypress
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
