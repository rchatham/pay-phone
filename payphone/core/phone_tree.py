import queue
import time
import logging
from typing import Dict, Optional, Callable
from ..audio.handler import AudioHandler

logger = logging.getLogger(__name__)

class PhoneTree:
    def __init__(self,
                 audio_file: str,
                 options: Optional[Dict[str, 'PhoneTree']] = None,
                 action: Optional[Callable] = None,
                 timeout: int = 30,
                 audio_handler=None):
        self.audio_file = audio_file
        self.options = options or {}
        self.action = action
        self.timeout = timeout
        self.audio_handler = audio_handler if audio_handler is not None else AudioHandler()
        
    def navigate(self,
                 input_queue: queue.Queue,
                 hook_status: Callable,
                 main_menu: Optional['PhoneTree'] = None) -> None:
        """Navigate through the phone tree"""

        # Check if phone is still off hook
        if not hook_status():
            logger.info("Phone hung up")
            return

        # Play audio prompt (non-blocking to allow interruption)
        self.audio_handler.play_file(self.audio_file, blocking=False)

        # Execute action if present
        if self.action:
            # Wait for audio to finish for actions
            while self.audio_handler.is_playing() and hook_status():
                time.sleep(0.1)

            continue_nav = self.action()
            if not continue_nav:
                if main_menu:
                    main_menu.navigate(input_queue, hook_status, main_menu)
                return

        # If no options, return to main menu
        if not self.options:
            # Wait for audio to finish before returning to menu
            while self.audio_handler.is_playing() and hook_status():
                time.sleep(0.1)

            if main_menu:
                time.sleep(2)
                main_menu.navigate(input_queue, hook_status, main_menu)
            return

        # Wait for input (allow interrupting audio)
        start_time = time.time()

        while hook_status():  # Continue while phone is off hook
            if time.time() - start_time > self.timeout:
                logger.info("Timeout reached")
                self.audio_handler.stop()  # Stop any playing audio
                self.audio_handler.play_file("prompts/timeout.mp3")
                if main_menu:
                    main_menu.navigate(input_queue, hook_status, main_menu)
                return

            try:
                # Check for input with short timeout for faster response
                choice = input_queue.get(timeout=0.1)

                # Check if audio was playing when button was pressed
                audio_was_playing = self.audio_handler.is_playing()

                # Button pressed - stop audio immediately
                if audio_was_playing:
                    self.audio_handler.stop()
                    logger.info(f"Audio interrupted by button press: {choice}")

                if choice in self.options:
                    self.options[choice].navigate(input_queue, hook_status, main_menu)
                    return
                else:
                    # Only play error message if audio was NOT playing (user pressed invalid after menu finished)
                    if not audio_was_playing:
                        # Play error message blocking to ensure user hears it
                        self.audio_handler.play_file("prompts/invalid_option.mp3", blocking=True)

                        # Short delay before replaying menu
                        time.sleep(0.5)
                    else:
                        # Audio was interrupted - just log and replay menu (no error message)
                        logger.info(f"Invalid option {choice} pressed during audio playback - skipping error message")

                    # Clear queue to prevent queued presses
                    cleared_count = 0
                    while not input_queue.empty():
                        try:
                            input_queue.get_nowait()
                            cleared_count += 1
                        except queue.Empty:
                            break

                    if cleared_count > 0:
                        logger.debug(f"Cleared {cleared_count} button presses from queue")

                    # Replay menu audio
                    self.audio_handler.play_file(self.audio_file, blocking=False)
                    start_time = time.time()  # Reset timeout

            except queue.Empty:
                # No input yet - continue waiting
                continue
