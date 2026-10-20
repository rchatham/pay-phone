# Worker B handoff — Information Booth

## Verdict: PASS (scoped automated implementation)

Implemented a canonical BIOS-selectable Booth with editable persisted categories,
messages, recorded category/message labels and content, service switches, weather
coordinates/units, timezone presets and local music selection. Public services use
actual current time, validated fixed-host Open-Meteo responses/cache/offline states,
local jokes, and a runnable original-music WAV generator. Handset editing requires
Worker A's capability, previews/confirms changes, and cancels/discards unpublished
takes on escape/hangup/expiry; no duplicate hardware, audio owner or LAM backend.

## Review follow-up — Worker B findings resolved (2026-10-12)

Retained `ContentStore` and `WeatherService` per **resolved state directory** in
`phone_systems/information_booth/state.py`. The registry lives outside discovery's
re-executed `system.py`; it retains only data, not systems, runtime/session handlers,
capabilities or cancellation callbacks. BIOS still constructs a fresh Booth with
fresh session-bound handlers and an independent copied content snapshot each call.
Different state directories remain isolated; process restart still resets memory.

All admin diagnostics, text/recorded previews and menu speech now poll capability
while waiting and stop on expiry/cancellation. Authorization `PermissionError` is
not swallowed by audio or admin operation handlers as a generic `OSError`.

Followed `docs/shared-commit-contract.md`: every Booth handset JSON save passes
`commit=admin.protected_commit` to `atomic_write_json`; recording's exclusive link
publication also uses `protected_commit`. JSON staging/fsync stays outside the lock;
only final replacement is guarded. Denied staged saves preserve disk/memory and
remove the temporary file. Post-replacement fsync uncertainty/media retention stays
unchanged. No A-owned files, root README/setup.py, secrets/backups/startup, commits
or pushes were touched in this follow-up.

Current focused verification (specified interpreter, after shared API implementation):

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/reidchatham/Developer/pay-phone/venv/bin/python -m pytest \
  tests/unit/test_information_booth.py tests/integration/test_information_booth_runtime.py \
  tests/unit/test_lam_recording.py -o addopts='' -p no:cacheprovider
```

**109 passed**: 83 Booth unit + 11 actual shared-runtime/BIOS integration + 15
unchanged shared recording tests. New tests include **two actual BIOS hook/pickup,
call-thread and discovery cycles**: customized spoken content followed by corrupt
JSON (bad source preserved), and online weather followed by aged-cache/offline
weather (explicitly stale report). They assert fresh instances/handlers, shared
state only and no duplicate hardware/audio owners. Also covered resolved-directory
aliases/isolation, capability polling for all preview types, real admin expiry and
irreversible late confirmation, protected callback wiring, and cancellation/revocation
during actual staged JSON fsync. The initial new regression run failed as expected
before implementation; the current focused suite passes. No hardware/live-HTTP/TTS
or full-repository verification is claimed; final coordinator review remains needed.

Final combined regression after the coordinator observed a preview-test timing
race: **208 passed**. The recorded-preview test now synchronizes actual playback
start before expiring the real capability by aging `last_activity` under its
lock; WAV setup cannot expire authorization before the operation begins.

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/reidchatham/Developer/pay-phone/venv/bin/python -m pytest \
  tests/test_bios_defaults.py tests/test_bios_runtime.py tests/unit/test_offline_speech.py \
  tests/unit/test_information_booth.py tests/integration/test_information_booth_runtime.py \
  tests/unit/test_lam_plugin.py tests/unit/test_lam_recording.py \
  tests/unit/test_phone_tree_core_behaviors.py -o addopts='' -p no:cacheprovider
```

AST parsing passed for seven scoped Python files; scoped Python/docs trailing
whitespace checks passed. Additional follow-up files: `state.py`, `content.py`,
`system.py`, Booth README, this handoff, and the two Booth test files only.

## Files owned/changed

