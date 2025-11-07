import pygame
import os
import logging
import subprocess
import signal
from typing import Optional
import threading

logger = logging.getLogger(__name__)

class AudioHandler:
    def __init__(self, audio_dir: str = "audio_files"):
        self.audio_dir = audio_dir

        # Set SDL audio device to USB audio (use plughw for format conversion)
        os.environ['SDL_AUDIODRIVER'] = 'alsa'
        os.environ['AUDIODEV'] = 'plughw:CARD=Set,DEV=0'

        self._init_audio()
        self.current_playback = None

    def _init_audio(self, max_retries: int = 3):
        """Initialize audio with automatic cleanup of busy devices"""
        for attempt in range(max_retries):
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                logger.info("Audio device initialized successfully")
                return
            except pygame.error as e:
                error_msg = str(e)
                if "Device or resource busy" in error_msg or "Couldn't open audio device" in error_msg:
                    logger.warning(f"Audio device is busy (attempt {attempt + 1}/{max_retries})")

                    if attempt < max_retries - 1:
                        # Try to find and kill the process using the audio device
                        if self._cleanup_audio_device():
                            logger.info("Retrying audio initialization...")
                            continue
                        else:
                            # Ask user interactively
                            print("\n" + "="*60)
                            print("AUDIO DEVICE BUSY")
                            print("="*60)
                            print(f"\nThe audio device is being used by another process.")
                            print("This usually happens when a previous payphone instance didn't exit cleanly.")

                            response = input("\nWould you like to kill the blocking process? (y/n): ").strip().lower()
                            if response == 'y':
                                if self._force_cleanup_audio():
                                    print("✓ Process killed. Retrying audio initialization...")
                                    continue
                                else:
                                    print("✗ Failed to kill blocking process")
                            else:
                                print("Exiting. Please manually kill the blocking process and try again.")
                                print("Hint: Run 'pkill -9 python3' to kill all Python processes")
                                raise
                    else:
                        logger.error(f"Failed to initialize audio after {max_retries} attempts")
                        raise
                else:
                    logger.error(f"Audio initialization error: {e}")
                    raise

    def _cleanup_audio_device(self) -> bool:
        """Try to automatically cleanup audio device by killing blocking processes"""
        try:
            # Find processes using the audio device
            result = subprocess.run(
                ['fuser', '/dev/snd/pcmC1D0p'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split()
                logger.info(f"Found processes using audio device: {pids}")

                # Kill the processes
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                        logger.info(f"Killed process {pid}")
                    except ProcessLookupError:
                        pass  # Process already gone
                    except Exception as e:
                        logger.warning(f"Failed to kill process {pid}: {e}")

                import time
                time.sleep(1)  # Give the system time to release the device
                return True
        except FileNotFoundError:
            logger.debug("fuser command not available")
        except Exception as e:
            logger.warning(f"Failed to cleanup audio device: {e}")

        return False

    def _force_cleanup_audio(self) -> bool:
        """Force cleanup by killing all python3 processes except ourselves"""
        try:
            # Get our own PID
            our_pid = os.getpid()
            logger.info(f"Current process PID: {our_pid}")

            # Get all python3 processes
            result = subprocess.run(
                ['pgrep', 'python3'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                killed_any = False

                logger.info(f"Found Python processes: {pids}")

                for pid_str in pids:
                    try:
                        pid = int(pid_str)

                        # Safety check: Never kill ourselves
                        if pid == our_pid:
                            logger.debug(f"Skipping PID {pid} (current process)")
                            continue

                        # Double-check: Verify PID is different from us
                        if os.getpid() == pid:
                            logger.warning(f"Safety check: PID {pid} matches current process, skipping")
                            continue

                        logger.info(f"Killing Python process {pid}")
                        os.kill(pid, signal.SIGKILL)
                        killed_any = True

                    except (ValueError, ProcessLookupError):
                        pass
                    except PermissionError as e:
                        logger.warning(f"No permission to kill process {pid}: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to kill process {pid}: {e}")

                if killed_any:
                    logger.info("Waiting for audio device to be released...")
                    import time
                    time.sleep(1)  # Give the system time to release the device
                    return True
                else:
                    logger.warning("No processes were killed")
        except Exception as e:
            logger.warning(f"Failed to force cleanup: {e}")

        return False
        
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