# Payphone BIOS/Bootloader System

The BIOS (Basic Input/Output System) provides a bootloader interface for the payphone, allowing you to:
- Select which phone system to run
- Experiment with different implementations
- Hot-reload systems without hardware reboot
- Configure system behavior

## Features

### 1. **Auto-Launch with Manual Override**
- **Normal Boot**: Pick up phone → automatically launches last selected system
- **BIOS Menu**: Hold handset for 3 seconds after pickup → enter BIOS menu

### 2. **Return to BIOS Anytime**
- While any system is running, press and hold `*` key for 5 seconds to return to BIOS menu
- Allows switching between systems without hanging up

### 3. **Dynamic System Discovery**
- Automatically scans multiple directories for phone systems:
  - `./phone_systems/` (built-in systems)
  - `../TDTM/` (sibling repositories)
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
│  - Hook hold detection (3s)             │
│  - Long-press * detection (5s)          │
│  - System discovery & loading           │
└─────────────────────────────────────────┘
                    ↓
        ┌───────────┴───────────┐
        │                       │
┌───────▼────────┐    ┌────────▼──────────┐
│ InformationBooth│    │  TDTM System     │
│ (built-in)      │    │  (external repo) │
└─────────────────┘    └──────────────────┘
```

## Usage

### Normal Operation

```bash
# Start payphone with BIOS (default)
payphone

# Pick up phone → last system auto-launches
# Hold phone for 3s after pickup → BIOS menu
# During operation: hold * for 5s → return to BIOS
```

### Legacy Mode (Bypass BIOS)

```bash
# Run specific system directly without BIOS
PAYPHONE_LEGACY_MODE=information_booth payphone
```

### Configuration

Edit `.bios_config.json` in the project root:

```json
{
  "last_system": "information_booth",
  "auto_launch": true,
  "bios_enter_hold_seconds": 3.0,
  "bios_exit_long_press_seconds": 5.0,
  "scan_paths": [
    "./phone_systems",
    "../TDTM",
    "../../TDTM"
  ],
  "available_systems": []
}
```

**Options:**
- `last_system`: ID of last selected system (auto-set by BIOS)
- `auto_launch`: If true, auto-launch last system; if false, always show BIOS menu
- `bios_enter_hold_seconds`: Seconds to hold hook to enter BIOS (default: 3.0)
- `bios_exit_long_press_seconds`: Seconds to hold * to return to BIOS (default: 5.0)
- `scan_paths`: Directories to scan for phone systems
- `available_systems`: Auto-populated with discovered systems

## Creating a Phone System

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

- `main_menu.mp3` - "Welcome to payphone BIOS. Press 1 for Information Booth, Press 2 for TDTM System..."
- `system_information_booth.mp3` - "Information Booth System" (spoken name)
- `system_tdtm.mp3` - "TDTM System" (spoken name)
- `system_<id>.mp3` - Audio for each discovered system

Also needed in `audio_files/prompts/`:
- `no_systems.mp3` - "No phone systems found. Please check configuration."

## Components

### BIOSBootloader (`bootloader.py`)
Main bootloader class that:
- Extends `PhoneSystemBase`
- Detects hook hold on pickup
- Monitors for long-press * during operation
- Manages system launching and switching

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

- Ensure you're holding handset for full 3 seconds immediately after pickup
- Check `bios_enter_hold_seconds` in config
- Try adjusting threshold higher (e.g., 5.0 seconds)

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
