# Information Booth

Canonical, BIOS-selectable system ID: `information_booth`. The old
`examples/information_booth/system.py` re-exports this class; it has no separate
implementation. The Booth does not choose itself as the persistent BIOS default.
Use the protected BIOS default-system controls if that is desired.

## Deployment prerequisites

Use **Python 3.10+** (zoneinfo/IANA timezones and modern type annotations; tests
were run with Python 3.13). Install the existing payphone requirements, an offline
speech executable (`espeak-ng`, or the `espeak` fallback), and an operating-system
timezone database; `tzdata` can supply that database where the OS does not.
For Raspberry Pi, install `espeak-ng` with your OS package manager. Dynamic menus,
time, weather and text messages need this speech dependency; missing offline TTS
is an explicit runtime error, not a prerecorded-menu fallback.

Microphone capture uses the **existing `payphone.audio.recording` backend**:
`ENABLE_RECORDING`, `RECORDING_DEVICE`, `RECORDING_SAMPLE_RATE`, and
`RECORDING_CHANNELS`. Install the existing recording extra/dependencies
(sounddevice, soundfile, NumPy, and system PortAudio). The existing
`LAM_MAX_RECORD_SECONDS` deployment setting also bounds Booth takes, clamped to
1–120 seconds. No LAM implementation or recorder is duplicated.

State is anchored by `payphone.config.persistence.state_directory()`:
`PAYPHONE_STATE_DIR`, or repository-root `.payphone_state/`. Run the music setup
with the **same state-directory environment as the deployed service**:

```sh
python3 scripts/generate_information_booth_music.py
# Or generate a WAV in a specific Booth audio directory:
python3 scripts/generate_information_booth_music.py --output /var/lib/payphone/information_booth_audio/sample.wav
```

The standard-library script creates an original eight-second mono PCM melody;
it does not download music or reproduce a commercial recording. It is intentionally
not generated when an unprivileged caller selects music. Before setup, the music
service explicitly announces unavailable audio. WAVs and menus are not bundled
package data. Repository-checkout deployment includes the setup script; a wheel
installation needs a separately supplied copy of that script or local WAVs. The
tracked `phone_systems/__init__.py` and this package's `__init__.py` make the Python
implementation eligible for the existing `find_packages()` configuration; no
parent-package or packaging-framework change is needed.

Keep state and its parent directories private to the service account. New handset
recordings use a 0700 audio directory and 0600 files. Existing directories are not
silently chmodded. Do not let untrusted users edit the state/audio directory.

## Public handset menus

- `1`: information; `1` weather and `2` current time inside that menu (when enabled).
- `2`: a locally bundled joke.
- `3`: selected local music.
- `4`–`9`: configurable categories, with message slots `1`–`9` inside each.
- `0`: go back inside menus, repeat at the root; `0` or `#` stops recorded playback.
- Reserved `***#`: returns to BIOS via the shared runtime. **It does not authenticate.**

Recorded category/message labels are played while reading menus; fallback labels
are spoken. Keypad input interrupts menu prompts. The Booth's iterative tree uses
only the filtered session queue, not a second raw input reader. Hangup, escape,
authorization expiry and playback cancellation are checked throughout.

Defaults are a community category with a text welcome, all four services enabled,
OS-local time, Celsius weather at **40.7128, -74.0060 (New York City)**, and
`sample.wav`. The clock does not infer the weather location: explicitly set both
location and timezone for the installed phone.

### Weather boundaries

One fixed TLS host: `https://api.open-meteo.com/v1/forecast`; no configurable URLs,
redirects, proxies, paid credentials or retries. Only configured coordinates and
units are sent. Response size is limited to 32 KiB; numeric values, WMO conditions,
UTC timestamp/currentness, and returned temperature units are checked. Valid
responses are cached for 10 minutes; failures may announce **stale** data for up
to six hours, otherwise they announce unavailable weather. The in-memory cache is
shared across BIOS pickups for the same resolved state directory, not across
separate state directories or process restarts. No fabricated forecast.
Reports identify Open-Meteo and the provider's UTC update time.

The caller has a four-second wall-clock limit, including DNS/header stalls, and
cancellation can end its wait sooner. Socket deadlines also apply. At most one
background HTTP request exists process-wide; if an OS resolver remains stuck,
further weather attempts fail unavailable until it finishes. That worker never
plays audio or mutates content, and late/cancelled responses are discarded.

Live availability, current API schema, licensing/commercial-use restrictions and
attribution terms were **not externally researched or verified** for this change.
Before public deployment, verify the primary provider documents and applicable
terms at <https://open-meteo.com/en/docs> and <https://open-meteo.com/en/terms>.
No claim is made that the free public endpoint is permitted for every deployment.

## Protected on-phone editor

Provision a separate valid `BIOS_ADMIN_PASSCODE` in the deployment environment,
following [BIOS administration](../../docs/BIOS_ADMIN.md). There is no Booth
passcode/default credential or public capability. From authenticated BIOS
administration choose system administration, then Information Booth.

