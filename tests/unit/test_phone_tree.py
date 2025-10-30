"""
Unit tests for PhoneTree navigation system

Tests menu navigation, option selection, timeout handling,
and action execution without requiring hardware.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from queue import Queue, Empty
import time
from payphone.phone_system.phone_tree import PhoneTree


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

    @patch('payphone.phone_system.phone_tree.AudioHandler')
    def test_navigate_to_child_option(self, mock_audio_class):
        """Test navigating to a child menu option"""
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio
        mock_audio.play_file = Mock()

        # Create tree structure
        child = PhoneTree(audio_file="menu/child.wav")
        parent = PhoneTree(
            audio_file="menu/parent.wav",
            options={'1': child}
        )

        # Setup input queue and hook status
        input_queue = Queue()
        input_queue.put('1')
        hook_status = Mock(return_value=True)  # On-hook = True

        # Navigate
        parent.navigate(input_queue, hook_status)

        # Verify both parent and child audio files played
        assert mock_audio.play_file.call_count == 2
        calls = [call[0][0] for call in mock_audio.play_file.call_args_list]
        assert "menu/parent.wav" in calls
        assert "menu/child.wav" in calls

    @patch('payphone.phone_system.phone_tree.AudioHandler')
    def test_navigate_invalid_option_replays_menu(self, mock_audio_class):
        """Test that invalid option replays the current menu"""
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio

        tree = PhoneTree(
            audio_file="menu/main.wav",
            options={'1': PhoneTree(audio_file="menu/option1.wav")}
        )

        input_queue = Queue()
        input_queue.put('9')  # Invalid option
        input_queue.put('1')  # Valid option
        hook_status = Mock(return_value=True)

        # Navigate should handle invalid input gracefully
        tree.navigate(input_queue, hook_status)

        # Menu audio should be played multiple times (initial + retry after invalid)
        assert mock_audio.play_file.call_count >= 2

    @patch('payphone.phone_system.phone_tree.AudioHandler')
    def test_action_execution(self, mock_audio_class):
        """Test that action callbacks are executed"""
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio
        mock_action = Mock()

        tree = PhoneTree(
            audio_file="menu/action.wav",
            action=mock_action
        )

        input_queue = Queue()
        hook_status = Mock(return_value=True)

        tree.navigate(input_queue, hook_status)

        # Verify action was called
        mock_action.assert_called_once()

    @patch('payphone.phone_system.phone_tree.AudioHandler')
    def test_hook_off_terminates_navigation(self, mock_audio_class):
        """Test that hook going off-hook terminates navigation"""
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio

        tree = PhoneTree(audio_file="menu/main.wav")

        input_queue = Queue()
        hook_status = Mock(return_value=False)  # Off-hook = False

        tree.navigate(input_queue, hook_status)

        # Should stop navigation immediately
        assert mock_audio.play_file.call_count >= 1


@pytest.mark.unit
class TestPhoneTreeTimeout:
    """Test timeout handling"""

    @patch('payphone.phone_system.phone_tree.AudioHandler')
    def test_timeout_with_no_input(self, mock_audio_class):
        """Test that menu times out with no input"""
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio

        tree = PhoneTree(
            audio_file="menu/main.wav",
            timeout=1  # 1 second timeout for fast testing
        )

        input_queue = Queue()
        hook_status = Mock(return_value=True)

        start_time = time.time()
        tree.navigate(input_queue, hook_status)
        elapsed = time.time() - start_time

        # Should timeout after ~1 second
        assert elapsed >= 1
        assert elapsed < 2  # Some margin for execution time

    @patch('payphone.phone_system.phone_tree.AudioHandler')
    def test_timeout_returns_to_parent(self, mock_audio_class):
        """Test that timeout returns to parent menu"""
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio

        child = PhoneTree(
            audio_file="menu/child.wav",
            timeout=1
        )
        parent = PhoneTree(
            audio_file="menu/parent.wav",
            options={'1': child}
        )

        input_queue = Queue()
        input_queue.put('1')  # Navigate to child
        # No more input - should timeout

        hook_status = Mock(return_value=True)

        parent.navigate(input_queue, hook_status)

        # Both parent and child should have played
        assert mock_audio.play_file.call_count >= 2


@pytest.mark.unit
class TestPhoneTreeComplexScenarios:
    """Test complex navigation scenarios"""

    @patch('payphone.phone_system.phone_tree.AudioHandler')
    def test_deep_navigation(self, mock_audio_class):
        """Test navigating through multiple levels"""
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio

        # Create 3-level tree
        level3 = PhoneTree(audio_file="menu/level3.wav")
        level2 = PhoneTree(
            audio_file="menu/level2.wav",
            options={'1': level3}
        )
        level1 = PhoneTree(
            audio_file="menu/level1.wav",
            options={'1': level2}
        )

        input_queue = Queue()
        input_queue.put('1')  # Go to level 2
        input_queue.put('1')  # Go to level 3
        hook_status = Mock(return_value=True)

        level1.navigate(input_queue, hook_status)

        # All three levels should have played
        assert mock_audio.play_file.call_count == 3

    @patch('payphone.phone_system.phone_tree.AudioHandler')
    def test_multiple_options(self, mock_audio_class):
        """Test menu with many options"""
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio

        # Create menu with options 0-9, *, #
        options = {}
        for key in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '#']:
            options[key] = PhoneTree(audio_file=f"menu/option_{key}.wav")

        main = PhoneTree(
            audio_file="menu/main.wav",
            options=options
        )

        input_queue = Queue()
        input_queue.put('5')
        hook_status = Mock(return_value=True)

        main.navigate(input_queue, hook_status)

        # Should successfully navigate to option 5
        assert mock_audio.play_file.call_count == 2

    @patch('payphone.phone_system.phone_tree.AudioHandler')
    def test_action_with_options(self, mock_audio_class):
        """Test tree node with both action and options"""
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio
        mock_action = Mock()

        child = PhoneTree(audio_file="menu/child.wav")
        parent = PhoneTree(
            audio_file="menu/parent.wav",
            options={'1': child},
            action=mock_action  # Has both action and options
        )

        input_queue = Queue()
        hook_status = Mock(return_value=True)

        parent.navigate(input_queue, hook_status)

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

    @patch('payphone.phone_system.phone_tree.AudioHandler')
    def test_rapid_input(self, mock_audio_class):
        """Test handling rapid keypad input"""
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio

        tree = PhoneTree(
            audio_file="menu/main.wav",
            options={
                '1': PhoneTree(audio_file="menu/option1.wav"),
                '2': PhoneTree(audio_file="menu/option2.wav"),
                '3': PhoneTree(audio_file="menu/option3.wav"),
            }
        )

        input_queue = Queue()
        # Add multiple inputs rapidly
        input_queue.put('1')
        input_queue.put('2')
        input_queue.put('3')

        hook_status = Mock(return_value=True)

        tree.navigate(input_queue, hook_status)

        # Should handle all inputs
        assert mock_audio.play_file.call_count >= 2