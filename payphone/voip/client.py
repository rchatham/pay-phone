"""
Transport-independent VoIP client interface.

Phone systems talk to a :class:`VoipClient`; :class:`~payphone.voip.baresip.BaresipClient`
drives a real baresip process and :class:`~payphone.voip.fake.FakeVoipClient`
is an in-memory stand-in for tests and the simulator.

Callbacks are plain attributes. Assign a callable to receive events::

    client.on_call_established = lambda peer_uri: logger.info("talking to %s", peer_uri)

Callbacks run on the client's event thread (BaresipClient) or synchronously
(FakeVoipClient). They may call client commands such as ``hangup()``. An
exception raised by a callback is logged and swallowed so one faulty phone
system cannot stop event delivery.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)

#: Characters a SIP DTMF digit may be (RFC 4733 events 0-15).
DTMF_DIGITS = frozenset("0123456789*#ABCD")


class CallState(Enum):
    """Where the (single) call is in its lifecycle."""

    IDLE = "idle"
    DIALING = "dialing"            # dial() accepted, no answer from the network yet
    RINGING = "ringing"            # far end is alerting (180 Ringing / 183 Progress)
    INCOMING = "incoming"          # someone is calling us; accept() answers
    ESTABLISHED = "established"    # audio is flowing


@dataclass(frozen=True)
class MessageWaiting:
    """Message-waiting state from a SIP NOTIFY (RFC 3842)."""

    waiting: bool
    new: int = 0
    old: int = 0


_MESSAGES_WAITING = re.compile(r"^\s*messages-waiting\s*:\s*(yes|no)\s*$", re.IGNORECASE | re.MULTILINE)
_VOICE_MESSAGE = re.compile(r"^\s*voice-message\s*:\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE | re.MULTILINE)


def parse_message_summary(body: str) -> MessageWaiting:
    """Parse an ``application/simple-message-summary`` body.

    Example body::

        Messages-Waiting: yes
        Message-Account: sip:463@10.0.0.1
        Voice-Message: 2/8 (0/2)

    Args:
        body: The NOTIFY body as text. Unknown or missing headers are tolerated.

    Returns:
        MessageWaiting; ``waiting`` falls back to ``new > 0`` when the
        Messages-Waiting header is absent.
    """
    new = old = 0
    voice = _VOICE_MESSAGE.search(body or "")
    if voice:
        new, old = int(voice.group(1)), int(voice.group(2))
    flag = _MESSAGES_WAITING.search(body or "")
    waiting = flag.group(1).lower() == "yes" if flag else new > 0
    return MessageWaiting(waiting=waiting, new=new, old=old)


class VoipClient(ABC):
    """A single-line SIP phone: one account, at most one call at a time."""

    def __init__(self) -> None:
        self.registered: bool = False
        self.call_state: CallState = CallState.IDLE
        self.peer_uri: Optional[str] = None
        self.message_waiting: MessageWaiting = MessageWaiting(waiting=False)

        #: (registered, detail) - detail is the account AOR or the failure reason.
        self.on_registration: Optional[Callable[[bool, str], None]] = None
        #: (peer_uri) - someone is calling this phone.
        self.on_call_incoming: Optional[Callable[[str], None]] = None
        #: (peer_uri) - the number we dialed is ringing.
        self.on_call_ringing: Optional[Callable[[str], None]] = None
        #: (peer_uri) - the call was answered; audio is flowing.
        self.on_call_established: Optional[Callable[[str], None]] = None
        #: (reason) - the call ended, failed or was rejected.
        self.on_call_closed: Optional[Callable[[str], None]] = None
        #: (MessageWaiting) - voicemail state for this phone's mailbox.
        self.on_message_waiting: Optional[Callable[[MessageWaiting], None]] = None

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @abstractmethod
    def start(self) -> bool:
        """Start talking to the SIP stack. Returns False if it cannot start."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the client and release its resources."""

    @abstractmethod
    def dial(self, target: str) -> bool:
        """Call ``target``: an extension such as ``"463"`` or a full ``sip:`` URI.

        Returns:
            True if the SIP stack accepted the request. Progress is reported
            through the call callbacks.
        """

    @abstractmethod
    def hangup(self) -> bool:
        """End, cancel or reject the current call."""

    @abstractmethod
    def accept(self) -> bool:
        """Answer the incoming call."""

    @abstractmethod
    def send_dtmf(self, digits: str) -> bool:
        """Send keypad digits to the far end of the established call."""

    @property
    def in_call(self) -> bool:
        """True while a call is being set up or is established."""
        return self.call_state is not CallState.IDLE

    # ------------------------------------------------------------------
    # Event dispatch for implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _check_dtmf(digits: str) -> str:
        digits = (digits or "").upper()
        if not digits or not set(digits) <= DTMF_DIGITS:
            raise ValueError(f"Invalid DTMF digits: {digits!r}")
        return digits

    def _notify(self, callback: Optional[Callable], *args) -> None:
        if callback is None:
            return
        try:
            callback(*args)
        except Exception:
            logger.exception("VoIP callback %r failed", getattr(callback, "__name__", callback))

    def _registration_changed(self, registered: bool, detail: str = "") -> None:
        self.registered = registered
        self._notify(self.on_registration, registered, detail)

    def _call_incoming(self, peer_uri: str) -> None:
        self.call_state = CallState.INCOMING
        self.peer_uri = peer_uri
        self._notify(self.on_call_incoming, peer_uri)

    def _call_ringing(self, peer_uri: str) -> None:
        self.call_state = CallState.RINGING
        self.peer_uri = peer_uri or self.peer_uri
        self._notify(self.on_call_ringing, self.peer_uri or "")

    def _call_established(self, peer_uri: str) -> None:
        self.call_state = CallState.ESTABLISHED
        self.peer_uri = peer_uri or self.peer_uri
        self._notify(self.on_call_established, self.peer_uri or "")

    def _call_closed(self, reason: str = "") -> None:
        self.call_state = CallState.IDLE
        self.peer_uri = None
        self._notify(self.on_call_closed, reason)

    def _message_waiting_changed(self, state: MessageWaiting) -> None:
        self.message_waiting = state
        self._notify(self.on_message_waiting, state)
