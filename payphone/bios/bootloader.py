"""Public selection and protected administration on a single shared runtime."""
import logging
import os
import queue
import time
from typing import Optional

from ..config.settings import Config
from ..core.phone_tree import PhoneTree
from ..core.runtime import shared_runtime
from ..core.system import PhoneSystemBase
from .auth import AdminAuthenticator
from .config_manager import ConfigManager
from .system_manager import SystemManager

logger = logging.getLogger(__name__)


class BIOSBootloader(PhoneSystemBase):
    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        self.bios_config = ConfigManager()
        self.system_manager = SystemManager(self.bios_config.get_scan_paths())
        self.authenticator = AdminAuthenticator()
        self.admin_session = None
        self.current_system: Optional[PhoneSystemBase] = None
        self.current_system_id: Optional[str] = None
        self.in_bios_menu = False
        self._pending_system = None
        self._configure_escape()
        self.runtime.on_escape = self._escape_requested

    def _configure_escape(self) -> None:
        candidate = self.bios_config.get("escape_sequence")
        interval = self.bios_config.get("escape_timeout")
        try:
            candidate = os.environ.get("BIOS_ESCAPE_SEQUENCE", candidate)
            interval = float(os.environ.get("BIOS_ESCAPE_TIMEOUT", interval))
            validated = ConfigManager._validate({"escape_sequence": candidate, "escape_timeout": interval})
        except (ValueError, TypeError):
            logger.error("Invalid escape settings; reserving the safe default ***# with a one second timeout")
            validated = ConfigManager.DEFAULT_CONFIG
        self.runtime.escape_sequence = validated["escape_sequence"]
        self.runtime.escape_timeout = validated["escape_timeout"]

    def _escape_requested(self) -> None:
        self._pending_system = None
        if self.admin_session:
            self.admin_session.revoke()

    def end_call(self) -> None:
        if self.admin_session:
            self.admin_session.revoke()
        super().end_call()

    def auto_launch_system(self) -> bool:
        """Compatibility entry point: only an explicitly chosen default may launch."""
        default = self.bios_config.get_default_system()
        return self.launch_system(default) if default else False

    def launch_system(self, system_id: str) -> bool:
        """Request a sequential per-call switch; never allocate or spawn here."""
        if not self.is_call_active():
            return False
        if not self.system_manager.discovered_systems:
            self.system_manager.discover_systems()
        if not self.system_manager.load_system(system_id):
            logger.error("Selected system is unavailable: %s", system_id)
            return False
        self._pending_system = system_id
        self.runtime.cancel("switch")
        return True

    def _node(self, text: str, **kwargs) -> PhoneTree:
        return PhoneTree("", audio_handler=self.audio_handler, speech_handler=self, speech_text=text, **kwargs)

    def setup_phone_tree(self) -> PhoneTree:
        self.system_manager.discover_systems()
        systems = self.system_manager.list_systems()[:9]
        options = {
            str(index): self._node("", action=lambda sid=system.id: self.launch_system(sid))
            for index, system in enumerate(systems, start=1)
        }
        options["0"] = self._node("", action=self._administer)
        choices = " ".join(f"Press {index} for {system.name}." for index, system in enumerate(systems, start=1))
        if not systems:
            choices = "No phone systems are currently available."
        return self._node(f"Select a phone system. {choices} Press zero for protected administration.", options=options, timeout=60)

    def _construct_system(self, system_id: str) -> Optional[PhoneSystemBase]:
        system_class = self.system_manager.load_system(system_id)
        if not system_class:
            return None
        try:
            with shared_runtime(self.runtime):
                return system_class(self.config)
        except Exception:
            logger.exception("Could not construct system %s", system_id)
            return None

    def _call_handler(self) -> None:
        """Only this thread navigates. Escape waits for the old action to unwind."""
        self.system_manager.discover_systems()
        target = self.bios_config.get_default_system()
        while self.running and self.runtime.off_hook:
            session = self._session
            self._pending_system = None
            self.current_system = self._construct_system(target) if target else None
            self.current_system_id = target if self.current_system else None
            self.in_bios_menu = self.current_system is None
            try:
                if self.current_system:
                    self.current_system._call_handler()
                else:
                    if target:
                        self.speak("The default system is unavailable. Please select another system.")
                    menu = self.setup_phone_tree()
                    menu.navigate(session.input_queue, self.is_call_active, menu)
            except PermissionError:
                # The revoked session cannot start even explanatory admin speech.
                logger.info("Administration expired or was cancelled")
                if self.is_call_active():
                    self.runtime.cancel("admin exit")
            except Exception:
                logger.exception("Navigation failed")
                if self.is_call_active():
                    # Retry a failed plugin through the picker once, but never
                    # hot-loop when BIOS itself has a missing speech dependency.
                    self.runtime.cancel("escape" if self.current_system else "navigation error")
            finally:
                if self.admin_session:
                    self.admin_session.revoke()
                    self.admin_session = None
            reason = session.reason
            target = self._pending_system if reason == "switch" else None
            self.current_system = None
            self.current_system_id = None
            self.runtime.cancel("navigation ended")
            if not self.runtime.off_hook or not self.running or reason not in ("escape", "switch", "admin exit"):
                return
            # Previous navigation has returned. Rebinding cannot overlap consumers.
            self._bind_session(self.runtime.new_session())

    def _administer(self) -> bool:
        capability = self.authenticator.authenticate(self)
        if capability is None:
            return False
        self.admin_session = capability
        try:
            tree = self._administration_tree(capability)
            tree.navigate(self.hardware_handler.input_queue, lambda: self.is_call_active() and capability.is_authorized(), tree)
        finally:
            capability.revoke()
            self.admin_session = None
        if self.is_call_active():
            self.runtime.cancel("admin exit")
        return False

    def _exit_administration(self) -> bool:
        if self.admin_session:
            self.admin_session.revoke()
        self.runtime.cancel("admin exit")
        return False

    def _administration_tree(self, capability) -> PhoneTree:
        return self._node(
            "Administrator menu. Press one to choose the persistent startup default. "
            "Press two to configure a phone system. Press zero to exit administration.",
            options={
                "1": self._node("", action=lambda: self._default_menu(capability)),
                "2": self._node("", action=lambda: self._system_admin_menu(capability)),
                "0": self._node("", action=self._exit_administration),
            }, timeout=120,
        )

    def _default_menu(self, capability) -> bool:
        capability.require_authorized()
        systems = self.system_manager.list_systems()[:9]
        options = {"0": self._node("", action=lambda: self._save_default(None, capability))}
        for index, system in enumerate(systems, start=1):
            options[str(index)] = self._node("", action=lambda sid=system.id: self._save_default(sid, capability))
        choices = " ".join(f"Press {index} for {system.name}." for index, system in enumerate(systems, start=1))
        tree = self._node(f"Choose a persistent startup default. {choices} Press zero for the public picker on every pickup.", options=options)
        # A choice returns to the administrator tree rather than replaying this submenu.
        tree.navigate(self.hardware_handler.input_queue, lambda: self.is_call_active() and capability.is_authorized())
        return False

    def _save_default(self, system_id: Optional[str], capability) -> bool:
        capability.require_authorized()
        self.speak("Press one to confirm this persistent startup default. Any other key cancels.")
        deadline = time.monotonic() + 30
        while self.is_call_active() and capability.is_authorized() and time.monotonic() < deadline:
            try:
                key = self.hardware_handler.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if key == "1":
                capability.require_authorized()
                if system_id and not self.system_manager.load_system(system_id):
                    self.speak("That system is unavailable. The default was not changed.")
                    return False
                try:
                    capability.require_authorized()
                    self.bios_config.set_default_system(system_id, commit=capability.protected_commit)
                except (OSError, ValueError) as exc:
                    logger.error("Could not save BIOS default: %s", exc)
                    self.speak("The default could not be saved. Check the state directory permissions and storage.")
                    return False
                self.speak("Persistent default saved.")
            return False
        return False

    def _system_admin_menu(self, capability) -> bool:
        capability.require_authorized()
        systems = self.system_manager.list_systems()[:9]
        options = {
            str(index): self._node("", action=lambda sid=system.id: self._configure_system(sid, capability))
            for index, system in enumerate(systems, start=1)
        }
        options["0"] = self._node("Return to administration.")
        choices = " ".join(f"Press {index} for {system.name}." for index, system in enumerate(systems, start=1))
        tree = self._node(f"Configure a phone system. {choices} Press zero to go back.", options=options)
        tree.navigate(self.hardware_handler.input_queue, lambda: self.is_call_active() and capability.is_authorized())
        return False

    def _configure_system(self, system_id: str, capability) -> bool:
        capability.require_authorized()
        system = self._construct_system(system_id)
        if system is None:
            self.speak("That system is unavailable.")
            return False
        tree = system.setup_admin_tree(capability)
        if tree is None:
            self.speak("This system has no handset administration menu.")
            return False
        capability.require_authorized()
        tree.navigate(self.hardware_handler.input_queue, lambda: self.is_call_active() and capability.is_authorized(), tree)
        return False

    def shutdown(self) -> None:
        if self.admin_session:
            self.admin_session.revoke()
        super().shutdown()
