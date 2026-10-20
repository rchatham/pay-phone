"""Booth-only tests; hardware, TTS, HTTP and capture are always mocked."""
from __future__ import annotations

import copy
import json
import queue
import threading
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from phone_systems.information_booth import content as content_module
from phone_systems.information_booth import services
from phone_systems.information_booth import system as booth_module
from phone_systems.information_booth.content import ContentStore, default_content, safe_media_path, validate_content
from phone_systems.information_booth.system import InformationBoothSystem
from scripts.generate_information_booth_music import generate_sample


class Capability:
    def __init__(self) -> None:
        self.authorized = True
        self.calls = 0

    def require_authorized(self) -> None:
        self.calls += 1
        if not self.authorized:
            raise PermissionError("Expired")

    def protected_commit(self, replace) -> None:
        self.require_authorized()
        replace()


@pytest.fixture
def admin():
    return Capability()


@pytest.fixture
def booth(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYPHONE_STATE_DIR", str(tmp_path))

    def mock_base_init(self, config):
        self.config = SimpleNamespace(ENABLE_RECORDING=True, RECORDING_DEVICE="USB",
                                      RECORDING_SAMPLE_RATE=22050, RECORDING_CHANNELS=1,
                                      LAM_MAX_RECORD_SECONDS=3)
        self.hardware_handler = SimpleNamespace(input_queue=queue.Queue())
        self.audio_handler = Mock(play_file=Mock(return_value=True), is_playing=Mock(return_value=False))
        self._phone_on_hook = False
        self.running = True
        self.say = Mock()
        self.speak = Mock()
        self.stop_speech = Mock()
        self.is_speaking = Mock(return_value=False)

    monkeypatch.setattr(booth_module.PhoneSystemBase, "__init__", mock_base_init)
    return InformationBoothSystem()


@pytest.fixture
def capture(booth, monkeypatch):
    record = booth_module.recording
    monkeypatch.setattr(record, "is_recording", False)
    monkeypatch.setattr(record, "init", Mock())
    monkeypatch.setattr(record, "finish_recording", Mock())
    monkeypatch.setattr(record, "cancel_recording", Mock())

    def start(path, timeout):
        generate_sample(Path(path))

    monkeypatch.setattr(record, "start_recording", Mock(side_effect=start))
    return record


def test_defaults_are_independent_and_valid(tmp_path):
    data = default_content()
    validate_content(data, tmp_path)
    data["services"]["music"] = False
    assert default_content()["services"]["music"] is True


@pytest.mark.parametrize("change", [
    lambda d: d.update(version=True),
    lambda d: d.update(version=2),
    lambda d: d.update(unexpected=1),
    lambda d: d["services"].update(weather=1),
    lambda d: d["weather"].update(latitude=float("nan")),
    lambda d: d["weather"].update(longitude=181),
    lambda d: d["weather"].update(latitude=True),
    lambda d: d["weather"].update(units="kelvin"),
    lambda d: d.update(timezone="Not/AZone"),
    lambda d: d.update(timezone="../UTC"),
    lambda d: d.update(music="../../other.wav"),
    lambda d: d.update(music="absent.wav"),
    lambda d: d["categories"][0].update(slot="1"),
    lambda d: d["categories"][0].update(slot="45"),
    lambda d: d["categories"].append(copy.deepcopy(d["categories"][0])),
    lambda d: d["categories"][0].update(label=""),
    lambda d: d["categories"][0].update(label="x" * 101),
    lambda d: d["categories"][0].update(label="hidden\x00"),
    lambda d: d["categories"][0]["messages"].append(copy.deepcopy(d["categories"][0]["messages"][0])),
    lambda d: d["categories"][0]["messages"][0].update(slot="0"),
    lambda d: d["categories"][0]["messages"][0].update(text=""),
    lambda d: d["categories"][0]["messages"][0].update(text="x" * 4001),
    lambda d: d["categories"][0]["messages"][0].update(audio="missing.wav"),
])
def test_schema_rejects_invalid_edits(tmp_path, change):
    data = default_content()
    change(data)
    with pytest.raises(ValueError):
        validate_content(data, tmp_path)


def test_audio_rejects_symlink_escape_and_oversize(tmp_path):
    root = tmp_path / "audio"
    root.mkdir()
    outside = tmp_path / "outside.wav"
    generate_sample(outside)
    (root / "link.wav").symlink_to(outside)
    with pytest.raises(ValueError):
        safe_media_path(root, "link.wav")
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError):
        safe_media_path(linked_root, "test.wav", must_exist=False)
    with (root / "big.wav").open("wb") as output:
        output.truncate(content_module.MAX_AUDIO_BYTES + 1)
    with pytest.raises(ValueError):
        safe_media_path(root, "big.wav")


