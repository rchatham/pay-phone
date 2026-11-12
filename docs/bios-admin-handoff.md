# Worker A handoff — BIOS/runtime/security

## Review follow-up — 2026-10-12

### Verdict: PASS (focused software verification; independent final review still required)

Resolved Worker A findings 1–5 from `docs/information-booth-review.md`. Published `docs/shared-commit-contract.md` first, and coordinated the exact optional `commit` callback with Worker B. No Booth files/tests, secrets/backups, startup, staging, commits, pushes or running services were touched by this follow-up.

### Follow-up files changed

- `payphone/core/system.py` — retain rapid pickup while a hung-up action unwinds, restart sequentially on the same call worker; a second hangup clears pending pickup. Poll capability during blocking admin speech without changing public speech behavior.
- `payphone/core/runtime.py` — generation-stamp raw hardware events at enqueue and reject stale events even if dequeued before rebinding; bind GPIO's producer to the same raw queue. Normal filtered input gets centralized DTMF before consumer delivery; PIN and complete escape stay silent. Poll admin expiry during long speech/no input. Hook/shutdown/cancellation share the publication lock.
- `payphone/bios/auth.py` — deadline-before-renewal and irreversible expiry; `protected_commit(replace)` performs final authorization and publication under the shared cancellation/revocation lock. Discard held credential prefixes before restoring normal tones.
- `payphone/config/persistence.py` — `atomic_write_json(path, data, *, commit=None)` stages/fsyncs before invoking the final replacement guard; denied publication cleans up the temporary file.
- `payphone/bios/config_manager.py` — thread the optional guard through BIOS save/default methods; preserve source and use safe defaults for deeply nested JSON `RecursionError`.
- `payphone/bios/bootloader.py` — BIOS confirmed default uses the final protected guard; revoked administration returns to the picker without attempting revoked speech.
- `tests/test_bios_runtime.py` — now **63 tests** (26 new regressions), including deterministic paused raw-event dispatch across generations, actual quick hangup/pickup, no overlapping navigation, irreversible late-input expiry during preview, idle dispatcher expiry, renewal before deadline, normal/PIN/escape tones, PIN terminator feedback race, held credential cleanup, deeply nested JSON preservation, cancellation during staged fsync, and serialized publication versus revocation/hangup/escape/direct session cancellation/shutdown.
- `docs/shared-commit-contract.md`, `docs/BIOS_ADMIN.md`, `payphone/bios/README.md`, `docs/bios-admin-handoff.md` — exact shared API, boundary semantics, lifecycle/input/expiry behavior, verification and handoff.

### Protected boundary semantics

Use `atomic_write_json(..., commit=admin_session.protected_commit)` for every admin JSON save; exclusive recording publication may use `admin_session.protected_commit(lambda: os.link(staged, destination))`. Stage/validate/fsync outside the guard. Cancellation/revocation that wins the shared lock before publication denies it with `PermissionError`, leaving old disk/in-memory state and no temporary file. Publication that wins is committed; later cancellation cannot undo an existing replacement/link. Directory fsync still occurs after replacement and retains the documented uncertain-durability error outcome. Worker B wired its JSON/recording publication to this interface and retained/polled its own Booth state/preview services.

### Verification actually run for this follow-up

Initial A baseline: **44 passed in 5.51s** (`test_bios_runtime`, `test_offline_speech`, `test_bios_defaults`). A later expanded run exposed a real raw-key cross-generation race (1 failed, 113 passed); fixed with enqueue-time generation tagging, not sleeps or weakened assertions.

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/reidchatham/Developer/pay-phone/venv/bin/python -m pytest tests/test_bios_runtime.py tests/unit/test_offline_speech.py tests/test_bios_defaults.py tests/unit/test_lam_plugin.py tests/unit/test_lam_recording.py tests/unit/test_phone_tree_core_behaviors.py -o addopts='' -p no:cacheprovider
```

**117 passed in 6.87s.**

Combined read-only verification of A and B tests:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/reidchatham/Developer/pay-phone/venv/bin/python -m pytest tests/test_bios_runtime.py tests/unit/test_offline_speech.py tests/test_bios_defaults.py tests/unit/test_lam_plugin.py tests/unit/test_lam_recording.py tests/unit/test_phone_tree_core_behaviors.py tests/unit/test_information_booth.py tests/integration/test_information_booth_runtime.py -o addopts='' -p no:cacheprovider
```

**211 passed in 11.48s.**

Concurrency regression repetition:

