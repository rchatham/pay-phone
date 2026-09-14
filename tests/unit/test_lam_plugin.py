from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock

from payphone.bios.system_manager import SystemManager
from plugins.LAM.message_manager import MessageManager
from plugins.LAM.system import LAMSystem


class StubAudioHandler:
    def __init__(self):
        self.played_files = []
        self.played_tones = []
        self.stopped = False

    def play_file(self, filename, blocking=True):
        self.played_files.append((filename, blocking))
        return True

    def play_dtmf_tone(self, key):
        self.played_tones.append(key)
        return True

    def is_playing(self):
        return False

    def stop(self):
        self.stopped = True


class StopDuringPlaybackAudioHandler(StubAudioHandler):
    def __init__(self, input_queue):
        super().__init__()
        self.input_queue = input_queue
        self.poll_count = 0

    def is_playing(self):
        self.poll_count += 1
        if self.poll_count == 1:
            self.input_queue.put("0")
            return True
        return False


def build_lam_system(tmp_path):
    system = LAMSystem.__new__(LAMSystem)
    system.audio_handler = StubAudioHandler()
    system.hardware_handler = Mock(input_queue=Queue())
    system.phone_on_hook = False
    system.config = SimpleNamespace(
        AUDIO_DIR=str(tmp_path / "audio_files"),
        ENABLE_RECORDING=True,
        RECORDING_DEVICE=None,
        RECORDING_SAMPLE_RATE=44100,
        RECORDING_CHANNELS=1,
        LAM_MAX_RECORD_SECONDS=60,
    )
    system.message_manager = MessageManager(audio_dir=system.config.AUDIO_DIR)
    system.is_recording = False
    system._recording_initialized = True
    system.tts_available = False
    system.say = Mock()
    return system


def test_lam_plugin_is_discovered():
    manager = SystemManager(scan_paths=["plugins"])
    systems = manager.discover_systems()

    assert "LAM" in systems
    assert systems["LAM"].name == "Leave a Message"
    loaded_system = manager.load_system("LAM")
    assert loaded_system.__name__ == LAMSystem.__name__
    assert loaded_system.get_metadata()["name"] == "Leave a Message"


def test_message_manager_lists_messages_chronologically(tmp_path):
    manager = MessageManager(audio_dir=str(tmp_path / "audio_files"))
    (manager.messages_dir / "002.wav").write_bytes(b"two")
    (manager.messages_dir / "001.wav").write_bytes(b"one")
    (manager.messages_dir / ".hidden.wav").write_bytes(b"hidden")
    (manager.messages_dir / "notes.txt").write_text("ignore")

    assert [path.name for path in manager.list_all()] == ["001.wav", "002.wav"]
    assert manager.filename_for_next().name == "003.wav"


def test_start_message_exchange_plays_random_message_and_announces_menu(tmp_path, monkeypatch):
    system = build_lam_system(tmp_path)
    message = system.message_manager.messages_dir / "001.wav"
    message.write_bytes(b"audio")
    monkeypatch.setattr("plugins.LAM.message_manager.random.choice", lambda messages: messages[0])

    assert system.start_message_exchange() is True

    assert system.audio_handler.played_files == [
        ("lam/intro.mp3", True),
        ("lam_messages/001.wav", True),
        ("lam/menu.mp3", False),
    ]
    system.say.assert_not_called()


def test_play_prompt_preserves_nonblocking_fallback_tts(tmp_path):
    system = build_lam_system(tmp_path)
    system.audio_handler.play_file = Mock(return_value=False)

    system._play_prompt("menu", blocking=False)

    system.audio_handler.play_file.assert_called_once_with("lam/menu.mp3", blocking=False)
    system.say.assert_called_once_with(
        "Press one to leave a message for the next person. "
        "Press two to listen to past messages from the burn. "
        "Dial star, then a three digit message number, then pound to hear a specific message. "
        "Press zero to return to the system menu.",
        blocking=False,
    )


def test_setup_phone_tree_registers_message_extensions(tmp_path):
    system = build_lam_system(tmp_path)
    (system.message_manager.messages_dir / "001.wav").write_bytes(b"one")

    tree = system.setup_phone_tree()

    assert tree.hybrid_mode is True
    assert tree.extension_prefix == "*"
    assert set(tree.options) == {"1", "2", "001"}


def test_play_extension_plays_specific_message(tmp_path):
    system = build_lam_system(tmp_path)
    (system.message_manager.messages_dir / "001.wav").write_bytes(b"one")

    assert system.play_extension("001") is True

    assert system.audio_handler.played_files == [
        ("lam/playing_message.mp3", True),
        ("lam_messages/001.wav", True),
    ]


def test_browse_messages_plays_chronological_playlist(tmp_path):
    system = build_lam_system(tmp_path)
    (system.message_manager.messages_dir / "002.wav").write_bytes(b"two")
    (system.message_manager.messages_dir / "001.wav").write_bytes(b"one")

    assert system.browse_messages() is True

    assert system.audio_handler.played_files == [
        ("lam/browse_intro.mp3", True),
        ("lam_messages/001.wav", False),
        ("lam_messages/002.wav", False),
        ("lam/end_of_messages.mp3", True),
    ]


