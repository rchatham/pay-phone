"""Real shared-runtime integration; no hardware allocation or network/TTS process."""
from __future__ import annotations

import copy
import json
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from payphone.bios.auth import AdminSession
from payphone.bios.bootloader import BIOSBootloader
from payphone.bios.system_manager import SystemManager
from payphone.core.runtime import PhoneRuntime, SessionAudio, SessionHardware, shared_runtime
from phone_systems.information_booth import services
from phone_systems.information_booth import system as booth_module
from phone_systems.information_booth.content import ContentStore, default_content
from phone_systems.information_booth.system import InformationBoothSystem
from scripts.generate_information_booth_music import generate_sample


def wait_until(predicate, limit=2.0):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate(), "Integration action did not complete within the test bound"


@pytest.fixture
def runtime_booth(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYPHONE_STATE_DIR", str(tmp_path))
    hardware = SimpleNamespace(input_queue=queue.Queue())
    audio = Mock(is_playing=Mock(return_value=False), play_file=Mock(return_value=True), audio_dir=str(tmp_path))
    runtime = PhoneRuntime(hardware, audio)
    runtime.speech = Mock(executable="mock-espeak", is_speaking=Mock(return_value=False))
    runtime.off_hook = True
    session = runtime.new_session()
    config = SimpleNamespace(ENABLE_RECORDING=True, RECORDING_DEVICE="USB",
                             RECORDING_SAMPLE_RATE=22050, RECORDING_CHANNELS=1,
                             LAM_MAX_RECORD_SECONDS=3)
    # Any allocation instead of runtime reuse is a hard test failure.
    monkeypatch.setattr("payphone.core.system.AudioHandler", Mock(side_effect=AssertionError("Duplicate audio owner")))
    monkeypatch.setattr("payphone.core.system.GPIOHandler", Mock(side_effect=AssertionError("Duplicate hardware owner")))
    monkeypatch.setattr("payphone.core.system.SerialHandler", Mock(side_effect=AssertionError("Duplicate hardware owner")))
    with shared_runtime(runtime):
        booth = InformationBoothSystem(config)
    runtime.start_dispatcher()
    try:
        yield runtime, session, booth
    finally:
        runtime.stop()


@pytest.fixture
def bios_pickups(tmp_path, monkeypatch):
    """Actual BIOS hook/call/discovery loop; only device and speech drivers mocked."""
    monkeypatch.setenv("PAYPHONE_STATE_DIR", str(tmp_path))
    root = Path(__file__).resolve().parents[2]
    (tmp_path / "bios.json").write_text(json.dumps({
        "default_system": "information_booth",
        "scan_paths": [str(root / "phone_systems" / "information_booth")],
    }))
    hardware = Mock(input_queue=queue.Queue())
    audio = Mock(is_playing=Mock(return_value=False), play_file=Mock(return_value=True), audio_dir=str(tmp_path))
    speech = Mock(executable="mock-espeak", is_speaking=Mock(return_value=False))
    monkeypatch.setattr("payphone.core.system.AudioHandler", Mock(return_value=audio))
    monkeypatch.setattr("payphone.core.system.SerialHandler", Mock(return_value=hardware))
    monkeypatch.setattr("payphone.core.system.OfflineSpeech", Mock(return_value=speech))
    config = SimpleNamespace(USE_GPIO=False, AUDIO_DIR=str(tmp_path), SERIAL_PORT="mock",
                             BAUDRATE=9600, ENABLE_RECORDING=False)
    original = sys.modules["phone_systems.information_booth.system"]
    bios = BIOSBootloader(config)
    # BIOS is the only owner; every plugin constructor must borrow its runtime.
    monkeypatch.setattr("payphone.core.system.AudioHandler", Mock(side_effect=AssertionError("Duplicate audio owner")))
    monkeypatch.setattr("payphone.core.system.SerialHandler", Mock(side_effect=AssertionError("Duplicate hardware owner")))
    monkeypatch.setattr("payphone.core.system.GPIOHandler", Mock(side_effect=AssertionError("Duplicate hardware owner")))
    try:
        yield bios
    finally:
        bios.hook_status_changed(False)
        if bios.current_call:
            bios.current_call.join(timeout=2)
            assert not bios.current_call.is_alive()
        bios.runtime.stop()
        sys.modules["phone_systems.information_booth.system"] = original


def pickup_booth(bios):
    bios.hook_status_changed(True)
    wait_until(lambda: bios.current_system is not None and any(
        "Welcome to the information booth" in call.args[0] for call in bios.runtime.speech.say.call_args_list))
    return bios.current_system


def hangup_booth(bios):
    bios.hook_status_changed(False)
    bios.current_call.join(timeout=2)
    assert not bios.current_call.is_alive()
    bios.runtime.speech.say.reset_mock()


def test_real_bios_pickups_retain_custom_content_after_corrupt_edit(bios_pickups, tmp_path):
    bios = bios_pickups
    data = default_content()
    data["categories"][0]["label"] = "Library information"
    text = "The library opens at nine, even on Saturdays."
    data["categories"][0]["messages"][0]["text"] = text
    path = tmp_path / "information_booth.json"
    path.write_text(json.dumps(data))
    first = pickup_booth(bios)
    for key in "41":
        bios.runtime.hardware.input_queue.put(key)
    wait_until(lambda: any(text in call.args for call in bios.runtime.speech.say.call_args_list))
    first_session = first._session
    hangup_booth(bios)

    path.write_text("{corrupt-local-edit")
    second = pickup_booth(bios)
    assert second is not first
    assert second._session is not first_session
    assert second.hardware_handler is not first.hardware_handler
    assert second.audio_handler is not first.audio_handler
    assert second.store is first.store
    assert second.content == data
    assert second.store.reload_error
    for key in "41":
        bios.runtime.hardware.input_queue.put(key)
    wait_until(lambda: any(text in call.args for call in bios.runtime.speech.say.call_args_list))
    assert path.read_text() == "{corrupt-local-edit"


def test_real_bios_pickups_retain_online_weather_when_next_call_offline(bios_pickups, monkeypatch):
    bios = bios_pickups
    response = {"current": {"temperature_2m": 12.5, "weather_code": 3,
                            "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")},
                "current_units": {"temperature_2m": "°C"}, "utc_offset_seconds": 0}
    fetch = Mock(return_value=response)
    monkeypatch.setattr(services, "fetch_weather", fetch)
    first = pickup_booth(bios)
    for key in "11":
        bios.runtime.hardware.input_queue.put(key)
    wait_until(lambda: any("12.5 degrees celsius" in call.args[0] for call in bios.runtime.speech.say.call_args_list))
    settings = first.content["weather"]
    key = tuple(settings[name] for name in ("latitude", "longitude", "units"))
    timestamp, text = first.weather_service.cache[key]
    # Age beyond fresh TTL without sleeping or changing the auth/runtime clock.
    first.weather_service.cache[key] = (timestamp - services.CACHE_SECONDS - 1, text)
    hangup_booth(bios)

    fetch.side_effect = OSError("offline")
    second = pickup_booth(bios)
    assert second is not first
    assert second.weather_service is first.weather_service
    for digit in "11":
        bios.runtime.hardware.input_queue.put(digit)
    wait_until(lambda: any("Weather is offline. This is stale cached weather" in call.args[0]
                          for call in bios.runtime.speech.say.call_args_list))
    assert fetch.call_count == 2
    assert any("12.5 degrees celsius" in call.args[0] for call in bios.runtime.speech.say.call_args_list)


