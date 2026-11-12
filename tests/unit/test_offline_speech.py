"""Mocked offline TTS subprocess lifecycle and late-playback prevention."""
import logging
import subprocess
import threading
import time
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from payphone.audio.speech import OfflineSpeech
from payphone.core.runtime import PhoneRuntime


class Playback:
    def __init__(self):
        self.playing = False
        self.played = []

    def play_file(self, path, blocking=True):
        self.played.append(path)
        self.playing = True
        return True

    def stop(self):
        self.playing = False

    def is_playing(self):
        return self.playing


class SynthProcess:
    def __init__(self, command, entered, release):
        self.wave = Path(command[2])
        self.entered = entered
        self.release = release
        self.returncode = None
        self.terminated = False
        self.input = None

    def communicate(self, input=None, timeout=None):
        self.input = input
        self.entered.set()
        assert self.release.wait(2)
        self.returncode = 0
        self.wave.write_bytes(b"mock wave")
        return None, None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.release.set()

    def kill(self):
        self.terminate()

    def wait(self, timeout=None):
        if not self.release.wait(timeout):
            raise subprocess.TimeoutExpired("mock", timeout)
        return 0


@pytest.fixture
def speech_fixture(monkeypatch):
    monkeypatch.setattr("payphone.audio.speech.shutil.which", lambda name: "/mock/espeak-ng")
    runtime = PhoneRuntime(SimpleNamespace(input_queue=Queue()), Playback())
    runtime.off_hook = True
    session = runtime.new_session()
    speech = OfflineSpeech(runtime)
    runtime.speech = speech
    entered = threading.Event()
    release = threading.Event()
    processes = []

    def synth(command, **kwargs):
        assert command[0] == "/mock/espeak-ng"
        assert command[-1] == "--stdin"
        assert "shell" not in kwargs
        process = SynthProcess(command, entered, release)
        processes.append(process)
        return process

    factory = Mock(side_effect=synth)
    monkeypatch.setattr("payphone.audio.speech.subprocess.Popen", factory)
    yield runtime, session, speech, entered, release, processes, factory
    release.set()
    runtime.stop()


def test_cancel_during_synthesis_terminates_owned_process(speech_fixture):
    runtime, session, speech, entered, release, processes, factory = speech_fixture
    speech.say("A dynamic menu.", session, blocking=False)
    assert entered.wait(1)
    runtime.cancel("escape")
    assert processes[0].terminated
    assert processes[0].input == b"A dynamic menu."
    assert not speech.is_speaking()
    assert runtime.audio.played == []
    assert not processes[0].wave.parent.exists()
    speech.say("Too late.", session)
    assert factory.call_count == 1


def test_cancel_during_playback_stops_audio(speech_fixture):
    runtime, session, speech, entered, release, processes, factory = speech_fixture
    release.set()
    speech.say("A spoken menu.", session, blocking=False)
    deadline = time.monotonic() + 2
    while not runtime.audio.playing and time.monotonic() < deadline:
        time.sleep(0.01)
    assert runtime.audio.playing
    runtime.cancel("hangup")
    assert not runtime.audio.playing
    assert not speech.is_speaking()
    assert not processes[0].wave.parent.exists()


def test_missing_dependency_has_explicit_setup_diagnostic(monkeypatch, caplog):
    monkeypatch.setattr("payphone.audio.speech.shutil.which", lambda name: None)
    runtime = PhoneRuntime(SimpleNamespace(input_queue=Queue()), Playback())
    runtime.off_hook = True
    session = runtime.new_session()
    with caplog.at_level(logging.ERROR):
        speech = OfflineSpeech(runtime)
    assert "install espeak-ng" in caplog.text
    with pytest.raises(RuntimeError, match="requires espeak-ng"):
        speech.say("Dynamic BIOS menu.", session)


def test_speech_text_is_bounded_before_subprocess(speech_fixture):
    runtime, session, speech, entered, release, processes, factory = speech_fixture
    with pytest.raises(ValueError):
        speech.say("x" * 8193, session)
    factory.assert_not_called()
