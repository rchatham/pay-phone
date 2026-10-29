"""Focused runtime/admin integration; no real GPIO, audio, network or main entrypoint."""
import json
import queue
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from payphone.bios.auth import AdminAuthenticator, AdminSession
from payphone.bios.bootloader import BIOSBootloader
from payphone.bios.config_manager import ConfigManager
from payphone.bios.system_manager import SystemInfo, SystemManager
from payphone.config import persistence
from payphone.core.phone_tree import PhoneTree
from payphone.core.runtime import PhoneRuntime, SessionAudio, shared_runtime
from payphone.core.system import PhoneSystemBase


class FakeAudio:
    def __init__(self, audio_dir=""):
        self.audio_dir = audio_dir
        self.played = []
        self.stops = 0
        self.playing = False
        self.tones = []

    def play_file(self, name, blocking=True):
        self.played.append(name)
        return True

    def stop(self):
        self.stops += 1
        self.playing = False

    def is_playing(self):
        return self.playing

    def play_dtmf_tone(self, key):
        self.tones.append(key)
        return True


class FakeHardware:
    def __init__(self, **kwargs):
        self.input_queue = queue.Queue()

    def start(self):
        return True

    def set_hook_callback(self, callback):
        self.callback = callback

    def stop(self):
        pass


class FakeSpeech:
    def __init__(self, runtime):
        self.executable = "mock-offline-speech"
        self.texts = []

    def say(self, text, session, blocking=True):
        self.texts.append(text)

    def stop_speech(self):
        pass

    def is_speaking(self):
        return False


class SimpleSystem(PhoneSystemBase):
    def setup_phone_tree(self):
        return PhoneTree("", speech_text="Simple system", speech_handler=self, audio_handler=self.audio_handler,
                         options={"1": PhoneTree("", audio_handler=self.audio_handler)})


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate(), "Timed out waiting for mocked call state"


