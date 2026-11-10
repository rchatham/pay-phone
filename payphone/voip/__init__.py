"""
VoIP (SIP) support for payphone systems.

Generic: works with any SIP server. A local baresip process handles SIP and
audio; :class:`BaresipClient` drives it, :class:`FakeVoipClient` stands in for
it in tests and the simulator.
"""

from typing import Optional

from .baresip import BaresipClient, BaresipResponse, NetstringDecoder, encode_netstring
from .client import CallState, MessageWaiting, VoipClient, parse_message_summary
from .fake import FakeVoipClient

__all__ = [
    "BaresipClient",
    "BaresipResponse",
    "CallState",
    "FakeVoipClient",
    "MessageWaiting",
    "NetstringDecoder",
    "VoipClient",
    "create_client",
    "encode_netstring",
    "parse_message_summary",
]


def create_client(config=None) -> Optional[VoipClient]:
    """Return a BaresipClient when ``VOIP_ENABLED`` is true, else None.

    The client is not started; call ``start()`` when the phone system that
    needs it starts.
    """
    if config is None:
        from ..config.settings import Config
        config = Config()
    if not getattr(config, "VOIP_ENABLED", False):
        return None
    return BaresipClient()
