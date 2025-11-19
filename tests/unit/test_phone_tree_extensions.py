"""
Unit tests for PhoneTree extension dialing functionality

Tests multi-digit extension input, validation, collection,
and navigation in extension mode.
"""

import pytest
from unittest.mock import Mock
from queue import Queue
import time
from payphone.core.phone_tree import PhoneTree


@pytest.fixture
def mock_audio():
    """Provide a mock audio handler for tests"""
    audio = Mock()
    audio.play_file = Mock(return_value=True)
    audio.stop = Mock()
    audio.is_playing = Mock(return_value=False)
    return audio


@pytest.mark.unit
class TestPhoneTreeExtensionModeValidation:
    """Test extension mode validation logic"""

    def test_extension_mode_with_fixed_length(self, mock_audio):
        """Test creating extension mode with fixed length"""
        tree = PhoneTree(
            audio_file="menu/directory.mp3",
            extension_mode=True,
            extension_length=3,
            audio_handler=mock_audio,
            options={
                "101": PhoneTree("directory/alice.mp3", audio_handler=mock_audio),
                "102": PhoneTree("directory/bob.mp3", audio_handler=mock_audio),
            }
        )
        assert tree.extension_mode is True
        assert tree.extension_length == 3
        assert tree.extension_terminator == '#'
        assert tree.extension_timeout == 3.0

    def test_extension_mode_with_variable_length(self, mock_audio):
        """Test creating extension mode with variable length (terminator-based)"""
        tree = PhoneTree(
            audio_file="menu/departments.mp3",
            extension_mode=True,
            extension_terminator='#',
            extension_timeout=5.0,
            audio_handler=mock_audio,
            options={
                "10": PhoneTree("dept/sales.mp3", audio_handler=mock_audio),
                "20": PhoneTree("dept/support.mp3", audio_handler=mock_audio),
            }
        )
        assert tree.extension_mode is True
        assert tree.extension_length is None
        assert tree.extension_terminator == '#'
        assert tree.extension_timeout == 5.0

    def test_extension_mode_validates_mixed_lengths(self, mock_audio):
        """Test that mixing single and multi-digit options raises error"""
        with pytest.raises(ValueError, match="Cannot mix single-digit and multi-digit"):
            PhoneTree(
                audio_file="menu/mixed.mp3",
                extension_mode=True,
                audio_handler=mock_audio,
                options={
                    "1": PhoneTree("option1.mp3", audio_handler=mock_audio),  # Single digit
                    "101": PhoneTree("option101.mp3", audio_handler=mock_audio),  # Multi digit
                }
            )

    def test_extension_mode_validates_fixed_length_mismatch(self, mock_audio):
        """Test that fixed length validation catches mismatches"""
        with pytest.raises(ValueError, match="All option keys must be 3 digits long"):
            PhoneTree(
                audio_file="menu/directory.mp3",
                extension_mode=True,
                extension_length=3,
                audio_handler=mock_audio,
                options={
                    "101": PhoneTree("alice.mp3", audio_handler=mock_audio),  # 3 digits - OK
                    "10": PhoneTree("bob.mp3", audio_handler=mock_audio),     # 2 digits - ERROR
                }
            )

    def test_extension_mode_validates_terminator_in_keys(self, mock_audio):
        """Test that terminator cannot appear in option keys"""
        with pytest.raises(ValueError, match="Extension terminator '#' cannot appear"):
            PhoneTree(
                audio_file="menu/bad.mp3",
                extension_mode=True,
                extension_terminator='#',
                audio_handler=mock_audio,
                options={
                    "10#": PhoneTree("option.mp3", audio_handler=mock_audio),  # Contains terminator
                }
            )

    def test_extension_mode_allows_all_multi_digit_same_length(self, mock_audio):
        """Test that all multi-digit options of same length are allowed"""
        tree = PhoneTree(
            audio_file="menu/directory.mp3",
            extension_mode=True,
            extension_length=3,
            audio_handler=mock_audio,
            options={
                "101": PhoneTree("alice.mp3", audio_handler=mock_audio),
                "102": PhoneTree("bob.mp3", audio_handler=mock_audio),
                "103": PhoneTree("charlie.mp3", audio_handler=mock_audio),
                "999": PhoneTree("admin.mp3", audio_handler=mock_audio),
            }
        )
        assert len(tree.options) == 4

    def test_extension_mode_custom_terminator(self, mock_audio):
        """Test using custom terminator (e.g., '*')"""
        tree = PhoneTree(
            audio_file="menu/custom.mp3",
            extension_mode=True,
            extension_terminator='*',
            audio_handler=mock_audio,
            options={
                "10": PhoneTree("option.mp3", audio_handler=mock_audio),
            }
        )
        assert tree.extension_terminator == '*'


