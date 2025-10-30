import RPi.GPIO as GPIO
import time
import queue
import threading
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class GPIOKeypad:
    """Handle matrix keypad (3x3 or 4x3) using Raspberry Pi GPIO pins"""
    
    def __init__(self, row_pins: List[int], col_pins: List[int], input_queue: queue.Queue):
        self.row_pins = row_pins
        self.col_pins = col_pins
        self.input_queue = input_queue
        self.running = False
        
        # Keypad matrix mapping
        # NOTE: Configured for rows 1-3 only (row 0 not connected)
        # If you have 4 rows, use: [['1','2','3'],['4','5','6'],['7','8','9'],['*','0','#']]
        # If you have 3 rows (current), use: [['4','5','6'],['7','8','9'],['*','0','#']]
        if len(self.row_pins) == 4:
            self.keys = [
                ['1', '2', '3'],
                ['4', '5', '6'],
                ['7', '8', '9'],
                ['*', '0', '#']
            ]
        elif len(self.row_pins) == 3:
            self.keys = [
                ['4', '5', '6'],
                ['7', '8', '9'],
                ['*', '0', '#']
            ]
        else:
            raise ValueError(f"Keypad must have 3 or 4 rows, got {len(self.row_pins)}")
        
        # Debounce settings
        self.debounce_time = 0.3
        self.last_key_time = 0
        
    def setup(self):
        """Initialize GPIO pins for keypad"""
        GPIO.setmode(GPIO.BCM)
        
        # Setup row pins as outputs (initially high)
        for pin in self.row_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
            
        # Setup column pins as inputs with pull-up resistors
        for pin in self.col_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
        logger.info(f"Keypad GPIO initialized - Rows: {self.row_pins}, Cols: {self.col_pins}")
        
    def scan_keypad(self) -> Optional[str]:
        """Scan the keypad matrix and return pressed key"""
        key = None
        
        # Scan each row
        for row_num, row_pin in enumerate(self.row_pins):
            # Set current row LOW
            GPIO.output(row_pin, GPIO.LOW)
            
            # Check each column
            for col_num, col_pin in enumerate(self.col_pins):
                if GPIO.input(col_pin) == GPIO.LOW:
                    # Key is pressed
                    key = self.keys[row_num][col_num]
                    
            # Set row back to HIGH
            GPIO.output(row_pin, GPIO.HIGH)
            
        return key
        
    def start(self):
        """Start scanning the keypad"""
        self.running = True
        thread = threading.Thread(target=self._scan_loop)
        thread.daemon = True
        thread.start()
        logger.info("Keypad scanning started")
        
    def _scan_loop(self):
        """Main scanning loop"""
        last_key = None
        
        while self.running:
            key = self.scan_keypad()
            
            if key and key != last_key:
                # New key pressed
                current_time = time.time()
                if current_time - self.last_key_time > self.debounce_time:
                    self.input_queue.put(key)
                    logger.debug(f"Key pressed: {key}")
                    self.last_key_time = current_time
                    
            last_key = key
            time.sleep(0.01)  # Small delay to prevent CPU overload
            
    def stop(self):
        """Stop scanning and cleanup"""
        self.running = False
        time.sleep(0.1)
        GPIO.cleanup(self.row_pins + self.col_pins)