```bash
for run in 1 2 3 4 5; do
  PYTHONDONTWRITEBYTECODE=1 /Users/reidchatham/Developer/pay-phone/venv/bin/python -m pytest tests/test_bios_runtime.py -k 'quick_pickup or raw_backlog or protected_replacement or cancellation_during_staging or late_admin_input or dispatcher_expires' -o addopts='' -p no:cacheprovider -q || exit $?
done
```

All five runs: **16 passed, 47 deselected** (0.63s, 0.65s, 0.63s, 0.70s, 0.62s). `git diff --check` passed without output. Manual source review checked lock ordering, final publication/cancellation linearization, current-session identity, PIN feedback ordering and pending pickup reset. No real hardware/audio/synthesis/network, startup, power-loss or full legacy suite verification was performed; earlier baseline full-suite ALSA/mock issues/timeouts remain out of scope. Parent must run independent final code/security review on the stable combined diff.

## Original implementation handoff (historical; API updates above supersede it)

### Verdict: PASS (focused software verification)

Worker A implementation is complete. Frozen integration interfaces are unchanged. No Information Booth implementation, Booth tests/docs/examples, root README/setup metadata, main entrypoint, secrets or backup files were edited by A. No staging, commits or pushes were performed. Shared working-tree changes outside the files listed below belong to other workers/coordinator.

## Exact Worker A files

- `.gitignore` — ignores private runtime state and legacy BIOS JSON.
- `payphone/config/persistence.py` — `REPOSITORY_ROOT`, `state_directory() -> Path`, `atomic_write_json(path: Path, data: dict) -> None`; validated JSON, private temp file, fsync/replace/directory fsync, explicit failures.
- `payphone/config/settings.py` — anchors default/relative `AUDIO_DIR` to installation root.
- `payphone/core/runtime.py` — `PhoneRuntime`, `CallSession`, `SessionHardware`, `SessionAudio`, `shared_runtime(runtime)` constructor/call injection; one raw dispatcher and ordered reserved-escape matching.
- `payphone/core/system.py` — one runtime allocation, bound cancellable plugin handlers, compatibility hook property, single navigation thread, shared construction, speech/admin interfaces.
- `payphone/core/phone_tree.py` — default audio reuses active runtime; cancellation checks before/after leaf actions, cancellable return pause, ordered first extension digit (no dequeue/requeue), no entered-key/extension logging, deterministic zero timeout.
- `payphone/audio/handler.py` — respects selected audio driver, explicit device failures instead of killing other processes, stoppable playback/tones, safe legacy recording subprocess argument list.
- `payphone/audio/speech.py` — offline eSpeak NG/eSpeak WAV synthesis on controlled subprocess, existing shared audio playback, cancellation/timeout/temp cleanup/setup diagnostics.
- `payphone/hardware/gpio_keypad.py`, `payphone/hardware/serial_handler.py` — removes input-value logging; serial accepts only single valid key events. BIOS/base allocates GPIO without raw keypad tones.
- `payphone/bios/auth.py` — environment-only 6–12 ASCII numeric passcode, fail closed, bounded PIN input, constant-time compare, in-process cooldown, revocable session capability/inactivity expiry.
- `payphone/bios/config_manager.py` — anchored BIOS state/schema, explicit default, atomic validated writes, safe legacy migration, no public writes/history promotion, corrupt-state preservation.
- `payphone/bios/system_manager.py` — deterministic root-anchored discovery; canonical package path preserved when plugins are scanned first.
- `payphone/bios/bootloader.py` — sequential call switching/escape, public picker, authenticated BIOS/system administration, confirmed persistent default; no long-press monitor, nested call threads or default-configuration retry hot loop.
- `tests/test_bios_runtime.py` — 37 focused mocked lifecycle/input/auth/persistence/discovery tests.
- `tests/unit/test_offline_speech.py` — 4 mocked subprocess/cancellation/dependency/bounds tests.
- `docs/BIOS_ADMIN.md`, `payphone/bios/README.md`, `docs/SECRETS_MANAGEMENT.md` — deployment/admin/runtime/security documentation.
- `docs/bios-admin-handoff.md` — this handoff.

## Exact integration interfaces / behavior

