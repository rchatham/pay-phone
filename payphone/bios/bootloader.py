"""
BIOS Bootloader system for payphone.

Provides system selection menu, configuration, and hot-reloading capabilities.
Supports:
- Hold hook for 3 seconds on boot to enter BIOS menu
- Long-press * for 5 seconds during system operation to return to BIOS
- Auto-launch last selected system
- Dynamic discovery and loading of phone systems
"""

import logging
import queue
import threading
import time
from typing import Optional

from ..audio.handler import AudioHandler
from ..config.settings import Config
from ..core.phone_tree import PhoneTree
from ..core.system import PhoneSystemBase
from .config_manager import ConfigManager
from .system_manager import SystemManager, SystemInfo

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

            # Record pickup time for hold detection
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

            # Stop any running call/system
            if self.current_call and self.current_call.is_alive():
                self.end_call()

            # Stop current system if running
            if self.current_system:
                logger.info("Stopping current system due to hang-up")
                self.current_system.running = False
                self.current_system = None

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

    def launch_system(self, system_id: str) -> bool:
        """
        Launch a phone system by ID.

        Args:
            system_id: System identifier

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

        # Instantiate the system
        try:
            self.current_system = system_class(self.config)
            self.current_system_id = system_id
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

    def start_long_press_monitor(self):
        """Start monitoring for long-press * to return to BIOS"""
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

                        # Check if held long enough
                        while self.star_key_press_start is not None:
                            hold_time = time.time() - self.star_key_press_start
                            if hold_time >= self.long_press_threshold:
                                logger.info(f"* key held for {hold_time:.1f}s - returning to BIOS")
                                self.bios_requested = True
                                self.star_key_press_start = None

                                # Stop current system
                                if self.current_system:
                                    self.current_system.running = False
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

        # Build menu options
        menu_options = {}
        for idx, system in enumerate(systems, start=1):
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
        self.bios_config.update_available_systems([s.to_dict() for s in systems])

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
                main_menu.navigate(
                    self.hardware_handler.input_queue,
                    lambda: not self.phone_on_hook and self.running,
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
        if self.long_press_monitor_thread:
            self.stop_long_press_monitor.set()
            self.long_press_monitor_thread.join(timeout=2)

        # Stop current system
        if self.current_system:
            self.current_system.running = False
            self.current_system = None

        # Call parent shutdown
        super().shutdown()

        logger.info("BIOS shutdown complete")
