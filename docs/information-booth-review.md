# Independent review, 2026-10-12

Read-only reviewer and security-reviewer evaluated the in-progress diff. All findings below are now resolved and covered by regression tests. Both independent second-pass reviews returned PASS with no concrete blockers.

## Worker A

1. **Lifecycle blocker** (`payphone/core/system.py:start_call`): hangup during action then pickup before cancelled thread exits is ignored permanently. Retain pending pickup; service sequentially after old navigation ends, no overlapping consumers. Test actual hangup/quick pickup while blocked action unwinds.
2. **Auth blocker** (`runtime._deliver`, `bios/auth.AdminSession`): keypad unconditionally refreshes session last_activity. If admin speech blocks past 120s before `require_authorized` polls, late input revives expired admin. Use irreversible deadline checking before renewal, and poll admin authorization during long spoken previews. Test delayed input after expiry while preview blocked.
3. Normal GPIO DTMF feedback lost because hardware receives no audio and runtime filtered delivery never plays tones. Restore centrally for normal input only; PIN and full escape stay silent. Add test.
4. BIOS JSON loader should catch RecursionError (small deeply nested JSON) and fallback without overwriting source.
5. Cancellation during staged save fsync still allows replacement. Support final authorization before replace serialized with revocation (preferred), or explicitly define confirmed saves irrevocable. Prototype plan promises cancellation, so implement protected commit boundary and test staging cancellation. Coordinate interface change with B for its saves.

## Worker B

6. **Content/cache blocker**: each BIOS call constructs fresh Booth/ContentStore, so valid custom content then corrupt local edit falls back to defaults rather than previous valid snapshot. Weather cache also resets per pickup. Retain content store/weather service per state directory across sessions without sharing session-bound handlers. Add two actual BIOS-pickup tests for valid then corrupt content and fresh then offline weather cache.
7. Poll capability during long admin speech (coordinate A's fix) and use A's final-authorized commit interface for every persist.

## Verification caveats

Coordinator final combined test run: 211 passed in 7.80 seconds (BIOS defaults/runtime, offline speech, Booth unit/runtime integration, LAM plugin/recording, core tree behavior); git diff --check clean. No physical hardware/unplug/live-weather/TTS verification performed. Full-suite retry collected 256 tests and progressed through 79% before a 60-second timeout in existing test_phone_tree navigation tests; baseline also failed/timed out before implementation. Wheel deployment/API terms remain unverified. Root README/setup.py owned by coordinator.