def test_actual_discovery_and_shared_constructor_work_outside_cwd(runtime_booth, tmp_path, monkeypatch):
    runtime, session, booth = runtime_booth
    root = Path(__file__).resolve().parents[2]
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    # Discovery loads the canonical module from its file path. Restore the
    # imported module afterward to keep independently collected unit tests stable.
    module_name = "phone_systems.information_booth.system"
    original = sys.modules[module_name]
    manager = SystemManager([str(root / "phone_systems")])
    try:
        discovered = manager.discover_systems()
        assert discovered["information_booth"].name == "Information Booth"
        cls = manager.load_system("information_booth")
        assert cls is not None
        with shared_runtime(runtime):
            loaded = cls(booth.config)
        assert loaded.runtime is runtime
        assert isinstance(loaded.audio_handler, SessionAudio)
        assert isinstance(loaded.hardware_handler, SessionHardware)
        assert loaded.hardware_handler.input_queue is session.input_queue
        assert loaded.store.path == tmp_path / "information_booth.json"
    finally:
        sys.modules[module_name] = original


def test_real_routed_public_menu_plays_edited_message_then_escape(runtime_booth):
    runtime, session, booth = runtime_booth
    candidate = copy.deepcopy(booth.content)
    candidate["categories"][0]["messages"][0]["text"] = "The library opens at nine."
    booth.store.save(candidate, AdminSession(runtime, session))
    tree = booth.setup_phone_tree()
    call = threading.Thread(target=tree.navigate, args=(session.input_queue, booth.is_call_active, tree))
    call.start()
    try:
        runtime.hardware.input_queue.put("4")
        runtime.hardware.input_queue.put("1")
        wait_until(lambda: any("The library opens at nine." in item.args for item in runtime.speech.say.call_args_list))
        for key in "***#":
            runtime.hardware.input_queue.put(key)
        call.join(timeout=2)
        assert not call.is_alive()
        assert session.reason == "escape"
        assert booth.phone_on_hook
    finally:
        runtime.cancel("test cleanup")
        call.join(timeout=2)


