"""Tests for core PhoneTree behavior shared by plugins."""

from queue import Queue
from unittest.mock import Mock

from payphone.core.phone_tree import PhoneTree


class FakeOption:
    def __init__(self) -> None:
        self.call_args = None

    def navigate(self, *args) -> None:
        self.call_args = args


class FakeAudioHandler:
    def __init__(self) -> None:
        self.played = []
        self.stopped = 0
        self.playing = False

    def play_file(self, filename: str, blocking: bool = True) -> bool:
        self.played.append((filename, blocking))
        self.playing = not blocking
        return True

    def stop(self) -> None:
        self.stopped += 1
        self.playing = False

    def is_playing(self) -> bool:
        return self.playing


class FakeSpeechHandler:
    def __init__(self) -> None:
        self.spoken = []
        self.stopped = 0
        self.speaking = False

    def say(self, text: str, blocking: bool = True) -> None:
        self.spoken.append((text, blocking))
        self.speaking = not blocking

    def stop_speech(self) -> None:
        self.stopped += 1
        self.speaking = False

    def is_speaking(self) -> bool:
        return self.speaking


def test_speech_prompt_interrupts_and_navigates_to_option() -> None:
    audio = FakeAudioHandler()
    speech = FakeSpeechHandler()
    child = FakeOption()
    menu = PhoneTree(
        "",
        audio_handler=audio,
        speech_text="Press one for child",
        speech_handler=speech,
        options={"1": child},
    )
    inputs = Queue()
    inputs.put("1")

    menu.navigate(inputs, lambda: True, menu)

    assert speech.spoken == [("Press one for child", False)]
    assert speech.stopped == 1
    assert audio.stopped == 1
    assert child.call_args is not None
    assert child.call_args[0] is inputs
    assert child.call_args[2] is menu


def test_children_can_return_to_current_menu() -> None:
    audio = FakeAudioHandler()
    child = FakeOption()
    menu = PhoneTree("menu.wav", audio_handler=audio, options={"1": child}, children_return_to_self=True)
    inputs = Queue()
    inputs.put("1")

    menu.navigate(inputs, lambda: True, Mock())

    assert child.call_args is not None
    assert child.call_args[2] is menu


def test_return_to_main_node_navigates_without_subclass() -> None:
    audio = FakeAudioHandler()
    root = Mock()
    node = PhoneTree("", audio_handler=audio, return_to_main=True)
    inputs = Queue()

    node.navigate(inputs, lambda: True, root)

    root.navigate.assert_called_once()
    assert root.navigate.call_args.args[0] is inputs
    assert root.navigate.call_args.args[2] is root
