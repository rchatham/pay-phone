"""Fail-closed handset administration; the escape sequence is never a credential."""
import hmac
import os
import queue
import re
import time
from typing import Callable


class AdminSession:
    """Revocable capability tied to this exact call and keypad inactivity."""
    def __init__(self, runtime, session, inactivity_seconds: float = 120.0):
        self.runtime = runtime
        self.session = session
        self.inactivity_seconds = inactivity_seconds
        self._revoked = False
        with self.session.authorization_lock:
            self.session.last_activity = time.monotonic()
            self.session.admin_session = self

    def revoke(self) -> None:
        with self.session.authorization_lock:
            self._revoked = True

    def _require_authorized(self, now: float) -> None:
        if self._revoked or not self.runtime.is_active(self.session) or now - self.session.last_activity >= self.inactivity_seconds:
            self._revoked = True
            raise PermissionError("Administration cancelled or expired")

    def require_authorized(self) -> None:
        with self.session.authorization_lock:
            self._require_authorized(time.monotonic())

    def note_activity(self, now: float) -> None:
        """Check the old deadline first: an expired capability cannot be renewed."""
        with self.session.authorization_lock:
            self._require_authorized(now)
            self.session.last_activity = now

    def protected_commit(self, replace: Callable[[], None]) -> None:
        """Linearize final authorization and publication against cancellation.

        Stage data outside this guard; only the atomic publication belongs inside.
        Cancellation after publication cannot undo an already committed save.
        """
        with self.session.authorization_lock:
            self._require_authorized(time.monotonic())
            replace()

    def is_authorized(self) -> bool:
        try:
            self.require_authorized()
            return True
        except PermissionError:
            return False


class AdminAuthenticator:
    def __init__(self, *, attempt_limit: int = 3, cooldown_seconds: float = 30.0):
        value = os.environ.get("BIOS_ADMIN_PASSCODE", "")
        self._passcode = value if re.fullmatch(r"[0-9]{6,12}", value) else None
        self.attempt_limit = attempt_limit
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.blocked_until = 0.0

    @property
    def configured(self) -> bool:
        return self._passcode is not None

    def verify(self, entered: str) -> bool:
        """Constant-time compare for valid bounded input; never log entered digits."""
        now = time.monotonic()
        if not self.configured or now < self.blocked_until:
            return False
        valid = bool(re.fullmatch(r"[0-9]{6,12}", entered))
        matched = hmac.compare_digest(entered if valid else "", self._passcode)
        if valid and matched:
            self.failures = 0
            return True
        self.failures += 1
        if self.failures >= self.attempt_limit:
            self.blocked_until = now + self.cooldown_seconds
            self.failures = 0
        return False

    def authenticate(self, system):
        if not self.configured:
            system.speak("Administration is disabled. Provision the admin passcode in the deployment environment.")
            return None
        if time.monotonic() < self.blocked_until:
            system.speak("Administration is temporarily locked. Please try later.")
            return None
        session = system._session
        session.suppress_tones = True
        try:
            system.clear_input_queue()
            system.speak("Enter the administrator passcode, then press pound. Hang up to cancel.")
            entered = ""
            invalid = False
            deadline = time.monotonic() + 30.0
            while system.is_call_active() and time.monotonic() < deadline:
                try:
                    key = session.input_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if not system.is_call_active():
                    return None
                if key == "#":
                    if self.verify("" if invalid else entered) and system.is_call_active():
                        return AdminSession(system.runtime, session)
                    system.speak("Authorization failed.")
                    return None
                if key in "0123456789" and len(entered) < 12:
                    entered += key
                else:
                    invalid = True
            if system.is_call_active():
                self.verify("")
                system.speak("Authorization timed out.")
            return None
        finally:
            with session.authorization_lock:
                # Discard held credential prefixes before normal feedback resumes.
                if system.runtime.session is session:
                    system.runtime._prefix = ""
                system.clear_input_queue()
                session.suppress_tones = False