Editor root: `1` categories/messages, `2` service switches, `3` weather coordinates
and units, `4` timezone presets, `5` local music, `0` exit.

- Categories: select a slot `4`–`9`. An empty slot records its label before creating
  it. For an existing category: `1` record label, `2` messages, `3` delete category,
  `4` move to an unused slot.
- Messages: select a slot `1`–`9`. An empty slot records message content. For an
  existing message: `1` record content, `2` record label, `3` preview, `4` delete,
  `5` move to an unused slot. Local JSON provides supplementary text/name editing.
- Recording: speak after the instruction; `#` finishes, `*` or `0` cancels. Takes
  finish at the configured limit. Audio is previewed before `1` publishes or `0`
  discards. Hangup/escape/expiry stop capture and remove unpublished media.
- Coordinates: choose positive/negative, type digits with `*` as decimal separator,
  and finish with `#`. Input length, latitude ±90 and longitude ±180 are bounded.
- Timezone choices: OS-local, UTC, New York, Chicago, Denver, Los Angeles, London,
  Paris, Tokyo. Other valid IANA names can be set in local JSON.
- Music: lists up to nine safe WAV names in sorted order; `pending-*`/`recording-*`
  files are deliberately not offered as music. The selection previews before save.
- Service switches, deletions, slot moves, coordinates, timezone and music changes
  all require explicit confirmation. Rejected duplicate slots leave content intact.

Admin speech and recorded previews poll the BIOS-issued capability while playing
and stop on expiry/cancellation. Every handset save uses the
[protected commit contract](../../docs/shared-commit-contract.md): JSON is staged
and fsynced outside the authorization lock, then final authorization and atomic
replacement occur under the same lock used for revocation/cancellation. Cancellation
that wins this boundary prevents publication; cancellation after it cannot undo an
already committed replacement. A recording is staged privately, previewed, then
published under a unique exclusive filename through the same guard **before** the
atomic JSON reference is saved. JSON save failures before replacement retain the
previous content and remove the unpublished take.
Old published audio is never overwritten or automatically garbage-collected;
reference deletion does not erase files needed by old snapshots. Disk-full/fsync
errors are surfaced, not silently ignored. If directory fsync fails **after** JSON
replacement, durability is uncertain: the referenced recording is retained and the
operator must inspect the on-disk JSON before retrying.

## Supplementary local editing

`information_booth.json` is a version-1 object. It is created on the first successful
handset edit, not merely by a public call. To create a default editable snapshot
from a trusted local shell (do not overwrite an existing file):

```sh
python3 - <<'PY'
from payphone.config.persistence import atomic_write_json, state_directory
from phone_systems.information_booth.content import default_content, validate_content
root = state_directory()
path = root / 'information_booth.json'
if path.exists():
    raise SystemExit('Existing Booth state retained; edit that file instead.')
data = validate_content(default_content(), root / 'information_booth_audio')
atomic_write_json(path, data)
print(path)
PY
```

Example category/message within `categories`:

```json
{
  "slot": "4",
  "label": "Library information",
  "label_audio": null,
  "messages": [
    {"slot": "1", "label": "Opening hours", "label_audio": null,
     "text": "Open Monday through Friday, nine until five.", "audio": null}
  ]
}
```

Top-level fields are exactly `version`, `services` (weather/time/jokes/music boolean
switches), `weather` (latitude/longitude/units), `timezone`, `music` (simple WAV name
or null), and `categories`. Labels are at most 100 characters; message text at most
4,000; JSON at most 64 KiB. Unknown fields, invalid zones/units, duplicate slots,
missing message content and malformed shapes are rejected. Audio references must
be simple bounded `.wav` filenames under `information_booth_audio/`, never paths
or symlinks; files are capped at 32 MiB. Only the optional default `sample.wav` may
be referenced before it exists, so setup/unavailable handling works normally.

A valid local edit is reloaded **next call**. Invalid edits retain the last valid
in-memory snapshot and log a warning without overwriting the bad file. Content stores
are retained per resolved state directory across fresh BIOS instances/discovery and
pickups; only data is shared, never session handlers or admin capabilities. Each call
uses its own copied snapshot. A fresh process with only invalid state safely uses
built-in defaults; the corrupted source
is still preserved. Handset editing and trusted local file editing should not run
concurrently: confirmation saves the editor's complete current snapshot (no merge).
Use a temporary file plus atomic replacement when editing locally; do not partially
write a live file. Back up state and referenced recordings using your normal private
operator procedure. Periodic orphan-file review/cleanup is an operator task; do
not delete media referenced by an active call, saved config, or retained backup.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 /path/to/venv/bin/python -m pytest \
  tests/unit/test_information_booth.py tests/integration/test_information_booth_runtime.py \
  -o addopts='' -p no:cacheprovider
```

Hardware/audio/HTTP/capture/TTS are mocked; integration uses the actual shared
runtime, discovery, capability, filtered queue, and atomic state helper. Physical
handset/keypad/USB audio/recording quality, live provider access, unplug/power-loss
behavior and production filesystem durability still require deployment testing.
No main startup or process-killing entrypoint is used in these checks.
