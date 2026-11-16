"""
BaresipClient: drive a local baresip process over its ``ctrl_tcp`` module.

baresip (https://github.com/baresip/baresip) does the SIP signalling, RTP,
codecs, jitter buffer and ALSA audio. This client only sends commands and
reads events, as JSON framed with netstrings (``<length>:<payload>,``).

Wire format (ctrl_tcp, the same in baresip 1.1.0 (Debian 12) and 4.x):

- Command:  ``{"command": "dial", "params": "sip:463@10.0.0.1", "token": "7"}``.
  ``command``/``params`` are the CLI command line (``/dial sip:...``), so the
  ``menu`` module must be loaded for dial/hangup/accept/sndcode to exist.
- Response: ``{"response": true, "ok": true, "data": "<text>", "token": "7"}``.
- Event:    ``{"event": true, "class": "call", "type": "CALL_ESTABLISHED",
  "peeruri": "sip:626@10.0.0.1", "param": "...", ...}``. ``class`` names differ
  between baresip versions, so events are dispatched on ``type`` only.

ctrl_tcp accepts one client at a time; a second connection replaces the first.
"""

import itertools
import json
import logging
import queue
import socket
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .client import CallState, VoipClient, parse_message_summary

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4444

#: Refuse frames larger than this; baresip's own limit is far smaller.
MAX_FRAME_BYTES = 1 << 20


# ---------------------------------------------------------------------------
# Netstring framing
# ---------------------------------------------------------------------------

def encode_netstring(payload: bytes) -> bytes:
    """Frame ``payload`` as a netstring: ``b"5:hello,"``."""
    return str(len(payload)).encode("ascii") + b":" + payload + b","


class NetstringDecoder:
    """Incremental netstring parser for a byte stream.

    TCP delivers arbitrary chunks: one ``recv`` may hold half a frame or
    several frames. ``feed`` buffers partial input and returns every complete
    payload, in order.
    """

    def __init__(self, max_frame: int = MAX_FRAME_BYTES) -> None:
        self._buffer = bytearray()
        self._max_frame = max_frame

    def feed(self, data: bytes) -> List[bytes]:
        """Add received bytes and return the complete payloads they finish.

        Raises:
            ValueError: on a malformed or oversized frame. The stream cannot be
                resynchronised after that; the caller should reconnect.
        """
        self._buffer.extend(data)
        frames: List[bytes] = []
        while True:
            colon = self._buffer.find(b":")
            if colon < 0:
                if len(self._buffer) > len(str(self._max_frame)):
                    raise ValueError("netstring length prefix too long")
                return frames
            prefix = bytes(self._buffer[:colon])
            if not prefix.isdigit() or (len(prefix) > 1 and prefix.startswith(b"0")):
                raise ValueError(f"bad netstring length prefix: {prefix[:20]!r}")
            length = int(prefix)
            if length > self._max_frame:
                raise ValueError(f"netstring frame too large: {length} bytes")
            end = colon + 1 + length
            if len(self._buffer) < end + 1:
                return frames
            if self._buffer[end:end + 1] != b",":
                raise ValueError("netstring frame missing trailing comma")
            frames.append(bytes(self._buffer[colon + 1:end]))
            del self._buffer[:end + 1]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BaresipResponse:
    """Reply to one ctrl_tcp command. ``data`` is baresip's printed text."""

    ok: bool
    data: str = ""


class _PendingCommand:
    def __init__(self) -> None:
        self.done = threading.Event()
        self.response = BaresipResponse(False, "no response")


