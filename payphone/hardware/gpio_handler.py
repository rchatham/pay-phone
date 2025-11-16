import queue
import logging
from typing import Callable, Optional, List

logger = logging.getLogger(__name__)

# Conditional import for RPi.GPIO (only available on Raspberry Pi)
try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    # RuntimeError can occur if GPIO is installed but not on a Pi
    _GPIO_AVAILABLE = False
    GPIO = None
    logger.debug("RPi.GPIO not available - GPIO functionality disabled")

# Only import GPIO-dependent modules if GPIO is available
if _GPIO_AVAILABLE:
    from .gpio_keypad import GPIOKeypad
    from .gpio_hook import GPIOHookSwitch


class GPIOHandler:
    """Main GPIO handler for direct Raspberry Pi connection"""

    def __init__(self,
                 keypad_rows: List[int],
                 keypad_cols: List[int],
                 hook_pin: int,
                 audio_handler=None):
        """
        Initialize GPIO handler

        Args:
            keypad_rows: List of GPIO pins for keypad rows
            keypad_cols: List of GPIO pins for keypad columns
            hook_pin: GPIO pin for hook switch
            audio_handler: Optional AudioHandler for DTMF tones
        """
        if not _GPIO_AVAILABLE:
            raise RuntimeError(
                "RPi.GPIO is not available. GPIO functionality requires running on a Raspberry Pi "
                "with RPi.GPIO installed. For development/testing on other platforms, use Serial mode."
            )

        self.input_queue = queue.Queue()

        # Initialize components (pass audio_handler to keypad for DTMF tones)
        self.keypad = GPIOKeypad(keypad_rows, keypad_cols, self.input_queue, audio_handler)
        self.hook_switch = GPIOHookSwitch(hook_pin)

        self.running = False

    def connect(self) -> bool:
        """Initialize GPIO connections"""
        try:
            # Set GPIO mode (will be set by first component)
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Setup components
            self.keypad.setup()
            self.hook_switch.setup()

            logger.info("GPIO connections established")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")
            return False

    def start(self) -> bool:
        """Start all GPIO monitoring"""
        if not self.connect():
            return False

        self.running = True
        self.keypad.start()

        logger.info("GPIO handler started")
        return True

    def set_hook_callback(self, callback: Callable):
        """Set callback for hook switch changes"""
        self.hook_switch.set_callback(callback)

    def stop(self):
        """Stop all GPIO monitoring and cleanup"""
        self.running = False

        # Stop components (they clean up their own GPIO pins)
        self.keypad.stop()
        self.hook_switch.cleanup()

        logger.info("GPIO handler stopped")