def test_escape_during_actual_session_audio_stops_playback(runtime_booth):
    runtime, session, booth = runtime_booth
    generate_sample(booth.store.media_root / "sample.wav")
    runtime.audio.is_playing.return_value = True
    action = threading.Thread(target=booth._play_audio, args=("sample.wav",))
    action.start()
    try:
        wait_until(lambda: runtime.audio.play_file.called)
        for key in "***#":
            runtime.hardware.input_queue.put(key)
        action.join(timeout=2)
        assert not action.is_alive()
        runtime.audio.stop.assert_called()
        assert session.reason == "escape"
        previous = runtime.audio.play_file.call_count
        booth._play_audio("sample.wav")
        assert runtime.audio.play_file.call_count == previous
    finally:
        runtime.cancel("test cleanup")
        action.join(timeout=2)


def test_real_authorized_record_publish_then_escape_cleans_second_take(runtime_booth, monkeypatch):
    runtime, session, booth = runtime_booth
    admin = AdminSession(runtime, session)
    record = booth_module.recording
    monkeypatch.setattr(record, "is_recording", False)
    monkeypatch.setattr(record, "init", Mock())
    finished = Mock()
    cancelled = Mock()
    monkeypatch.setattr(record, "finish_recording", finished)
    monkeypatch.setattr(record, "cancel_recording", cancelled)
    started = Mock(side_effect=lambda path, timeout: generate_sample(Path(path)))
    monkeypatch.setattr(record, "start_recording", started)
    candidate = copy.deepcopy(booth.content)
    target = candidate["categories"][0]["messages"][0]
    errors = []

    def take():
        try:
            booth._record_publish(candidate, target, "audio", admin)
        except PermissionError as exc:
            errors.append(exc)

    action = threading.Thread(target=take)
    action.start()
    try:
        wait_until(lambda: started.called)
        runtime.hardware.input_queue.put("#")
        wait_until(lambda: finished.called)
        runtime.hardware.input_queue.put("1")
        action.join(timeout=2)
        assert not action.is_alive()
        assert not errors
        saved = ContentStore(booth.store.directory).snapshot
        old_name = saved["categories"][0]["messages"][0]["audio"]
        assert (booth.store.media_root / old_name).exists()
        old_json = booth.store.path.read_bytes()

        second = copy.deepcopy(booth.content)
        target = second["categories"][0]["messages"][0]
        candidate = second
        action = threading.Thread(target=take)
        action.start()
        wait_until(lambda: started.call_count == 2)
        for key in "***#":
            runtime.hardware.input_queue.put(key)
        action.join(timeout=2)
        assert not action.is_alive()
        cancelled.assert_called_once()
        assert not list(booth.store.media_root.glob("pending-*"))
        assert booth.store.path.read_bytes() == old_json
        assert (booth.store.media_root / old_name).exists()
        assert session.reason == "escape"
        with pytest.raises(PermissionError):
            admin.require_authorized()
    finally:
        runtime.cancel("test cleanup")
        action.join(timeout=2)


