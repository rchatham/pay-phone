#!/usr/bin/env python3
"""
Base class for payphone systems.

This provides the core functionality for running a payphone system,
while allowing subclasses to define their own phone tree structure.
"""
import logging
import signal
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional

from ..audio.handler import AudioHandler
from ..config.settings import Config
from ..hardware.gpio_handler import GPIOHandler
from ..hardware.serial_handler import SerialHandler
from .phone_tree import PhoneTree

logger = logging.getLogger(__name__)


class PhoneSystemBase(ABC):
    """
    Abstract base class for payphone systems.

    Subclasses must implement setup_phone_tree() to define
    the phone menu structure.

    Example:
        class MyPhoneSystem(PhoneSystemBase):
            def setup_phone_tree(self) -> PhoneTree:
                return PhoneTree(
                    "welcome.mp3",
                    audio_handler=self.audio_handler,
                    options={
                        "1": PhoneTree("option1.mp3", audio_handler=self.audio_handler)
                    }
                )
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the phone system.

        Args:
            config: Optional Config object. If not provided, uses default Config().
        """
        self.config = config or Config()
        self.audio_handler = AudioHandler(self.config.AUDIO_DIR)
        self.phone_on_hook = True
        self.running = True
        self.current_call = None

        # Initialize hardware handler based on config
        if self.config.USE_GPIO:
            logger.info("Using GPIO mode (direct Raspberry Pi connection)")
            self.hardware_handler = GPIOHandler(
                keypad_rows=self.config.KEYPAD_ROW_PINS,
                keypad_cols=self.config.KEYPAD_COL_PINS,
                hook_pin=self.config.HOOK_SWITCH_PIN,
                audio_handler=self.audio_handler  # Pass audio handler for DTMF tones
            )
        else:
            logger.info("Using Serial mode (Arduino connection)")
            self.hardware_handler = SerialHandler(
                port=self.config.SERIAL_PORT,
                baudrate=self.config.BAUDRATE
            )

    @abstractmethod
    def setup_phone_tree(self) -> PhoneTree:
        """
        Build the phone menu tree.

        This method must be implemented by subclasses to define the
        menu structure for their specific phone system.

        Returns:
            PhoneTree: The root node of the phone tree

        Example:
            def setup_phone_tree(self) -> PhoneTree:
                audio = self.audio_handler

                main_menu = PhoneTree(
                    "menu/main.mp3",
                    audio_handler=audio,
                    options={
                        "1": PhoneTree("menu/option1.mp3", audio_handler=audio),
                        "2": PhoneTree("menu/option2.mp3", audio_handler=audio)
                    }
                )

                return main_menu
        """
        pass

    def hook_status_changed(self, off_hook: bool):
        """Handle hook switch changes"""
        self.phone_on_hook = not off_hook

        if off_hook:
            logger.info("Phone picked up")
            self.start_call()
        else:
            logger.info("Phone hung up")
            self.end_call()

    def start_call(self):
        """Start a new call session"""
        self.audio_handler.play_file("prompts/dial_tone.mp3", blocking=False)
        time.sleep(1)
        self.audio_handler.stop()

        # Start navigation in new thread
        self.current_call = threading.Thread(
            target=self._call_handler
        )
        self.current_call.start()

    def _call_handler(self):
        """Handle the call navigation"""
        main_menu = self.setup_phone_tree()
        main_menu.navigate(
            self.hardware_handler.input_queue,
            lambda: not self.phone_on_hook,
            main_menu
        )

    def end_call(self):
        """End current call"""
        self.audio_handler.stop()
        # Clear input queue
        while not self.hardware_handler.input_queue.empty():
            self.hardware_handler.input_queue.get()

        # Wait for call thread to finish
        if self.current_call and self.current_call.is_alive():
            self.current_call.join(timeout=2.0)

    def run(self):
        """Main application loop"""
        # Setup hardware communication
        self.hardware_handler.set_hook_callback(self.hook_status_changed)
        if not self.hardware_handler.start():
            logger.error("Failed to start hardware communication")
            return

        logger.info("Payphone system started")

        # Keep running until interrupted
        try:
            while self.running:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        """Cleanup and shutdown"""
        logger.info("Shutting down...")
        self.running = False

        # Signal phone is on hook to exit navigation loops
        self.phone_on_hook = True

        # Stop audio playback
        self.audio_handler.stop()

        # Wait for call thread to finish
        if self.current_call and self.current_call.is_alive():
            logger.info("Waiting for call thread to finish...")
            self.current_call.join(timeout=3.0)
            if self.current_call.is_alive():
                logger.warning("Call thread did not exit cleanly")

        # Stop hardware and cleanup
        self.hardware_handler.stop()

        # Quit pygame last (after all threads are stopped)
        try:
            import pygame
            pygame.quit()
        except:
            pass

        logger.info("Shutdown complete")
