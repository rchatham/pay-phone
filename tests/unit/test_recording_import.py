"""Recording remains optional on hosts without native audio libraries."""

import builtins
from pathlib import Path
import runpy

import pytest


@pytest.mark.parametrize("module", ["sounddevice", "soundfile"])
@pytest.mark.parametrize("error", [ImportError, OSError])
def test_missing_audio_dependency_defers_failure_until_recording(monkeypatch, module, error):
    original_import = builtins.__import__

    def import_without_audio(name, *args, **kwargs):
        if name == module:
            raise error("native audio unavailable")
        if name in {"sounddevice", "soundfile"}:
            return object()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_audio)
    backend = runpy.run_path(str(Path(__file__).resolve().parents[2] / "payphone/audio/recording.py"))
    assert backend["_RECORDING_AVAILABLE"] is False
    with pytest.raises(RuntimeError, match="native audio unavailable"):
        backend["init"]()
