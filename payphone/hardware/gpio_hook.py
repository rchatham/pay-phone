import RPi.GPIO as GPIO
import time
import threading
import logging
from typing import Callable, Optional, Union, List

logger = logging.getLogger(__name__)

class GPIOHookSwitch:
    """
    Handle hook switch using Raspberry Pi GPIO pins.

    Supports two configurations:
    1. Single pin mode: One GPIO pin with other side connected to GND
    2. Two pin mode: Two GPIO pins that connect/disconnect (no GND connection)
    """

    def __init__(self, hook_pin: Union[int, List[int]], callback: Optional[Callable] = None):
        # Support both single pin (int) and dual pin (list) configurations
        if isinstance(hook_pin, list):
            if len(hook_pin) != 2:
                raise ValueError(f"Hook switch requires 1 or 2 pins, got {len(hook_pin)}")
            self.hook_pins = hook_pin
            self.mode = '2pin'
        else:
            self.hook_pins = [hook_pin]
            self.mode = '1pin'

        self.callback = callback
        self.running = False
        self.last_state = None

        # Debounce settings
        self.debounce_time = 0.1

        logger.info(f"Hook switch initialized in {self.mode} mode with pins {self.hook_pins}")
        
    def setup(self):
        """Initialize GPIO pins for hook switch"""
        GPIO.setmode(GPIO.BCM)

        if self.mode == '1pin':
            # Single pin mode: pin connected to GND via hook switch
            # Setup hook pin as input with pull-up resistor
            # Hook switch connects pin to ground when handset is lifted
            pin = self.hook_pins[0]
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Setup interrupt-based detection
            GPIO.add_event_detect(
                pin,
                GPIO.BOTH,
                callback=self._hook_changed,
                bouncetime=int(self.debounce_time * 1000)
            )

            # Get initial state
            self.last_state = GPIO.input(pin)
            logger.info(f"Hook switch GPIO initialized (1-pin mode) on pin {pin}")

        else:  # 2pin mode
            # Two pin mode: two GPIO pins that connect/disconnect
            # Pin 0 is OUTPUT (driven HIGH), Pin 1 is INPUT (pull-down)
            # When connected, Pin 1 reads HIGH; when disconnected, reads LOW
            output_pin = self.hook_pins[0]
            input_pin = self.hook_pins[1]

            GPIO.setup(output_pin, GPIO.OUT)
            GPIO.output(output_pin, GPIO.HIGH)  # Always drive HIGH

            GPIO.setup(input_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            # Setup interrupt on input pin
            GPIO.add_event_detect(
                input_pin,
                GPIO.BOTH,
                callback=self._hook_changed,
                bouncetime=int(self.debounce_time * 1000)
            )

            # Get initial state
            self.last_state = GPIO.input(input_pin)
            logger.info(f"Hook switch GPIO initialized (2-pin mode) on pins {self.hook_pins}")
        
    def _hook_changed(self, channel):
        """Handle hook switch state change"""
        if self.mode == '1pin':
            # Read the single pin
            current_state = GPIO.input(self.hook_pins[0])
            # LOW = handset lifted (off hook), HIGH = on hook
            off_hook = (current_state == GPIO.LOW)
        else:  # 2pin mode
            # Read the input pin (pin 1)
            current_state = GPIO.input(self.hook_pins[1])
            # HIGH = connected (off hook), LOW = disconnected (on hook)
            off_hook = (current_state == GPIO.HIGH)

        if current_state != self.last_state:
            self.last_state = current_state

            logger.info(f"Hook switch changed: {'OFF HOOK' if off_hook else 'ON HOOK'}")

            if self.callback:
                # Run callback in separate thread to avoid blocking
                threading.Thread(
                    target=self.callback,
                    args=(off_hook,)
                ).start()

    def get_state(self) -> bool:
        """Get current hook state (True = off hook, False = on hook)"""
        if self.mode == '1pin':
            # LOW = off hook
            return GPIO.input(self.hook_pins[0]) == GPIO.LOW
        else:  # 2pin mode
            # HIGH = off hook (pins connected)
            return GPIO.input(self.hook_pins[1]) == GPIO.HIGH
        
    def set_callback(self, callback: Callable):
        """Set or update the callback function"""
        self.callback = callback
        
    def cleanup(self):
        """Cleanup GPIO resources"""
        if self.mode == '1pin':
            GPIO.remove_event_detect(self.hook_pins[0])
            GPIO.cleanup(self.hook_pins[0])
        else:  # 2pin mode
            GPIO.remove_event_detect(self.hook_pins[1])
            GPIO.cleanup(self.hook_pins)