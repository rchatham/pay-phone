"""
BIOS Bootloader system for payphone.

Provides system selection menu, configuration, and hot-reloading capabilities.
Supports:
- Pick up handset to enter BIOS menu (default)
- Pickup routes: a key held while the handset is lifted picks the system that
  starts (e.g. hold 9 and lift for a network mode)
- Long-press * for 5 seconds during system operation to return to BIOS
- Optional legacy auto-launch of the last selected system
- Dynamic discovery and loading of phone systems

A launched system shares the BIOS's hardware and audio handlers, so it reads
the same keypad input queue the BIOS started and inherits the off-hook state.

Keypad input queue ownership:
- On hook: nobody reads the queue. Keys pressed while hung up are discarded
  when the handset is lifted, so they never leak into the next call.
- Off hook: the BIOS menu or the launched system reads the queue; the
  long-press-* monitor peeks at it while a launched system runs.
"""

import inspect
import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from ..audio.handler import AudioHandler
from ..config.settings import Config
from ..core.phone_tree import PhoneTree
from ..core.system import PhoneSystemBase
from .config_manager import ConfigManager
from ..hardware.key_hold import KeyHold
from .pickup_routes import DEFAULT_RELEASE_GRACE_SECONDS, match_pickup_route, normalize_routes
from .system_manager import SystemManager, SystemInfo, load_theme

logger = logging.getLogger(__name__)


