from types import SimpleNamespace
from unittest.mock import Mock

import time

import pytest

from payphone.audio import recording as record


INPUT_DEVICES = [
    {"index": 0, "name": "Built-in Output", "max_input_channels": 0, "default_samplerate": 44100},
    {"index": 1, "name": "USB Audio Mic", "max_input_channels": 1, "default_samplerate": 48000},
    {"index": 2, "name": "Audio Injector", "max_input_channels": 2, "default_samplerate": 44100},
]


@pytest.fixture(autouse=True)
def reset_recording_state(monkeypatch):
    monkeypatch.setattr(record, "is_recording", False)
    monkeypatch.setattr(record, "filename", None)
    monkeypatch.setattr(record, "file", None)
    monkeypatch.setattr(record, "stream", None)
    monkeypatch.setattr(record, "samplerate", 44100)
    monkeypatch.setattr(record, "device", None)
    monkeypatch.setattr(record, "channels", 1)
    monkeypatch.setattr(record, "start_time", int(time.time()))


def patch_sounddevice(monkeypatch, query_devices):
    monkeypatch.setattr(record, "_RECORDING_AVAILABLE", True)
    monkeypatch.setattr(record, "sd", SimpleNamespace(query_devices=Mock(side_effect=query_devices)))


def test_list_input_devices_filters_output_only_devices(monkeypatch):
    patch_sounddevice(monkeypatch, [INPUT_DEVICES])

    devices = record.list_input_devices()

    assert [device["index"] for device in devices] == [1, 2]


def test_list_input_devices_wraps_query_failure(monkeypatch):
    monkeypatch.setattr(record, "_RECORDING_AVAILABLE", True)
    monkeypatch.setattr(
        record,
        "sd",
        SimpleNamespace(query_devices=Mock(side_effect=RuntimeError("portaudio failed"))),
    )

    with pytest.raises(RuntimeError, match="Could not query audio input devices"):
        record.list_input_devices()


def test_init_uses_integer_device_index(monkeypatch):
    patch_sounddevice(monkeypatch, [INPUT_DEVICES])

    record.init(preferred_device="2", preferred_samplerate=22050, preferred_channels=2)

    assert record.device == 2
    assert record.samplerate == 22050
    assert record.channels == 2


def test_init_matches_device_name_fragment(monkeypatch):
    patch_sounddevice(monkeypatch, [INPUT_DEVICES])

    record.init(preferred_device="injector", preferred_samplerate=44100, preferred_channels=1)

    assert record.device == 2


def test_init_uses_default_input_device_when_unset(monkeypatch):
    patch_sounddevice(monkeypatch, [INPUT_DEVICES, INPUT_DEVICES[1]])

    record.init(preferred_device=None, preferred_samplerate=44100, preferred_channels=1)

    assert record.device == 1


def test_init_reports_missing_configured_device(monkeypatch):
    patch_sounddevice(monkeypatch, [INPUT_DEVICES, INPUT_DEVICES])

    with pytest.raises(RuntimeError, match="Configured input device index 99 was not found"):
        record.init(preferred_device=99, preferred_samplerate=44100, preferred_channels=1)


def test_check_recording_available_reports_import_error(monkeypatch):
    monkeypatch.setattr(record, "_RECORDING_AVAILABLE", False)
    monkeypatch.setattr(record, "_IMPORT_ERROR", "missing portaudio")

    with pytest.raises(RuntimeError, match="missing portaudio"):
        record.list_input_devices()


def test_init_reports_no_input_devices(monkeypatch):
    patch_sounddevice(monkeypatch, [[], []])

    with pytest.raises(RuntimeError, match="No audio input devices found"):
        record.init()


def test_init_reports_missing_configured_device_name(monkeypatch):
    patch_sounddevice(monkeypatch, [INPUT_DEVICES, INPUT_DEVICES])

    with pytest.raises(RuntimeError, match="Configured input device 'not-a-mic' was not found"):
        record.init(preferred_device="not-a-mic", preferred_samplerate=44100, preferred_channels=1)


def test_init_rejects_too_many_channels(monkeypatch):
    patch_sounddevice(monkeypatch, [INPUT_DEVICES, INPUT_DEVICES])

    with pytest.raises(RuntimeError, match="supports 1"):
        record.init(preferred_device=1, preferred_samplerate=44100, preferred_channels=2)


