# Information Booth / protected BIOS administration

## Scope

- Standard selectable Information Booth with configurable information categories/messages.
- Working weather, current time, local jokes, and local music prototypes (no paid API required).
- On-phone authenticated configuration after assembly; supplementary local JSON editing.
- Reserved configurable keypad escape `***#` returns to BIOS (application reset, not an OS reboot).
- Separate env-provisioned admin passcode, no insecure default.
- Explicit persistent default phone system restored after power loss; public picker if none or unavailable.

## Worker A: BIOS/runtime/security

Own existing BIOS/core/config/hardware/audio changes, new runtime/auth/persistence/speech helpers, related tests, BIOS docs. Do not edit Information Booth files.

Fix current lifecycle/input flaws: one hardware/audio allocation; one raw input consumer; no dequeue/requeue escape monitor; no long-press on press-only hardware; no nested call threads. Route filtered input to one cancellable active call session. Share runtime with plugins constructed using existing `(config)` signature. Cancellation must appear as on-hook to existing plugin loops and stop media. Do not start another consumer if prior navigation refuses to exit. `PhoneTree` checks cancellation after leaf actions as well as while waiting.

Authenticate before BIOS administration. `BIOS_ADMIN_PASSCODE`: 6–12 numeric digits, fail closed when absent/invalid; constant-time comparison; bounded input, no key/PIN logging, attempt cooldown, clear auth on hangup/exit, inactivity expiry. `***#` is a reserved escape, not authentication. Preserve order of unmatched prefixes with bounded inter-key timeout. Keep public selection per-call and do not silently promote `last_system` to default.

Use deterministic discovery anchored independently of CWD. `PAYPHONE_STATE_DIR` or repository-root `.payphone_state/`; BIOS `bios.json`; booth `information_booth.json`. Validated atomic JSON saves with fsync/replace, explicit failure; migrate legacy configuration without inferring an admin-chosen default. Ignore state in git. Invalid saved default/config falls back safely without overwriting corrupt source.

Implement runtime speech (offline eSpeak NG or existing available offline TTS) with controlled subprocesses, cancellable audio playback, clear dependency/setup diagnostics. Dynamic spoken system/admin menus are needed; do not depend on missing generated MP3s.

## Frozen minimal integration contract

Worker A must implement these interfaces, Worker B may code against them immediately:

1. `PhoneSystemBase.setup_admin_tree(admin_session) -> Optional[PhoneTree]` (default None). BIOS invokes after successful authentication.
2. Admin capability object method `require_authorized() -> None`, raises PermissionError when cancelled/expired. Booth must call immediately before every persisted mutation. No public path receives capability.
3. `PhoneSystemBase.speak(text: str) -> None`: cancellation-aware spoken output, usable within leaf actions. Existing `.say()`, `.stop_speech()`, `.is_speaking()` speech-handler protocol also supported for menu prompts.
4. `PhoneSystemBase.is_call_active() -> bool`, cancellation included; `.hardware_handler.input_queue` gives filtered session queue. `.phone_on_hook` true on session cancellation for existing plugins.
5. `payphone.config.persistence.state_directory() -> Path`; `atomic_write_json(path: Path, data: dict) -> None` (explicit exception on failure). B may create a temporary local stub only in its tests, never modify A's modules. Config reload/validation owned by each subsystem.
6. Booth's `setup_phone_tree()` creates its normal PhoneTree. Dynamic prompts can use standard PhoneTree speech-handler support or a small Booth-only subclass; no Booth edits to core.

## Worker B: Information Booth

Own new `phone_systems/information_booth/` package, standalone example compatibility, Booth tests/docs/audio setup script. Do not edit existing core/BIOS or LAM.

Canonical system metadata and configurable default services, categories/messages. Persistent schema validation, bounded sizes/unique slots, no traversal or escaped audio symlinks. Reload valid local edits next call; preserve last valid snapshot on invalid edits. Keep weather/time/jokes/music demo recognizable but functional. Weather: fixed HTTPS public endpoint (Open-Meteo proposed), configured lat/lon/units, bounded request timeout/body, validate fields, cache, announce offline/stale state, never play after cancellation. Current local time using zoneinfo; bundled jokes; local music with generated original sample and explicit unavailable diagnostics. No paid services and no fabricated weather. Document network/API terms verification limitation if not researched.

On-phone `setup_admin_tree`: category slots and recorded labels; message recording/playback/save/delete; service enable/disable; weather coordinates/units; timezone presets or OS-local; choose available local music. Use existing `payphone.audio.recording` backend, honoring recording settings. Preview and confirm before publishing. Cancel/escape/hangup must stop recording and discard unpublished audio. Recheck authorization before every mutation. Publish unique recordings before atomic JSON reference; failed save retains old content.

Re-export canonical class from `examples/information_booth/system.py` (no duplicate implementation).

## Verification and boundaries

Use `/Users/reidchatham/Developer/pay-phone/venv/bin/python`; worktree has no venv. Run targeted tests with `PYTHONDONTWRITEBYTECODE=1 ... -m pytest ... -o addopts='' -p no:cacheprovider`. Mock hardware/audio/HTTP/TTS/recording; never invoke main's process-killing startup. Never read secrets, `.env.payphone`, or `sd-card-backups`. No commits/pushes. Baseline 98 tests: BIOS/LAM pass initially, four failures in test_phone_tree then outer 120-second timeout; reproduce/report separately rather than claim full suite green.

Tests: one runtime/input owner, escape prefix routing/order and during playback/recording, cancellation/no overlapping calls, auth fail-closed/cooldown/expiry, public selection nonpersistent, explicit default survives new instance/different CWD, unavailable fallback, atomic failed save, Booth validation/current-time/mock-weather/local music, authenticated recording publish/cancel, persistent edited content and config. Final independent code/security review required. Physical keypad/audio/unplug verification remains hardware-only; do not claim performed.

## Progress

- Initial reconnaissance and plan complete.
- Baseline has existing failures/timeouts.
- Implementation complete in feature/information-booth-admin.
- Independent code/security reviews returned PASS after lifecycle, expiry, cancellation/persistence and cross-call cache fixes.
- Coordinator combined focused regression: 211 passed; whitespace check clean. Full suite remains blocked by existing navigation-test timeouts.
- Deployment still requires Python 3.10+, offline eSpeak, separately provisioned admin passcode, weather/timezone configuration and local music setup. Physical keypad/audio/recording, live weather/provider terms, wheel deployment and unplug/power-loss checks remain unverified.
- Implementation initially remained uncommitted; publication was subsequently authorized on 2026-10-20. The main checkout and existing sd-card-backups remain untouched.
- Publication preflight: focused 211 tests passed again; independent code/security pre-commit reviews returned PASS. Changes are grouped into BIOS/runtime, Information Booth, and implementation/review documentation commits.