- `phone_systems/information_booth/__init__.py` — package marker.
- `phone_systems/information_booth/content.py` — bounded version-1 schema, safe
  state-local media references, last-valid snapshot reload, capability-checked
  atomic persistence, conservative media retention after uncertain saves.
- `phone_systems/information_booth/state.py` — resolved-directory process-local
  store/weather retention across rediscovery and fresh BIOS calls, no handlers.
- `phone_systems/information_booth/services.py` — actual clock/zoneinfo, local
  jokes, fixed-host HTTPS weather, validation/cache/stale diagnostics, four-second
  caller bound and process-wide single outstanding HTTP worker.
- `phone_systems/information_booth/system.py` — canonical metadata/constructor,
  Booth-only iterative tree, dynamic/recorded-label public menus, protected editor,
  shared recording backend staging/preview/exclusive publication/cleanup.
- `phone_systems/information_booth/README.md` — full setup, handset keys, local
  editing schema, dependency/security/network limitations.
- `scripts/generate_information_booth_music.py` — original eight-second PCM WAV
  generator with atomic publication; no downloads/paid APIs/non-original music.
- `examples/information_booth/system.py` — canonical class re-export only.
- `examples/information_booth/run.py` — unambiguous canonical import for direct run.
- `examples/information_booth/README.md` — compatibility/setup instructions.
- `tests/unit/test_information_booth.py` — 83 mocked Booth tests.
- `tests/integration/test_information_booth_runtime.py` — 11 actual shared-runtime/BIOS
  integration tests with hardware/audio/TTS/capture mocked.
- `docs/information-booth-handoff.md` — this handoff.

No Worker A-owned BIOS/core/config/hardware/audio files or tests were edited.
No staging, commits, pushes, real main startup, servers, secret files or backups.
Root README was left to the coordinator.

## Interfaces exercised with Worker A's actual implementation

- `PhoneSystemBase.setup_admin_tree(admin_session)`; no public capability passed.
- `admin_session.require_authorized()` during admin speech/previews and
  `admin_session.protected_commit()` at every final persisted publication; real
  `AdminSession` rejects cancelled/expired sessions.
- `speak`, `say(blocking=False)`, `stop_speech`, `is_speaking`.
- `is_call_active`, cancellation-aware `phone_on_hook`, filtered
  `hardware_handler.input_queue`.
- Shared-runtime `(config)` construction, `SessionAudio`/`SessionHardware`; tests
  fail if another AudioHandler/GPIOHandler/SerialHandler is allocated.
- Actual `state_directory()` and `atomic_write_json()`.
- Actual SystemManager file-path discovery outside the repository CWD.
- Actual runtime `***#` escape routing while awaiting input, playing audio, and
  capturing audio; cancellation stops Booth work and invalidates the capability.

The Booth uses a small PhoneTree subclass, with one iterative runner per session.
Its weather I/O worker never consumes keypad input, plays media or mutates content.

## Initial verification actually run (before review follow-up)

From this worktree with `/Users/reidchatham/Developer/pay-phone/venv/bin/python`:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/reidchatham/Developer/pay-phone/venv/bin/python -m pytest \
  tests/unit/test_information_booth.py tests/integration/test_information_booth_runtime.py \
  tests/unit/test_lam_recording.py -o addopts='' -p no:cacheprovider
