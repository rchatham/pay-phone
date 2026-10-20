"""Payphone plugin base with shared, cancellable hardware/audio ownership."""
import logging
import queue
import threading
from abc import ABC, abstractmethod
from typing import Optional

from ..audio.handler import AudioHandler
from ..audio.speech import OfflineSpeech
from ..config.settings import Config
from ..hardware.gpio_handler import GPIOHandler
from ..hardware.serial_handler import SerialHandler
from .phone_tree import PhoneTree
from .runtime import PhoneRuntime, SessionAudio, SessionHardware, construction_runtime, shared_runtime

logger = logging.getLogger(__name__)


class PhoneSystemBase(ABC):
    """Plugins keep their existing (config) constructor and setup_phone_tree API."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        runtime = construction_runtime()
        self._owns_runtime = runtime is None
        if runtime is None:
            audio = AudioHandler(self.config.AUDIO_DIR)
            if self.config.USE_GPIO:
                # Raw GPIO never plays tones or logs digits (PINs travel here too).
                hardware = GPIOHandler(
                    keypad_rows=self.config.KEYPAD_ROW_PINS,
                    keypad_cols=self.config.KEYPAD_COL_PINS,
                    hook_pin=self.config.HOOK_SWITCH_PIN,
                    audio_handler=None,
                )
            else:
                hardware = SerialHandler(port=self.config.SERIAL_PORT, baudrate=self.config.BAUDRATE)
            runtime = PhoneRuntime(hardware, audio)
            runtime.speech = OfflineSpeech(runtime)
        self.runtime = runtime
        self._session = None
        self._phone_on_hook = True
        self.hardware_handler = runtime.hardware
        self.audio_handler = runtime.audio
        self.running = True
        self.current_call = None
        self._call_lock = threading.RLock()
        self._call_running = False
        self._pending_pickup = False
        self.tts = runtime.speech
        self.tts_available = bool(runtime.speech and runtime.speech.executable)
        if not self._owns_runtime and runtime.session:
            self._bind_session(runtime.session)

    def _bind_session(self, session) -> None:
        self._session = session
        self.hardware_handler = SessionHardware(session)
        self.audio_handler = SessionAudio(self.runtime, session)

    @property
    def phone_on_hook(self) -> bool:
        # Legacy __new__-based plugins/tests can still set/read this attribute.
        if getattr(self, "_session", None) is not None:
            return not self.runtime.is_active(self._session)
        return getattr(self, "_phone_on_hook", True)

    @phone_on_hook.setter
    def phone_on_hook(self, value: bool) -> None:
        self._phone_on_hook = value

    def is_call_active(self) -> bool:
        return not self.phone_on_hook and getattr(self, "running", True)

    def say(self, text: str, blocking: bool = True) -> None:
        if self._session and self.is_call_active():
            capability = self._session.admin_session
            if capability:
                capability.require_authorized()
            # Admin speech never hides inactivity expiry behind a blocking join.
            self.runtime.speech.say(text, self._session, blocking=blocking and capability is None)
            if blocking and capability:
                try:
                    while self.is_call_active() and self.runtime.speech.is_speaking():
                        capability.require_authorized()
                        self._session.cancelled.wait(0.05)
                    capability.require_authorized()
                except PermissionError:
                    self.runtime.speech.stop_speech()
                    raise

    def speak(self, text: str) -> None:
        self.say(text, blocking=True)

    def stop_speech(self) -> None:
        self.runtime.speech.stop_speech()

    def is_speaking(self) -> bool:
        return self.is_call_active() and self.runtime.speech.is_speaking()

    @abstractmethod
    def setup_phone_tree(self) -> PhoneTree:
        """Build a public call tree using this system's bound handlers."""
        raise NotImplementedError

    def setup_admin_tree(self, admin_session) -> Optional[PhoneTree]:
        """Optional authenticated administration; never invoked on public paths."""
        return None

    def hook_status_changed(self, off_hook: bool) -> None:
        with self._call_lock:
            was_off_hook = self.runtime.off_hook
            self.runtime.off_hook = off_hook
            self._phone_on_hook = not off_hook
            if off_hook:
                if self._call_running and not was_off_hook:
                    self._pending_pickup = True
                self.start_call()
            else:
                self._pending_pickup = False
                self.end_call()

    def start_call(self) -> bool:
        """Never overlap consumers, including when a cancelled action refuses exit."""
        if not self._owns_runtime:
            raise RuntimeError("Shared plugins may not start independent call threads")
        with self._call_lock:
            if self._call_running:
                # Hook callbacks retain pending pickup; direct starts never create
                # another consumer while the old navigation is unwinding.
                return False
            if not self.running or not self.runtime.off_hook:
                return False
            self.runtime.start_dispatcher()
            self._bind_session(self.runtime.new_session())
            self._pending_pickup = False
            self._call_running = True
            self.current_call = threading.Thread(target=self._run_call, name="payphone-call", daemon=True)
            self.current_call.start()
            return True

    def _run_call(self) -> None:
        while True:
            try:
                with shared_runtime(self.runtime):
                    self._call_handler()
            except Exception:
                logger.exception("Call navigation failed")
            finally:
                with self._call_lock:
                    self.runtime.cancel("call ended")
                    restart = self._pending_pickup and self.running and self.runtime.off_hook
                    self._pending_pickup = False
                    if restart:
                        self._bind_session(self.runtime.new_session())
                    else:
                        self._call_running = False
            if not restart:
                return

    def _call_handler(self) -> None:
        main_menu = self.setup_phone_tree()
        main_menu.navigate(self.hardware_handler.input_queue, self.is_call_active, main_menu)

    def clear_input_queue(self) -> int:
        # The dispatcher alone reads raw hardware input, even before first pickup.
        if getattr(self, "_session", None) is None:
            return 0
        cleared = 0
        while True:
            try:
                self.hardware_handler.input_queue.get_nowait()
                cleared += 1
            except queue.Empty:
                return cleared

    def end_call(self) -> None:
        self.runtime.cancel("hangup")
        self.clear_input_queue()
        # Hook callbacks must remain available while plugins cooperatively unwind.

    def run(self) -> None:
        if not self._owns_runtime:
            raise RuntimeError("Only the runtime owner can start hardware")
        self.runtime.start_dispatcher()
        self.runtime.hardware.set_hook_callback(self.hook_status_changed)
        if not self.runtime.hardware.start():
            logger.error("Failed to start hardware communication")
            self.shutdown()
            return
        try:
            while self.running:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self) -> None:
        self.running = False
        if not self._owns_runtime:
            return
        self.runtime.off_hook = False
        self.runtime.stop()
        if self.current_call and self.current_call is not threading.current_thread():
            self.current_call.join(timeout=3)
            if self.current_call.is_alive():
                logger.error("Cancelled navigation did not exit; runtime remains closed")
        self.runtime.hardware.stop()
        try:
            import pygame
            pygame.quit()
        except Exception:
            logger.exception("Audio shutdown failed")