def test_init_reports_default_device_that_is_not_input_capable(monkeypatch):
    patch_sounddevice(monkeypatch, [INPUT_DEVICES, INPUT_DEVICES[0], INPUT_DEVICES])

    with pytest.raises(RuntimeError, match="Default input device is not input-capable"):
        record.init(preferred_device=None, preferred_samplerate=44100, preferred_channels=1)


def test_start_recording_creates_wav_stream_and_writes_callback_data(tmp_path, monkeypatch):
    written = []
    started = Mock()
    input_stream = Mock(start=started)
    sound_file = Mock(write=lambda data: written.append(data), close=Mock())

    class FakeSoundFile:
        def __new__(cls, *args, **kwargs):
            sound_file.args = args
            sound_file.kwargs = kwargs
            return sound_file

    def fake_input_stream(**kwargs):
        input_stream.kwargs = kwargs
        return input_stream

    class FakeInputData:
        def copy(self):
            return "copied-audio"

    monkeypatch.setattr(record, "_RECORDING_AVAILABLE", True)
    monkeypatch.setattr(record, "sf", SimpleNamespace(SoundFile=FakeSoundFile))
    monkeypatch.setattr(record, "sd", SimpleNamespace(InputStream=fake_input_stream, CallbackStop=RuntimeError))
    monkeypatch.setattr(record, "samplerate", 22050)
    monkeypatch.setattr(record, "channels", 1)
    monkeypatch.setattr(record, "device", 7)

    target = tmp_path / "messages" / "001.wav"
    record.start_recording(target, timeout=0)
    input_stream.kwargs["callback"](FakeInputData(), 128, object(), None)

    assert target.parent.exists()
    assert sound_file.args == (str(target),)
    assert sound_file.kwargs == {"mode": "w", "samplerate": 22050, "channels": 1}
    assert input_stream.kwargs["samplerate"] == 22050
    assert input_stream.kwargs["channels"] == 1
    assert input_stream.kwargs["device"] == 7
    assert written == ["copied-audio"]
    started.assert_called_once_with()


def test_start_recording_callback_stops_on_timeout(tmp_path, monkeypatch):
    timeout_callback = Mock()
    input_stream = Mock(start=Mock())
    sound_file = Mock(write=Mock(), close=Mock())

    def fake_input_stream(**kwargs):
        input_stream.kwargs = kwargs
        return input_stream

    class FakeInputData:
        def copy(self):
            return "copied-audio"

    monkeypatch.setattr(record, "_RECORDING_AVAILABLE", True)
    monkeypatch.setattr(record, "sf", SimpleNamespace(SoundFile=Mock(return_value=sound_file)))
    monkeypatch.setattr(record, "sd", SimpleNamespace(InputStream=fake_input_stream))
    record.start_recording(tmp_path / "001.wav", timeout=1, timeout_callback=timeout_callback)
    monkeypatch.setattr(record, "start_time", int(time.time()) - 10)

    input_stream.kwargs["callback"](FakeInputData(), 128, object(), None)

    input_stream.stop.assert_called_once_with()
    timeout_callback.assert_called_once_with()
    sound_file.write.assert_not_called()


def test_finish_recording_stops_and_closes_resources(monkeypatch):
    fake_stream = Mock()
    fake_file = Mock()
    monkeypatch.setattr(record, "_RECORDING_AVAILABLE", True)
    monkeypatch.setattr(record, "is_recording", True)
    monkeypatch.setattr(record, "stream", fake_stream)
    monkeypatch.setattr(record, "file", fake_file)

    record.finish_recording()

    fake_stream.stop.assert_called_once_with()
    fake_stream.close.assert_called_once_with()
    fake_file.close.assert_called_once_with()
    assert record.is_recording is False
    assert record.stream is None
    assert record.file is None


def test_cancel_recording_deletes_partial_file(tmp_path, monkeypatch):
    partial = tmp_path / "001.wav"
    partial.write_bytes(b"partial")
    fake_stream = Mock()
    fake_file = Mock()
    monkeypatch.setattr(record, "_RECORDING_AVAILABLE", True)
    monkeypatch.setattr(record, "is_recording", True)
    monkeypatch.setattr(record, "filename", partial)
    monkeypatch.setattr(record, "stream", fake_stream)
    monkeypatch.setattr(record, "file", fake_file)

    record.cancel_recording()

    assert not partial.exists()
    assert record.filename is None
    assert record.is_recording is False
