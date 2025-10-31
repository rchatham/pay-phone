import queue
import time
import logging
from typing import Dict, Optional, Callable
from ..audio.handler import AudioHandler

logger = logging.getLogger(__name__)

class PhoneTree:
    def __init__(self,
                 audio_file: str,
                 options: Optional[Dict[str, 'PhoneTree']] = None,
                 action: Optional[Callable] = None,
                 timeout: int = 30,
                 audio_handler=None):
        self.audio_file = audio_file
        self.options = options or {}
        self.action = action
        self.timeout = timeout
        self.audio_handler = audio_handler if audio_handler is not None else AudioHandler()
        
    def navigate(self, 
                 input_queue: queue.Queue,
                 hook_status: Callable,
                 main_menu: Optional['PhoneTree'] = None) -> None:
        """Navigate through the phone tree"""
        
        # Check if phone is still off hook
        if not hook_status():
            logger.info("Phone hung up")
            return
            
        # Play audio prompt
        self.audio_handler.play_file(self.audio_file)
        
        # Execute action if present
        if self.action:
            continue_nav = self.action()
            if not continue_nav:
                if main_menu:
                    main_menu.navigate(input_queue, hook_status, main_menu)
                return
                
        # If no options, return to main menu
        if not self.options:
            if main_menu:
                time.sleep(2)
                main_menu.navigate(input_queue, hook_status, main_menu)
            return
            
        # Wait for input
        start_time = time.time()
        
        while hook_status():  # Continue while phone is off hook
            if time.time() - start_time > self.timeout:
                logger.info("Timeout reached")
                self.audio_handler.play_file("prompts/timeout.mp3")
                if main_menu:
                    main_menu.navigate(input_queue, hook_status, main_menu)
                return
                
            try:
                choice = input_queue.get(timeout=0.5)
                
                if choice in self.options:
                    self.options[choice].navigate(input_queue, hook_status, main_menu)
                    return
                else:
                    self.audio_handler.play_file("prompts/invalid_option.mp3")
                    self.audio_handler.play_file(self.audio_file)
                    start_time = time.time()  # Reset timeout
                    
            except queue.Empty:
                continue