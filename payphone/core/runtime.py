"""One hardware owner, one raw-input reader, and one cancellable session at a time."""
import contextvars
import logging
import queue
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)
_shared_runtime = contextvars.ContextVar("payphone_runtime", default=None)


@contextmanager
def shared_runtime(runtime):
    """Inject the runtime without changing existing plugin (config) constructors."""
    token = _shared_runtime.set(runtime)
    try:
        yield
    finally:
        _shared_runtime.reset(token)


def construction_runtime():
    return _shared_runtime.get()


@dataclass
class CallSession:
    cancelled: threading.Event = field(default_factory=threading.Event)
    input_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=256))
    last_activity: float = field(default_factory=time.monotonic)
    reason: Optional[str] = None
    suppress_tones: bool = False
    authorization_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    admin_session: object = field(default=None, repr=False)

    def cancel(self, reason: str) -> None:
        with self.authorization_lock:
            self.reason = reason
            self.cancelled.set()


@dataclass(frozen=True)
class RawKeyEvent:
    key: str = field(repr=False)
    session: Optional[CallSession] = field(repr=False)


class RuntimeInputQueue(queue.Queue):
    """Stamp at enqueue, not dequeue: old hardware backlog cannot cross calls."""
    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime

    def put(self, key: str, block: bool = True, timeout: Optional[float] = None) -> None:
        with self.runtime._lock:
            event = RawKeyEvent(key, self.runtime.session)
            super().put(event, block=block, timeout=timeout)


class SessionHardware:
    """Expose only a session's filtered queue to a plugin."""
    def __init__(self, session: CallSession):
        self.input_queue = session.input_queue


class SessionAudio:
    """Prevent a cancelled plugin action from starting later playback."""
    def __init__(self, runtime, session: CallSession):
        self.runtime = runtime
        self.session = session

    def play_file(self, filename: str, blocking: bool = True) -> bool:
        with self.runtime.media_lock:
            if not self.runtime.is_active(self.session):
                return False
            played = self.runtime.audio.play_file(filename, blocking=False)
        if blocking and played:
            while self.runtime.is_active(self.session) and self.runtime.audio.is_playing():
                self.session.cancelled.wait(0.05)
        return played

    def play_dtmf_tone(self, key: str) -> bool:
        with self.runtime.media_lock:
            if not self.runtime.is_active(self.session) or self.session.suppress_tones:
                return False
            return self.runtime.audio.play_dtmf_tone(key)

    def stop(self) -> None:
        with self.runtime.media_lock:
            self.runtime.audio.stop()

    def is_playing(self) -> bool:
        return self.runtime.is_active(self.session) and self.runtime.audio.is_playing()

    @property
    def audio_dir(self):
        return self.runtime.audio.audio_dir


class PhoneRuntime:
    def __init__(self, hardware, audio, escape_sequence: str = "***#", escape_timeout: float = 1.0):
        self.hardware = hardware
        self.audio = audio
        self.escape_sequence = escape_sequence
        self.escape_timeout = escape_timeout
        self._lock = threading.RLock()
        self._off_hook = False
        self.session: Optional[CallSession] = None
        # Hardware has not started yet. Bind both GPIO's producer and the exposed
        # raw queue to the same generation-stamped queue before monitoring begins.
        hardware.input_queue = RuntimeInputQueue(self)
        if getattr(hardware, "keypad", None) is not None:
            hardware.keypad.input_queue = hardware.input_queue
        self.speech = None
        self.media_lock = threading.RLock()
        self._stop = threading.Event()
        self._dispatcher = None
        self._prefix = ""
        self._prefix_time = 0.0
        self.on_escape = None

    @property
    def off_hook(self) -> bool:
        return self._off_hook

    @off_hook.setter
    def off_hook(self, value: bool) -> None:
        # Hook state participates in the same boundary as cancellation and saves.
        with self._lock:
            self._off_hook = value

    def start_dispatcher(self) -> None:
        with self._lock:
            if self._dispatcher and self._dispatcher.is_alive():
                return
            self._stop.clear()
            self._dispatcher = threading.Thread(target=self._dispatch_loop, name="payphone-input", daemon=True)
            self._dispatcher.start()

    def new_session(self) -> CallSession:
        with self._lock:
            if self.session and not self.session.cancelled.is_set():
                raise RuntimeError("Previous call session is still active")
            self._prefix = ""
            self.session = CallSession(authorization_lock=self._lock)
            return self.session

    def is_active(self, session: CallSession) -> bool:
        return self.session is session and self.off_hook and not session.cancelled.is_set() and not self._stop.is_set()

    def cancel(self, reason: str) -> None:
        with self._lock:
            if self.session:
                self.session.cancel(reason)
            self._prefix = ""
            # Keep new_session behind cleanup. Speech workers do not acquire _lock.
            if self.speech:
                self.speech.stop_speech()
            with self.media_lock:
                self.audio.stop()

    def _deliver(self, keys: str) -> None:
        session = self.session
        if not session or not self.is_active(session):
            return
        for key in keys:
            try:
                # Feedback must precede delivery: consuming PIN's final # can
                # immediately restore normal tones on the navigation thread.
                if not session.suppress_tones:
                    SessionAudio(self, session).play_dtmf_tone(key)
                session.input_queue.put_nowait(key)
            except queue.Full:
                logger.error("Session input overflow; cancelling call")
                self.cancel("input overflow")
                return

    def route_key(self, key: str, now: Optional[float] = None) -> None:
        """Match escape prefixes without stealing/requeueing application input."""
        now = time.monotonic() if now is None else now
        escaped = False
        with self._lock:
            if not self.session or not self.is_active(self.session):
                return
            if len(key) != 1 or key not in "0123456789*#":
                return
            capability = self.session.admin_session
            if capability:
                try:
                    capability.note_activity(now)
                except PermissionError:
                    self.cancel("admin exit")
                    return
            else:
                self.session.last_activity = now
            self.flush_prefix(now)
            self._prefix += key
            self._prefix_time = now
            while self._prefix and not self.escape_sequence.startswith(self._prefix):
                self._deliver(self._prefix[0])
                self._prefix = self._prefix[1:]
            if self._prefix == self.escape_sequence:
                self._prefix = ""
                escaped = True
        if escaped:
            self.cancel("escape")
            if self.on_escape:
                self.on_escape()

    def flush_prefix(self, now: Optional[float] = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            if self._prefix and now - self._prefix_time >= self.escape_timeout:
                self._deliver(self._prefix)
                self._prefix = ""

    def _route_event(self, event: RawKeyEvent) -> None:
        with self._lock:
            if event.session is not self.session:
                return
            self.route_key(event.key)

    def _poll_administration(self) -> None:
        with self._lock:
            session = self.session
            if session and self.is_active(session) and session.admin_session:
                if not session.admin_session.is_authorized():
                    self.cancel("admin exit")

    def _dispatch_loop(self) -> None:
        while not self._stop.is_set():
            self._poll_administration()
            try:
                event = self.hardware.input_queue.get(timeout=0.05)
            except queue.Empty:
                self.flush_prefix()
                continue
            try:
                self._route_event(event)
            except Exception:
                logger.exception("Input dispatcher failed; cancelling call")
                self.cancel("dispatcher error")

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            self.cancel("shutdown")
        if self._dispatcher and self._dispatcher is not threading.current_thread():
            self._dispatcher.join(timeout=2)
            if self._dispatcher.is_alive():
                logger.error("Input dispatcher did not exit")
