"""Offline, bounded eSpeak synthesis through the runtime's existing audio device."""
import logging
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class OfflineSpeech:
    def __init__(self, runtime):
        self.runtime = runtime
        self.executable = shutil.which("espeak-ng") or shutil.which("espeak")
        self._lock = threading.RLock()
        self._worker = None
        self._process = None
        self._cancel = threading.Event()
        if not self.executable:
            logger.error("Offline speech unavailable: install espeak-ng (apt install espeak-ng or brew install espeak-ng)")

    def say(self, text: str, session, blocking: bool = True) -> None:
        if not self.runtime.is_active(session):
            return
        if not isinstance(text, str) or not text or len(text) > 8192:
            raise ValueError("Speech text must contain 1 to 8192 characters")
        if not self.executable:
            raise RuntimeError("Offline speech requires espeak-ng; see docs/BIOS_ADMIN.md")
        self.stop_speech()
        with self._lock:
            if self._worker and self._worker.is_alive():
                raise RuntimeError("Previous speech worker did not exit")
            self._cancel = threading.Event()
            worker = threading.Thread(target=self._speak, args=(text, session, self._cancel), name="payphone-speech", daemon=True)
            self._worker = worker
            worker.start()
        if blocking:
            worker.join()

    def _speak(self, text: str, session, cancelled: threading.Event) -> None:
        try:
            with tempfile.TemporaryDirectory(prefix="payphone-speech-") as directory:
                wave = Path(directory) / "speech.wav"
                with self._lock:
                    if cancelled.is_set() or not self.runtime.is_active(session):
                        return
                    process = subprocess.Popen(
                        [self.executable, "-w", str(wave), "--stdin"],
                        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    self._process = process
                try:
                    process.communicate(input=text.encode("utf-8"), timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                    raise RuntimeError("Offline speech synthesis timed out")
                finally:
                    with self._lock:
                        if self._process is process:
                            self._process = None
                if cancelled.is_set() or not self.runtime.is_active(session):
                    return
                if process.returncode != 0 or not wave.exists():
                    raise RuntimeError("Offline speech synthesis failed")
                with self.runtime.media_lock:
                    if cancelled.is_set() or not self.runtime.is_active(session):
                        return
                    if not self.runtime.audio.play_file(str(wave), blocking=False):
                        raise RuntimeError("Offline speech audio playback failed")
                while not cancelled.is_set() and self.runtime.is_active(session) and self.runtime.audio.is_playing():
                    cancelled.wait(0.05)
        except Exception:
            logger.exception("Offline speech failed")

    def stop_speech(self) -> None:
        with self._lock:
            self._cancel.set()
            process = self._process
            worker = self._worker
            if process and process.poll() is None:
                process.terminate()
        with self.runtime.media_lock:
            self.runtime.audio.stop()
        if process:
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=0.5)
        if worker and worker is not threading.current_thread():
            worker.join(timeout=1)
            if worker.is_alive():
                logger.error("Speech worker did not exit; refusing overlapping speech")

    def is_speaking(self) -> bool:
        with self._lock:
            return bool(self._worker and self._worker.is_alive())