class BIOSBootloader(PhoneSystemBase):
    """
    BIOS/Bootloader system for payphone.

    Acts as a base system that can launch other phone systems and
    provide configuration/selection menus.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize BIOS bootloader.

        Args:
            config: Optional Config object
        """
        super().__init__(config)

        # BIOS-specific configuration
        self.bios_config = ConfigManager()
        self.system_manager = SystemManager(self.bios_config.get_scan_paths())

        # State management
        self.current_system: Optional[PhoneSystemBase] = None
        self.current_system_id: Optional[str] = None
        self.in_bios_menu = False
        self.bios_requested = False
        self.star_key_press_start: Optional[float] = None

        # Hook hold detection
        self.hook_pickup_time: Optional[float] = None
        self.hook_hold_threshold = self.bios_config.get_bios_enter_hold_seconds()

        # Long-press detection
        self.long_press_threshold = self.bios_config.get_bios_exit_long_press_seconds()
        self.long_press_monitor_thread: Optional[threading.Thread] = None
        self.stop_long_press_monitor = threading.Event()

        # Pickup routes: same clock as the keypad's hold timestamps
        self._clock = time.monotonic
        self._warned_no_key_holds = False

        logger.info("BIOS Bootloader initialized")

    def hook_status_changed(self, off_hook: bool):
        """
        Override hook status change handler to detect BIOS entry condition.

        Args:
            off_hook: True if phone picked up, False if hung up
        """
        logger.info(f"Hook status changed: {'OFF' if off_hook else 'ON'} hook")

        if off_hook:
            # Phone picked up
            self.phone_on_hook = False

            # A routed key held while lifting chooses a system. Keys pressed
            # while hung up are discarded either way.
            target = self._take_pickup_route()
            if target:
                logger.info(f"Pickup route matched: launching {target}")
                if self.launch_system(target, remember=False):
                    return
                logger.warning(f"Pickup route target {target!r} did not launch; normal pickup")

            # Enter the BIOS/main menu immediately when configured to do so.
            if self.bios_config.get_always_show_menu_on_pickup() or not self.bios_config.get_auto_launch():
                logger.info("Entering BIOS menu on pickup")
                self.in_bios_menu = True
                self.start_call()
                return

            # Legacy auto-launch without a hold window: lift goes straight to
            # the last system (art phones).
            if self.hook_hold_threshold <= 0:
                self.auto_launch_system()
                return

            # Record pickup time for hold detection when legacy auto-launch is enabled.
            self.hook_pickup_time = time.time()

            # Wait for hold threshold to check if user wants BIOS
            time.sleep(self.hook_hold_threshold)

            # Check if hook is still off after hold period
            if not self.phone_on_hook:
                hold_time = time.time() - self.hook_pickup_time
                if hold_time >= self.hook_hold_threshold:
                    logger.info(f"Hook held for {hold_time:.1f}s - entering BIOS menu")
                    self.in_bios_menu = True
                    self.start_call()
                else:
                    # Released before threshold - auto-launch
                    self.auto_launch_system()
            # else: Hook already hung up, ignore
        else:
            # Phone hung up
            self.phone_on_hook = True
            self.hook_pickup_time = None

            # Stop current system first so its navigate() loop sees on-hook,
            # then wait for the call thread to finish.
            if self.current_system:
                logger.info("Stopping current system due to hang-up")
                self._stop_current_system()

            # Nothing may read the keypad queue while on hook: the long-press
            # monitor would otherwise keep pulling keys (and could reopen the
            # BIOS menu on a hung-up phone).
            self._halt_long_press_monitor()

            if self.current_call and self.current_call.is_alive():
                self.end_call()

    def auto_launch_system(self):
        """Auto-launch the last selected system if configured"""
        if not self.bios_config.get_auto_launch():
            logger.info("Auto-launch disabled, entering BIOS menu")
            self.in_bios_menu = True
            self.start_call()
            return

        last_system = self.bios_config.get_last_system()
        if not last_system:
            logger.info("No last system configured, entering BIOS menu")
            self.in_bios_menu = True
            self.start_call()
            return

        logger.info(f"Auto-launching last system: {last_system}")
        self.launch_system(last_system)

    def launch_system(self, system_id: str, remember: bool = True) -> bool:
        """
        Launch a phone system by ID.

        Args:
            system_id: System identifier
            remember: Save it as ``last_system`` (what legacy auto-launch
                starts). Pickup routes pass False so pressing 9 for network
                mode once does not change what the next caller gets.

        Returns:
            True if launched successfully, False otherwise
        """
        # Discover systems if not already done
        if not self.system_manager.discovered_systems:
            logger.info("Discovering phone systems...")
            self.system_manager.discover_systems()

        # Load the system class
        system_class = self.system_manager.load_system(system_id)
        if not system_class:
            logger.error(f"Failed to load system: {system_id}")
            return False

        # Instantiate the system around the BIOS's live handlers
        try:
            self.current_system = self._instantiate_system(system_class)
            self.current_system_id = system_id
            if remember:
                self.bios_config.set_last_system(system_id)
            self.in_bios_menu = False

            logger.info(f"Launched system: {system_id}")

            # Start long-press monitoring for returning to BIOS
            self.start_long_press_monitor()

            # Start the call
            self.start_call()

            return True
        except Exception as e:
            logger.error(f"Error launching system {system_id}: {e}", exc_info=True)
            return False

    def _instantiate_system(self, system_class: type) -> PhoneSystemBase:
        """
        Construct a phone system that shares the BIOS's hardware and audio handlers.

        The BIOS owns the started hardware handler (the keypad feeds its
        input_queue) and the audio handler. A system built with
        ``system_class(config)`` would get fresh, never-started handlers and
        ``phone_on_hook=True``: its menu would exit immediately and every
        keypress would stay in the BIOS queue. Inject our handlers through the
        constructor when it accepts them (PhoneSystemBase and TDTM do), else
        swap them in after construction.

        Args:
            system_class: PhoneSystemBase subclass loaded by SystemManager

        Returns:
            Instance wired to self.hardware_handler / self.audio_handler and
            carrying the BIOS's current hook state.
        """
        if self._accepts_injected_handlers(system_class):
            system = system_class(
                self.config,
                hardware_handler=self.hardware_handler,
                audio_handler=self.audio_handler,
            )
        else:
            logger.warning(
                f"{system_class.__name__} does not accept hardware_handler/audio_handler; "
                "replacing its handlers after construction"
            )
            system = system_class(self.config)
            # The handlers it built were never started; do not stop() them, a
            # GPIO cleanup would tear down the pins the shared handler uses.
            system.hardware_handler = self.hardware_handler
            system.audio_handler = self.audio_handler

        system.phone_on_hook = self.phone_on_hook
        system.running = True
        return system

    @staticmethod
    def _accepts_injected_handlers(system_class: type) -> bool:
        """Return True if system_class.__init__ takes hardware_handler and audio_handler."""
        try:
            parameters = inspect.signature(system_class.__init__).parameters
        except (TypeError, ValueError):
            return False
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
            return True
        return {"hardware_handler", "audio_handler"} <= set(parameters)

    def _stop_current_system(self) -> None:
        """Tell the launched system to stop and forget it.

        Its _call_handler polls ``phone_on_hook`` (not ``running``), so both
        flags are set to end its navigation loop.
        """
        system = self.current_system
        if system is None:
            return
        system.running = False
        system.phone_on_hook = True
        self.current_system = None

    # ------------------------------------------------------------------
    # Pickup routes: a key held while the handset is lifted
    # ------------------------------------------------------------------

    def _key_holds(self) -> Optional[List[KeyHold]]:
        """Key holds from the hardware handler, or None if it cannot report them.

        GPIO keypads always can. The serial handler can once the Arduino
        firmware sends KEYUP lines; custom handlers may not implement
        ``key_holds()`` at all.
        """
        reader = getattr(self.hardware_handler, "key_holds", None)
        holds = reader() if callable(reader) else None
        if not isinstance(holds, (list, tuple)):
            return None
        return list(holds)

    def _pickup_route_settings(self) -> Tuple[Dict[str, str], float]:
        """Routes and release grace: .bios_config.json first, then the theme's theme.json."""
        routes_raw: Any = self.bios_config.get_pickup_routes()
        grace_raw: Any = self.bios_config.get_pickup_route_release_grace_seconds()
        if routes_raw is None or grace_raw is None:
            theme = load_theme(self.bios_config.get_theme_path()) or {}
            if routes_raw is None:
                routes_raw = theme.get("pickup_routes")
            if grace_raw is None:
                grace_raw = theme.get("pickup_route_release_grace_seconds")

        try:
            grace = float(grace_raw) if grace_raw is not None else DEFAULT_RELEASE_GRACE_SECONDS
        except (TypeError, ValueError):
            grace = DEFAULT_RELEASE_GRACE_SECONDS
        if grace < 0:
            grace = DEFAULT_RELEASE_GRACE_SECONDS
        return normalize_routes(routes_raw), grace

    def _take_pickup_route(self) -> Optional[str]:
        """On lift: return the system routed by the key held while lifting, if any.

        Always discards the keys queued while on hook (including the held
        key's own press), so they never reach the BIOS menu or the launched
        system.
        """
        try:
            routes, grace = self._pickup_route_settings()
            if not routes:
                return None
            holds = self._key_holds()
            if holds is None:
                if not self._warned_no_key_holds:
                    logger.warning(
                        "pickup_routes are configured but the keypad cannot report held keys "
                        "(update the Arduino firmware); using the normal pickup"
                    )
                    self._warned_no_key_holds = True
                return None
            return match_pickup_route(holds, self._clock(), routes, grace)
        except Exception:
            logger.exception("Pickup route matching failed; using the normal pickup")
            return None
        finally:
            self.clear_input_queue()

    # ------------------------------------------------------------------
    # Long-press * to return to the BIOS
    # ------------------------------------------------------------------

    def _halt_long_press_monitor(self) -> None:
        """Stop the long-press-* monitor (on hang-up and shutdown)."""
        self.stop_long_press_monitor.set()
        thread = self.long_press_monitor_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self.long_press_monitor_thread = None
        self.star_key_press_start = None

    def start_long_press_monitor(self):
        """Start monitoring for long-press * to return to BIOS"""
        self._halt_long_press_monitor()
        self.stop_long_press_monitor.clear()
        self.long_press_monitor_thread = threading.Thread(
            target=self._long_press_monitor_loop,
            daemon=True
        )
        self.long_press_monitor_thread.start()
        logger.debug("Started long-press monitor thread")

    def _long_press_monitor_loop(self):
        """Monitor input queue for long-press * key"""
        while not self.stop_long_press_monitor.is_set():
            try:
                # Peek at input queue (non-destructive check)
                if not self.hardware_handler.input_queue.empty():
                    # Get digit from queue
                    digit = self.hardware_handler.input_queue.get(timeout=0.1)

                    if digit == '*':
                        # Start timing
                        if self.star_key_press_start is None:
                            self.star_key_press_start = time.time()
                            logger.debug("* key pressed, monitoring for long-press")

                        # Check if held long enough (give up if stopped, e.g. hang-up)
                        while self.star_key_press_start is not None:
                            if self.stop_long_press_monitor.is_set() or self.phone_on_hook:
                                self.star_key_press_start = None
                                return
                            hold_time = time.time() - self.star_key_press_start
                            if hold_time >= self.long_press_threshold:
                                logger.info(f"* key held for {hold_time:.1f}s - returning to BIOS")
                                self.bios_requested = True
                                self.star_key_press_start = None

                                # Stop current system
                                if self.current_system:
                                    self._stop_current_system()
                                    self.end_call()

                                # Return to BIOS menu
                                self.in_bios_menu = True
                                self.start_call()
                                return

                            # Check if another key was pressed (release)
                            if not self.hardware_handler.input_queue.empty():
                                next_digit = self.hardware_handler.input_queue.get(timeout=0.1)
                                # Put both digits back for system to handle
                                self.hardware_handler.input_queue.put('*')
                                self.hardware_handler.input_queue.put(next_digit)
                                self.star_key_press_start = None
                                break

                            time.sleep(0.1)
                    else:
                        # Different key pressed, reset
                        self.star_key_press_start = None
                        # Put digit back in queue
                        self.hardware_handler.input_queue.put(digit)

                time.sleep(0.1)
            except queue.Empty:
                # Reset star key timer if queue empty
                self.star_key_press_start = None
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in long-press monitor: {e}", exc_info=True)
                time.sleep(1)

    def setup_phone_tree(self) -> PhoneTree:
        """
        Build BIOS menu phone tree.

        Returns:
            PhoneTree for BIOS menu selection
        """
        # Discover available systems
        self.system_manager.discover_systems()
        systems = self.system_manager.list_systems()

        if not systems:
            logger.warning("No phone systems discovered!")
            # Return empty menu
            return PhoneTree(
                "prompts/no_systems.mp3",
                audio_handler=self.audio_handler
            )

        # Build menu options. Installed theme packs (theme_path in .bios_config.json)
        # control the ordering; unknown ids fall back to alphabetical order.
        menu_options: dict[str, PhoneTree] = {}
        theme = load_theme(self.bios_config.get_theme_path())
        order_ids: list[str] = list(theme.get("system_order", [])) if theme else []
        priority = {system_id: index for index, system_id in enumerate(order_ids)}
        ordered_systems = sorted(
            systems,
            key=lambda system: (priority.get(system.id, len(order_ids)), system.name),
        )
        for idx, system in enumerate(ordered_systems, start=1):
            if idx > 9:
                logger.warning(f"Too many systems (max 9), skipping: {system.name}")
                break

            # Create a leaf node that launches the system
            digit = str(idx)
            menu_options[digit] = PhoneTree(
                f"bios/system_{system.id}.mp3",
                audio_handler=self.audio_handler,
                action=lambda sid=system.id: self.launch_system(sid)
            )

        # Update config with discovered systems
        self.bios_config.update_available_systems([s.to_dict() for s in ordered_systems])

        # Main BIOS menu
        main_menu = PhoneTree(
            "bios/main_menu.mp3",
            audio_handler=self.audio_handler,
            options=menu_options,
            timeout=60  # Longer timeout for BIOS menu
        )

        logger.info(f"BIOS menu created with {len(menu_options)} systems")
        return main_menu

    def _call_handler(self):
        """
        Override call handler to support both BIOS menu and launched systems.
        """
        try:
            if self.in_bios_menu:
                # Show BIOS menu
                logger.info("Starting BIOS menu navigation")
                main_menu = self.setup_phone_tree()
                # Stop navigating the BIOS menu as soon as a system is launched,
                # otherwise this loop keeps consuming keypresses from the shared
                # input queue alongside the launched system.
                main_menu.navigate(
                    self.hardware_handler.input_queue,
                    lambda: not self.phone_on_hook and self.running and self.in_bios_menu,
                    main_menu
                )
            elif self.current_system:
                # Delegate to current system
                logger.info(f"Starting system: {self.current_system_id}")
                self.current_system._call_handler()
            else:
                logger.error("No system to run and not in BIOS menu")

        except Exception as e:
            logger.error(f"Error in call handler: {e}", exc_info=True)
        finally:
            logger.info("Call handler ended")

    def shutdown(self):
        """Shutdown BIOS and any running systems"""
        logger.info("Shutting down BIOS bootloader...")

        # Stop long-press monitor
        self._halt_long_press_monitor()

        # Stop current system
        self._stop_current_system()

        # Call parent shutdown
        super().shutdown()

        logger.info("BIOS shutdown complete")