@pytest.fixture
def bios_factory(monkeypatch, tmp_path):
    monkeypatch.setenv("PAYPHONE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("BIOS_ADMIN_PASSCODE", "938271")
    monkeypatch.delenv("BIOS_ESCAPE_SEQUENCE", raising=False)
    monkeypatch.delenv("BIOS_ESCAPE_TIMEOUT", raising=False)
    audio_factory = Mock(side_effect=FakeAudio)
    hardware_factory = Mock(side_effect=FakeHardware)
    monkeypatch.setattr("payphone.core.system.AudioHandler", audio_factory)
    monkeypatch.setattr("payphone.core.system.GPIOHandler", hardware_factory)
    monkeypatch.setattr("payphone.core.system.OfflineSpeech", FakeSpeech)
    instances = []

    def make(systems=None):
        bios = BIOSBootloader(SimpleNamespace(AUDIO_DIR=str(tmp_path), USE_GPIO=True,
                                              KEYPAD_ROW_PINS=[], KEYPAD_COL_PINS=[], HOOK_SWITCH_PIN=17))
        if systems is not None:
            manager = Mock()
            infos = {sid: SystemInfo(sid, cls.__name__, "mock", cls.__name__) for sid, cls in systems.items()}
            manager.discovered_systems = infos
            manager.discover_systems.return_value = infos
            manager.list_systems.return_value = [infos[sid] for sid in sorted(infos)]
            manager.load_system.side_effect = lambda sid: systems.get(sid)
            bios.system_manager = manager
        instances.append(bios)
        return bios

    make.audio_factory = audio_factory
    make.hardware_factory = hardware_factory
    yield make
    for bios in instances:
        bios.shutdown()


def enter_keys(bios, text):
    for key in text:
        bios.runtime.hardware.input_queue.put(key)


def prompt_seen(bios, text, after=0):
    return any(text in prompt for prompt in bios.runtime.speech.texts[after:])


def new_runtime():
    runtime = PhoneRuntime(FakeHardware(), FakeAudio())
    runtime.off_hook = True
    return runtime, runtime.new_session()


def drain(q):
    result = []
    while not q.empty():
        result.append(q.get_nowait())
    return "".join(result)


@pytest.mark.parametrize("text,expected", [("*1", "*1"), ("**2", "**2"), ("****1", "****1"), ("12*34", "12*34"), ("**#", "**#")])
def test_escape_unmatched_prefix_preserves_order(text, expected):
    runtime, session = new_runtime()
    for key in text:
        runtime.route_key(key)
    runtime.flush_prefix(time.monotonic() + 2)
    assert drain(session.input_queue) == expected
    assert not session.cancelled.is_set()


def test_escape_timeout_flushes_before_later_keys():
    runtime, session = new_runtime()
    runtime.route_key("*", 10)
    runtime.route_key("*", 11.1)
    runtime.route_key("1", 11.2)
    assert drain(session.input_queue) == "**1"


def test_escape_cancels_media_and_never_reaches_plugin():
    runtime, session = new_runtime()
    runtime.audio.playing = True
    runtime.speech = Mock()
    for key in "***#":
        runtime.route_key(key)
    assert session.cancelled.is_set()
    assert session.reason == "escape"
    assert drain(session.input_queue) == ""
    assert runtime.audio.stops == 1
    runtime.speech.stop_speech.assert_called_once()
    assert not SessionAudio(runtime, session).play_file("late.wav")
    assert runtime.audio.played == []


def test_dispatcher_is_single_raw_consumer():
    runtime, session = new_runtime()
    runtime.start_dispatcher()
    original = runtime._dispatcher
    runtime.start_dispatcher()
    assert runtime._dispatcher is original
    for key in "1234":
        runtime.hardware.input_queue.put(key)
    wait_until(lambda: session.input_queue.qsize() == 4)
    assert drain(session.input_queue) == "1234"
    runtime.stop()
    assert not original.is_alive()


@pytest.mark.parametrize("passcode", [None, "", "12345", "1234567890123", "12345x", "１２３４５６"])
def test_admin_fails_closed_without_valid_environment(monkeypatch, passcode):
    if passcode is None:
        monkeypatch.delenv("BIOS_ADMIN_PASSCODE", raising=False)
    else:
        monkeypatch.setenv("BIOS_ADMIN_PASSCODE", passcode)
    auth = AdminAuthenticator()
    assert not auth.configured
    assert not auth.verify("123456")


def test_auth_constant_time_cooldown_expiry(monkeypatch):
    monkeypatch.setenv("BIOS_ADMIN_PASSCODE", "938271")
    clock = Mock(return_value=10)
    monkeypatch.setattr("payphone.bios.auth.time.monotonic", clock)
    compare = Mock(wraps=__import__("hmac").compare_digest)
    monkeypatch.setattr("payphone.bios.auth.hmac.compare_digest", compare)
    auth = AdminAuthenticator()
    for _ in range(3):
        assert not auth.verify("000000")
    assert auth.blocked_until == 40
    assert not auth.verify("938271")
    clock.return_value = 41
    assert auth.verify("938271")
    assert compare.call_count == 4


def test_capability_revokes_on_inactivity_hangup_cancel(monkeypatch):
    runtime, session = new_runtime()
    capability = AdminSession(runtime, session, 5)
    capability.require_authorized()
    session.last_activity -= 6
    with pytest.raises(PermissionError):
        capability.require_authorized()
    session.last_activity = time.monotonic()
    with pytest.raises(PermissionError):
        capability.require_authorized()
    for condition in ("hangup", "escape"):
        runtime.off_hook = True
        fresh = AdminSession(runtime, session)
        if condition == "hangup":
            runtime.off_hook = False
        else:
            session.cancel("escape")
        with pytest.raises(PermissionError):
            fresh.require_authorized()


def test_shared_plugins_allocate_no_hardware_or_audio(bios_factory):
    bios = bios_factory({"simple": SimpleSystem})
    bios.runtime.off_hook = True
    bios._bind_session(bios.runtime.new_session())
    with shared_runtime(bios.runtime):
        plugin = SimpleSystem(bios.config)
    assert bios_factory.audio_factory.call_count == 1
    assert bios_factory.hardware_factory.call_count == 1
    assert plugin.runtime is bios.runtime
    assert plugin.hardware_handler.input_queue is bios.hardware_handler.input_queue
    assert plugin.is_call_active()
    bios.runtime.cancel("escape")
    assert plugin.phone_on_hook
    assert not plugin.is_call_active()
    with pytest.raises(RuntimeError):
        plugin.start_call()


def test_tree_default_audio_reuses_active_runtime(bios_factory, monkeypatch):
    bios = bios_factory({})
    bios.runtime.off_hook = True
    session = bios.runtime.new_session()
    monkeypatch.setattr("payphone.core.phone_tree.AudioHandler", Mock(side_effect=AssertionError("Duplicate audio owner")))
    with shared_runtime(bios.runtime):
        tree = PhoneTree("")
    assert isinstance(tree.audio_handler, SessionAudio)
    assert tree.audio_handler.session is session
    assert bios_factory.audio_factory.call_count == 1


def test_no_overlapping_call_when_cancelled_action_refuses_exit(bios_factory):
    entered = threading.Event()
    release = threading.Event()

    class Stubborn(SimpleSystem):
        def _call_handler(self):
            entered.set()
            release.wait(3)

    bios = bios_factory({"slow": Stubborn})
    bios.bios_config.set_default_system("slow")
    bios.hook_status_changed(True)
    assert entered.wait(2)
    original = bios.current_call
    enter_keys(bios, "***#")
    wait_until(lambda: bios._session.cancelled.is_set())
    assert not bios.start_call()
    assert bios.current_call is original
    assert not prompt_seen(bios, "Select a phone system")
    release.set()
    wait_until(lambda: prompt_seen(bios, "Select a phone system"))
    assert bios.current_call is original  # Escape transitions on the same worker.


def test_public_selection_is_nonpersistent_and_unavailable_default_falls_back(bios_factory):
    bios = bios_factory({"simple": SimpleSystem})
    bios.hook_status_changed(True)
    wait_until(lambda: prompt_seen(bios, "Select a phone system"))
    enter_keys(bios, "1")
    wait_until(lambda: bios.current_system_id == "simple")
    assert bios.bios_config.get_default_system() is None
    assert not bios.bios_config.config_path.exists()
    bios.hook_status_changed(False)
    bios.current_call.join(2)
    bios.bios_config.set_default_system("missing")
    offset = len(bios.runtime.speech.texts)
    bios.hook_status_changed(True)
    wait_until(lambda: prompt_seen(bios, "default system is unavailable", offset))
    assert bios.current_system is None
    assert json.loads(bios.bios_config.config_path.read_text())["default_system"] == "missing"


def test_failed_atomic_save_preserves_disk_and_memory(tmp_path, monkeypatch):
    path = tmp_path / "bios.json"
    config = ConfigManager(str(path))
    config.set_default_system("old")
    original = path.read_bytes()
    monkeypatch.setattr("payphone.config.persistence.os.replace", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        config.set_default_system("new")
    assert path.read_bytes() == original
    assert config.get_default_system() == "old"
    assert list(tmp_path.iterdir()) == [path]


def test_atomic_json_rejects_nan_before_creating_file(tmp_path):
    path = tmp_path / "new" / "state.json"
    with pytest.raises(ValueError):
        persistence.atomic_write_json(path, {"invalid": float("nan")})
    assert not path.parent.exists()


def test_corrupt_config_is_not_overwritten(tmp_path):
    path = tmp_path / "bios.json"
    path.write_text('{"default_system": 22}')
    original = path.read_bytes()
    assert ConfigManager(str(path)).get_default_system() is None
    assert path.read_bytes() == original


def test_legacy_migration_does_not_promote_last_system(tmp_path, monkeypatch):
    monkeypatch.setattr("payphone.bios.config_manager.REPOSITORY_ROOT", tmp_path)
    monkeypatch.setenv("PAYPHONE_STATE_DIR", str(tmp_path / "state"))
    legacy = tmp_path / ".bios_config.json"
    legacy.write_text('{"last_system": "LAM", "auto_launch": true}')
    config = ConfigManager()
    assert config.get_default_system() is None
    assert config.get_last_system() == "LAM"
    assert config.config_path.exists()
    assert legacy.exists()


def test_explicit_default_and_discovery_are_anchored_across_cwd(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYPHONE_STATE_DIR", str(tmp_path / "state"))
    first = ConfigManager()
    first.set_default_system("LAM")
    paths = first.get_scan_paths()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    second = ConfigManager()
    assert second.get_default_system() == "LAM"
    assert second.config_path == first.config_path
    assert second.get_scan_paths() == paths
    manager = SystemManager(["plugins"])
    assert "LAM" in manager.discover_systems()


def test_leaf_does_not_execute_or_reenter_menu_after_cancellation():
    active = True
    audio = FakeAudio()
    root = Mock()

    def action():
        nonlocal active
        active = False
        return False

    node = PhoneTree("", action=action, audio_handler=audio)
    node.navigate(queue.Queue(), lambda: active, root)
    root.navigate.assert_not_called()
    audio.playing = True
    calls = 0

    def cancelled_while_prompt_plays():
        nonlocal calls
        calls += 1
        return calls < 3

    action_mock = Mock()
    PhoneTree("", action=action_mock, audio_handler=audio).navigate(queue.Queue(), cancelled_while_prompt_plays, root)
    action_mock.assert_not_called()


@pytest.mark.parametrize("entered,authorized", [("938271#", True), ("938271111111111111111111#", False), ("93827*1#", False), ("000000#", False)])
def test_authentication_bounded_input_without_pin_logging(monkeypatch, caplog, entered, authorized):
    monkeypatch.setenv("BIOS_ADMIN_PASSCODE", "938271")
    runtime, session = new_runtime()
    system = SimpleSystem.__new__(SimpleSystem)
    system.runtime = runtime
    system.running = True
    system._bind_session(session)

    def speak(text):
        if text.startswith("Enter the administrator"):
            for key in entered:
                session.input_queue.put(key)

    system.speak = speak
    result = AdminAuthenticator().authenticate(system)
    assert (result is not None) is authorized
    assert not session.suppress_tones
    assert "938271" not in caplog.text
    assert entered not in caplog.text


def test_authentication_cancel_does_not_grant_capability(monkeypatch):
    monkeypatch.setenv("BIOS_ADMIN_PASSCODE", "938271")
    runtime, session = new_runtime()
    system = SimpleSystem.__new__(SimpleSystem)
    system.runtime = runtime
    system.running = True
    system._bind_session(session)
    system.speak = lambda text: session.cancel("escape")
    assert AdminAuthenticator().authenticate(system) is None


def test_persistent_mutation_rechecks_capability(bios_factory):
    bios = bios_factory({"simple": SimpleSystem})
    bios.runtime.off_hook = True
    bios._bind_session(bios.runtime.new_session())
    capability = AdminSession(bios.runtime, bios._session)
    bios.speak = lambda text: (bios._session.input_queue.put("1"), capability.revoke())
    bios._save_default("simple", capability)
    assert not bios.bios_config.config_path.exists()


def test_serial_key_events_never_log_pin(caplog):
    from payphone.hardware.serial_handler import SerialHandler
    handler = SerialHandler.__new__(SerialHandler)
    handler.input_queue = queue.Queue()
    for key in "938271":
        handler._process_data(f"KEY:{key}")
    assert drain(handler.input_queue) == "938271"
    assert not caplog.records
    handler._process_data("KEY:938271")
    assert handler.input_queue.empty()


def test_cancelled_session_exposes_on_hook_during_recording(bios_factory):
    bios = bios_factory({"simple": SimpleSystem})
    bios.runtime.off_hook = True
    bios._bind_session(bios.runtime.new_session())
    with shared_runtime(bios.runtime):
        plugin = SimpleSystem(bios.config)
    recording_stopped = threading.Event()
    consumer_entered = threading.Event()

    def recording_loop():
        consumer_entered.set()
        while not plugin.phone_on_hook:
            try:
                plugin.hardware_handler.input_queue.get(timeout=0.02)
            except queue.Empty:
                continue
        recording_stopped.set()

    consumer = threading.Thread(target=recording_loop)
    consumer.start()
    assert consumer_entered.wait(1)
    for key in "***#":
        bios.runtime.route_key(key)
    assert recording_stopped.wait(1)
    consumer.join(1)
    assert not consumer.is_alive()


def test_bios_dependency_failure_does_not_hot_loop(bios_factory):
    bios = bios_factory({})
    bios.runtime.speech.say = Mock(side_effect=RuntimeError("offline speech unavailable"))
    bios.hook_status_changed(True)
    bios.current_call.join(2)
    assert not bios.current_call.is_alive()
    assert bios.runtime.speech.say.call_count == 1
    assert bios._session.cancelled.is_set()


def test_extension_prompt_interruption_preserves_first_digit_order(caplog):
    audio = FakeAudio()
    audio.playing = True
    action = Mock(return_value=False)
    leaf = PhoneTree("", audio_handler=audio, action=action)
    menu = PhoneTree("", audio_handler=audio, options={"123": leaf}, extension_mode=True, extension_length=3)
    inputs = queue.Queue()
    for key in "123":
        inputs.put(key)
    with caplog.at_level("DEBUG"):
        menu.navigate(inputs, lambda: True)
    action.assert_called_once()
    assert "123" not in caplog.text
    assert "Extension input buffered" in caplog.text


def test_configurable_escape_environment(bios_factory, monkeypatch):
    monkeypatch.setenv("BIOS_ESCAPE_SEQUENCE", "##*#")
    monkeypatch.setenv("BIOS_ESCAPE_TIMEOUT", "0.5")
    bios = bios_factory({})
    assert bios.runtime.escape_sequence == "##*#"
    assert bios.runtime.escape_timeout == 0.5
    monkeypatch.setenv("BIOS_ESCAPE_SEQUENCE", "not-a-key")
    invalid = bios_factory({})
    assert invalid.runtime.escape_sequence == "***#"


def test_quick_pickup_after_hangup_waits_for_old_action_then_starts(bios_factory, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    second_entered = threading.Event()
    event_dequeued = threading.Event()
    allow_dispatch = threading.Event()
    event_processed = threading.Event()
    sessions = []
    consumers = 0
    maximum = 0

    class Slow(SimpleSystem):
        def _call_handler(self):
            nonlocal consumers, maximum
            consumers += 1
            maximum = max(maximum, consumers)
            sessions.append(self._session)
            if len(sessions) == 1:
                entered.set()
                assert release.wait(3)
            else:
                second_entered.set()
                self._session.cancelled.wait(3)
            consumers -= 1

    bios = bios_factory({"slow": Slow})
    original_route = bios.runtime._route_event

    def paused_route(event):
        if event.key == "2":
            event_dequeued.set()
            assert allow_dispatch.wait(3)
            original_route(event)
            event_processed.set()
        else:
            original_route(event)

    monkeypatch.setattr(bios.runtime, "_route_event", paused_route)
    bios.bios_config.set_default_system("slow")
    bios.hook_status_changed(True)
    assert entered.wait(1)
    original = bios.current_call
    old_queue = bios.hardware_handler.input_queue
    try:
        bios.hook_status_changed(False)
        bios.hook_status_changed(True)
        assert bios.current_call is original
        assert not second_entered.is_set()
        enter_keys(bios, "2")
        assert event_dequeued.wait(1)  # Raw event stamped before replacement session.
        assert sessions[0].cancelled.is_set()
        assert old_queue.empty()
        release.set()
        assert second_entered.wait(1)
        assert maximum == 1
        assert bios.current_call is original
        assert sessions[1] is not sessions[0]
        assert bios.hardware_handler.input_queue is not old_queue
        allow_dispatch.set()
        assert event_processed.wait(1)  # Stale event reaches routing after rebinding.
        assert sessions[1].input_queue.empty()
        enter_keys(bios, "3")
        wait_until(lambda: not sessions[1].input_queue.empty())
        assert drain(sessions[1].input_queue) == "3"
    finally:
        release.set()
        allow_dispatch.set()
        bios.hook_status_changed(False)
        original.join(1)
    assert not original.is_alive()


def test_second_hangup_clears_queued_pickup(bios_factory):
    entered = threading.Event()
    release = threading.Event()
    calls = []

    class Slow(SimpleSystem):
        def _call_handler(self):
            calls.append(self._session)
            entered.set()
            release.wait(2)

    bios = bios_factory({"slow": Slow})
    bios.bios_config.set_default_system("slow")
    bios.hook_status_changed(True)
    assert entered.wait(1)
    bios.hook_status_changed(False)
    bios.hook_status_changed(True)
    bios.hook_status_changed(False)
    release.set()
    bios.current_call.join(1)
    assert not bios.current_call.is_alive()
    assert len(calls) == 1


def test_late_admin_input_cannot_renew_expired_blocked_preview(bios_factory, monkeypatch):
    bios = bios_factory({})
    bios.runtime.off_hook = True
    bios._bind_session(bios.runtime.new_session())
    clock = Mock(return_value=100.0)
    monkeypatch.setattr("payphone.bios.auth.time.monotonic", clock)
    capability = AdminSession(bios.runtime, bios._session, inactivity_seconds=5)
    preview_started = threading.Event()
    errors = []
    bios.runtime.speech.say = Mock(side_effect=lambda *args, **kwargs: preview_started.set())
    bios.runtime.speech.is_speaking = Mock(return_value=True)
    bios.runtime.speech.stop_speech = Mock()

    def preview():
        try:
            bios.speak("Long administrator preview")
        except PermissionError as exc:
            errors.append(exc)

    thread = threading.Thread(target=preview)
    thread.start()
    assert preview_started.wait(1)
    clock.return_value = 106.0
    bios.runtime.route_key("1")  # No dispatcher/poll has observed expiry yet.
    thread.join(1)
    assert not thread.is_alive()
    assert errors and isinstance(errors[0], PermissionError)
    assert bios._session.last_activity == 100.0
    assert bios._session.input_queue.empty()
    assert bios.runtime.audio.tones == []
    assert not capability.is_authorized()
    bios.runtime.speech.say.assert_called_once_with("Long administrator preview", bios._session, blocking=False)
    assert bios.runtime.speech.stop_speech.called


def test_dispatcher_expires_admin_during_preview_without_input(monkeypatch):
    runtime, session = new_runtime()
    runtime.speech = Mock()
    clock = Mock(return_value=100.0)
    monkeypatch.setattr("payphone.bios.auth.time.monotonic", clock)
    capability = AdminSession(runtime, session, inactivity_seconds=5)
    runtime.start_dispatcher()
    try:
        clock.return_value = 106.0
        assert session.cancelled.wait(1)
        assert session.reason == "admin exit"
        assert not capability.is_authorized()
        assert runtime.speech.stop_speech.called
    finally:
        runtime.stop()


def test_admin_activity_before_deadline_renews_then_expires_irreversibly(monkeypatch):
    runtime, session = new_runtime()
    clock = Mock(return_value=100.0)
    monkeypatch.setattr("payphone.bios.auth.time.monotonic", clock)
    capability = AdminSession(runtime, session, inactivity_seconds=5)
    clock.return_value = 104.0
    runtime.route_key("1")
    assert session.last_activity == 104.0
    clock.return_value = 108.0
    capability.require_authorized()
    clock.return_value = 109.0
    runtime.route_key("2")
    assert session.last_activity == 104.0
    assert drain(session.input_queue) == "1"
    assert not capability.is_authorized()


def test_filtered_normal_keys_get_tones_but_pin_and_escape_are_silent():
    runtime, session = new_runtime()
    for key in "12*3#":
        runtime.route_key(key)
    assert drain(session.input_queue) == "12*3#"
    assert runtime.audio.tones == list("12*3#")
    runtime.audio.tones.clear()
    session.suppress_tones = True
    for key in "938271#":
        runtime.route_key(key)
    assert drain(session.input_queue) == "938271#"
    assert runtime.audio.tones == []
    session.suppress_tones = False
    for key in "***#":
        runtime.route_key(key)
    assert session.cancelled.is_set()
    assert session.input_queue.empty()
    assert runtime.audio.tones == []


def test_held_normal_prefix_gets_feedback_only_when_released():
    runtime, session = new_runtime()
    runtime.route_key("*", 10.0)
    assert runtime.audio.tones == []
    runtime.flush_prefix(11.1)
    assert runtime.audio.tones == ["*"]
    assert drain(session.input_queue) == "*"


def test_pin_terminator_cannot_restore_tones_before_feedback_decision():
    runtime, session = new_runtime()
    session.suppress_tones = True
    original_put = session.input_queue.put_nowait

    def consume_and_restore(key):
        session.suppress_tones = False
        original_put(key)

    session.input_queue.put_nowait = consume_and_restore
    runtime.route_key("#")
    assert drain(session.input_queue) == "#"
    assert runtime.audio.tones == []


def test_deeply_nested_bios_json_falls_back_without_overwriting(tmp_path):
    path = tmp_path / "bios.json"
    original = '{"nested":' + '[' * 2000 + '0' + ']' * 2000 + '}'
    path.write_text(original)
    config = ConfigManager(str(path))
    assert config.get_default_system() is None
    assert path.read_text() == original
    assert list(tmp_path.iterdir()) == [path]


def cancel_admin(runtime, session, capability, reason):
    if reason == "revoke":
        capability.revoke()
    elif reason == "hangup":
        runtime.off_hook = False
        runtime.cancel("hangup")
    elif reason == "session cancel":
        session.cancel("escape")
    elif reason == "shutdown":
        runtime.stop()
    elif reason == "expiry":
        with session.authorization_lock:
            session.last_activity -= capability.inactivity_seconds + 1
    else:
        runtime.cancel("escape")


@pytest.mark.parametrize("reason", ["hangup", "escape", "revoke", "session cancel", "shutdown", "expiry"])
def test_protected_json_save_denied_after_cancellation_during_staging(tmp_path, monkeypatch, reason):
    config = ConfigManager(str(tmp_path / "bios.json"))
    config.set_default_system("old")
    original = config.config_path.read_bytes()
    runtime, session = new_runtime()
    capability = AdminSession(runtime, session)
    staged = threading.Event()
    release = threading.Event()
    real_fsync = persistence.os.fsync
    errors = []

    def blocked_fsync(fd):
        staged.set()
        assert release.wait(2)
        real_fsync(fd)

    monkeypatch.setattr(persistence.os, "fsync", blocked_fsync)
    replace = Mock(wraps=persistence.os.replace)
    monkeypatch.setattr(persistence.os, "replace", replace)

    def save():
        try:
            config.set_default_system("new", commit=capability.protected_commit)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=save)
    worker.start()
    try:
        assert staged.wait(1)
        cancel_admin(runtime, session, capability, reason)
    finally:
        release.set()
        worker.join(1)
    assert not worker.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], PermissionError)
    replace.assert_not_called()
    assert config.config_path.read_bytes() == original
    assert config.get_default_system() == "old"
    assert list(tmp_path.iterdir()) == [config.config_path]


@pytest.mark.parametrize("reason", ["revoke", "hangup", "escape", "session cancel", "shutdown"])
def test_protected_replacement_is_serialized_with_cancellation(tmp_path, monkeypatch, reason):
    path = tmp_path / "bios.json"
    persistence.atomic_write_json(path, {"value": "old"})
    runtime, session = new_runtime()
    capability = AdminSession(runtime, session)
    at_replace = threading.Event()
    release = threading.Event()
    cancellation_attempted = threading.Event()
    cancellation_done = threading.Event()
    errors = []
    real_replace = persistence.os.replace

    def blocked_replace(source, destination):
        at_replace.set()
        assert release.wait(2)
        real_replace(source, destination)

    monkeypatch.setattr(persistence.os, "replace", blocked_replace)

    def save():
        try:
            persistence.atomic_write_json(path, {"value": "new"}, commit=capability.protected_commit)
        except Exception as exc:
            errors.append(exc)

    def cancel():
        cancellation_attempted.set()
        cancel_admin(runtime, session, capability, reason)
        cancellation_done.set()

    writer = threading.Thread(target=save)
    canceller = threading.Thread(target=cancel)
    writer.start()
    try:
        assert at_replace.wait(1)
        assert not session.authorization_lock.acquire(blocking=False)
        canceller.start()
        assert cancellation_attempted.wait(1)
        assert not cancellation_done.wait(0.05)
        assert json.loads(path.read_text()) == {"value": "old"}
    finally:
        release.set()
        writer.join(1)
        if canceller.ident is not None:
            canceller.join(1)
    assert not writer.is_alive() and not canceller.is_alive()
    assert not errors
    assert cancellation_done.is_set()
    assert json.loads(path.read_text()) == {"value": "new"}
    assert not capability.is_authorized()
    assert list(tmp_path.iterdir()) == [path]


def test_bios_confirmed_default_uses_final_protected_commit(bios_factory, monkeypatch):
    bios = bios_factory({"simple": SimpleSystem})
    bios.runtime.off_hook = True
    bios._bind_session(bios.runtime.new_session())
    bios.bios_config.set_default_system("old")
    original = bios.bios_config.config_path.read_bytes()
    capability = AdminSession(bios.runtime, bios._session)
    bios._session.input_queue.put("1")
    real_fsync = persistence.os.fsync

    def cancel_during_fsync(fd):
        capability.revoke()
        real_fsync(fd)

    monkeypatch.setattr(persistence.os, "fsync", cancel_during_fsync)
    with pytest.raises(PermissionError):
        bios._save_default("simple", capability)
    assert bios.bios_config.config_path.read_bytes() == original
    assert bios.bios_config.get_default_system() == "old"
    assert not prompt_seen(bios, "Persistent default saved")


def test_actual_authentication_filters_pin_feedback_and_discards_held_prefix(monkeypatch):
    monkeypatch.setenv("BIOS_ADMIN_PASSCODE", "938271")
    runtime, session = new_runtime()
    system = SimpleSystem.__new__(SimpleSystem)
    system.runtime = runtime
    system.running = True
    system._bind_session(session)

    def speak(text):
        if text.startswith("Enter the administrator"):
            for key in "938271#*":
                runtime.route_key(key)

    system.speak = speak
    capability = AdminAuthenticator().authenticate(system)
    assert capability is not None
    assert runtime.audio.tones == []
    runtime.flush_prefix(time.monotonic() + 2)
    assert session.input_queue.empty()
    assert runtime.audio.tones == []
    runtime.route_key("1")
    assert runtime.audio.tones == ["1"]
    assert drain(session.input_queue) == "1"


def test_denied_admin_action_returns_to_picker_without_revoked_speech(bios_factory):
    bios = bios_factory({})
    created = []

    def authenticate(system):
        capability = AdminSession(system.runtime, system._session)
        created.append(capability)
        return capability

    def denied_tree(capability):
        def action():
            capability.revoke()
            capability.require_authorized()

        return bios._node("", action=action)

    bios.authenticator.authenticate = authenticate
    bios._administration_tree = denied_tree
    bios.hook_status_changed(True)
    wait_until(lambda: prompt_seen(bios, "Select a phone system"))
    old_session = bios._session
    enter_keys(bios, "0")
    wait_until(lambda: bios._session is not old_session)
    wait_until(lambda: sum("Select a phone system" in text for text in bios.runtime.speech.texts) == 2)
    assert created and not created[0].is_authorized()
    assert not prompt_seen(bios, "Administration expired or was cancelled")
    assert bios.current_call.is_alive()


@pytest.mark.parametrize("before_pickup", [True, False])
def test_raw_backlog_cannot_cross_session_generation(before_pickup):
    runtime = PhoneRuntime(FakeHardware(), FakeAudio())
    if not before_pickup:
        runtime.off_hook = True
        runtime.new_session()
    runtime.hardware.input_queue.put("1")
    runtime.cancel("hangup")
    runtime.off_hook = True
    session = runtime.new_session()
    runtime.start_dispatcher()
    try:
        runtime.hardware.input_queue.put("2")
        wait_until(lambda: not session.input_queue.empty())
        assert drain(session.input_queue) == "2"
        assert runtime.audio.tones == ["2"]
    finally:
        runtime.stop()


def test_runtime_rebinds_gpio_producer_to_generation_queue():
    hardware = FakeHardware()
    hardware.keypad = SimpleNamespace(input_queue=hardware.input_queue)
    old_queue = hardware.input_queue
    runtime = PhoneRuntime(hardware, FakeAudio())
    assert hardware.keypad.input_queue is hardware.input_queue
    assert hardware.input_queue is not old_queue
    runtime.off_hook = True
    session = runtime.new_session()
    hardware.keypad.input_queue.put("1")
    event = hardware.input_queue.get_nowait()
    assert event.key == "1" and event.session is session
