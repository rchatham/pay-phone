# Shared protected commit contract — Worker A / Worker B

Frozen interface for this follow-up:

```python
AdminSession.protected_commit(replace: Callable[[], None]) -> None
atomic_write_json(path: Path, data: dict, *,
                  commit: Optional[Callable[[Callable[[], None]], None]] = None) -> None
```

Use `atomic_write_json(path, validated_candidate, commit=admin_session.protected_commit)` for **every handset-admin persisted mutation**. Thread this optional keyword-only `commit` callback through subsystem save methods. Existing two-argument calls remain compatible for non-admin writes (migration/cache/etc.). Do not wrap the entire save in `protected_commit`: staging/JSON serialization/file fsync must remain cancellable.

`atomic_write_json` validates/serializes/stages/fsyncs a private temporary file first. Then it invokes `commit(replace)` (or directly replaces for non-admin callers). The `replace` closure performs only `os.replace(temp, destination)`. `AdminSession.protected_commit` acquires the runtime authorization/cancellation lock, rechecks that the exact session is current, off-hook, not cancelled/revoked, and not expired, then runs `replace` under that same lock. Hangup, escape, shutdown, explicit session cancellation and capability revocation use this lock too. A cancellation/revocation that wins before the protected boundary prevents replacement; once replacement wins the boundary it is committed (later cancellation cannot undo it). Temporary files are removed on denied commits. In-memory snapshots update only after the save returns successfully. Directory fsync remains after replacement: failure there is an uncertain-durability error, not a denied/uncommitted save.

`PermissionError` must propagate to administration cancellation handling; do not announce a successful save. Keep adjacent early `require_authorized()` checks for UX, but they do not replace the final guard.

Admin input renewal checks the deadline **before** renewing activity under the same lock. Expiry is irreversible; late input cannot revive it. Worker B should poll `admin_session.require_authorized()` while waiting for long admin spoken previews (nonblocking speech plus a short bounded wait); stop speech on denied authorization and propagate `PermissionError`. Worker A will also provide runtime-wide polling while an admin capability is attached to the call session, covering BIOS/admin menu speech.

Worker A owns implementation of these shared interfaces and BIOS default persistence. Worker B owns threading the callback through Booth persistence and its regression tests. No Booth files/tests are owned by A.
