#!/usr/bin/env python3
import logging
import signal
import sys
import queue
import threading
import time
import pygame
from .hardware.serial_handler import SerialHandler
from .hardware.gpio_handler import GPIOHandler
from .phone_system.phone_tree import PhoneTree
from .audio.handler import AudioHandler
from .config.settings import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PayphoneSystem:
    def __init__(self):
        self.config = Config()
        self.audio_handler = AudioHandler(self.config.AUDIO_DIR)
        self.phone_on_hook = True
        self.running = True
        self.current_call = None
        
        # Initialize hardware handler based on config
        if self.config.USE_GPIO:
            logger.info("Using GPIO mode (direct Raspberry Pi connection)")
            self.hardware_handler = GPIOHandler(
                keypad_rows=self.config.KEYPAD_ROW_PINS,
                keypad_cols=self.config.KEYPAD_COL_PINS,
                hook_pin=self.config.HOOK_SWITCH_PIN
            )
        else:
            logger.info("Using Serial mode (Arduino connection)")
            self.hardware_handler = SerialHandler(
                port=self.config.SERIAL_PORT,
                baudrate=self.config.BAUDRATE
            )
        
    def setup_phone_tree(self) -> PhoneTree:
        """Build the phone menu tree"""
        # Leaf nodes
        weather = PhoneTree("menu/weather_info.mp3")
        time_info = PhoneTree("menu/time_info.mp3")
        
        # Branch nodes
        info_menu = PhoneTree(
            "menu/info_menu.mp3",
            options={
                "1": weather,
                "2": time_info
            }
        )
        
        # Root menu
        main_menu = PhoneTree(
            "menu/main_menu.mp3",
            options={
                "1": info_menu,
                "2": PhoneTree("menu/jokes.mp3"),
                "3": PhoneTree("menu/music.mp3")
            }
        )
        
        return main_menu
        
    def hook_status_changed(self, off_hook: bool):
        """Handle hook switch changes"""
        self.phone_on_hook = not off_hook
        
        if off_hook:
            logger.info("Phone picked up")
            self.start_call()
        else:
            logger.info("Phone hung up")
            self.end_call()
            
    def start_call(self):
        """Start a new call session"""
        self.audio_handler.play_file("prompts/dial_tone.mp3", blocking=False)
        time.sleep(1)
        self.audio_handler.stop()
        
        # Start navigation in new thread
        self.current_call = threading.Thread(
            target=self._call_handler
        )
        self.current_call.start()
        
    def _call_handler(self):
        """Handle the call navigation"""
        main_menu = self.setup_phone_tree()
        main_menu.navigate(
            self.hardware_handler.input_queue,
            lambda: not self.phone_on_hook,
            main_menu
        )
        
    def end_call(self):
        """End current call"""
        self.audio_handler.stop()
        # Clear input queue
        while not self.hardware_handler.input_queue.empty():
            self.hardware_handler.input_queue.get()
            
    def run(self):
        """Main application loop"""
        # Setup hardware communication
        self.hardware_handler.set_hook_callback(self.hook_status_changed)
        if not self.hardware_handler.start():
            logger.error("Failed to start hardware communication")
            return
            
        logger.info("Payphone system started")
        
        # Keep running until interrupted
        try:
            while self.running:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            self.shutdown()
            
    def shutdown(self):
        """Cleanup and shutdown"""
        logger.info("Shutting down...")
        self.running = False
        self.hardware_handler.stop()
        pygame.quit()
        
def main():
    system = PayphoneSystem()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, lambda *args: system.shutdown())
    signal.signal(signal.SIGTERM, lambda *args: system.shutdown())
    
    system.run()

if __name__ == "__main__":
    main()