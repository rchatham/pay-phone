# Protected BIOS administration

## Handset operation

- Pickup launches only an **explicitly chosen persistent default**. With no default, or an unavailable default, the public system picker opens. Public selections last only for the current call; they do not write history or become startup defaults.
- Dial `***#` to stop the active session and return to the public picker. This is an application reset, **not an OS reboot and not authentication**. Long-press star and handset-hold detection are no longer used on press-only hardware.
- In the picker, press **0**, enter the separate administrator passcode, then **#**. The administrator menu provides **1**: choose/confirm a persistent default (0 clears it), **2**: a system's protected configuration menu, **0**: exit administration.
- Hangup, escape, administrator exit, or 120 seconds without keypad activity revokes authorization. Expiry is irreversible: late input checks the old deadline before renewal. The dispatcher and blocking admin speech poll authorization even without new input. Recording, network work and other plugin actions must cooperate with cancellation; the runtime never starts a second navigation consumer while an old action remains running. A quick pickup after hangup is retained and starts sequentially when the old action returns; another hangup cancels that pending pickup. Raw events are tagged with their enqueue-time session, so old queued/dequeued keys cannot leak into the next call.

## Deployment settings

Provision `BIOS_ADMIN_PASSCODE` through the deployment's environment/secret manager: **6–12 ASCII numeric digits**, no default. Missing, malformed, Unicode-digit or nonnumeric values disable administration. Do not reuse a public extension or other service credential. Do not put the passcode in BIOS/Booth JSON, repository files, command history or logs. Restart the service after changing the provisioned passcode.

Authentication collects at most 12 digits, rejects overflow, expires input after 30 seconds, uses constant-time comparison, and applies a 30-second cooldown after three failed attempts. Cooldown survives hangups in the running process; it is not a durable anti-tamper/rate-limit store and resets on process restart. Python hardware and core navigation do not log entered keys/PINs. Raw hardware never plays keypad tones. The runtime plays feedback only for delivered normal input, before the consumer can change input mode; passcode input and the complete reserved escape remain silent. Check separate Arduino firmware, serial capture and external logging before deploying.

Optional escape overrides:

| Setting | Default | Validation |
|---|---|---|
| `BIOS_ESCAPE_SEQUENCE` | `***#` | 3–12 characters, each `0–9`, `*` or `#` |
| `BIOS_ESCAPE_TIMEOUT` | `1.0` seconds | Finite number from 0.2 through 5 seconds |

The same settings can be set locally as `escape_sequence` and `escape_timeout` in BIOS JSON; environment overrides take precedence. Invalid environment overrides explicitly log a diagnostic and reserve `***#` with a one-second timeout. Choose a sequence that does not conflict with intended extensions. Unmatched prefixes are released in their original order after mismatch or the inter-key timeout; a complete escape is never delivered to plugins. A partial star prefix can therefore delay normal extension/rerecord input briefly. Keep the inter-key interval below the configured timeout while entering the escape.

## Offline dynamic speech

Install **eSpeak NG** on the host (`sudo apt install espeak-ng` on Raspberry Pi OS; `brew install espeak-ng` on macOS) and ensure `espeak-ng` is in the service's `PATH`. Existing `espeak` is accepted as an offline fallback. BIOS system names and administration menus are spoken at runtime; no generated BIOS MP3 files are required.

Speech synthesizes a private temporary WAV using argument-list subprocess execution and stdin, then plays it through the **same** runtime audio device. Synthesis is bounded to 15 seconds and text to 8192 characters. Escape/hangup terminates only the owned synthesis process and stops playback; temporary WAVs are removed. Missing dependency, synthesis timeout or playback failure produces an explicit diagnostic. Missing speech prevents usable spoken BIOS menus: provision the dependency before deploying. Audio initialization errors never kill other Python processes; select a working SDL audio device and release conflicting audio use manually.

## Persistent state and local editing

`payphone.config.persistence.state_directory()` resolves:

1. `PAYPHONE_STATE_DIR` when set (absolute recommended; relative values anchor to the installation/repository root).
2. Otherwise `<installation/repository root>/.payphone_state/`.

