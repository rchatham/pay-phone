"""FakeVoipClient (tests/simulator stand-in), MWI parsing and the client factory."""

import pytest

from payphone.config.settings import Config
from payphone.voip import BaresipClient, CallState, FakeVoipClient, MessageWaiting, create_client, parse_message_summary


@pytest.fixture
def calls():
    return []


@pytest.fixture
def voip(calls):
    client = FakeVoipClient()
    for name in ("on_registration", "on_call_incoming", "on_call_ringing",
                 "on_call_established", "on_call_closed", "on_message_waiting"):
        setattr(client, name, lambda *args, _name=name: calls.append((_name, *args)))
    return client


def test_start_registers(voip, calls):
    assert voip.start() is True
    assert voip.registered is True
    assert calls == [("on_registration", True, "sip:fake@localhost")]


def test_dial_then_far_end_answers_and_hangs_up(voip, calls):
    voip.start()
    calls.clear()

    assert voip.dial("626") is True
    assert voip.call_state is CallState.DIALING
    voip.simulate_ringing()
    voip.simulate_answer()
    assert voip.send_dtmf("1") is True
    voip.simulate_remote_hangup("busy")

    assert voip.dialed == ["626"]
    assert voip.dtmf_sent == ["1"]
    assert calls == [
        ("on_call_ringing", "626"),
        ("on_call_established", "626"),
        ("on_call_closed", "busy"),
    ]
    assert voip.call_state is CallState.IDLE


def test_auto_answer(calls):
    voip = FakeVoipClient(auto_answer=True)
    voip.on_call_established = lambda peer: calls.append(peer)
    voip.dial("0")
    assert calls == ["0"]
    assert voip.call_state is CallState.ESTABLISHED


def test_local_hangup_closes_the_call(voip, calls):
    voip.dial("626")
    voip.simulate_answer()
    assert voip.hangup() is True
    assert calls[-1] == ("on_call_closed", "local hangup")
    assert voip.hangups == 1


def test_incoming_call_is_accepted(voip, calls):
    voip.simulate_incoming("sip:0@hub")
    assert voip.call_state is CallState.INCOMING
    assert voip.accept() is True
    assert calls == [("on_call_incoming", "sip:0@hub"), ("on_call_established", "sip:0@hub")]


def test_accept_and_dtmf_need_the_right_call_state(voip):
    assert voip.accept() is False
    assert voip.send_dtmf("5") is False
    assert voip.dtmf_sent == []


def test_command_result_false_simulates_sip_stack_errors(voip):
    voip.command_result = False
    assert voip.dial("626") is False
    assert voip.call_state is CallState.IDLE


def test_message_waiting(voip, calls):
    voip.simulate_message_waiting(new=3, old=1)
    assert calls == [("on_message_waiting", MessageWaiting(True, 3, 1))]


def test_stop_closes_call_and_unregisters(voip, calls):
    voip.start()
    voip.dial("626")
    voip.simulate_answer()
    calls.clear()
    voip.stop()
    assert calls == [("on_call_closed", "client stopped"), ("on_registration", False, "client stopped")]


@pytest.mark.parametrize(
    "body, expected",
    [
        ("Messages-Waiting: yes\r\nVoice-Message: 2/8 (0/2)\r\n", MessageWaiting(True, 2, 8)),
        ("messages-waiting: no\nvoice-message: 0/4\n", MessageWaiting(False, 0, 4)),
        ("Voice-Message: 1/0", MessageWaiting(True, 1, 0)),
        ("", MessageWaiting(False, 0, 0)),
        ("garbage", MessageWaiting(False, 0, 0)),
    ],
)
def test_parse_message_summary(body, expected):
    assert parse_message_summary(body) == expected


def test_create_client_follows_voip_enabled(monkeypatch):
    monkeypatch.setattr(Config, "VOIP_ENABLED", False)
    assert create_client(Config()) is None
    monkeypatch.setattr(Config, "VOIP_ENABLED", True)
    client = create_client(Config())
    assert isinstance(client, BaresipClient)
    assert not client.connected