@pytest.mark.unit
class TestPhoneTreeExtensionCollection:
    """Test extension collection logic"""

    def test_collect_fixed_length_extension(self, mock_audio):
        """Test collecting fixed-length extension (auto-submit)"""
        tree = PhoneTree(
            audio_file="menu/directory.mp3",
            extension_mode=True,
            extension_length=3,
            audio_handler=mock_audio,
            options={
                "101": PhoneTree("directory/alice.mp3", audio_handler=mock_audio),
            }
        )

        input_queue = Queue()
        # Simulate dialing "101"
        input_queue.put('1')
        input_queue.put('0')
        input_queue.put('1')

        hook_status = Mock(side_effect=[True] * 50 + [False])  # Stay on hook, then hang up

        tree.navigate(input_queue, hook_status, tree)

        # Verify extension was processed
        assert mock_audio.play_file.call_count >= 2  # Main menu + Alice's menu

    def test_collect_variable_length_with_terminator(self, mock_audio):
        """Test collecting variable-length extension with terminator"""
        tree = PhoneTree(
            audio_file="menu/departments.mp3",
            extension_mode=True,
            extension_terminator='#',
            audio_handler=mock_audio,
            options={
                "10": PhoneTree("dept/sales.mp3", audio_handler=mock_audio),
            }
        )

        input_queue = Queue()
        # Simulate dialing "10#"
        input_queue.put('1')
        input_queue.put('0')
        input_queue.put('#')

        hook_status = Mock(side_effect=[True] * 50 + [False])

        tree.navigate(input_queue, hook_status, tree)

        # Verify extension was processed
        assert mock_audio.play_file.call_count >= 2

    def test_collect_invalid_extension(self, mock_audio):
        """Test handling of invalid extension (not in options)"""
        tree = PhoneTree(
            audio_file="menu/directory.mp3",
            extension_mode=True,
            extension_length=3,
            audio_handler=mock_audio,
            options={
                "101": PhoneTree("directory/alice.mp3", audio_handler=mock_audio),
            }
        )

        input_queue = Queue()
        # Simulate dialing invalid extension "999"
        input_queue.put('9')
        input_queue.put('9')
        input_queue.put('9')
        # Then dial valid "101"
        input_queue.put('1')
        input_queue.put('0')
        input_queue.put('1')

        hook_status = Mock(side_effect=[True] * 100 + [False])

        tree.navigate(input_queue, hook_status, tree)

        # Should have played invalid_extension.mp3 and then retried
        calls = [str(call) for call in mock_audio.play_file.call_args_list]
        assert any('invalid' in call.lower() for call in calls)


