"""BaresipClient against a fake baresip ctrl_tcp server.

``FakeCtrlTcp`` listens on an ephemeral loopback port and speaks the ctrl_tcp
wire format with its own (independent) netstring parser: it records every
command, answers with ``{"response": true, ...}`` and can push events.
"""

import json
import queue
import socket
import threading
import time

import pytest

from payphone.voip.baresip import BaresipClient, NetstringDecoder, encode_netstring
from payphone.voip.client import CallState, MessageWaiting

WAIT = 2.0


# ---------------------------------------------------------------------------
# Fake ctrl_tcp server
# ---------------------------------------------------------------------------

class FakeCtrlTcp:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.server.settimeout(0.1)
        self.port = self.server.getsockname()[1]
        self.commands: "queue.Queue[dict]" = queue.Queue()
        self.respond = True
        self.ok = True
        self.connections = 0
        self.conn = None
        self.connected = threading.Event()
        self._closing = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while not self._closing.is_set():
            try:
                conn, _ = self.server.accept()
            except (socket.timeout, OSError):
                continue
            conn.settimeout(0.1)
            self.conn = conn
            self.connections += 1
            self.connected.set()
            self._read(conn)
            self.connected.clear()

    def _read(self, conn):
        buffer = b""
        while not self._closing.is_set():
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                return
            buffer += chunk
            while b":" in buffer:
                length, rest = buffer.split(b":", 1)
                size = int(length)
                if len(rest) < size + 1:
                    break
                payload, buffer = rest[:size], rest[size + 1:]
                message = json.loads(payload)
                self.commands.put(message)
                if self.respond:
                    self.send({"response": True, "ok": self.ok, "data": "", "token": message.get("token")})

    def send_raw(self, data: bytes):
        self.conn.sendall(data)

    def send(self, message: dict):
        payload = json.dumps(message).encode()
        self.send_raw(str(len(payload)).encode() + b":" + payload + b",")

    def emit(self, event_type: str, **fields):
        self.send({"event": True, "class": "call", "type": event_type, **fields})

    def next_command(self) -> dict:
        return self.commands.get(timeout=WAIT)

    def drop(self):
        conn, self.conn = self.conn, None
        conn.shutdown(socket.SHUT_RDWR)
        conn.close()

    def close(self):
        self._closing.set()
        if self.conn:
            self.conn.close()
        self.server.close()
        self._thread.join(timeout=WAIT)


@pytest.fixture
def ctrl():
    server = FakeCtrlTcp()
    yield server
    server.close()


@pytest.fixture
def client(ctrl):
    voip = BaresipClient("127.0.0.1", ctrl.port, command_timeout=1.0, reconnect_interval=0.05)
    voip.start()
    assert voip.wait_connected(WAIT)
    assert ctrl.connected.wait(WAIT)
    yield voip
    voip.stop()


def recorder(voip, *names):
    """Route the named callbacks into one queue of (name, args) tuples."""
    events: "queue.Queue[tuple]" = queue.Queue()
    for name in names:
        setattr(voip, name, lambda *args, _name=name: events.put((_name, args)))
    return events


# ---------------------------------------------------------------------------
# Netstring framing
# ---------------------------------------------------------------------------

def test_encode_netstring():
    assert encode_netstring(b"hello") == b"5:hello,"
    assert encode_netstring(b"") == b"0:,"


def test_decoder_handles_frames_split_byte_by_byte():
    decoder = NetstringDecoder()
    data = encode_netstring(b'{"a":1}') + encode_netstring(b"xy")
    frames = []
    for byte in data:
        frames.extend(decoder.feed(bytes([byte])))
    assert frames == [b'{"a":1}', b"xy"]


def test_decoder_returns_several_frames_from_one_chunk():
    decoder = NetstringDecoder()
    assert decoder.feed(b"1:a,0:,3:bcd,2:e") == [b"a", b"", b"bcd"]
    assert decoder.feed(b"f,") == [b"ef"]


@pytest.mark.parametrize("data", [b"x:abc,", b"3:abcX", b"01:a,", b"-1:a,", b"99999999999:"])
def test_decoder_rejects_malformed_frames(data):
    with pytest.raises(ValueError):
        NetstringDecoder(max_frame=1024).feed(data)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def test_dial_sends_dial_command_and_reports_success(client, ctrl):
    assert client.dial("sip:463@10.0.0.1") is True

    command = ctrl.next_command()
    assert command["command"] == "dial"
    assert command["params"] == "sip:463@10.0.0.1"
    assert command["token"]
    assert client.call_state is CallState.DIALING


def test_dial_passes_a_bare_extension_for_baresip_to_complete(client, ctrl):
    assert client.dial("463") is True
    assert ctrl.next_command()["params"] == "463"


def test_failed_command_returns_false_and_resets_dialing(client, ctrl):
    ctrl.ok = False
    assert client.dial("999") is False
    assert client.call_state is CallState.IDLE


def test_command_times_out_when_baresip_does_not_answer(client, ctrl):
    ctrl.respond = False
    started = time.monotonic()
    response = client.command("reginfo", timeout=0.2)
    assert response.ok is False and response.data == "timeout"
    assert time.monotonic() - started < 1.0


def test_command_without_connection_fails_fast():
    voip = BaresipClient("127.0.0.1", 9, command_timeout=5.0)
    response = voip.command("hangup")
    assert response.ok is False and response.data == "not connected"


