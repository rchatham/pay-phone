# Information Booth example compatibility

Information Booth is now a standard BIOS-selectable system, implemented once in
[`phone_systems/information_booth`](../../phone_systems/information_booth/README.md).
This example re-exports that canonical class and retains the direct runner:

```sh
python3 examples/information_booth/run.py
```

Direct mode runs the public Booth without BIOS administration. Use the normal BIOS
runtime and a separately provisioned `BIOS_ADMIN_PASSCODE` for protected on-phone
editing and persistent default-system selection. Both modes use the same validated
`information_booth.json` and state-local WAV files.

Requires Python 3.10+, offline eSpeak NG/eSpeak, the usual payphone dependencies,
and optional shared recording dependencies. Generate original sample music from
the repository checkout with:

```sh
python3 scripts/generate_information_booth_music.py
```

See the canonical README for editable categories/messages, handset editor keys,
weather/time/jokes/music behavior, deployment settings and verification limitations.
Do not add this example directory to BIOS scans: the canonical package already
provides `information_booth`.
