# Information Booth Example

This is a runnable example phone system kept outside the BIOS default scan path.

Run it directly from the repository root:

```bash
python3 examples/information_booth/run.py
```

The BIOS scans `./phone_systems` and `./plugins` by default, so this example is not shown in the BIOS menu unless you explicitly add `./examples/information_booth` to `.bios_config.json`.