@pytest.mark.parametrize(
    "call, expected",
    [
        (lambda v: v.hangup(), {"command": "hangup"}),
        (lambda v: v.accept(), {"command": "accept"}),
        (lambda v: v.send_dtmf("12#"), {"command": "sndcode", "params": "12#"}),
    ],
)
def test_call_control_commands(client, ctrl, call, expected):
    assert call(client) is True
    command = ctrl.next_command()
    command.pop("token")
    assert command == expected


def test_send_dtmf_rejects_non_dtmf_characters(client, ctrl):
    with pytest.raises(ValueError):
        client.send_dtmf("1x")
    with pytest.raises(ValueError):
        client.send_dtmf("")
    assert ctrl.commands.empty()


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def test_registration_events(client, ctrl):
    events = recorder(client, "on_registration")

    ctrl.emit("REGISTER_OK", accountaor="sip:463@10.0.0.1")
    assert events.get(timeout=WAIT) == ("on_registration", (True, "sip:463@10.0.0.1"))
    assert client.registered is True

    ctrl.emit("REGISTER_FAIL", accountaor="sip:463@10.0.0.1", param="401 Unauthorized")
    assert events.get(timeout=WAIT) == ("on_registration", (False, "401 Unauthorized"))
    assert client.registered is False


def test_outgoing_call_lifecycle(client, ctrl):
    events = recorder(client, "on_call_ringing", "on_call_established", "on_call_closed")
    client.dial("626")
    ctrl.next_command()

    ctrl.emit("CALL_PROGRESS", direction="outgoing", peeruri="sip:626@10.0.0.1")
    ctrl.emit("CALL_RINGING", direction="outgoing", peeruri="sip:626@10.0.0.1")
    ctrl.emit("CALL_ESTABLISHED", direction="outgoing", peeruri="sip:626@10.0.0.1", id="abc")
    assert events.get(timeout=WAIT) == ("on_call_ringing", ("sip:626@10.0.0.1",))
    assert events.get(timeout=WAIT) == ("on_call_established", ("sip:626@10.0.0.1",))
    assert client.call_state is CallState.ESTABLISHED

    ctrl.emit("CALL_CLOSED", peeruri="sip:626@10.0.0.1", param="Connection reset by peer")
    assert events.get(timeout=WAIT) == ("on_call_closed", ("Connection reset by peer",))
    assert client.call_state is CallState.IDLE
    assert events.empty(), "183 then 180 must report ringing once"


def test_message_waiting_notify_is_parsed(client, ctrl):
    events = recorder(client, "on_message_waiting")
    body = "Messages-Waiting: yes\r\nMessage-Account: sip:*97@10.0.0.1\r\nVoice-Message: 2/8 (0/2)\r\n"

    ctrl.send({"event": True, "class": "ua", "type": "MWI_NOTIFY", "param": body})

    assert events.get(timeout=WAIT) == ("on_message_waiting", (MessageWaiting(True, 2, 8),))
    assert client.message_waiting.new == 2


def test_event_flag_sent_as_string_is_accepted(client, ctrl):
    events = recorder(client, "on_call_incoming")
    ctrl.send({"event": "true", "class": "call", "type": "CALL_INCOMING", "peeruri": "sip:0@10.0.0.1"})
    assert events.get(timeout=WAIT) == ("on_call_incoming", ("sip:0@10.0.0.1",))
    assert client.call_state is CallState.INCOMING


def test_event_split_across_tcp_writes_is_delivered(client, ctrl):
    events = recorder(client, "on_call_incoming")
    payload = json.dumps({"event": True, "type": "CALL_INCOMING", "peeruri": "sip:1@h"}).encode()
    frame = str(len(payload)).encode() + b":" + payload + b","
    ctrl.send_raw(frame[:7])
    time.sleep(0.05)
    ctrl.send_raw(frame[7:])
    assert events.get(timeout=WAIT) == ("on_call_incoming", ("sip:1@h",))


def test_callback_can_send_commands_without_deadlock(client, ctrl):
    answered = threading.Event()

    def answer(peer_uri):
        if client.accept():
            answered.set()

    client.on_call_incoming = answer
    ctrl.emit("CALL_INCOMING", direction="incoming", peeruri="sip:0@10.0.0.1")

    assert answered.wait(WAIT)
    assert ctrl.next_command()["command"] == "accept"


def test_callback_exception_does_not_stop_event_delivery(client, ctrl):
    events = recorder(client, "on_call_closed")
    client.on_call_incoming = lambda peer: 1 / 0
    ctrl.emit("CALL_INCOMING", peeruri="sip:1@h")
    ctrl.emit("CALL_CLOSED", param="bye")
    assert events.get(timeout=WAIT) == ("on_call_closed", ("bye",))


def test_disconnect_reports_unregistered_and_reconnects(client, ctrl):
    events = recorder(client, "on_registration", "on_call_closed")
    ctrl.emit("REGISTER_OK", accountaor="sip:463@10.0.0.1")
    ctrl.emit("CALL_ESTABLISHED", peeruri="sip:626@10.0.0.1")
    assert events.get(timeout=WAIT)[0] == "on_registration"

    ctrl.drop()

    assert events.get(timeout=WAIT) == ("on_call_closed", ("baresip disconnected",))
    assert events.get(timeout=WAIT) == ("on_registration", (False, "baresip disconnected"))
    deadline = time.monotonic() + WAIT
    while ctrl.connections < 2 and time.monotonic() < deadline:
        time.sleep(0.02)
    assert ctrl.connected.wait(WAIT) and client.wait_connected(WAIT)
    assert client.hangup() is True
