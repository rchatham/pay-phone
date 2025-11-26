import queue
import time
import logging
from typing import Dict, Optional, Callable
from enum import Enum
from ..audio.handler import AudioHandler

logger = logging.getLogger(__name__)


class NavigationState(Enum):
    """State enumeration for hybrid navigation mode"""
    MENU_PLAYING = "menu_playing"
    COLLECTING_EXTENSION = "collecting_ext"
    EXTENSION_PLAYING = "ext_playing"
    WAITING_FOR_INPUT = "waiting"


class HybridNavigationContext:
    """Context object for hybrid navigation state"""
    def __init__(self):
        self.state = NavigationState.MENU_PLAYING
        self.digit_buffer = []
        self.last_input_time = None
        self.in_extension_mode = False

class PhoneTree:
    def __init__(self,
                 audio_file: str,
                 options: Optional[Dict[str, 'PhoneTree']] = None,
                 action: Optional[Callable] = None,
                 timeout: int = 30,
                 audio_handler=None,
                 extension_mode: bool = False,
                 extension_length: Optional[int] = None,
                 extension_terminator: str = '#',
                 extension_timeout: float = 3.0,
                 hybrid_mode: bool = False,
                 extension_prefix: str = '*',
                 return_to_menu_key: str = '0',
                 allow_continuous_dialing: bool = True):
        """
        Initialize a PhoneTree node.

        Args:
            audio_file: Path to audio file to play for this menu
            options: Dictionary mapping keys to child PhoneTree nodes
            action: Optional callback function to execute
            timeout: Overall timeout in seconds before returning to main menu
            audio_handler: AudioHandler instance (created if not provided)
            extension_mode: Enable multi-digit extension dialing
            extension_length: Fixed length for extensions (e.g., 3 for "101")
                             If None, uses terminator to end input
            extension_terminator: Key to end variable-length extension input (default '#')
            extension_timeout: Seconds of inactivity before auto-submitting extension
            hybrid_mode: Enable hybrid single-digit + extension dialing
            extension_prefix: Key to activate extension mode (default '*')
            return_to_menu_key: Universal "go back" key (default '0')
            allow_continuous_dialing: Allow dialing next extension while current plays
        """
        self.audio_file = audio_file
        self.options = options or {}
        self.action = action
        self.timeout = timeout
        self.audio_handler = audio_handler if audio_handler is not None else AudioHandler()
        self.extension_mode = extension_mode
        self.extension_length = extension_length
        self.extension_terminator = extension_terminator
        self.extension_timeout = extension_timeout
        self.hybrid_mode = hybrid_mode
        self.extension_prefix = extension_prefix
        self.return_to_menu_key = return_to_menu_key
        self.allow_continuous_dialing = allow_continuous_dialing

        # Validate configuration
        if self.extension_mode and self.options:
            self._validate_extension_options()
        elif self.hybrid_mode and self.options:
            self._validate_hybrid_options()

    def _validate_extension_options(self) -> None:
        """
        Validate that extension mode configuration is correct.

        Raises:
            ValueError: If options violate extension mode constraints
        """
        if not self.options:
            return

        # Check all option keys
        key_lengths = set(len(key) for key in self.options.keys())

        # Disallow mixing single-digit and multi-digit options
        if len(key_lengths) > 1 and 1 in key_lengths:
            single_digit_keys = [k for k in self.options.keys() if len(k) == 1]
            multi_digit_keys = [k for k in self.options.keys() if len(k) > 1]
            raise ValueError(
                f"Cannot mix single-digit and multi-digit options in extension mode. "
                f"Single-digit keys: {single_digit_keys}, "
                f"Multi-digit keys: {multi_digit_keys}. "
                f"Use separate menus for each type."
            )

        # If extension_length is specified, validate all keys match
        if self.extension_length:
            invalid_keys = [k for k in self.options.keys() if len(k) != self.extension_length]
            if invalid_keys:
                raise ValueError(
                    f"All option keys must be {self.extension_length} digits long when "
                    f"extension_length is specified. Invalid keys: {invalid_keys}"
                )

        # Validate that extension_terminator is not used in option keys
        if self.extension_terminator:
            invalid_keys = [k for k in self.options.keys() if self.extension_terminator in k]
            if invalid_keys:
                raise ValueError(
                    f"Extension terminator '{self.extension_terminator}' cannot appear in "
                    f"option keys. Invalid keys: {invalid_keys}"
                )

        logger.info(f"Extension mode validated: {len(self.options)} options, "
                   f"lengths={key_lengths}, terminator='{self.extension_terminator}'")

    def _validate_hybrid_options(self) -> None:
        """
        Validate hybrid mode configuration.

        Raises:
            ValueError: If options violate hybrid mode constraints
        """
        if not self.options:
            return

        # Ensure extension_prefix is not in options
        if self.extension_prefix in self.options:
            raise ValueError(
                f"Extension prefix '{self.extension_prefix}' cannot be a menu option"
            )

        # Ensure return_to_menu_key is not in options
        if self.return_to_menu_key in self.options:
            raise ValueError(
                f"Return key '{self.return_to_menu_key}' cannot be a menu option"
            )

        # Separate single-digit and multi-digit options
        single_digit_keys = [k for k in self.options.keys() if len(k) == 1]
        multi_digit_keys = [k for k in self.options.keys() if len(k) > 1]

        # Note: In hybrid mode, extensions are accessed via prefix (e.g., *101)
        # So "1" as a single-digit option and "101" as an extension do NOT conflict
        # User presses "1" for direct option, or "*101" for extension

        # Validate extension length consistency (if specified)
        if self.extension_length:
            invalid_keys = [k for k in multi_digit_keys if len(k) != self.extension_length]
            if invalid_keys:
                raise ValueError(
                    f"All extensions must be {self.extension_length} digits long. "
                    f"Invalid keys: {invalid_keys}"
                )

        logger.info(f"Hybrid mode validated: {len(single_digit_keys)} single-digit options, "
                   f"{len(multi_digit_keys)} extensions, "
                   f"prefix='{self.extension_prefix}', return_key='{self.return_to_menu_key}'")

    def _collect_extension(self,
                          input_queue: queue.Queue,
                          hook_status: Callable) -> Optional[str]:
        """
        Collect multi-digit extension input.

        Args:
            input_queue: Queue containing keypad input
            hook_status: Function to check if phone is off hook

        Returns:
            str: The collected extension, or None if timeout/hang-up/empty
        """
        buffer = []
        last_input_time = time.time()

        logger.info(f"Collecting extension (length={self.extension_length}, "
                   f"terminator='{self.extension_terminator}', "
                   f"timeout={self.extension_timeout}s)")

        while hook_status():
            # Check for timeout since last input
            if buffer and time.time() - last_input_time > self.extension_timeout:
                extension = ''.join(buffer)
                logger.info(f"Extension timeout - auto-submitting: {extension}")
                return extension

            try:
                digit = input_queue.get(timeout=0.1)

                # Check for terminator
                if digit == self.extension_terminator:
                    extension = ''.join(buffer)
                    logger.info(f"Extension terminated with '{self.extension_terminator}': {extension}")
                    return extension if extension else None

                # Validate digit (allow 0-9, *, but not the terminator)
                if digit in '0123456789*':
                    buffer.append(digit)
                    last_input_time = time.time()
                    logger.debug(f"Extension buffer: {''.join(buffer)}")

                    # Check if we've reached fixed length
                    if self.extension_length and len(buffer) >= self.extension_length:
                        extension = ''.join(buffer)
                        logger.info(f"Extension complete (fixed length {self.extension_length}): {extension}")
                        return extension
                else:
                    logger.warning(f"Invalid digit in extension: {digit}")

            except queue.Empty:
                continue

        logger.info("Phone hung up during extension collection")
        return None

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
        if self.audio_file:
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
            # Check if we're in hybrid mode with continuous dialing enabled
            if main_menu and hasattr(main_menu, 'hybrid_mode') and main_menu.hybrid_mode and main_menu.allow_continuous_dialing:
                # Collect next extension while audio plays
                next_extension = main_menu._collect_while_playing(input_queue, hook_status, main_menu)

                if next_extension and next_extension in main_menu.options:
                    # Navigate to next extension
                    logger.info(f"Continuous dialing: navigating to extension {next_extension}")
                    main_menu.options[next_extension].navigate(input_queue, hook_status, main_menu)
                    return
                elif next_extension:
                    # Invalid extension entered
                    logger.info(f"Invalid extension during continuous dialing: {next_extension}")
                    self.audio_handler.play_file("prompts/invalid_extension.mp3", blocking=True)
                # else: next_extension is None (0 pressed or audio finished with no input) -> return to menu
            else:
                # Original behavior: Wait for audio to finish before returning to menu
                while self.audio_handler.is_playing() and hook_status():
                    time.sleep(0.1)

            if main_menu:
                time.sleep(2)
                main_menu.navigate(input_queue, hook_status, main_menu)
            return

        # Wait for input (allow interrupting audio)
        start_time = time.time()

        # Branch based on navigation mode
        if self.hybrid_mode:
            self._navigate_hybrid_mode(input_queue, hook_status, main_menu, start_time)
        elif self.extension_mode:
            self._navigate_extension_mode(input_queue, hook_status, main_menu, start_time)
        else:
            self._navigate_single_digit_mode(input_queue, hook_status, main_menu, start_time)

    def _navigate_single_digit_mode(self,
                                    input_queue: queue.Queue,
                                    hook_status: Callable,
                                    main_menu: Optional['PhoneTree'],
                                    start_time: float) -> None:
        """Handle navigation in single-digit mode (original behavior)."""
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

    def _navigate_extension_mode(self,
                                 input_queue: queue.Queue,
                                 hook_status: Callable,
                                 main_menu: Optional['PhoneTree'],
                                 start_time: float) -> None:
        """Handle navigation in extension mode (multi-digit input)."""
        while hook_status():
            # Overall timeout check
            if time.time() - start_time > self.timeout:
                logger.info("Overall timeout reached in extension mode")
                self.audio_handler.stop()
                self.audio_handler.play_file("prompts/timeout.mp3")
                if main_menu:
                    main_menu.navigate(input_queue, hook_status, main_menu)
                return

            # Stop audio on first keypress to allow silent extension entry
            if self.audio_handler.is_playing():
                # Wait briefly for first digit
                try:
                    first_digit = input_queue.get(timeout=0.1)
                    self.audio_handler.stop()
                    logger.info("Audio stopped - beginning extension collection")
                    # Put the digit back for _collect_extension to process
                    input_queue.put(first_digit)
                except queue.Empty:
                    continue

            # Collect extension
            extension = self._collect_extension(input_queue, hook_status)

            if not extension:
                # Empty input - replay prompt
                logger.info("No extension collected, replaying menu")
                self.audio_handler.play_file(self.audio_file, blocking=False)
                start_time = time.time()
                continue

            # Check if extension matches an option
            if extension in self.options:
                logger.info(f"Extension matched: {extension}")
                self.options[extension].navigate(input_queue, hook_status, main_menu)
                return
            else:
                # Invalid extension
                logger.info(f"Invalid extension: {extension}")
                self.audio_handler.play_file("prompts/invalid_extension.mp3", blocking=True)
                time.sleep(0.5)

                # Clear queue
                cleared_count = 0
                while not input_queue.empty():
                    try:
                        input_queue.get_nowait()
                        cleared_count += 1
                    except queue.Empty:
                        break

                if cleared_count > 0:
                    logger.debug(f"Cleared {cleared_count} keypresses from queue")

                # Replay menu
                self.audio_handler.play_file(self.audio_file, blocking=False)
                start_time = time.time()

    def _navigate_hybrid_mode(self,
                             input_queue: queue.Queue,
                             hook_status: Callable,
                             main_menu: Optional['PhoneTree'],
                             start_time: float) -> None:
        """Handle navigation in hybrid mode (single-digit + extension prefix)."""
        context = HybridNavigationContext()

        while hook_status():
            # Overall timeout check
            if time.time() - start_time > self.timeout:
                self._handle_timeout(main_menu, input_queue, hook_status)
                return

            # Poll for input
            try:
                digit = input_queue.get(timeout=0.1)

                # PRIORITY 1: If in extension mode, handle as extension digit
                if context.in_extension_mode:
                    self._handle_extension_digit(digit, context, input_queue,
                                                hook_status, main_menu)
                    continue

                # PRIORITY 2: Check for return-to-menu key (only when NOT in extension mode)
                if digit == self.return_to_menu_key:
                    self._handle_return_to_menu(main_menu, input_queue, hook_status, context)
                    return

                # PRIORITY 3: Check for extension prefix
                if digit == self.extension_prefix:
                    self._activate_extension_mode(context)
                    continue

                # PRIORITY 4: Handle as single-digit option
                self._handle_single_digit(digit, context, input_queue,
                                        hook_status, main_menu)

            except queue.Empty:
                # No input - check for extension timeout
                if context.in_extension_mode and context.digit_buffer:
                    if time.time() - context.last_input_time > self.extension_timeout:
                        self._submit_extension(context, input_queue, hook_status, main_menu)
                continue

    def _activate_extension_mode(self, context: HybridNavigationContext) -> None:
        """Activate extension collection mode"""
        # Stop any playing audio
        if self.audio_handler.is_playing():
            self.audio_handler.stop()
            logger.info("Menu audio stopped - entering extension mode")

        # Reset state
        context.in_extension_mode = True
        context.digit_buffer = []
        context.last_input_time = time.time()
        context.state = NavigationState.COLLECTING_EXTENSION

        logger.info(f"Extension mode activated (prefix: '{self.extension_prefix}')")

    def _handle_single_digit(self,
                           digit: str,
                           context: HybridNavigationContext,
                           input_queue: queue.Queue,
                           hook_status: Callable,
                           main_menu: Optional['PhoneTree']) -> None:
        """Process single-digit input (no prefix)"""
        # Check if audio was playing
        audio_was_playing = self.audio_handler.is_playing()

        # Stop audio if playing
        if audio_was_playing:
            self.audio_handler.stop()
            logger.info(f"Audio interrupted by button press: {digit}")

        # Validate option
        if digit in self.options:
            self.options[digit].navigate(input_queue, hook_status, main_menu)
        else:
            # Invalid option
            if not audio_was_playing:
                self.audio_handler.play_file("prompts/invalid_option.mp3", blocking=True)
                time.sleep(0.5)

            # Clear queue and replay
            self._clear_queue(input_queue)
            self.audio_handler.play_file(self.audio_file, blocking=False)

    def _handle_extension_digit(self,
                               digit: str,
                               context: HybridNavigationContext,
                               input_queue: queue.Queue,
                               hook_status: Callable,
                               main_menu: Optional['PhoneTree']) -> None:
        """Process digit in extension collection mode"""
        # Check if user pressed return-to-menu key to cancel extension entry
        if digit == self.return_to_menu_key and len(context.digit_buffer) == 0:
            # Pressed return key with empty buffer - cancel extension mode
            logger.info(f"Extension mode cancelled with '{self.return_to_menu_key}'")
            self._handle_return_to_menu(main_menu, input_queue, hook_status, context)
            return

        # Validate digit
        if digit not in '0123456789*#':
            logger.warning(f"Invalid digit in extension: {digit}")
            return

        # Add to buffer
        context.digit_buffer.append(digit)
        context.last_input_time = time.time()
        logger.debug(f"Extension buffer: {''.join(context.digit_buffer)}")

        # Check if complete
        if self._is_extension_complete(context.digit_buffer, digit):
            # Remove terminator from buffer if present
            if digit == self.extension_terminator:
                context.digit_buffer.pop()

            extension = ''.join(context.digit_buffer)
            self._submit_extension_str(extension, context, input_queue, hook_status, main_menu)

    def _submit_extension(self,
                        context: HybridNavigationContext,
                        input_queue: queue.Queue,
                        hook_status: Callable,
                        main_menu: Optional['PhoneTree']) -> None:
        """Submit collected extension (timeout case)"""
        extension = ''.join(context.digit_buffer)
        self._submit_extension_str(extension, context, input_queue, hook_status, main_menu)

    def _submit_extension_str(self,
                            extension: str,
                            context: HybridNavigationContext,
                            input_queue: queue.Queue,
                            hook_status: Callable,
                            main_menu: Optional['PhoneTree']) -> None:
        """Submit extension and navigate"""
        logger.info(f"Extension submitted: {extension}")

        # Validate extension
        if extension and extension in self.options:
            # Valid extension - navigate
            context.digit_buffer = []
            context.in_extension_mode = False
            context.state = NavigationState.EXTENSION_PLAYING

            self.options[extension].navigate(input_queue, hook_status, main_menu)
        else:
            # Invalid extension
            logger.info(f"Invalid extension: {extension}")
            self.audio_handler.play_file("prompts/invalid_extension.mp3", blocking=True)

            # Clear state and replay menu
            context.digit_buffer = []
            context.in_extension_mode = False
            self._clear_queue(input_queue)
            self.audio_handler.play_file(self.audio_file, blocking=False)

    def _handle_return_to_menu(self,
                              main_menu: Optional['PhoneTree'],
                              input_queue: queue.Queue,
                              hook_status: Callable,
                              context: HybridNavigationContext) -> None:
        """Handle return-to-menu key press"""
        logger.info(f"Return to menu via '{self.return_to_menu_key}'")

        # Stop any playing audio
        self.audio_handler.stop()

        # Clear state
        context.digit_buffer = []
        context.in_extension_mode = False
        self._clear_queue(input_queue)

        # Navigate to main menu
        if main_menu:
            main_menu.navigate(input_queue, hook_status, main_menu)

    def _handle_timeout(self,
                       main_menu: Optional['PhoneTree'],
                       input_queue: queue.Queue,
                       hook_status: Callable) -> None:
        """Handle overall timeout"""
        logger.info("Timeout reached in hybrid mode")
        self.audio_handler.stop()
        self.audio_handler.play_file("prompts/timeout.mp3")
        if main_menu:
            main_menu.navigate(input_queue, hook_status, main_menu)

    def _is_extension_complete(self, buffer: list, last_digit: str) -> bool:
        """Check if buffered extension is complete"""
        # Fixed length
        if self.extension_length and len(buffer) >= self.extension_length:
            return True

        # Terminator
        if last_digit == self.extension_terminator:
            return True

        return False

    def _clear_queue(self, input_queue: queue.Queue) -> None:
        """Clear all pending input from queue"""
        cleared_count = 0
        while not input_queue.empty():
            try:
                input_queue.get_nowait()
                cleared_count += 1
            except queue.Empty:
                break

        if cleared_count > 0:
            logger.debug(f"Cleared {cleared_count} keypresses from queue")

    def _collect_while_playing(self,
                              input_queue: queue.Queue,
                              hook_status: Callable,
                              main_menu: Optional['PhoneTree']) -> Optional[str]:
        """
        Collect extension input while audio continues playing.

        Only interrupts playback when:
        - Complete extension collected
        - Return-to-menu key pressed
        - Audio naturally finishes

        Returns:
            str: Complete extension to navigate to
            None: Return to menu or no extension collected
        """
        buffer = []
        last_input_time = time.time()

        while hook_status():
            # Check if audio finished naturally
            if not self.audio_handler.is_playing():
                # Audio complete
                if buffer:
                    # User started dialing - auto-submit partial buffer
                    extension = ''.join(buffer)
                    logger.info(f"Audio finished, partial buffer auto-submit: {extension}")
                    return extension
                else:
                    # No input - return to menu
                    logger.info("Audio finished, no input - returning to menu")
                    return None

            # Poll for input (non-blocking to not interrupt audio)
            try:
                digit = input_queue.get(timeout=0.1)

                # Check for return-to-menu key (use main_menu's key if this is a leaf node)
                return_key = getattr(main_menu, 'return_to_menu_key', '0') if main_menu else '0'
                if digit == return_key:
                    self.audio_handler.stop()
                    logger.info(f"Return key '{return_key}' pressed during playback")
                    return None  # Signal to return to menu

                # Validate and add to buffer
                if digit in '0123456789*#':
                    buffer.append(digit)
                    last_input_time = time.time()
                    logger.debug(f"Continuous dial buffer: {''.join(buffer)}")

                    # Check if complete (use main_menu's settings)
                    extension_length = getattr(main_menu, 'extension_length', None) if main_menu else None
                    extension_terminator = getattr(main_menu, 'extension_terminator', '#') if main_menu else '#'

                    is_complete = False
                    if extension_length and len(buffer) >= extension_length:
                        is_complete = True
                    elif digit == extension_terminator:
                        is_complete = True

                    if is_complete:
                        # Remove terminator if present
                        if digit == extension_terminator:
                            buffer.pop()

                        extension = ''.join(buffer)
                        self.audio_handler.stop()  # STOP current audio
                        logger.info(f"Complete extension during playback: {extension}")
                        return extension

            except queue.Empty:
                # Check for timeout (use main_menu's timeout)
                extension_timeout = getattr(main_menu, 'extension_timeout', 3.0) if main_menu else 3.0
                if buffer and time.time() - last_input_time > extension_timeout:
                    extension = ''.join(buffer)
                    self.audio_handler.stop()
                    logger.info(f"Extension timeout during playback: {extension}")
                    return extension
                continue

        logger.info("Phone hung up during continuous dialing")
        return None