class BaresipClient(VoipClient):
    """VoipClient backed by baresip's ctrl_tcp socket.

    ``start()`` spawns two daemon threads:

    - a reader that (re)connects to baresip, decodes frames, completes pending
      commands and queues events. It reconnects every ``reconnect_interval``
      seconds, so payphone can start before baresip does.
    - a dispatcher that applies queued events and runs the callbacks. Keeping
      callbacks off the reader thread lets a callback issue commands (e.g.
      ``accept()`` from ``on_call_incoming``) without deadlocking on its own
      response.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        *,
        command_timeout: float = 3.0,
        connect_timeout: float = 2.0,
        reconnect_interval: float = 2.0,
    ) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.command_timeout = command_timeout
        self.connect_timeout = connect_timeout
        self.reconnect_interval = reconnect_interval

        self._sock: Optional[socket.socket] = None
        self._send_lock = threading.Lock()
        self._pending: Dict[str, _PendingCommand] = {}
        self._tokens = itertools.count(1)
        self._events: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()
        self._connected = threading.Event()
        self._stopping = threading.Event()
        self._reader: Optional[threading.Thread] = None
        self._dispatcher: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def start(self) -> bool:
        if self._reader and self._reader.is_alive():
            return True
        self._stopping.clear()
        self._reader = threading.Thread(target=self._read_loop, name="baresip-reader", daemon=True)
        self._dispatcher = threading.Thread(target=self._dispatch_loop, name="baresip-events", daemon=True)
        self._dispatcher.start()
        self._reader.start()
        logger.info("baresip client started (ctrl_tcp %s:%s)", self.host, self.port)
        return True

    def wait_connected(self, timeout: Optional[float] = None) -> bool:
        """Block until the ctrl_tcp connection is up. Returns False on timeout."""
        return self._connected.wait(timeout)

    def stop(self) -> None:
        self._stopping.set()
        self._close_socket()
        self._events.put(None)
        for thread in (self._reader, self._dispatcher):
            if thread and thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=2.0)
        logger.info("baresip client stopped")

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def command(self, command: str, params: Optional[str] = None, timeout: Optional[float] = None) -> BaresipResponse:
        """Send one ctrl_tcp command and wait for its response.

        Never raises for transport problems: a missing connection, a send error
        or a timeout come back as ``BaresipResponse(ok=False, data=<reason>)``.
        """
        token = str(next(self._tokens))
        message: Dict[str, Any] = {"command": command, "token": token}
        if params:
            message["params"] = params
        frame = encode_netstring(json.dumps(message).encode("utf-8"))

        pending = _PendingCommand()
        with self._send_lock:
            sock = self._sock
            if sock is None:
                logger.warning("baresip not connected; dropped command %r", command)
                return BaresipResponse(False, "not connected")
            self._pending[token] = pending
            try:
                sock.sendall(frame)
            except OSError as exc:
                self._pending.pop(token, None)
                logger.warning("baresip send failed for %r: %s", command, exc)
                return BaresipResponse(False, f"send failed: {exc}")

        if not pending.done.wait(self.command_timeout if timeout is None else timeout):
            self._pending.pop(token, None)
            logger.warning("baresip command %r timed out", command)
            return BaresipResponse(False, "timeout")
        if not pending.response.ok:
            logger.warning("baresip command %r failed: %s", command, pending.response.data)
        return pending.response

    def dial(self, target: str) -> bool:
        """Dial an extension or URI; baresip completes ``"463"`` to ``sip:463@<account domain>``."""
        target = (target or "").strip()
        if not target:
            raise ValueError("dial target is empty")
        # Enter DIALING before sending: baresip can emit CALL_RINGING or
        # CALL_CLOSED before the command's response reaches this thread.
        placed_call = not self.in_call
        if placed_call:
            self.call_state = CallState.DIALING
            self.peer_uri = target
        ok = self.command("dial", target).ok
        if not ok and placed_call and self.call_state is CallState.DIALING:
            self.call_state = CallState.IDLE
            self.peer_uri = None
        return ok

    def hangup(self) -> bool:
        return self.command("hangup").ok

    def accept(self) -> bool:
        return self.command("accept").ok

    def send_dtmf(self, digits: str) -> bool:
        return self.command("sndcode", self._check_dtmf(digits)).ok

    # ------------------------------------------------------------------
    # Reader thread
    # ------------------------------------------------------------------

    def _read_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
            except OSError as exc:
                logger.debug("baresip ctrl_tcp not reachable (%s); retrying", exc)
                self._stopping.wait(self.reconnect_interval)
                continue

            sock.settimeout(0.2)  # poll interval for stop(); shutdown() usually wakes recv sooner
            with self._send_lock:
                self._sock = sock
            self._connected.set()
            logger.info("Connected to baresip ctrl_tcp at %s:%s", self.host, self.port)
            try:
                self._receive(sock)
            except (OSError, ValueError) as exc:
                if not self._stopping.is_set():
                    logger.warning("baresip connection lost: %s", exc)
            finally:
                self._on_disconnect()
            if not self._stopping.is_set():
                self._stopping.wait(self.reconnect_interval)

    def _receive(self, sock: socket.socket) -> None:
        decoder = NetstringDecoder()
        while not self._stopping.is_set():
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            if not data:
                raise OSError("baresip closed the connection")
            for frame in decoder.feed(data):
                self._handle_frame(frame)

    def _handle_frame(self, frame: bytes) -> None:
        try:
            message = json.loads(frame.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Ignoring non-JSON baresip frame: %r", frame[:200])
            return
        if not isinstance(message, dict):
            return
        if _truthy(message.get("response")):
            pending = self._pending.pop(str(message.get("token", "")), None)
            if pending is not None:
                pending.response = BaresipResponse(bool(message.get("ok")), str(message.get("data") or ""))
                pending.done.set()
        elif _truthy(message.get("event")):
            self._events.put(message)

    def _on_disconnect(self) -> None:
        self._close_socket()
        self._connected.clear()
        for token in list(self._pending):
            pending = self._pending.pop(token, None)
            if pending is not None:
                pending.response = BaresipResponse(False, "disconnected")
                pending.done.set()
        # baresip may have been restarted: whatever we knew is stale.
        self._events.put({"event": True, "type": "_DISCONNECTED"})

    def _close_socket(self) -> None:
        with self._send_lock:
            sock, self._sock = self._sock, None
        if sock is not None:
            # shutdown() wakes a reader blocked in recv(); close() alone may not.
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Dispatcher thread
    # ------------------------------------------------------------------

    def _dispatch_loop(self) -> None:
        while True:
            event = self._events.get()
            if event is None or self._stopping.is_set():
                return
            try:
                self._apply_event(event)
            except Exception:
                logger.exception("Error handling baresip event %r", event)

    def _apply_event(self, event: Dict[str, Any]) -> None:
        event_type = str(event.get("type", ""))
        param = str(event.get("param") or "")
        peer = str(event.get("peeruri") or "")
        logger.debug("baresip event %s %s %s", event_type, peer, param)

        if event_type == "REGISTER_OK":
            self._registration_changed(True, str(event.get("accountaor") or ""))
        elif event_type in ("REGISTER_FAIL", "UNREGISTERING"):
            self._registration_changed(False, param or event_type.lower())
        elif event_type == "CALL_INCOMING":
            self._call_incoming(peer)
        elif event_type in ("CALL_RINGING", "CALL_PROGRESS"):
            # Asterisk often answers a Dial() with 183 + ringback instead of 180.
            if self.call_state is not CallState.RINGING:
                self._call_ringing(peer)
        elif event_type == "CALL_ESTABLISHED":
            self._call_established(peer)
        elif event_type == "CALL_CLOSED":
            self._call_closed(param)
        elif event_type == "MWI_NOTIFY":
            self._message_waiting_changed(parse_message_summary(param))
        elif event_type == "_DISCONNECTED":
            if self.in_call:
                self._call_closed("baresip disconnected")
            if self.registered:
                self._registration_changed(False, "baresip disconnected")


def _truthy(value: Any) -> bool:
    """ctrl_tcp sends JSON booleans; older docs show the string "true"."""
    return value is True or value == "true"
