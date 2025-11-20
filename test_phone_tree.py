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
    def __init__(self, audio_dir="audio_files", silent=False):
        self.audio_dir = audio_dir
        self.silent = silent
        if not silent:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        logger.info(f"Audio initialized with directory: {audio_dir} (silent={silent})")

    def play_file(self, filename, blocking=True):
        """Play an audio file"""
        if self.silent:
            logger.info(f"[SILENT MODE] Would play: {filename}")
            return True

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
        if not self.silent:
            pygame.mixer.music.stop()

    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        if self.silent:
            return False
        try:
            return pygame.mixer.music.get_busy()
        except:
            return False

    def play_dtmf_tone(self, key: str) -> bool:
        """Play DTMF tone for a keypad button press"""
        if self.silent:
            return True

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

def setup_hybrid_phone_tree(audio_player: AudioPlayer) -> PhoneTree:
    """Build a hybrid phone tree for testing prefix-based extension dialing"""

    # Single-digit leaf nodes
    info = PhoneTree("menu/info.mp3", audio_handler=audio_player)
    help_node = PhoneTree("menu/jokes.mp3", audio_handler=audio_player)  # Reuse jokes as help

    # Extension leaf nodes (employees)
    alice = PhoneTree("directory/alice.mp3", audio_handler=audio_player)
    bob = PhoneTree("directory/bob.mp3", audio_handler=audio_player)
    charlie = PhoneTree("directory/charlie.mp3", audio_handler=audio_player)
    diana = PhoneTree("directory/diana.mp3", audio_handler=audio_player)

    # Hybrid main menu: single-digit options + extensions via * prefix
    main_menu = PhoneTree(
        "menu/main_menu_ext.mp3",
        audio_handler=audio_player,
        hybrid_mode=True,
        extension_prefix='*',
        return_to_menu_key='0',
        extension_length=3,
        extension_timeout=3.0,
        allow_continuous_dialing=True,
        options={
            # Single-digit options (no prefix needed)
            "1": info,
            "2": help_node,
            # Extensions (require * prefix)
            "101": alice,
            "102": bob,
            "103": charlie,
            "104": diana,
        }
    )

    return main_menu

def setup_bios_phone_tree(audio_player: AudioPlayer) -> PhoneTree:
    """Build a BIOS-style system selection menu"""
    from payphone.bios.system_manager import SystemManager
    from payphone.config.settings import Config

    # Discover systems
    manager = SystemManager(scan_paths=["./phone_systems", "../TDTM"])
    systems = manager.discover_systems()

    logger.info(f"Discovered {len(systems)} systems for BIOS menu")

    # Build menu options by actually loading each system
    menu_options = {}
    for idx, (system_id, system_info) in enumerate(systems.items(), start=1):
        if idx > 9:
            break

        digit = str(idx)
        logger.info(f"  {digit}: {system_info.name}")

        # Load the system class
        system_class = manager.load_system(system_id)
        if not system_class:
            logger.error(f"Failed to load system: {system_id}")
            continue

        # Create system instance (NOTE: Hardware init may fail in simulator on macOS)
        try:
            # For the simulator, we need to handle hardware init failures gracefully
            # Try to instantiate, but if it fails due to audio/hardware, create a mock

            # Special handling for known systems that we can mock
            if system_id == "information_booth":
                # Use the built-in phone tree setup for information booth
                menu_options[digit] = setup_phone_tree(audio_player)
                logger.info(f"    Loaded phone tree for {system_info.name} (using local setup)")

            elif system_id == "TDTM":
                # TDTM requires special handling - create a simple placeholder
                # In a real deployment, this would work fine
                tdtm_placeholder = PhoneTree(
                    "bios/system_TDTM.mp3",
                    audio_handler=audio_player,
                    options={
                        "1": PhoneTree("", audio_handler=audio_player)
                    }
                )
                menu_options[digit] = tdtm_placeholder
                logger.warning(f"    Using placeholder for {system_info.name} (hardware init not available in simulator)")

            else:
                # Try to load normally for other systems
                config = Config()
                system_instance = system_class(config)
                system_instance.audio_handler = audio_player
                system_phone_tree = system_instance.setup_phone_tree()
                menu_options[digit] = system_phone_tree
                logger.info(f"    Loaded phone tree for {system_info.name}")

        except Exception as e:
            logger.warning(f"Could not load system {system_id} in simulator: {e}")
            # Create placeholder node
            placeholder = PhoneTree(
                f"bios/system_{system_id}.mp3",
                audio_handler=audio_player,
                options={
                    "1": PhoneTree("", audio_handler=audio_player)
                }
            )
            menu_options[digit] = placeholder
            logger.info(f"    Using placeholder for {system_info.name}")

    # Main BIOS menu
    bios_menu = PhoneTree(
        "bios/main_menu.mp3",
        audio_handler=audio_player,
        options=menu_options,
        timeout=60
    )

    return bios_menu

def main():
    """Run the phone tree simulator"""
    print("\n" + "="*60)
    print("PAYPHONE SIMULATOR - Local Testing Mode")
    print("="*60)
    print("\nSelect test mode:")
    print("  1. Regular phone tree (single-digit options)")
    print("  2. Extension phone tree (multi-digit extensions)")
    print("  3. Hybrid mode (single-digit + * prefix extensions)")
    print("  4. BIOS mode (system selection menu)")
    print("="*60)

    # Get mode selection
    mode = input("\nEnter mode (1, 2, 3, or 4, default=1): ").strip()
    use_extensions = (mode == "2")
    use_hybrid = (mode == "3")
    use_bios = (mode == "4")

    print("\n" + "="*60)
    if use_bios:
        print("BIOS MODE - System Selection Menu")
        print("="*60)
        print("\nTest scenarios:")
        print("  SYSTEM SELECTION:")
        print("     - Press '1' for Information Booth System")
        print("     - Press '2' for TDTM System")
        print("\n  Note: This is a simulated BIOS menu.")
        print("  On real hardware, hold hook for 3s to enter BIOS.")
    elif use_hybrid:
        print("HYBRID MODE - Single-Digit + * Prefix Extensions")
        print("="*60)
        print("\nTest scenarios:")
        print("  SINGLE-DIGIT OPTIONS (press directly):")
        print("     - Press '1' for Information")
        print("     - Press '2' for Help/Jokes")
        print("\n  EXTENSIONS (press * then 3-digit number):")
        print("     - Press '*101' for Alice")
        print("     - Press '*102' for Bob")
        print("     - Press '*103' for Charlie")
        print("     - Press '*104' for Diana")
        print("\n  CONTINUOUS DIALING:")
        print("     - While extension plays, dial another extension")
        print("     - e.g., While Alice plays, dial '102' to hear Bob")
        print("\n  RETURN TO MENU:")
        print("     - Press '0' at any time to return to main menu")
    elif use_extensions:
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

    # Ask about silent mode
    silent_input = input("Run in silent mode (no audio)? (y/N): ").strip().lower()
    silent_mode = (silent_input == 'y')

    # Initialize components
    audio_player = AudioPlayer("audio_files", silent=silent_mode)
    keyboard = KeyboardInput()
    keyboard.set_audio_player(audio_player)  # Enable DTMF tones on keypress

    # Setup phone tree based on mode
    if use_bios:
        phone_tree = setup_bios_phone_tree(audio_player)
    elif use_hybrid:
        phone_tree = setup_hybrid_phone_tree(audio_player)
    elif use_extensions:
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