```

**96 passed**: 76 Booth unit + five Booth/runtime integration + 15 unchanged shared
recording tests. Initial Booth mocked run was 70 passing before integration;
subsequent hardening added wall-clock weather bounds, failed-preview suppression,
recorder collision protections and more tests.

Also ran:

- Music setup CLI through the specified interpreter with `--output` pointing to a
  task-owned temporary directory; inspected WAV metadata: 128,000 frames, 16 kHz,
  mono PCM16, eight seconds. Temporary output was cleaned automatically.
- `git diff --check -- examples/information_booth` — clean.
- AST parsing and trailing-whitespace checks on all 10 scoped Python files — pass.
- `find_packages()` check using the specified venv — **not available**, because
  `setuptools` is missing in that venv. No dependencies were installed.

Actual integration was tested, not only frozen-interface mocks. Hardware, live
HTTP, speech synthesis and microphone drivers remain mocked. Full-repository tests
were not claimed green; the plan records baseline core failures/timeouts, and the
coordinator/Worker A owns final combined regression verification.

## Persistence/cancellation notes

- Categories use unique slots 4–9; message slots 1–9. Service keys 1–3 remain
  reserved so the weather/time/jokes/music demo remains recognizable.
- JSON: 64 KiB maximum, labels 100 characters, text 4,000; audio: simple WAV names
  only, 32 MiB maximum, no traversal or audio-file/directory symlinks.
- Valid local JSON edits reload next call. Invalid edits preserve last valid memory
  and corrupt source across fresh BIOS instances in the same process/state directory.
  A fresh process falls back to defaults without overwriting it.
- Recording uses the existing configured backend with the existing duration setting
  clamped to 1–120 seconds. Booth owns the monotonic capture timeout rather than
  stopping streams from their audio callback. New recording files are exclusive
  UUID names; old referenced recordings are never overwritten/deleted.
- Audio is fsynced and published exclusively before atomic JSON reference save.
  Pre-replacement save errors retain old state and remove unpublished audio.
  Post-replacement directory-fsync errors cannot honestly guarantee rollback:
  preserve media referenced by the possibly replaced JSON and report uncertain
  durability. The operator must inspect on-disk state before retrying.
- Cleanup of this operation's unpublished files is allowed after authorization
  expires; that is safety cleanup, not permission to publish configuration.

## Deployment caveats / remaining verification

- Python **3.10+**, OS tzdata (or Python tzdata), offline `espeak-ng`/`espeak`, normal
  payphone dependencies, and optional shared sounddevice/soundfile/NumPy/PortAudio
  recording setup are required. No existing missing menu MP3s are used.
- Default weather is New York City (40.7128, -74.0060), not inferred from the phone.
  Set weather coordinates and clock timezone for deployment. Default timezone is
  OS-local. The cache is in memory, not durable across power loss.
- Generate `sample.wav` under the same PAYPHONE_STATE_DIR as the service. Otherwise
  music announces unavailable; do not mistake that for a bundled artifact.
- The tracked parent `phone_systems/__init__.py` exists, so the new Python package
  is eligible for existing find_packages. No package_data is needed for generated
  media. Wheel construction was not verified (missing setuptools), and the root
  `scripts/` generator is supplied with the repository checkout, not installed by
  current setup.py. Use checkout deployment or separately supply script/local WAVs.
- Live Open-Meteo API availability, schema and current licensing/commercial terms
  were not externally researched or audited. Verify provider docs/terms before
  public deployment; the README includes primary URLs and attribution behavior.
- The caller is bounded to four seconds even on stalled DNS/header parsing. A
  stalled resolver may leave one daemon request outstanding process-wide, during
  which weather returns unavailable rather than spawning additional workers.
- Keep state private; new state/audio directories are 0700 and handset recording
  files 0600. Existing directory permissions are not forcibly changed. Local JSON
  editing and handset editing should not happen concurrently: saves replace a
  complete snapshot and do not merge external concurrent changes.
- Retained old/orphan published audio can accumulate. Manual operator cleanup must
  respect current config, in-flight calls and private backups; no destructive GC.
- Direct example mode provides the public Booth, not BIOS administration; the
  canonical BIOS runtime provides authenticated editing and BIOS escape navigation.
- Physical keypad/handset/USB audio/microphone quality, live provider requests,
  real filesystem fault behavior, unplug/power-loss restoration are not performed.
- Final independent code/security review and coordinator combined regression pass
  remain required by the plan. No claim of production/hardware merge-readiness.
