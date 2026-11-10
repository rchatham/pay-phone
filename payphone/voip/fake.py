"""
FakeVoipClient: an in-memory VoipClient for tests and the simulator.

Commands are recorded instead of sent anywhere; ``simulate_*`` methods play the
network's part. Callbacks run synchronously on the calling thread, so a test
can assert on their effects right after a ``simulate_*`` call.

    voip = FakeVoipClient(auto_answer=True)
    voip.start()
    voip.dial("626")          # -> on_call_ringing, then on_call_established
    voip.send_dtmf("1")
    voip.simulate_remote_hangup()
    assert voip.dialed == ["626"] and voip.dtmf_sent == ["1"]
"""

from typing import List

from .client import CallState, MessageWaiting, VoipClient


class FakeVoipClient(VoipClient):
    """Records commands; a test or the simulator drives the far end."""

    def __init__(self, *, auto_answer: bool = False, register_on_start: bool = True,
                 account_aor: str = "sip:fake@localhost") -> None:
        """
        Args:
            auto_answer: When True, ``dial()`` immediately reports ringing and
                then an answered call, like a far end that always picks up.
            register_on_start: When True, ``start()`` reports a successful
                registration.
            account_aor: Detail passed to ``on_registration``.
        """
        super().__init__()
        self.auto_answer = auto_answer
        self.register_on_start = register_on_start
        self.account_aor = account_aor
        self.started = False
        #: Value the next commands return; set False to simulate a SIP stack error.
        self.command_result = True
        self.dialed: List[str] = []
        self.dtmf_sent: List[str] = []
        self.hangups = 0
        self.accepts = 0

    # ------------------------------------------------------------------
    # VoipClient commands
    # ------------------------------------------------------------------

    def start(self) -> bool:
        self.started = True
        if self.register_on_start:
            self._registration_changed(True, self.account_aor)
        return True

    def stop(self) -> None:
        self.started = False
        if self.in_call:
            self._call_closed("client stopped")
        if self.registered:
            self._registration_changed(False, "client stopped")

    def dial(self, target: str) -> bool:
        target = (target or "").strip()
        if not target:
            raise ValueError("dial target is empty")
        self.dialed.append(target)
        if not self.command_result:
            return False
        self.call_state = CallState.DIALING
        self.peer_uri = target
        if self.auto_answer:
            self.simulate_ringing()
            self.simulate_answer()
        return True

    def hangup(self) -> bool:
        self.hangups += 1
        if not self.command_result:
            return False
        if self.in_call:
            self._call_closed("local hangup")
        return True

    def accept(self) -> bool:
        self.accepts += 1
        if not self.command_result or self.call_state is not CallState.INCOMING:
            return False
        self._call_established(self.peer_uri or "")
        return True

    def send_dtmf(self, digits: str) -> bool:
        digits = self._check_dtmf(digits)
        if not self.command_result or self.call_state is not CallState.ESTABLISHED:
            return False
        self.dtmf_sent.append(digits)
        return True

    # ------------------------------------------------------------------
    # The network's side
    # ------------------------------------------------------------------

    def simulate_registration(self, registered: bool, detail: str = "") -> None:
        self._registration_changed(registered, detail or (self.account_aor if registered else "failed"))

    def simulate_incoming(self, peer_uri: str) -> None:
        self._call_incoming(peer_uri)

    def simulate_ringing(self) -> None:
        self._call_ringing(self.peer_uri or "")

    def simulate_answer(self) -> None:
        self._call_established(self.peer_uri or "")

    def simulate_remote_hangup(self, reason: str = "remote hangup") -> None:
        self._call_closed(reason)

    def simulate_message_waiting(self, new: int, old: int = 0) -> None:
        self._message_waiting_changed(MessageWaiting(waiting=new > 0, new=new, old=old))
