"""
Configuration manager for BIOS/Bootloader system.

Handles persistent storage of system selection and BIOS settings.
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages BIOS configuration and persistence"""

    DEFAULT_CONFIG = {
        "last_system": None,
        "auto_launch": True,
        "bios_enter_hold_seconds": 3.0,
        "bios_exit_long_press_seconds": 5.0,
        "scan_paths": [
            "./phone_systems",
            "../TDTM",
            "../../TDTM"
        ],
        "available_systems": []
    }

    def __init__(self, config_path: str = ".bios_config.json"):
        """
        Initialize config manager.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded BIOS config from {self.config_path}")
                # Merge with defaults for any missing keys
                return {**self.DEFAULT_CONFIG, **config}
            except Exception as e:
                logger.error(f"Error loading config: {e}, using defaults")
                return self.DEFAULT_CONFIG.copy()
        else:
            logger.info("No BIOS config found, creating default")
            config = self.DEFAULT_CONFIG.copy()
            self.save_config(config)
            return config

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Save configuration to file.

        Args:
            config: Config dict to save (uses self.config if None)
        """
        if config is None:
            config = self.config

        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved BIOS config to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value and save"""
        self.config[key] = value
        self.save_config()

    def get_last_system(self) -> Optional[str]:
        """Get the last selected system ID"""
        return self.config.get("last_system")

    def set_last_system(self, system_id: str) -> None:
        """Set the last selected system ID"""
        self.set("last_system", system_id)

    def get_auto_launch(self) -> bool:
        """Check if auto-launch is enabled"""
        return self.config.get("auto_launch", True)

    def get_scan_paths(self) -> List[str]:
        """Get list of paths to scan for phone systems"""
        return self.config.get("scan_paths", [])

    def add_scan_path(self, path: str) -> None:
        """Add a path to scan for phone systems"""
        paths = self.get_scan_paths()
        if path not in paths:
            paths.append(path)
            self.set("scan_paths", paths)

    def update_available_systems(self, systems: List[Dict[str, str]]) -> None:
        """Update list of discovered systems"""
        self.config["available_systems"] = systems
        self.save_config()

    def get_bios_enter_hold_seconds(self) -> float:
        """Get seconds to hold hook to enter BIOS"""
        return self.config.get("bios_enter_hold_seconds", 3.0)

    def get_bios_exit_long_press_seconds(self) -> float:
        """Get seconds to hold * to return to BIOS"""
        return self.config.get("bios_exit_long_press_seconds", 5.0)
