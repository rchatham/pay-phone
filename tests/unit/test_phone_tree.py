"""
Unit tests for the deprecated payphone.phone_system.phone_tree wrapper.

The wrapper keeps the old import path alive and auto-creates an audio
handler. These tests cover wrapper construction plus navigation behavior
inherited from payphone.core.phone_tree.PhoneTree using mocked audio so
they run quickly and deterministically on any machine.
"""

import time
from itertools import chain, repeat
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from payphone.phone_system.phone_tree import PhoneTree


class FakeAudioHandler:
    """Records playback calls; never reports an active prompt."""

    def __init__(self) -> None:
        self.played = []
        self.stopped = 0

    def play_file(self, filename: str, blocking: bool = True) -> bool:
        self.played.append((filename, blocking))
        return True

    def stop(self) -> None:
        self.stopped += 1

    def is_playing(self) -> bool:
        return False


@pytest.fixture(autouse=True)
def fake_audio(monkeypatch):
    """Replace the wrapper's eager AudioHandler with a fake instance."""
    audio = FakeAudioHandler()
    monkeypatch.setattr(
        "payphone.phone_system.phone_tree.AudioHandler",
        lambda *args, **kwargs: audio,
    )
    return audio


@pytest.fixture(autouse=True)
def fast_time(monkeypatch):
    """Remove real sleeps from navigation loops to keep tests fast."""
    monkeypatch.setattr(
        "payphone.core.phone_tree.time",
        SimpleNamespace(time=time.time, sleep=lambda *_: None),
    )


def on_hook_for(seconds: float):
    """Return a hook_status that stays off hook for a bounded time."""
    deadline = time.time() + seconds
    return lambda: time.time() < deadline


def finite_hook(true_calls: int = 3):
    """Return a hook_status that goes on hook after true_calls checks."""
    states = chain([True] * true_calls, repeat(False))
    return lambda: next(states, False)


def played_names(audio) -> list[str]:
    return [filename for filename, _ in audio.played]


@pytest.mark.unit
class TestPhoneTreeBasics:
    """Test basic PhoneTree construction and properties"""

    def test_create_simple_tree(self):
        """Test creating a simple PhoneTree node"""
        tree = PhoneTree(audio_file="menu/main.wav")
        assert tree.audio_file == "menu/main.wav"
        assert tree.options == {}
        assert tree.action is None
        assert tree.timeout == 30

    def test_create_tree_with_options(self):
        """Test creating a PhoneTree with child options"""
        child1 = PhoneTree(audio_file="menu/option1.wav")
        child2 = PhoneTree(audio_file="menu/option2.wav")

        parent = PhoneTree(
            audio_file="menu/main.wav",
            options={'1': child1, '2': child2}
        )

        assert len(parent.options) == 2
        assert parent.options['1'] == child1
        assert parent.options['2'] == child2

    def test_create_tree_with_action(self):
        """Test creating a PhoneTree with an action callback"""
        mock_action = Mock()
        tree = PhoneTree(
            audio_file="menu/action.wav",
            action=mock_action
        )
        assert tree.action == mock_action

    def test_create_tree_with_custom_timeout(self):
        """Test creating a PhoneTree with custom timeout"""
        tree = PhoneTree(
            audio_file="menu/main.wav",
            timeout=60
        )
        assert tree.timeout == 60


@pytest.mark.unit
class TestPhoneTreeNavigation:
    """Test PhoneTree navigation logic"""

    def test_navigate_to_child_option(self, fake_audio):
        """Test navigating to a child menu option"""
        child = PhoneTree(audio_file="menu/child.wav", timeout=1)
        parent = PhoneTree(
            audio_file="menu/parent.wav",
            options={'1': child},
            timeout=1,
        )

        input_queue = Queue()
        input_queue.put('1')

        parent.navigate(input_queue, on_hook_for(2.0), parent)

        # Both parent and child audio files played
        names = played_names(fake_audio)
        assert "menu/parent.wav" in names
        assert "menu/child.wav" in names

    def test_navigate_invalid_option_replays_menu(self, fake_audio):
        """Test that invalid option replays the current menu"""
        tree = PhoneTree(
            audio_file="menu/main.wav",
            options={'1': PhoneTree(audio_file="menu/option1.wav", timeout=1)},
            timeout=1,
        )

        input_queue = Queue()
        input_queue.put('9')  # Invalid option

        tree.navigate(input_queue, on_hook_for(2.0), tree)

        # Menu audio replayed after the invalid press
        names = played_names(fake_audio)
        assert names.count("menu/main.wav") >= 2
        assert "prompts/invalid_option.mp3" in names

    def test_action_execution(self, fake_audio):
        """Test that action callbacks are executed"""
        mock_action = Mock(return_value=True)

        tree = PhoneTree(
            audio_file="menu/action.wav",
            action=mock_action,
            timeout=1,
        )

        tree.navigate(Queue(), finite_hook(1))

        mock_action.assert_called_once()

    def test_hook_off_terminates_navigation(self, fake_audio):
        """Test that an on-hook phone terminates navigation before playback"""
        tree = PhoneTree(audio_file="menu/main.wav", timeout=1)

        input_queue = Queue()

        # Current behavior checks the hook before playing anything.
        tree.navigate(input_queue, lambda: False, tree)

        assert fake_audio.played == []