def test_store_persists_and_reloads_from_different_cwd(tmp_path, monkeypatch, admin):
    monkeypatch.setenv("PAYPHONE_STATE_DIR", str(tmp_path))
    store = ContentStore()
    changed = default_content()
    changed["timezone"] = "UTC"
    changed["categories"][0]["messages"][0]["text"] = "Library hours: nine until five."
    store.save(changed, admin)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    loaded = ContentStore()
    assert loaded.snapshot == changed
    assert loaded.path == tmp_path / "information_booth.json"


def test_invalid_reload_retains_snapshot_without_overwriting_source(tmp_path, admin):
    store = ContentStore(tmp_path)
    changed = default_content()
    changed["timezone"] = "UTC"
    store.save(changed, admin)
    store.path.write_text("{broken")
    assert store.reload() == changed
    assert store.reload_error
    assert store.path.read_text() == "{broken"
    fresh = ContentStore(tmp_path)
    assert fresh.snapshot == default_content()
    assert fresh.path.read_text() == "{broken"


def test_oversized_reload_is_rejected(tmp_path):
    (tmp_path / "information_booth.json").write_bytes(b" " * (content_module.MAX_JSON_BYTES + 1))
    store = ContentStore(tmp_path)
    assert store.reload_error
    assert store.snapshot == default_content()


def test_expired_capability_blocks_save(tmp_path, admin):
    store = ContentStore(tmp_path)
    admin.authorized = False
    with pytest.raises(PermissionError):
        store.save(default_content(), admin)
    assert not store.path.exists()


