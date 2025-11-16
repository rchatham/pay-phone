import threading
import queue
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Conditional import for pyserial (only available when installed)
try:
    import serial
    _SERIAL_AVAILABLE = True
except ImportError:
    _SERIAL_AVAILABLE = False
    serial = None
    logger.debug("pyserial not available - Serial functionality disabled")

class SerialHandler:
    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 9600):
        if not _SERIAL_AVAILABLE:
            raise RuntimeError(
                "pyserial is not available. Serial functionality requires installing pyserial. "
                "Install with: pip install pyserial"
            )

        self.port = port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        self.input_queue = queue.Queue()
        self.running = False
        self.hook_callback: Optional[Callable] = None
        
    def connect(self) -> bool:
        """Establish serial connection with Arduino"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            logger.info(f"Connected to Arduino on {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect: {e}")
            return False
            
    def start(self):
        """Start reading from serial port"""
        if not self.serial:
            if not self.connect():
                return False
                
        self.running = True
        thread = threading.Thread(target=self._read_loop)
        thread.daemon = True
        thread.start()
        return True
        
    def _read_loop(self):
        """Main loop for reading serial data"""
        while self.running:
            try:
                if self.serial.in_waiting:
                    data = self.serial.readline().decode().strip()
                    self._process_data(data)
            except Exception as e:
                logger.error(f"Serial read error: {e}")
                
    def _process_data(self, data: str):
        """Process incoming serial data"""
        if data.startswith("KEY:"):
            key = data.split(":")[1]
            self.input_queue.put(key)
            logger.debug(f"Keypad: {key}")
        elif data.startswith("HOOK:"):
            status = data.split(":")[1]
            if self.hook_callback:
                self.hook_callback(status == "ON")
        elif data == "READY":
            logger.info("Arduino ready")
            
    def set_hook_callback(self, callback: Callable):
        """Set callback for hook switch changes"""
        self.hook_callback = callback
        
    def stop(self):
        """Stop serial communication"""
        self.running = False
        if self.serial:
            self.serial.close()