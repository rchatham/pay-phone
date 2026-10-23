# Payphone BIOS/Bootloader System

The BIOS (Basic Input/Output System) provides a bootloader interface for the payphone, allowing you to:
- Select which phone system to run
- Experiment with different implementations
- Hot-reload systems without hardware reboot
- Configure system behavior

## Features

### 1. **BIOS Menu on Pickup** (default)
- **Pick up the handset** → the BIOS menu plays and you dial a digit to launch a system
- Controlled by `always_show_menu_on_pickup: true` and `auto_launch: false` in `.bios_config.json`
- **Legacy auto-launch** (opt-in): set `auto_launch: true`, `always_show_menu_on_pickup: false`
  and `bios_enter_hold_seconds` > 0. Pick up → the last selected system launches after the
  hold window; keep the handset lifted for `bios_enter_hold_seconds` without hanging up to
  enter the BIOS menu instead. With the default `bios_enter_hold_seconds: 0.0` the hold
  check always passes, so legacy mode still opens the menu.

### 2. **Return to BIOS Anytime**
- While any system is running, press and hold `*` key for 5 seconds to return to BIOS menu
- Allows switching between systems without hanging up

### 3. **Dynamic System Discovery**
- Automatically scans multiple directories for phone systems:
  - `./phone_systems/` (built-in systems)
  - `./plugins/` (external systems via symlinks)
  - Custom paths configured in `.bios_config.json`
- No recompilation needed to add new systems

### 4. **Persistent Configuration**
- Saves last selected system to `.bios_config.json`
- Remembers BIOS settings across reboots

## Architecture

```
┌─────────────────────────────────────────┐
│         BIOSBootloader                  │
│  - Hardware initialization              │
│  - Pickup → BIOS menu (default)         │
│  - Long-press * detection (5s)          │
│  - System discovery & loading           │
└─────────────────────────────────────────┘
                    ↓
        ┌───────────┴───────────┐
        │                       │
┌───────▼────────┐    ┌────────▼──────────┐
│  TDTM System   │    │ Burning Man Info  │
│ (external repo)│    │ (external repo)   │
└────────────────┘    └───────────────────┘
```

## Usage

### Normal Operation

```bash
# Start payphone with BIOS (default)
payphone

# Pick up phone → BIOS menu plays, dial 1-9 to launch a system
# During operation: hold * for 5s → return to BIOS
# (legacy auto-launch of the last system: see Configuration below)
```

### Legacy Mode (Bypass BIOS)

```bash
# Run specific system directly without BIOS
PAYPHONE_LEGACY_MODE=<system_id> payphone
```

### Configuration

Edit `.bios_config.json` in the project root:

```json
{
  "last_system": "bm-info-line",
  "auto_launch": false,
  "always_show_menu_on_pickup": true,
  "bios_enter_hold_seconds": 0.0,
  "bios_exit_long_press_seconds": 5.0,
  "scan_paths": [
    "./phone_systems",
    "./plugins"
  ],
  "theme_path": "",
  "available_systems": []
}
```

**Options:**
- `last_system`: ID of last selected system (auto-set by BIOS)
- `auto_launch`: If true, auto-launch last system unless `always_show_menu_on_pickup` is enabled; if false (default), always show the BIOS menu
- `always_show_menu_on_pickup`: If true (default), picking up the handset opens the BIOS menu immediately
- `bios_enter_hold_seconds`: Legacy auto-launch mode only. Seconds the handset must stay lifted after pickup to enter the BIOS instead of auto-launching (default: 0.0, which means the BIOS menu always opens; set e.g. 3.0 to actually auto-launch)
- `bios_exit_long_press_seconds`: Seconds to hold * to return to BIOS (default: 5.0)
- `scan_paths`: Directories to scan for phone systems
- `theme_path`: Filesystem path of an installed BIOS theme pack (contains `theme/theme.json`); empty for the default theme
- `available_systems`: Auto-populated with discovered systems

### Themes

The default BIOS is generic: systems are listed alphabetically and the prompts say
"Welcome to payphone BIOS.". A theme pack customizes menu ordering and ships its own
rendered audio. When `theme_path` points at a pack containing `theme/theme.json`, the
BIOS orders the menu by the pack's `system_order` list (unknown system ids fall back
to alphabetical order) and plays the pack's `audio_files/bios/*.mp3` overrides.

The Burning Man theme lives in the separate `bm-payphone-theme` repo. With it checked
out next to this repo, `make run-simulator` installs it automatically; to install or
remove it manually:

```bash
python3 ../bm-payphone-theme/scripts/install.py --pay-phone .   # install
python3 ../bm-payphone-theme/scripts/install.py --remove        # uninstall
```
## Creating a Phone System

Runnable examples that should not appear in BIOS can live outside the default scan paths, such as `examples/information_booth/`.

To make your phone system discoverable by BIOS:

### 1. Create a system.py file

```python
# phone_systems/my_system/system.py
from payphone.core.system import PhoneSystemBase
from payphone.core.phone_tree import PhoneTree

class MySystem(PhoneSystemBase):
    """My custom phone system"""

    @staticmethod
    def get_metadata():
        """Optional: Provide metadata for BIOS menu"""
        return {
            "name": "My Custom System",
            "description": "A custom phone system",
            "version": "1.0.0",
            "author": "Your Name"
        }

    def setup_phone_tree(self) -> PhoneTree:
        """Define your phone tree structure"""
        return PhoneTree(
            "my_system/main_menu.mp3",
            audio_handler=self.audio_handler,
            options={
                "1": PhoneTree("my_system/option1.mp3",
                              audio_handler=self.audio_handler)
            }
        )
```

### 2. Place in a scanned directory

- **Built-in**: `phone_systems/my_system/system.py`
- **External repo**: Clone to `../my_system/` (sibling to pay-phone)
- **Custom path**: Add path to `scan_paths` in `.bios_config.json`

### 3. System will be auto-discovered on next boot

The BIOS will:
1. Scan all configured paths
2. Find `system.py` files
3. Import classes inheriting from `PhoneSystemBase`
4. Add to BIOS menu (numbered 1-9)

## BIOS Menu Audio Files

Create these audio files in `audio_files/bios/`:

- `main_menu.mp3` - Generic switchboard prompt ("Welcome to payphone BIOS..."); a theme pack overrides it
- `system_<id>.mp3` - Audio for each discovered system

Also needed in `audio_files/prompts/`:
- `no_systems.mp3` - "No phone systems found. Please check configuration."

## Components

### BIOSBootloader (`bootloader.py`)
Main bootloader class that:
- Extends `PhoneSystemBase`
- Opens BIOS menu on pickup by default, with legacy hook-hold support for auto-launch mode
- Launches the chosen system on the BIOS's own hardware and audio handlers, so the system
  reads the same keypad input queue and starts off-hook (see `_instantiate_system`)
- Monitors for long-press * during operation
- Manages system launching and switching; hang-up puts the launched system back on hook

### SystemManager (`system_manager.py`)
Discovers and loads phone systems:
- Scans configured directories
- Imports system modules dynamically
- Extracts metadata from systems
- Provides system class loading

### ConfigManager (`config_manager.py`)
Handles persistent configuration:
- Loads/saves `.bios_config.json`
- Manages system selection history
- Configures timing thresholds

## Troubleshooting

### System Not Appearing in BIOS Menu

1. Check file structure:
   ```
   my_system/
   └── system.py  (must contain PhoneSystemBase subclass)
   ```

2. Check scan paths in `.bios_config.json`

3. Look for errors in logs:
   ```bash
   journalctl -u payphone.service -f
   ```

### Can't Enter BIOS Menu

- With the defaults (`always_show_menu_on_pickup: true`), the menu should play on every pickup;
  if it doesn't, check the logs for `Error in call handler` and that `audio_files/bios/main_menu.mp3` exists
- In legacy auto-launch mode, keep the handset lifted for the full `bios_enter_hold_seconds`
  before the last system starts; raise the value (e.g. 5.0) if the window is too short

### * Long-Press Not Working

- Ensure you're holding * for full 5 seconds
- Check `bios_exit_long_press_seconds` in config
- Verify keypad is sending * key correctly

## Development

### Testing BIOS Locally

```bash
# Use keyboard simulator
python test_phone_tree.py

# Test with serial mode (Arduino)
USE_GPIO=false python -m payphone.main

# Test with GPIO mode (Raspberry Pi)
USE_GPIO=true sudo python -m payphone.main
```

### Adding Debug Logging

```bash
# Enable DEBUG logging
export LOG_LEVEL=DEBUG
payphone
```

## Future Enhancements

Potential additions:
- Web interface for BIOS configuration
- Remote system installation
- System versioning and updates
- Configuration backup/restore
- System health monitoring
- Usage statistics per system