@pytest.mark.parametrize("preview", ["speech", "recorded"])
def test_real_admin_expiry_stops_long_booth_preview(runtime_booth, preview):
    runtime, session, booth = runtime_booth
    if preview == "recorded":
        generate_sample(booth.store.media_root / "sample.wav")
        runtime.audio.is_playing.return_value = True
    else:
        runtime.speech.is_speaking.return_value = True
    admin = AdminSession(runtime, session, inactivity_seconds=30)
    errors = []
    def preview_action():
        try:
            if preview == "recorded":
                booth._play_audio("sample.wav", admin)
            else:
                booth._speak("A long administrator-only preview.", admin)
        except PermissionError as exc:
            errors.append(exc)
    action = threading.Thread(target=preview_action)
    action.start()
    try:
        wait_until(lambda: runtime.audio.play_file.called if preview == "recorded" else runtime.speech.say.called)
        # Expire only after playback begins, independent of WAV setup/scheduling.
        with session.authorization_lock:
            session.last_activity = time.monotonic() - 31
        action.join(timeout=1)
        assert not action.is_alive()
        assert not admin.is_authorized()
        # Runtime polling may cancel the session before Booth's own poll, in
        # which case the inactive preview returns quietly rather than raising.
        assert errors or not booth.is_call_active()
        if preview == "recorded":
            runtime.audio.stop.assert_called()
        else:
            runtime.speech.stop_speech.assert_called()
            runtime.speech.say.assert_called_with("A long administrator-only preview.", session, blocking=False)
        runtime.hardware.input_queue.put("1")  # late confirmation cannot revive it
        time.sleep(0.06)
        assert not admin.is_authorized()
        assert not booth.store.path.exists()
    finally:
        runtime.cancel("test cleanup")
        action.join(timeout=2)


@pytest.mark.parametrize("cancel", ["hangup", "revoke"])
def test_real_booth_save_denies_cancellation_during_staging(runtime_booth, monkeypatch, cancel):
    from payphone.config import persistence
    runtime, session, booth = runtime_booth
    admin = AdminSession(runtime, session)
    booth.store.save(booth.content, admin)
    previous = booth.store.path.read_bytes()
    previous_content = copy.deepcopy(booth.content)
    candidate = copy.deepcopy(booth.content)
    candidate["timezone"] = "UTC"
    staged = threading.Event()
    release = threading.Event()
    fsync = persistence.os.fsync
    def paused_fsync(fd):
        fsync(fd)
        staged.set()
        assert release.wait(2), "Test did not release JSON staging"
    monkeypatch.setattr(persistence.os, "fsync", paused_fsync)
    errors = []
    def save():
        try:
            booth._save(candidate, admin)
        except Exception as exc:
            errors.append(exc)
    action = threading.Thread(target=save)
    action.start()
    try:
        assert staged.wait(1)
        if cancel == "hangup":
            runtime.off_hook = False
            runtime.cancel("hangup")
        else:
            admin.revoke()
        release.set()
        action.join(timeout=2)
        assert not action.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], PermissionError)
        assert booth.store.path.read_bytes() == previous
        assert booth.content == previous_content
        assert booth.store.snapshot == previous_content
        assert not list(booth.store.directory.glob(".information_booth.json.*.tmp"))
    finally:
        release.set()
        runtime.cancel("test cleanup")
        action.join(timeout=2)


def test_actual_admin_tree_can_configure_without_new_input_consumer(runtime_booth):
    runtime, session, booth = runtime_booth
    admin = AdminSession(runtime, session)
    tree = booth.setup_admin_tree(admin)
    dispatcher = runtime._dispatcher
    action = threading.Thread(target=tree.navigate, args=(session.input_queue, booth.is_call_active, tree))
    action.start()
    try:
        for key in "2110":  # service switches, weather toggle, save, leave admin
            runtime.hardware.input_queue.put(key)
        action.join(timeout=2)
        assert not action.is_alive()
        assert not ContentStore(booth.store.directory).snapshot["services"]["weather"]
        assert runtime._dispatcher is dispatcher
        assert session.input_queue.empty()
    finally:
        runtime.cancel("test cleanup")
        action.join(timeout=2)