def test_browse_messages_returns_to_menu_when_stopped_during_playback(tmp_path):
    system = build_lam_system(tmp_path)
    system.audio_handler = StopDuringPlaybackAudioHandler(system.hardware_handler.input_queue)
    (system.message_manager.messages_dir / "001.wav").write_bytes(b"one")
    (system.message_manager.messages_dir / "002.wav").write_bytes(b"two")

    assert system.browse_messages() is True

    assert system.audio_handler.stopped is True
    assert system.audio_handler.played_files == [
        ("lam/browse_intro.mp3", True),
        ("lam_messages/001.wav", False),
        ("lam/returning_to_menu.mp3", True),
    ]


def test_record_message_initializes_recorder_before_first_use(tmp_path, monkeypatch):
    system = build_lam_system(tmp_path)
    system._recording_initialized = False
    system.phone_tree = Mock(options={})

    def start_recording(filename, timeout=60):
        filename.write_bytes(b"recorded")
        system.hardware_handler.input_queue.put("#")

    init_recording = Mock()
    monkeypatch.setattr("plugins.LAM.record.init", init_recording)
    monkeypatch.setattr("plugins.LAM.record.start_recording", start_recording)
    monkeypatch.setattr("plugins.LAM.record.stop_recording", Mock())

    assert system.record_message() is True

    init_recording.assert_called_once_with(
        preferred_device=None,
        preferred_samplerate=44100,
        preferred_channels=1,
    )
    assert system._recording_initialized is True


def test_record_message_respects_disabled_recording_config(tmp_path, monkeypatch):
    system = build_lam_system(tmp_path)
    system._recording_initialized = False
    system.config.ENABLE_RECORDING = False
    init_recording = Mock()
    start_recording = Mock()
    monkeypatch.setattr("plugins.LAM.record.init", init_recording)
    monkeypatch.setattr("plugins.LAM.record.start_recording", start_recording)

    assert system.record_message() is True

    init_recording.assert_not_called()
    start_recording.assert_not_called()
    assert system.audio_handler.played_files == [("lam/recording_unavailable.mp3", True)]


def test_record_message_reports_initialization_failure(tmp_path, monkeypatch):
    system = build_lam_system(tmp_path)
    system._recording_initialized = False
    init_recording = Mock(side_effect=RuntimeError("no input device"))
    start_recording = Mock()
    monkeypatch.setattr("plugins.LAM.record.init", init_recording)
    monkeypatch.setattr("plugins.LAM.record.start_recording", start_recording)

    assert system.record_message() is True

    init_recording.assert_called_once_with(
        preferred_device=None,
        preferred_samplerate=44100,
        preferred_channels=1,
    )
    start_recording.assert_not_called()
    assert system.audio_handler.played_files == [("lam/recording_unavailable.mp3", True)]


def test_record_message_saves_on_pound(tmp_path, monkeypatch):
    system = build_lam_system(tmp_path)
    system.phone_tree = Mock(options={})

    def start_recording(filename, timeout=60):
        filename.write_bytes(b"recorded")
        system.hardware_handler.input_queue.put("#")

    stop_recording = Mock()
    monkeypatch.setattr("plugins.LAM.record.start_recording", start_recording)
    monkeypatch.setattr("plugins.LAM.record.stop_recording", stop_recording)

    assert system.record_message() is True

    assert stop_recording.called
    assert (system.message_manager.messages_dir / "001.wav").exists()
    assert system.audio_handler.played_tones == ["#"]
    assert "001" in system.phone_tree.options


def test_record_message_uses_configured_max_duration(tmp_path, monkeypatch):
    system = build_lam_system(tmp_path)
    system.config.LAM_MAX_RECORD_SECONDS = 0
    system.phone_tree = Mock(options={})

    def start_recording(filename, timeout=60):
        filename.write_bytes(b"recorded")

    stop_recording = Mock()
    monkeypatch.setattr("plugins.LAM.record.start_recording", start_recording)
    monkeypatch.setattr("plugins.LAM.record.stop_recording", stop_recording)

    assert system.record_message() is True

    assert stop_recording.called
    assert (system.message_manager.messages_dir / "001.wav").exists()
    assert "001" in system.phone_tree.options


def test_record_message_cancels_on_zero(tmp_path, monkeypatch):
    system = build_lam_system(tmp_path)

    def start_recording(filename, timeout=60):
        filename.write_bytes(b"recorded")
        system.hardware_handler.input_queue.put("0")

    monkeypatch.setattr("plugins.LAM.record.start_recording", start_recording)
    monkeypatch.setattr("plugins.LAM.record.stop_recording", Mock())

    assert system.record_message() is True

    assert not (system.message_manager.messages_dir / "001.wav").exists()


