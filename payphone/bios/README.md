# Payphone BIOS/Bootloader

The BIOS owns one hardware/audio runtime and routes each call to a selectable phone system. See [protected administration and deployment](../../docs/BIOS_ADMIN.md) for the full operator guide and security/persistence contract.

## Operation

- Pickup launches an explicitly chosen persistent default, otherwise the public picker.
- Public system selection is per-call and never silently becomes a persistent default.
- Dial `***#` to cancel the active session and return to the public picker. This is not an OS reboot and grants no administrative access. Press-only hardware does not support long-press detection.
- Press **0** in the picker for administration. `BIOS_ADMIN_PASSCODE` must be provisioned separately as 6–12 ASCII numeric digits; missing/invalid values fail closed.
- Administrator menu: **1** choose/confirm the persistent default, **2** system-specific configuration, **0** exit. Hangup/escape/exit/inactivity clears authorization.

## State and discovery

`PAYPHONE_STATE_DIR` or root `.payphone_state/` holds `bios.json` and subsystem state. A legacy root `.bios_config.json` can migrate, but its `last_system` does not imply an administrator-chosen default. Invalid saved state falls back safely without overwriting the source.

Default scan paths are root-anchored `phone_systems/` and `plugins/`, independent of CWD. Discovery is ordered deterministically and presents up to nine systems. Paths are trusted Python code, not an untrusted upload/install mechanism.

```json
{
  "default_system": null,
  "scan_paths": ["phone_systems", "plugins"],
  "escape_sequence": "***#",
  "escape_timeout": 1.0
}
```

## Plugins

Create `phone_systems/<id>/system.py` or a trusted plugin directory containing a `PhoneSystemBase` subclass with its existing `(config)` constructor and `setup_phone_tree()` method. Use the base's bound handlers; do not start another hardware owner or navigation thread. Optional static `get_metadata()` supplies spoken names/descriptions. Optional `setup_admin_tree(admin_session)` returns a protected tree; check `require_authorized()` early and use `atomic_write_json(..., commit=admin_session.protected_commit)` for final persisted replacement (or `protected_commit` around exclusive recording publication). Staging/fsync stays outside the guard; cancellation/revocation and publication are serialized. See [the shared commit contract](../../docs/shared-commit-contract.md).

Dynamic prompts use `PhoneTree("", speech_text="...", speech_handler=self, audio_handler=self.audio_handler)` or `self.speak(text)`. BIOS requires offline `espeak-ng` (or `espeak`) in the service PATH rather than generated menu MP3s. Speech synthesis/playback is bounded and cancellable through the existing audio device.

## Components

- `bootloader.py`: public selection, authenticated admin routing, and sequential session transitions.
- `auth.py`: fail-closed provisioning, bounded PIN entry/cooldown, revocable inactivity-limited capability.
- `config_manager.py`: validated BIOS schema and explicit default persistence.
- `system_manager.py`: deterministic anchored discovery and constructor loading.
- `../core/runtime.py`: sole raw dispatcher, ordered escape filtering, session cancellation and guarded media.
- `../config/persistence.py`: anchored state and fsync/atomic JSON replacement.

## Focused verification

```bash
PYTHONDONTWRITEBYTECODE=1 /path/to/venv/bin/python -m pytest \
  tests/test_bios_runtime.py tests/unit/test_offline_speech.py \
  tests/test_bios_defaults.py tests/unit/test_lam_plugin.py \
  tests/unit/test_lam_recording.py tests/unit/test_phone_tree_core_behaviors.py \
  -o addopts='' -p no:cacheprovider
```

These mock hardware/audio/subprocesses and do not invoke the process-killing legacy main startup. Physical keypad/audio/power-loss checks remain device-only verification.
