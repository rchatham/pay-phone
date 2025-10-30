import pygame
import os
import logging
from typing import Optional
import threading

logger = logging.getLogger(__name__)

class AudioHandler:
    def __init__(self, audio_dir: str = "audio_files"):
        self.audio_dir = audio_dir
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        self.current_playback = None
        
    def play_file(self, filename: str, blocking: bool = True) -> bool:
        """Play an audio file"""
        filepath = os.path.join(self.audio_dir, filename)
        if not os.path.exists(filepath):
            logger.error(f"Audio file not found: {filepath}")
            return False
            
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            if blocking:
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
            return True
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            return False
            
    def stop(self):
        """Stop current playback"""
        pygame.mixer.music.stop()
        
    def record_audio(self, duration: int, filename: str) -> bool:
        """Record audio from microphone"""
        try:
            cmd = f"arecord -d {duration} -f cd {filename}"
            os.system(cmd)
            return True
        except Exception as e:
            logger.error(f"Recording error: {e}")
            return False