BIOS state is `bios.json`; Booth state is `information_booth.json` in the same directory. Discovery defaults to root-anchored `phone_systems/` and `plugins/`, ordered deterministically. Neither discovery nor default state depends on launch CWD. Scan directories and Python plugins are trusted executable code: never point discovery at writable/untrusted downloads.

Minimal BIOS file:

```json
{
  "default_system": "information_booth",
  "scan_paths": ["phone_systems", "plugins"],
  "escape_sequence": "***#",
  "escape_timeout": 1.0
}
```

Set `default_system` to `null` for the public picker on every pickup. Local BIOS edits load on the next BIOS instance/service restart. Booth owns its own validated next-call reload. Invalid saved configuration or an unavailable default falls back safely; startup and public discovery never overwrite corrupt source files. Fix invalid JSON deliberately using an authorized local account. BIOS JSON is bounded to 64 KiB.

Legacy root `.bios_config.json` is migrated only when the new `bios.json` is absent. Legacy `last_system`/`auto_launch` never infer an administrator-chosen default. The original legacy file is retained. Deprecated hold/auto-launch fields may be retained for compatibility but no longer control boot selection.

Saves validate JSON before writing, create a same-directory private temporary file (0600), flush/fsync, atomically replace, then fsync the parent directory. Exceptions propagate; failed replacement preserves old disk state and the in-memory snapshot. A directory-fsync failure **after** replacement leaves an uncertain durability outcome: inspect the saved file before retrying rather than assuming a rollback. New state directories are 0700; protect existing directories yourself and grant the service account write access. State and legacy configuration are git-ignored. `PAYPHONE_STATE_DIR` elsewhere must also be excluded from your backups/public sync as appropriate.

## Plugin integration contract

Plugins retain `(config)` constructors. BIOS injects one shared runtime during construction; plugins must not allocate hardware/audio or start independent call threads.

- `setup_phone_tree() -> PhoneTree`: public call tree, no administrator capability.
- `setup_admin_tree(admin_session) -> Optional[PhoneTree]`: default returns `None`; BIOS calls only after authentication. Early `admin_session.require_authorized()` checks raise `PermissionError` on revocation, inactivity or cancellation. Every persisted admin mutation must additionally use the final protected publication boundary: `atomic_write_json(path, data, commit=admin_session.protected_commit)` or `admin_session.protected_commit(lambda: os.link(staged, destination))` for exclusive recording publication. Stage/validate/fsync outside the guard; it locks, rechecks authorization, and publishes atomically under the same lock as hangup, revocation and cancellation. A cancellation that wins before publication prevents it; publication that wins is already committed and cannot be undone by later cancellation. See [shared commit contract](shared-commit-contract.md).
- `speak(text)`: blocking cancellable speech. `say(text, blocking=...)`, `stop_speech()`, `is_speaking()` implement the standard PhoneTree speech-handler protocol.
- `is_call_active()`: includes physical hook status and cancellation. Cancellation also makes legacy `phone_on_hook` reads true.
- `hardware_handler.input_queue`: this session's filtered queue, **not** raw hardware input. Only the runtime dispatcher reads the raw queue.
- Bound `audio_handler.play_file()` checks cancellation before starting and makes blocking playback interruptible. Leaf actions and recording loops must still check cancellation and clean up their own unpublished files. `PhoneTree` checks cancellation before and after actions.
- `state_directory() -> Path` and `atomic_write_json(path: Path, data: dict, *, commit=None) -> None` are shared persistence helpers; each subsystem owns schema validation/reloading. The optional callback runs only the final replacement, after staging/fsync. The writer raises on failure or denied authorization, cleans up unpublished temporary files, and does not update subsystem snapshots on denial.

A noncooperative plugin blocks further navigation rather than creating overlapping consumers. Stop/restart such a plugin only after investigating its action; the runtime's bounded shutdown does not claim it forcibly terminated Python threads.

## Verification limitations

Mocked runtime/auth/persistence/speech/LAM tests cover software paths. Physical keypad timing, USB audio routing, microphone cancellation, service environment provisioning, power-loss durability and unplug/replug behavior require device checks. Final independent code/security review remains a separate integration step. No hardware or process-killing main startup is required by focused tests.