def test_failed_atomic_save_retains_memory_and_disk(tmp_path, monkeypatch, admin):
    store = ContentStore(tmp_path)
    store.save(default_content(), admin)
    old = store.path.read_bytes()
    changed = default_content()
    changed["timezone"] = "UTC"
    monkeypatch.setattr(content_module, "atomic_write_json", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        store.save(changed, admin)
    assert store.snapshot == default_content()
    assert store.path.read_bytes() == old


def test_save_passes_final_protected_boundary(tmp_path, admin, monkeypatch):
    store = ContentStore(tmp_path)
    writer = Mock()
    monkeypatch.setattr(content_module, "atomic_write_json", writer)
    candidate = default_content()
    store.save(candidate, admin)
    writer.assert_called_once_with(store.path, candidate, commit=admin.protected_commit)


def test_cancellation_during_staged_save_retains_snapshot_and_cleans_temp(tmp_path, admin, monkeypatch):
    from payphone.config import persistence
    store = ContentStore(tmp_path)
    store.save(default_content(), admin)
    original = store.path.read_bytes()
    changed = default_content()
    changed["timezone"] = "UTC"
    fsync = persistence.os.fsync
    def cancel_after_staging(fd):
        fsync(fd)
        admin.authorized = False
    monkeypatch.setattr(persistence.os, "fsync", cancel_after_staging)
    with pytest.raises(PermissionError):
        store.save(changed, admin)
    assert store.snapshot == default_content()
    assert store.path.read_bytes() == original
    assert not list(tmp_path.glob(".information_booth.json.*.tmp"))


def test_public_setup_reloads_external_edits(booth):
    changed = default_content()
    changed["timezone"] = "UTC"
    booth.store.path.write_text(json.dumps(changed))
    tree = booth.setup_phone_tree()
    assert tree.audio_handler is booth.audio_handler
    assert booth.content == changed
    booth.store.path.write_text("invalid")
    booth.setup_phone_tree()
    assert booth.content == changed


def test_time_uses_clock_and_timezone():
    now = datetime(2026, 1, 2, 15, 4, tzinfo=timezone.utc)
    assert "03:04 PM" in services.current_time_text("UTC", now)
    assert "10:04 AM" in services.current_time_text("America/New_York", now)
    assert "EST" in services.current_time_text("America/New_York", now)
    assert "current time" in services.current_time_text("local")


def weather_data():
    return {"current": {"temperature_2m": 12.5, "weather_code": 3,
                        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")},
            "current_units": {"temperature_2m": "°C"}, "utc_offset_seconds": 0}


def test_weather_current_cache_stale_and_unavailable(monkeypatch):
    fetch = Mock(return_value=weather_data())
    monkeypatch.setattr(services, "fetch_weather", fetch)
    service = services.WeatherService()
    settings = default_content()["weather"]
    assert "12.5 degrees celsius" in service.report(settings)
    assert "Recent cached" in service.report(settings)
    assert fetch.call_count == 1
    key = tuple(settings[name] for name in ("latitude", "longitude", "units"))
    old = service.cache[key]
    service.cache[key] = (time.monotonic() - 700, old[1])
    fetch.side_effect = OSError("offline")
    assert "stale cached" in service.report(settings)
    service.cache[key] = (time.monotonic() - services.MAX_STALE_SECONDS - 1, old[1])
    assert "unavailable" in service.report(settings)


@pytest.mark.parametrize("change", [
    lambda d: d["current"].update(temperature_2m=float("nan")),
    lambda d: d["current"].update(temperature_2m=True),
    lambda d: d["current"].update(weather_code=999),
    lambda d: d["current"].update(weather_code=True),
    lambda d: d["current"].update(time="2000-01-01T00:00"),
    lambda d: d["current_units"].update(temperature_2m="°F"),
    lambda d: d.update(utc_offset_seconds=3600),
])
def test_invalid_weather_never_becomes_fabricated_report(monkeypatch, change):
    data = weather_data()
    change(data)
    monkeypatch.setattr(services, "fetch_weather", Mock(return_value=data))
    assert "unavailable" in services.WeatherService().report(default_content()["weather"])


@pytest.mark.parametrize("status,body,content_type", [
    (302, b"", "application/json"),
    (200, b"x" * (services.MAX_WEATHER_BYTES + 1), "application/json"),
    (200, b"{}", "text/html"),
])
def test_http_rejects_redirects_large_bodies_and_bad_type(monkeypatch, status, body, content_type):
    chunks = [body[index:index + 4096] for index in range(0, len(body), 4096)] + [b""]
    response = Mock(status=status, getheader=Mock(return_value=content_type), read1=Mock(side_effect=chunks))
    connection = Mock(getresponse=Mock(return_value=response))
    factory = Mock(return_value=connection)
    monkeypatch.setattr(services.http.client, "HTTPSConnection", factory)
    with pytest.raises(ValueError):
        services.fetch_weather(default_content()["weather"])
    factory.assert_called_once_with("api.open-meteo.com", timeout=services.WEATHER_TIMEOUT)
    assert connection.request.call_args.args[0] == "GET"
    assert connection.request.call_args.args[1].startswith("/v1/forecast?")
    connection.close.assert_called_once()


def test_weather_wall_clock_bound_and_single_outstanding_worker(monkeypatch):
    gate = threading.Lock()
    monkeypatch.setattr(services, "_REQUEST_GATE", gate)
    monkeypatch.setattr(services, "WEATHER_TIMEOUT", 0.08)
    release = threading.Event()
    fetch = Mock(side_effect=lambda settings: (release.wait(2), weather_data())[1])
    monkeypatch.setattr(services, "fetch_weather", fetch)
    service = services.WeatherService()
    started = time.monotonic()
    try:
        assert "unavailable" in service.report(default_content()["weather"])
        assert time.monotonic() - started < 0.5
        assert "unavailable" in service.report(default_content()["weather"])
        assert fetch.call_count == 1
    finally:
        release.set()
        deadline = time.monotonic() + 2
        while gate.locked() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert not gate.locked()


def test_weather_cancellation_does_not_start_http(monkeypatch):
    fetch = Mock()
    monkeypatch.setattr(services, "fetch_weather", fetch)
    assert "unavailable" in services.WeatherService().report(default_content()["weather"], lambda: False)
    fetch.assert_not_called()


def test_weather_completion_after_hangup_does_not_speak(booth, monkeypatch):
    def report(settings, active):
        booth.phone_on_hook = True
        return "Should not be heard"
    monkeypatch.setattr(booth, "_choose", Mock(return_value="1"))
    booth.weather_service.report = report
    booth._information_menu()
    booth.speak.assert_not_called()


def test_jokes_are_local_and_music_generation_is_real(tmp_path):
    assert services.joke_text() in services.JOKES
    destination = tmp_path / "sample.wav"
    generate_sample(destination)
    with wave.open(str(destination)) as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getnframes() == 128000
        assert any(audio.readframes(1000))
    assert list(tmp_path.iterdir()) == [destination]


def test_local_music_playback_and_unavailable_diagnostic(booth):
    booth._play_audio("sample.wav")
    assert "unavailable" in booth.speak.call_args.args[0]
    generate_sample(booth.store.media_root / "sample.wav")
    booth._play_audio("sample.wav")
    booth.audio_handler.play_file.assert_called_with(str(booth.store.media_root / "sample.wav"), blocking=False)


def test_playback_after_hangup_is_suppressed(booth):
    generate_sample(booth.store.media_root / "sample.wav")
    booth.phone_on_hook = True
    booth._play_audio("sample.wav")
    booth.audio_handler.play_file.assert_not_called()


def test_recorded_labels_are_used_with_barge_in(booth):
    generate_sample(booth.store.media_root / "label.wav")
    # With a playing recorded label, the first key should interrupt, not be lost.
    booth.audio_handler.is_playing.return_value = True
    booth.hardware_handler.input_queue.put("4")
    assert booth._prompt_part("Category four", "label.wav") == "4"
    booth.audio_handler.stop.assert_called()


def test_public_tree_exposes_no_admin_capability(booth, monkeypatch):
    choices = iter(("2", None))
    monkeypatch.setattr(booth, "_choose", Mock(side_effect=lambda *args, **kwargs: next(choices)))
    monkeypatch.setattr(booth, "_admin_menu", Mock())
    tree = booth.setup_phone_tree()
    tree.navigate(booth.hardware_handler.input_queue, booth.is_call_active, tree)
    booth.speak.assert_called()
    booth._admin_menu.assert_not_called()
    assert not booth.store.path.exists()


def test_admin_setup_rejects_expired_capability(booth, admin):
    admin.authorized = False
    with pytest.raises(PermissionError):
        booth.setup_admin_tree(admin)


def test_service_toggle_confirm_and_persistence(booth, admin, monkeypatch):
    monkeypatch.setattr(booth, "_choose", Mock(side_effect=("1", "1")))
    booth._edit_services(admin)
    assert not booth.content["services"]["weather"]
    assert not ContentStore(booth.store.directory).snapshot["services"]["weather"]
    assert admin.calls > 0


def test_service_toggle_discard_does_not_save(booth, admin, monkeypatch):
    monkeypatch.setattr(booth, "_choose", Mock(side_effect=("1", "0")))
    booth._edit_services(admin)
    assert booth.content == default_content()
    assert not booth.store.path.exists()


def test_coordinate_entry_is_bounded_and_supports_negative_decimal(booth, admin, monkeypatch):
    monkeypatch.setattr(booth, "_choose", Mock(return_value="2"))
    for key in "73*9857#":
        booth.hardware_handler.input_queue.put(key)
    assert booth._coordinate("longitude", 180, admin) == -73.9857
    for key in "12345678901#":
        booth.hardware_handler.input_queue.put(key)
    with pytest.raises(ValueError):
        booth._coordinate("longitude", 180, admin)


def test_weather_settings_confirmation_and_timezone_persist(booth, admin, monkeypatch):
    monkeypatch.setattr(booth, "_coordinate", Mock(side_effect=(51.5, -0.12)))
    monkeypatch.setattr(booth, "_choose", Mock(side_effect=("2", "1", "2", "1")))
    booth._edit_weather(admin)
    booth._edit_timezone(admin)
    loaded = ContentStore(booth.store.directory).snapshot
    assert loaded["weather"] == {"latitude": 51.5, "longitude": -0.12, "units": "fahrenheit"}
    assert loaded["timezone"] == "UTC"


def test_music_selection_only_lists_safe_music_not_private_recordings(booth, admin, monkeypatch):
    root = booth.store.media_root
    generate_sample(root / "sample.wav")
    generate_sample(root / "recording-private.wav")
    generate_sample(root / "pending-secret.wav")
    (root / "escaped.wav").symlink_to(root / "sample.wav")
    choose = Mock(side_effect=("1", "1"))
    monkeypatch.setattr(booth, "_choose", choose)
    booth._edit_music(admin)
    assert choose.call_args_list[0].args[3] == [("1", "sample", None)]
    assert ContentStore(booth.store.directory).snapshot["music"] == "sample.wav"


def record_target(booth):
    candidate = copy.deepcopy(booth.content)
    target = candidate["categories"][0]["messages"][0]
    return candidate, target


def test_authenticated_record_publish_preview_confirm_reload(booth, admin, capture, monkeypatch):
    candidate, target = record_target(booth)
    monkeypatch.setattr(booth, "_key", Mock(return_value="#"))
    monkeypatch.setattr(booth, "_choose", Mock(return_value="1"))
    booth._record_publish(candidate, target, "audio", admin)
    capture.init.assert_called_once_with(preferred_device="USB", preferred_samplerate=22050, preferred_channels=1)
    capture.start_recording.assert_called_once()
    capture.finish_recording.assert_called_once()
    capture.cancel_recording.assert_not_called()
    saved = ContentStore(booth.store.directory).snapshot
    name = saved["categories"][0]["messages"][0]["audio"]
    assert name.startswith("recording-")
    assert safe_media_path(booth.store.media_root, name).is_file()
    assert not list(booth.store.media_root.glob("pending-*"))
    assert "pending-" in booth.audio_handler.play_file.call_args.args[0]
    assert admin.calls >= 5


@pytest.mark.parametrize("cancel_at", ["record", "preview", "confirm", "hangup", "expire"])
def test_recording_cancellation_discards_unpublished_audio(booth, admin, capture, monkeypatch, cancel_at):
    candidate, target = record_target(booth)
    def key(*args):
        if cancel_at == "hangup":
            booth.phone_on_hook = True
        if cancel_at == "expire":
            admin.authorized = False
        return "*" if cancel_at == "record" else "#"
    monkeypatch.setattr(booth, "_key", key)
    monkeypatch.setattr(booth, "_choose", Mock(return_value="0" if cancel_at == "confirm" else "1"))
    if cancel_at == "preview":
        monkeypatch.setattr(booth, "_play_audio", lambda *args: setattr(booth, "phone_on_hook", True))
    if cancel_at == "expire":
        with pytest.raises(PermissionError):
            booth._record_publish(candidate, target, "audio", admin)
    else:
        booth._record_publish(candidate, target, "audio", admin)
    assert list(booth.store.media_root.iterdir()) == []
    assert booth.content == default_content()
    assert not booth.store.path.exists()
    if cancel_at in ("record", "hangup", "expire"):
        capture.cancel_recording.assert_called_once()


def test_authorization_rechecked_after_confirmation(booth, admin, capture, monkeypatch):
    candidate, target = record_target(booth)
    monkeypatch.setattr(booth, "_key", Mock(return_value="#"))
    def confirm(*args):
        admin.authorized = False
        return True
    monkeypatch.setattr(booth, "_confirm", confirm)
    with pytest.raises(PermissionError):
        booth._record_publish(candidate, target, "audio", admin)
    assert not booth.store.path.exists()
    assert list(booth.store.media_root.iterdir()) == []


def test_record_failed_json_save_preserves_old_published_content(booth, admin, capture, monkeypatch):
    booth.store.save(booth.content, admin)
    old = booth.store.path.read_bytes()
    candidate, target = record_target(booth)
    monkeypatch.setattr(booth, "_key", Mock(return_value="#"))
    monkeypatch.setattr(booth, "_choose", Mock(return_value="1"))
    monkeypatch.setattr(content_module, "atomic_write_json", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        booth._record_publish(candidate, target, "audio", admin)
    assert booth.store.path.read_bytes() == old
    assert booth.content == default_content()
    assert list(booth.store.media_root.iterdir()) == []


def test_postreplace_fsync_failure_never_deletes_json_referenced_audio(booth, admin, capture, monkeypatch):
    candidate, target = record_target(booth)
    monkeypatch.setattr(booth, "_key", Mock(return_value="#"))
    monkeypatch.setattr(booth, "_choose", Mock(return_value="1"))
    def uncertain_save(path, data, *, commit):
        commit(lambda: path.write_text(json.dumps(data)))
        raise OSError("directory fsync failed after replacement")
    monkeypatch.setattr(content_module, "atomic_write_json", uncertain_save)
    with pytest.raises(OSError):
        booth._record_publish(candidate, target, "audio", admin)
    saved = ContentStore(booth.store.directory).snapshot
    name = saved["categories"][0]["messages"][0]["audio"]
    assert safe_media_path(booth.store.media_root, name).is_file()


def test_record_startup_failure_stops_partial_backend_and_cleans_file(booth, admin, capture, monkeypatch):
    def partial_start(path, timeout):
        path.write_bytes(b"partial")
        raise RuntimeError("stream could not start")
    capture.start_recording.side_effect = partial_start
    candidate, target = record_target(booth)
    with pytest.raises(RuntimeError):
        booth._record_publish(candidate, target, "audio", admin)
    capture.cancel_recording.assert_called_once()
    assert not list(booth.store.media_root.iterdir())


def test_recording_disabled_diagnostic(booth, admin, capture):
    booth.config.ENABLE_RECORDING = False
    candidate, target = record_target(booth)
    booth._record_publish(candidate, target, "audio", admin)
    capture.start_recording.assert_not_called()
    assert "disabled" in booth.say.call_args.args[0]


def test_failed_record_preview_never_publishes(booth, admin, capture, monkeypatch):
    candidate, target = record_target(booth)
    monkeypatch.setattr(booth, "_key", Mock(return_value="#"))
    monkeypatch.setattr(booth, "_confirm", Mock(return_value=True))
    booth.audio_handler.play_file.return_value = False
    booth._record_publish(candidate, target, "audio", admin)
    booth._confirm.assert_not_called()
    assert not booth.store.path.exists()
    assert list(booth.store.media_root.iterdir()) == []


def test_active_other_recorder_is_not_disrupted(booth, admin, capture, monkeypatch):
    monkeypatch.setattr(capture, "is_recording", True)
    candidate, target = record_target(booth)
    with pytest.raises(RuntimeError, match="Another recorder"):
        booth._record_publish(candidate, target, "audio", admin)
    capture.cancel_recording.assert_not_called()
    capture.start_recording.assert_not_called()


def test_colliding_recording_names_never_overwrite_existing_audio(booth, admin, capture, monkeypatch):
    token = "a" * 32
    monkeypatch.setattr(booth_module.uuid, "uuid4", lambda: SimpleNamespace(hex=token))
    published = booth.store.media_root / f"recording-{token}.wav"
    generate_sample(published)
    old = published.read_bytes()
    candidate, target = record_target(booth)
    monkeypatch.setattr(booth, "_key", Mock(return_value="#"))
    monkeypatch.setattr(booth, "_confirm", Mock(return_value=True))
    with pytest.raises(FileExistsError):
        booth._record_publish(candidate, target, "audio", admin)
    assert published.read_bytes() == old
    assert not list(booth.store.media_root.glob("pending-*"))
    assert not booth.store.path.exists()


def test_colliding_pending_names_are_not_deleted_or_overwritten(booth, admin, capture, monkeypatch):
    token = "b" * 32
    monkeypatch.setattr(booth_module.uuid, "uuid4", lambda: SimpleNamespace(hex=token))
    pending = booth.store.media_root / f"pending-{token}.wav"
    generate_sample(pending)
    old = pending.read_bytes()
    candidate, target = record_target(booth)
    with pytest.raises(FileExistsError):
        booth._record_publish(candidate, target, "audio", admin)
    assert pending.read_bytes() == old
    capture.start_recording.assert_not_called()


def test_category_create_label_and_message_record_delete(booth, admin, capture, monkeypatch):
    monkeypatch.setattr(booth, "_key", Mock(return_value="#"))
    monkeypatch.setattr(booth, "_choose", Mock(side_effect=("5", "1")))
    booth._edit_category(admin)
    created = next(item for item in booth.content["categories"] if item["slot"] == "5")
    assert created["label_audio"].startswith("recording-")
    monkeypatch.setattr(booth, "_choose", Mock(side_effect=("2", "1")))
    booth._edit_message("5", admin)
    created = next(item for item in booth.content["categories"] if item["slot"] == "5")
    assert created["messages"][0]["audio"].startswith("recording-")
    monkeypatch.setattr(booth, "_choose", Mock(side_effect=("2", "4", "1")))
    booth._edit_message("5", admin)
    created = next(item for item in booth.content["categories"] if item["slot"] == "5")
    assert created["messages"] == []
    # Deleting references does not destructively erase files needed by old snapshots.
    assert len(list(booth.store.media_root.glob("recording-*"))) == 2


def test_category_move_and_delete_confirmed(booth, admin, monkeypatch):
    monkeypatch.setattr(booth, "_choose", Mock(side_effect=("4", "4", "6", "1", "6", "3", "1")))
    booth._edit_category(admin)
    assert booth.content["categories"][0]["slot"] == "6"
    booth._edit_category(admin)
    assert booth.content["categories"] == []


def test_message_move_and_recorded_label(booth, admin, capture, monkeypatch):
    monkeypatch.setattr(booth, "_choose", Mock(side_effect=("1", "5", "2", "1")))
    booth._edit_message("4", admin)
    assert booth.content["categories"][0]["messages"][0]["slot"] == "2"
    monkeypatch.setattr(booth, "_key", Mock(return_value="#"))
    monkeypatch.setattr(booth, "_choose", Mock(side_effect=("2", "2", "1")))
    booth._edit_message("4", admin)
    assert booth.content["categories"][0]["messages"][0]["label_audio"].startswith("recording-")


def test_fresh_booths_share_only_state_for_resolved_directory(booth, tmp_path, monkeypatch, admin):
    candidate = copy.deepcopy(booth.content)
    candidate["timezone"] = "UTC"
    booth.store.save(candidate, admin)
    # Different spellings resolve to the same state key.
    alias = tmp_path.parent / (tmp_path.name + "-alias")
    alias.symlink_to(tmp_path, target_is_directory=True)
    monkeypatch.setenv("PAYPHONE_STATE_DIR", str(alias))
    second = InformationBoothSystem()
    assert second.store is booth.store
    assert second.weather_service is booth.weather_service
    assert second.content == candidate
    assert second.content is not booth.content
    assert second.hardware_handler is not booth.hardware_handler
    assert second.audio_handler is not booth.audio_handler

    monkeypatch.setenv("PAYPHONE_STATE_DIR", str(tmp_path / "other-state"))
    other = InformationBoothSystem()
    assert other.store is not booth.store
    assert other.weather_service is not booth.weather_service
    assert other.content == default_content()
    assert not other.weather_service.cache


@pytest.mark.parametrize("preview", ["speech", "message", "label", "audio"])
def test_admin_previews_poll_and_stop_on_expiry(booth, admin, monkeypatch, preview):
    generate_sample(booth.store.media_root / "sample.wav")
    booth.is_speaking.return_value = True
    booth.audio_handler.is_playing.return_value = True
    if preview == "message":
        monkeypatch.setattr(booth, "_choose", Mock(side_effect=("1", "3")))
    before = admin.calls
    def expire():
        if admin.calls > before + 2:
            admin.authorized = False
        Capability.require_authorized(admin)
    monkeypatch.setattr(admin, "require_authorized", expire)
    with pytest.raises(PermissionError):
        if preview == "speech":
            booth._speak("A long administrator diagnostic.", admin)
        elif preview == "message":
            booth._edit_message("4", admin)
        elif preview == "label":
            booth._prompt_part("A long menu label.", None, admin)
        else:
            booth._play_audio("sample.wav", admin)
    assert admin.calls > before + 2
    if preview in ("speech", "message", "label"):
        assert booth.say.call_args.kwargs == {"blocking": False}
        booth.speak.assert_not_called()
        booth.stop_speech.assert_called()
    else:
        booth.audio_handler.stop.assert_called()
    assert not booth.store.path.exists()


def test_compatibility_import_is_canonical_class():
    from examples.information_booth.system import InformationBoothSystem as example
    assert example is InformationBoothSystem