@pytest.mark.unit
class TestPhoneTreeExtensionNavigation:
    """Test navigation behavior in extension mode"""

    def test_extension_mode_stops_audio_on_first_digit(self, mock_audio):
        """Test that audio stops when first digit is pressed"""
        mock_audio.is_playing.side_effect = [True, True, False]  # Playing, then stopped

        tree = PhoneTree(
            audio_file="menu/directory.mp3",
            extension_mode=True,
            extension_length=3,
            audio_handler=mock_audio,
            options={
                "101": PhoneTree("directory/alice.mp3", audio_handler=mock_audio),
            }
        )

        input_queue = Queue()
        input_queue.put('1')
        input_queue.put('0')
        input_queue.put('1')

        hook_status = Mock(side_effect=[True] * 50 + [False])

        tree.navigate(input_queue, hook_status, tree)

        # Verify audio was stopped
        mock_audio.stop.assert_called()

    def test_mixed_navigation_single_then_extension(self, mock_audio):
        """Test navigation from single-digit menu to extension submenu"""
        # Create directory with extension mode
        directory = PhoneTree(
            audio_file="menu/directory.mp3",
            extension_mode=True,
            extension_length=3,
            audio_handler=mock_audio,
            options={
                "101": PhoneTree("directory/alice.mp3", audio_handler=mock_audio),
            }
        )

        # Main menu with single-digit options
        main_menu = PhoneTree(
            audio_file="menu/main.mp3",
            audio_handler=mock_audio,
            options={
                "1": directory,
                "2": PhoneTree("menu/other.mp3", audio_handler=mock_audio),
            }
        )

        input_queue = Queue()
        # Navigate to directory (single-digit)
        input_queue.put('1')
        # Then dial extension (multi-digit)
        input_queue.put('1')
        input_queue.put('0')
        input_queue.put('1')

        hook_status = Mock(side_effect=[True] * 15 + [False])

        main_menu.navigate(input_queue, hook_status, main_menu)

        # Should have navigated through main -> directory -> alice
        assert mock_audio.play_file.call_count >= 3

    def test_extension_mode_empty_input_replays(self, mock_audio):
        """Test that pressing terminator with no digits replays menu"""
        tree = PhoneTree(
            audio_file="menu/directory.mp3",
            extension_mode=True,
            extension_terminator='#',
            audio_handler=mock_audio,
            options={
                "10": PhoneTree("dept/sales.mp3", audio_handler=mock_audio),
            }
        )

        input_queue = Queue()
        # Press terminator immediately (no digits)
        input_queue.put('#')
        # Then valid input
        input_queue.put('1')
        input_queue.put('0')
        input_queue.put('#')

        hook_status = Mock(side_effect=[True] * 100 + [False])

        tree.navigate(input_queue, hook_status, tree)

        # Menu should replay after empty input
        calls = [str(call) for call in mock_audio.play_file.call_args_list]
        menu_plays = sum(1 for call in calls if 'directory.mp3' in call)
        assert menu_plays >= 2


@pytest.mark.unit
class TestPhoneTreeExtensionEdgeCases:
    """Test edge cases and error scenarios"""

    def test_extension_mode_defaults(self, mock_audio):
        """Test default extension mode parameters"""
        tree = PhoneTree(
            audio_file="menu/test.mp3",
            extension_mode=True,
            audio_handler=mock_audio,
            options={}
        )
        assert tree.extension_terminator == '#'
        assert tree.extension_timeout == 3.0
        assert tree.extension_length is None

    def test_regular_mode_ignores_extension_params(self, mock_audio):
        """Test that regular mode ignores extension parameters"""
        tree = PhoneTree(
            audio_file="menu/test.mp3",
            extension_mode=False,
            extension_length=3,  # Should be ignored
            audio_handler=mock_audio,
            options={
                "1": PhoneTree("option1.mp3", audio_handler=mock_audio),
            }
        )
        assert tree.extension_mode is False
        # Extension params are set but not used in regular mode

    def test_extension_mode_with_no_options(self, mock_audio):
        """Test extension mode with no options (leaf node)"""
        tree = PhoneTree(
            audio_file="menu/leaf.mp3",
            extension_mode=True,
            audio_handler=mock_audio,
            options={}
        )

        input_queue = Queue()
        hook_status = Mock(side_effect=[True, True, False])

        tree.navigate(input_queue, hook_status, tree)

        # Should play audio and return (no extension collection)
        assert mock_audio.play_file.call_count >= 1

    def test_extension_mode_validation_only_on_init(self, mock_audio):
        """Test that validation only runs when options are provided"""
        # Should not raise error even with extension_mode=True
        tree = PhoneTree(
            audio_file="menu/test.mp3",
            extension_mode=True,
            extension_length=3,
            audio_handler=mock_audio,
            options=None
        )
        assert tree.options == {}
