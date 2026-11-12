"""Audio playback without process-killing device recovery or shell commands."""
import io
import logging
import os
import subprocess
import sys
from importlib import resources

import pygame

logger = logging.getLogger(__name__)


class AudioHandler:
    def __init__(self, audio_dir: str = "audio_files"):
        self.audio_dir = audio_dir
        if sys.platform.startswith("linux"):
            os.environ.setdefault("SDL_AUDIODRIVER", "alsa")
            os.environ.setdefault("AUDIODEV", "plughw:CARD=Set,DEV=0")
        self._init_audio()
        self.current_playback = None

    def _init_audio(self, max_retries: int = 3) -> None:
        # Busy hardware is an operator error. Never kill unrelated processes.
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except pygame.error:
            logger.exception("Could not initialize audio; check the selected SDL device and other audio users")
            raise

    def play_file(self, filename: str, blocking: bool = True) -> bool:
        filepath = os.path.join(self.audio_dir, filename)
        if not os.path.isfile(filepath):
            logger.error("Audio file not found: %s", filepath)
            return False
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            if blocking:
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(20)
            return True
        except (pygame.error, OSError) as exc:
            logger.error("Audio playback failed: %s", exc)
            return False

    def stop(self) -> None:
        pygame.mixer.music.stop()
        pygame.mixer.stop()

    def is_playing(self) -> bool:
        try:
            return pygame.mixer.music.get_busy()
        except pygame.error as exc:
            logger.error("Could not inspect audio playback: %s", exc)
            return False

    def play_dtmf_tone(self, key: str) -> bool:
        names = {str(i): f"{i}.wav" for i in range(10)}
        names.update({"*": "star.wav", "#": "pound.wav"})
        if key not in names:
            return False
        custom = os.path.join(self.audio_dir, "dtmf", names[key])
        try:
            if os.path.isfile(custom):
                sound = pygame.mixer.Sound(custom)
            else:
                bundled = resources.files("payphone").joinpath("audio_files", "dtmf", names[key])
                sound = pygame.mixer.Sound(io.BytesIO(bundled.read_bytes()))
            sound.play()
            return True
        except (pygame.error, OSError) as exc:
            # No keypad digits in logs, including dependency/debug diagnostics.
            logger.error("DTMF playback failed: %s", type(exc).__name__)
            return False

    def record_audio(self, duration: int, filename: str) -> bool:
        """Legacy helper; new plugins should use payphone.audio.recording."""
        if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 3600:
            raise ValueError("Recording duration must be 1 to 3600 seconds")
        try:
            subprocess.run(["arecord", "-d", str(duration), "-f", "cd", "--", filename], check=True, timeout=duration + 5)
            return True
        except (OSError, subprocess.SubprocessError) as exc:
            logger.error("Audio recording failed: %s", exc)
            return False