def test_play_random_message_with_empty_archive_plays_no_messages_prompt(tmp_path):
    system = build_lam_system(tmp_path)

    assert system.play_random_message() is True

    assert system.audio_handler.played_files == [("lam/no_messages.mp3", True)]


def test_play_prompt_falls_back_to_tts_when_generated_audio_missing(tmp_path):
    system = build_lam_system(tmp_path)
    system.audio_handler.play_file = Mock(return_value=False)

    system._play_prompt("intro")

    system.audio_handler.play_file.assert_called_once_with("lam/intro.mp3", blocking=True)
    system.say.assert_called_once_with("Leave a message. First, listen to someone who came before you.", blocking=True)


def test_browse_messages_with_empty_archive_plays_no_past_messages_prompt(tmp_path):
    system = build_lam_system(tmp_path)

    assert system.browse_messages() is True

    assert system.audio_handler.played_files == [("lam/no_past_messages.mp3", True)]


def test_browse_messages_returns_when_phone_hangs_up(tmp_path):
    system = build_lam_system(tmp_path)
    system.phone_on_hook = True
    (system.message_manager.messages_dir / "001.wav").write_bytes(b"one")

    assert system.browse_messages() is True

    assert system.audio_handler.played_files == [("lam/browse_intro.mp3", True)]


def test_play_extension_reports_missing_message(tmp_path):
    system = build_lam_system(tmp_path)

    assert system.play_extension("404") is True

    assert system.audio_handler.played_files == [("lam/message_not_found.mp3", True)]


def test_register_extension_noops_without_phone_tree(tmp_path):
    system = build_lam_system(tmp_path)
    system.phone_tree = None
    message = system.message_manager.messages_dir / "001.wav"

    system._register_extension("001", message)

    assert system.phone_tree is None


def test_consume_stop_key_returns_false_when_queue_empty(tmp_path):
    system = build_lam_system(tmp_path)

    assert system._consume_stop_key() is False


def test_consume_stop_key_accepts_zero_and_pound(tmp_path):
    system = build_lam_system(tmp_path)
    system.hardware_handler.input_queue.put("0")

    assert system._consume_stop_key() is True

    system.hardware_handler.input_queue.put("#")

    assert system._consume_stop_key() is True


def test_consume_stop_key_ignores_non_stop_key(tmp_path):
    system = build_lam_system(tmp_path)
    system.hardware_handler.input_queue.put("5")

    assert system._consume_stop_key() is False


def test_record_message_rerecords_on_star_then_saves_next_take(tmp_path, monkeypatch):
    system = build_lam_system(tmp_path)
    system.phone_tree = Mock(options={})
    attempts = []

    def start_recording(filename, timeout=60):
        attempts.append(filename)
        filename.write_bytes(b"recorded")
        system.hardware_handler.input_queue.put("*" if len(attempts) == 1 else "#")

    monkeypatch.setattr("plugins.LAM.record.start_recording", start_recording)
    monkeypatch.setattr("plugins.LAM.record.stop_recording", Mock())

    assert system.record_message() is True

    assert len(attempts) == 2
    assert (system.message_manager.messages_dir / "001.wav").exists()
    assert "001" in system.phone_tree.options
    assert ("lam/recording_again.mp3", True) in system.audio_handler.played_files


def test_record_message_stops_and_deletes_partial_file_on_hangup(tmp_path, monkeypatch):
    system = build_lam_system(tmp_path)
    system.phone_on_hook = True

    def start_recording(filename, timeout=60):
        filename.write_bytes(b"recorded")

    stop_recording = Mock()
    monkeypatch.setattr("plugins.LAM.record.start_recording", start_recording)
    monkeypatch.setattr("plugins.LAM.record.stop_recording", stop_recording)

    assert system.record_message() is True

    stop_recording.assert_called_once_with()
    assert not (system.message_manager.messages_dir / "001.wav").exists()


def test_record_message_deletes_partial_file_on_start_error(tmp_path, monkeypatch):
    system = build_lam_system(tmp_path)

    def start_recording(filename, timeout=60):
        filename.write_bytes(b"partial")
        raise RuntimeError("input failure")

    monkeypatch.setattr("plugins.LAM.record.start_recording", start_recording)
    monkeypatch.setattr("plugins.LAM.record.stop_recording", Mock())

    assert system.record_message() is True

    assert not (system.message_manager.messages_dir / "001.wav").exists()
    assert ("lam/recording_error.mp3", True) in system.audio_handler.played_files


def test_message_manager_helpers_handle_random_paths_and_deletes(tmp_path, monkeypatch):
    manager = MessageManager(audio_dir=str(tmp_path / "audio_files"))
    message = manager.messages_dir / "001.wav"
    message.write_bytes(b"one")
    monkeypatch.setattr("plugins.LAM.message_manager.random.choice", lambda messages: messages[0])

    assert manager.total_count() == 1
    assert manager.get_random() == message
    assert manager.relative_audio_path(message) == str(Path("lam_messages") / "001.wav")

    manager.delete_file(message)

    assert not message.exists()
    assert manager.get_random() is None