1. `PhoneSystemBase.setup_admin_tree(admin_session) -> Optional[PhoneTree]` defaults to `None`; BIOS calls only after successful authentication.
2. `payphone.bios.auth.AdminSession.require_authorized() -> None` raises `PermissionError` after revocation, cancellation/hangup, or 120-second keypad inactivity. Plugins must recheck immediately before every persisted mutation. Public call paths receive no capability.
3. Base `speak(text: str) -> None`, `say(text, blocking=True)`, `stop_speech()`, `is_speaking()` use runtime speech. Cancellable plugin actions should use these rather than private TTS engines.
4. Base `is_call_active() -> bool` includes cancellation; legacy `phone_on_hook` reads become true after cancellation. `hardware_handler.input_queue` is the bound filtered `CallSession.input_queue`; raw queue is `runtime.hardware.input_queue`, read only by dispatcher.
5. Shared persistence functions have exactly the frozen signatures; each subsystem owns its validation/reload.
6. Normal `setup_phone_tree()` and `(config)` constructors remain compatible. BIOS wraps constructors and navigation in `shared_runtime(runtime)`. Plugins may not independently `start_call()`/`run()` when shared.

`***#` cancels and stops media, then the **same call worker** waits for old navigation to return before binding a new public-picker session. A stubborn action does not cause another navigation thread/consumer. Auth entry is picker key `0`; escape itself is not authorization. Administration offers default selection/confirmation and invocation of system-specific trees. Public selection writes nothing. Default selection is the only boot-selection mutation.

`BIOS_ESCAPE_SEQUENCE` overrides `escape_sequence`: 3–12 keypad characters. `BIOS_ESCAPE_TIMEOUT` overrides `escape_timeout`: finite 0.2–5 seconds. Invalid overrides explicitly diagnose and reserve default `***#` / one second. Unmatched prefixes preserve order; partial star prefixes are held for the configured inter-key interval. No press/release inference remains.

`PAYPHONE_STATE_DIR` (relative values root-anchored) or root `.payphone_state/`; BIOS `bios.json`, Booth `information_booth.json`. Legacy root `.bios_config.json` migration never promotes `last_system`. Failed replacement preserves old disk/in-memory values; directory-fsync failure after replacement has an explicitly documented uncertain-durability outcome.

## Verification actually run

Baseline focused check before implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/reidchatham/Developer/pay-phone/venv/bin/python -m pytest tests/test_bios_defaults.py tests/unit/test_lam_plugin.py tests/unit/test_lam_recording.py -o addopts='' -p no:cacheprovider
```

**45 passed in 0.95s.**

Final focused check, including Worker B's available real-runtime integration tests:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/reidchatham/Developer/pay-phone/venv/bin/python -m pytest tests/test_bios_runtime.py tests/unit/test_offline_speech.py tests/test_bios_defaults.py tests/unit/test_lam_plugin.py tests/unit/test_lam_recording.py tests/unit/test_phone_tree_core_behaviors.py tests/integration/test_information_booth_runtime.py -o addopts='' -p no:cacheprovider
```

**96 passed in 4.12s.** `git diff --check` also passed (no output). Earlier focused runs exposed/fixed canonical discovery namespace hiding and a pre-existing zero-timeout edge; the duplicate temporary Booth end-to-end test was removed per coordinator request.

Tests cover shared construction/default tree audio reuse, single dispatcher, unmatched/overlapping escape prefix order/timeout, escape during playback and cooperative recording, stubborn cancelled navigation/no overlapping calls, no credential input logging, fail-closed provisioning, bounded PIN overflow, constant-time comparison/cooldown, capability revocation/expiry, public nonpersistence, explicit defaults/anchored discovery across CWD, unavailable/corrupt fallback, legacy migration, failed atomic saves, cancellation before/after actions, speech cancellation during synthesis/playback, missing dependency and bounded text. Existing LAM tests remain green.

## Blockers / final integration responsibilities

- **No implementation blocker in Worker A's scope.** Do not claim the full legacy suite is green: coordinator reports four pre-existing `test_phone_tree` failures followed by timeout, including compatibility-wrapper ALSA availability failure. A did not rerun the full timeout-prone suite or invoke `payphone.main`.
- Coordinator explicitly assigned full BIOS → Booth → `***#` → authentication → confirmed persistent default → reconstructed BIOS/different-CWD integration to Worker B (`tests/integration/test_information_booth_bios.py` anticipated). Only `test_information_booth_runtime.py` existed at A's final run. Do not duplicate that pending test in A's test file; run the eventual integration test during final integration.
- Independent code/security review remains required, especially lifecycle transitions, authorization-before-mutation and cancellation cleanup.
- Physical keypad/audio/microphone, service environment, unplug and power-loss checks remain hardware-only and were **not** performed. eSpeak must be installed on the deployment host; no real synthesis/audio/network was invoked by A's tests.
- Legacy real main's process-killing startup is intentionally untouched/uninvoked. This implementation removes process-killing recovery from owned audio initialization only.