@pytest.mark.unit
class TestPhoneTreeTimeout:
    """Test timeout handling"""

    def test_timeout_with_no_input(self, fake_audio):
        """Test that a menu with options times out with no input and replays"""
        tree = PhoneTree(
            audio_file="menu/main.wav",
            options={'1': PhoneTree(audio_file="menu/option1.wav", timeout=1)},
            timeout=1,
        )

        start_time = time.time()
        tree.navigate(Queue(), on_hook_for(2.5), tree)
        elapsed = time.time() - start_time

        # Should timeout after ~1 second
        assert elapsed >= 1
        names = played_names(fake_audio)
        assert "prompts/timeout.mp3" in names
        assert names.count("menu/main.wav") >= 2

    def test_timeout_returns_to_parent(self, fake_audio):
        """Test that child timeout returns to the parent menu"""
        child = PhoneTree(
            audio_file="menu/child.wav",
            timeout=1,
        )
        parent = PhoneTree(
            audio_file="menu/parent.wav",
            options={'1': child},
            timeout=1,
        )

        input_queue = Queue()
        input_queue.put('1')  # Navigate to child
        # No more input - child should timeout

        parent.navigate(input_queue, on_hook_for(3.0), parent)

        # Both parent and child should have played
        names = played_names(fake_audio)
        assert "menu/child.wav" in names
        assert names.count("menu/parent.wav") >= 2


@pytest.mark.unit
class TestPhoneTreeComplexScenarios:
    """Test complex navigation scenarios"""

    def test_deep_navigation(self, fake_audio):
        """Test navigating through multiple levels"""
        level3 = PhoneTree(audio_file="menu/level3.wav", timeout=1)
        level2 = PhoneTree(
            audio_file="menu/level2.wav",
            options={'1': level3},
            timeout=1,
        )
        level1 = PhoneTree(
            audio_file="menu/level1.wav",
            options={'1': level2},
            timeout=1,
        )

        input_queue = Queue()
        input_queue.put('1')  # Go to level 2
        input_queue.put('1')  # Go to level 3

        level1.navigate(input_queue, on_hook_for(4.0), level1)

        # All three levels should have played
        names = played_names(fake_audio)
        for audio_file in ("menu/level1.wav", "menu/level2.wav", "menu/level3.wav"):
            assert audio_file in names

    def test_multiple_options(self, fake_audio):
        """Test menu with many options"""
        options = {
            key: PhoneTree(audio_file=f"menu/option_{key}.wav", timeout=1)
            for key in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '#']
        }

        main = PhoneTree(
            audio_file="menu/main.wav",
            options=options,
            timeout=1,
        )

        input_queue = Queue()
        input_queue.put('5')

        main.navigate(input_queue, on_hook_for(2.0), main)

        # Should successfully navigate to option 5
        assert "menu/option_5.wav" in played_names(fake_audio)

    def test_action_with_options(self, fake_audio):
        """Test tree node with both action and options"""
        mock_action = Mock(return_value=True)

        child = PhoneTree(audio_file="menu/child.wav", timeout=1)
        parent = PhoneTree(
            audio_file="menu/parent.wav",
            options={'1': child},
            action=mock_action,  # Has both action and options
            timeout=1,
        )

        parent.navigate(Queue(), on_hook_for(2.0), parent)

        # Action should be executed
        mock_action.assert_called_once()


@pytest.mark.unit
class TestPhoneTreeEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_options(self):
        """Test tree with no options"""
        tree = PhoneTree(audio_file="menu/main.wav", options={})
        assert tree.options == {}

    def test_none_audio_file(self):
        """Test handling of None audio file"""
        tree = PhoneTree(audio_file=None)
        assert tree.audio_file is None

    def test_rapid_input(self, fake_audio):
        """Test handling rapid keypad input"""
        tree = PhoneTree(
            audio_file="menu/main.wav",
            options={
                '1': PhoneTree(audio_file="menu/option1.wav", timeout=1),
                '2': PhoneTree(audio_file="menu/option2.wav", timeout=1),
                '3': PhoneTree(audio_file="menu/option3.wav", timeout=1),
            },
            timeout=1,
        )

        input_queue = Queue()
        # Add multiple inputs rapidly
        input_queue.put('1')
        input_queue.put('2')
        input_queue.put('3')

        tree.navigate(input_queue, on_hook_for(3.5), tree)

        # Should handle all inputs
        names = played_names(fake_audio)
        for digit in '123':
            assert f"menu/option{digit}.wav" in names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])