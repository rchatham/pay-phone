import RPi.GPIO as GPIO
import queue
import logging
from typing import Callable, Optional, List
from .gpio_keypad import GPIOKeypad
from .gpio_hook import GPIOHookSwitch

logger = logging.getLogger(__name__)

class GPIOHandler:
    """Main GPIO handler for direct Raspberry Pi connection"""
    
    def __init__(self, 
                 keypad_rows: List[int],
                 keypad_cols: List[int],
                 hook_pin: int):
        """
        Initialize GPIO handler
        
        Args:
            keypad_rows: List of GPIO pins for keypad rows
            keypad_cols: List of GPIO pins for keypad columns
            hook_pin: GPIO pin for hook switch
        """
        self.input_queue = queue.Queue()
        
        # Initialize components
        self.keypad = GPIOKeypad(keypad_rows, keypad_cols, self.input_queue)
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
        
        # Stop components
        self.keypad.stop()
        self.hook_switch.cleanup()
        
        # Final cleanup
        GPIO.cleanup()
        logger.info("GPIO handler stopped")