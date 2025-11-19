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

def setup_extension_phone_tree(audio_player: AudioPlayer) -> PhoneTree:
    """Build an extension-based phone tree for testing multi-digit dialing"""

    # Create employee directory with 3-digit extensions
    alice = PhoneTree("directory/alice.mp3", audio_handler=audio_player)
    bob = PhoneTree("directory/bob.mp3", audio_handler=audio_player)
    charlie = PhoneTree("directory/charlie.mp3", audio_handler=audio_player)
    diana = PhoneTree("directory/diana.mp3", audio_handler=audio_player)

    # Directory menu with fixed-length 3-digit extensions
    directory = PhoneTree(
        "menu/directory.mp3",
        audio_handler=audio_player,
        extension_mode=True,
        extension_length=3,
        extension_terminator='#',
        extension_timeout=3.0,
        options={
            "101": alice,
            "102": bob,
            "103": charlie,
            "104": diana,
        }
    )

    # Department menus with variable-length extensions (terminated by #)
    sales_dept = PhoneTree("departments/sales.mp3", audio_handler=audio_player)
    support_dept = PhoneTree("departments/support.mp3", audio_handler=audio_player)
    engineering_dept = PhoneTree("departments/engineering.mp3", audio_handler=audio_player)

    departments = PhoneTree(
        "menu/departments.mp3",
        audio_handler=audio_player,
        extension_mode=True,
        extension_terminator='#',
        extension_timeout=3.0,
        options={
            "10": sales_dept,
            "20": support_dept,
            "30": engineering_dept,
        }
    )

    # Main menu with regular single-digit options
    main_menu = PhoneTree(
        "menu/main_menu_ext.mp3",
        audio_handler=audio_player,
        options={
            "1": directory,
            "2": departments,
            "3": PhoneTree("menu/info.mp3", audio_handler=audio_player),
        }
    )

    return main_menu

def main():
    """Run the phone tree simulator"""
    print("\n" + "="*60)
    print("PAYPHONE SIMULATOR - Local Testing Mode")
    print("="*60)
    print("\nSelect test mode:")
    print("  1. Regular phone tree (single-digit options)")
    print("  2. Extension phone tree (multi-digit extensions)")
    print("="*60)

    # Get mode selection
    mode = input("\nEnter mode (1 or 2, default=1): ").strip()
    use_extensions = (mode == "2")

    print("\n" + "="*60)
    if use_extensions:
        print("EXTENSION MODE - Multi-digit Dialing Test")
        print("="*60)
        print("\nTest scenarios:")
        print("  1. Press '1' for Employee Directory (3-digit extensions)")
        print("     - Dial '101' for Alice (auto-submits after 3 digits)")
        print("     - Dial '102' for Bob")
        print("     - Dial '103' for Charlie")
        print("     - Dial '104' for Diana")
        print("\n  2. Press '2' for Departments (variable-length)")
        print("     - Dial '10#' for Sales (# terminates)")
        print("     - Dial '20#' for Support")
        print("     - Dial '30#' for Engineering")
        print("\n  3. Press '3' for Information (regular single-digit)")
    else:
        print("REGULAR MODE - Single-digit Options")
        print("="*60)
        print("\nMenu options:")
        print("  1. Information menu")
        print("  2. Jokes")
        print("  3. Music")

    print("\nInstructions:")
    print("  - Type keys (0-9, *, #) and press Enter to simulate keypad")
    print("  - Type 'q' to quit")
    print("  - Audio files will play if they exist")
    print("="*60 + "\n")

    # Initialize components
    audio_player = AudioPlayer("audio_files")
    keyboard = KeyboardInput()
    keyboard.set_audio_player(audio_player)  # Enable DTMF tones on keypress

    # Setup phone tree based on mode
    if use_extensions:
        phone_tree = setup_extension_phone_tree(audio_player)
    else:
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
