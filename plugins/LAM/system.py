#!/usr/bin/env python3
"""Leave a Message payphone plugin."""

from __future__ import annotations

import logging
import queue
import time
from pathlib import Path
from typing import Optional

from payphone.config.settings import Config
from payphone.core import PhoneSystemBase, PhoneTree

from . import record
from .message_manager import MessageManager

logger = logging.getLogger(__name__)


class LAMSystem(PhoneSystemBase):
    """Leave a Message: hear a stranger, leave one for the next caller."""

    @staticmethod
    def get_metadata() -> dict[str, str]:
        return {
            "name": "Leave a Message",
            "description": "Hear a random message, leave one for the next caller, and browse the burn archive.",
            "version": "1.0.0",
            "author": "Reid Chatham",
        }

    def __init__(self, config: Optional[Config] = None) -> None:
        super().__init__(config)
        self.message_manager = MessageManager(audio_dir=self.config.AUDIO_DIR)
        self.is_recording = False
        self._recording_initialized = False

    def setup_phone_tree(self) -> PhoneTree:
        """Build the Leave a Message menu."""
        record_node = PhoneTree("", action=self.record_message, audio_handler=self.audio_handler)
        browse_node = PhoneTree("", action=self.browse_messages, audio_handler=self.audio_handler)

        menu_options = {"1": record_node, "2": browse_node}
        for message in self.message_manager.list_all():
            extension = message.stem
            menu_options[extension] = self._create_message_node(message)

        main_menu = PhoneTree(
            "",
            audio_handler=self.audio_handler,
            action=self.start_message_exchange,
            options=menu_options,
            hybrid_mode=True,
            extension_prefix="*",
            extension_terminator="#",
            extension_timeout=5.0,
            return_to_menu_key="0",
            allow_continuous_dialing=False,
            timeout=300,
        )
        self.phone_tree = main_menu
        return main_menu

    def _ensure_recording_initialized(self) -> bool:
        """Initialize the recording input device once before recording."""
        if getattr(self, "_recording_initialized", False):
            return True

        try:
            record.init()
        except Exception as exc:
            logger.error("LAM recording initialization error: %s", exc)
            self.say("Sorry, recording is not available right now.", blocking=True)
            return False

        self._recording_initialized = True
        return True

    def start_message_exchange(self) -> bool:
        """Play the pickup flow: intro, random message, then menu instructions."""
        self.say("Leave a message. First, listen to someone who came before you.", blocking=True)
        self.play_random_message()
        self.say(
            "Press one to leave a message for the next person. "
            "Press two to listen to past messages from the burn. "
            "Dial star, then a three digit message number, then pound to hear a specific message. "
            "Press zero to return to the system menu.",
            blocking=True,
        )
        return True

    def play_random_message(self) -> bool:
        """Play a random saved message, if one exists."""
        message = self.message_manager.get_random()
        if message is None:
            self.say("No one has left a message yet. You can be the first.", blocking=True)
            return True

        logger.info("Playing random LAM message: %s", message)
        self._play_message(message)
        return True

    def browse_messages(self) -> bool:
        """Play all saved messages in chronological order."""
        self.clear_input_queue()
        messages = self.message_manager.list_all()
        if not messages:
            self.say("There are no past messages yet.", blocking=True)
            return True

        self.say("Playing all past messages in the order they were left. Press zero to stop.", blocking=True)
        for index, message in enumerate(messages, start=1):
            if self.phone_on_hook:
                return True

            self.say(f"Message {index} of {len(messages)}.", blocking=True)
            interrupted = self._play_message(message, interruptible=True)

            if interrupted:
                self.say("Returning to the menu.", blocking=True)
                return True

        self.say("End of messages.", blocking=True)
        return True

    def record_message(self) -> bool:
        """Record a message. Pound saves, star restarts, zero cancels."""
        logger.info("Entering LAM recording mode")
        self.clear_input_queue()
        if not self._ensure_recording_initialized():
            return True

        while True:
            filename = self.message_manager.filename_for_next()
            self.say("Record your message after the beep.", blocking=True)
            self.say("Press pound to save, star to re-record, or zero to cancel.", blocking=True)
            self.audio_handler.play_dtmf_tone("#")

            try:
                record.start_recording(filename, timeout=0)
                self.is_recording = True
                start_time = time.time()

                while time.time() - start_time < 60:
                    if self.phone_on_hook:
                        logger.info("Phone hung up during LAM recording")
                        record.stop_recording()
                        self.is_recording = False
                        return True

                    try:
                        key = self.hardware_handler.input_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    if key == "#":
                        record.stop_recording()
                        self.is_recording = False
                        extension = filename.stem
                        self._register_extension(extension, filename)
                        self.say(
                            f"Thank you. Your message has been saved as message {extension}.",
                            blocking=True,
                        )
                        logger.info("LAM recording saved: %s", filename)
                        return True

                    if key == "*":
                        record.stop_recording()
                        self.is_recording = False
                        self.message_manager.delete_file(filename)
                        self.say("Recording again.", blocking=True)
                        self.clear_input_queue()
                        break

                    if key == "0":
                        record.stop_recording()
                        self.is_recording = False
                        self.message_manager.delete_file(filename)
                        self.say("Recording cancelled.", blocking=True)
                        return True
                else:
                    record.stop_recording()
                    self.is_recording = False
                    extension = filename.stem
                    self._register_extension(extension, filename)
                    self.say(f"Time is up. Your message has been saved as message {extension}.", blocking=True)
                    logger.info("LAM recording auto-saved after timeout: %s", filename)
                    return True

            except Exception as exc:
                logger.error("LAM recording error: %s", exc)
                self.is_recording = False
                try:
                    record.stop_recording()
                except Exception:
                    pass
                self.message_manager.delete_file(filename)
                self.say("Sorry, there was an error recording your message.", blocking=True)
                return True

    def play_extension(self, extension: str) -> bool:
        """Play a specific message extension."""
        message = self.message_manager.messages_dir / f"{extension}.wav"
        if not message.exists():
            self.say("Sorry, that message does not exist.", blocking=True)
            return True

        self.say(f"Playing message {extension}.", blocking=True)
        self._play_message(message)
        return True

    def _register_extension(self, extension: str, message: Path) -> None:
        """Register a new message extension on the active phone tree."""
        if not hasattr(self, "phone_tree") or self.phone_tree is None:
            return
        self.phone_tree.options[extension] = self._create_message_node(message)

    def _create_message_node(self, message: Path) -> PhoneTree:
        """Create a PhoneTree node for one message extension."""
        extension = message.stem
        return PhoneTree(
            "",
            action=lambda extension=extension: self.play_extension(extension),
            audio_handler=self.audio_handler,
        )

    def _play_message(self, message: Path, interruptible: bool = False) -> bool:
        """Play a message and return True when playback was interrupted."""
        relative_path = self.message_manager.relative_audio_path(message)
        self.audio_handler.play_file(relative_path, blocking=not interruptible)

        if not interruptible:
            while self.audio_handler.is_playing() and not self.phone_on_hook:
                time.sleep(0.1)
            return False

        while self.audio_handler.is_playing() and not self.phone_on_hook:
            if self._consume_stop_key():
                self.audio_handler.stop()
                return True
            time.sleep(0.1)

        return False

    def _consume_stop_key(self) -> bool:
        try:
            key = self.hardware_handler.input_queue.get_nowait()
        except queue.Empty:
            return False
        return key in {"0", "#"}
