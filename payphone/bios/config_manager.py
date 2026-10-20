"""Validated BIOS state; public selections never become persistent defaults."""
import copy
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..config.persistence import REPOSITORY_ROOT, atomic_write_json, state_directory

logger = logging.getLogger(__name__)


class ConfigManager:
    DEFAULT_CONFIG = {
        "default_system": None,
        "last_system": None,  # Legacy informational field, never used for boot.
        "auto_launch": False,
        "always_show_menu_on_pickup": True,
        "bios_enter_hold_seconds": 0.0,
        "bios_exit_long_press_seconds": 5.0,
        "escape_sequence": "***#",
        "escape_timeout": 1.0,
        "scan_paths": ["phone_systems", "plugins"],
        "available_systems": [],
    }

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else state_directory() / "bios.json"
        self.config = self._load_config()

    @classmethod
    def _validate(cls, data: dict) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("BIOS state must be an object")
        result = {**copy.deepcopy(cls.DEFAULT_CONFIG), **data}
        for field in ("default_system", "last_system"):
            value = result[field]
            if value is not None and (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value)):
                raise ValueError(f"Invalid {field}")
        paths = result["scan_paths"]
        if not isinstance(paths, list) or len(paths) > 32 or any(not isinstance(p, str) or not p or len(p) > 4096 for p in paths):
            raise ValueError("Invalid scan paths")
        for field in ("auto_launch", "always_show_menu_on_pickup"):
            if not isinstance(result[field], bool):
                raise ValueError(f"Invalid {field}")
        sequence = result["escape_sequence"]
        if not isinstance(sequence, str) or not 3 <= len(sequence) <= 12 or any(k not in "0123456789*#" for k in sequence):
            raise ValueError("Invalid escape sequence")
        interval = result["escape_timeout"]
        if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not 0.2 <= interval <= 5:
            raise ValueError("Invalid escape timeout")
        if not isinstance(result["available_systems"], list):
            raise ValueError("Invalid available systems")
        return result

    def _load_config(self) -> Dict[str, Any]:
        source = self.config_path
        migrate = False
        if not source.exists() and source == state_directory() / "bios.json":
            source = REPOSITORY_ROOT / ".bios_config.json"
            migrate = source.exists()
        if not source.exists():
            return copy.deepcopy(self.DEFAULT_CONFIG)
        try:
            if source.stat().st_size > 65536:
                raise ValueError("BIOS state exceeds size limit")
            data = self._validate(json.loads(source.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            logger.error("Invalid BIOS state at %s; using safe defaults: %s", source, exc)
            return copy.deepcopy(self.DEFAULT_CONFIG)
        if migrate:
            # Copy legacy settings, but never infer intent from last_system/auto_launch.
            data["default_system"] = None
            try:
                atomic_write_json(self.config_path, data)
            except OSError as exc:
                logger.error("Could not migrate BIOS state: %s", exc)
        return data

    def save_config(self, config: Optional[Dict[str, Any]] = None, *,
                    commit: Optional[Callable[[Callable[[], None]], None]] = None) -> None:
        validated = self._validate(self.config if config is None else config)
        atomic_write_json(self.config_path, validated, commit=commit)
        self.config = validated

    def get(self, key: str, default: Any = None) -> Any:
        return copy.deepcopy(self.config.get(key, default))

    def set(self, key: str, value: Any, *,
            commit: Optional[Callable[[Callable[[], None]], None]] = None) -> None:
        candidate = copy.deepcopy(self.config)
        candidate[key] = value
        self.save_config(candidate, commit=commit)

    def get_default_system(self) -> Optional[str]:
        return self.config["default_system"]

    def set_default_system(self, system_id: Optional[str], *,
                           commit: Optional[Callable[[Callable[[], None]], None]] = None) -> None:
        self.set("default_system", system_id, commit=commit)

    def get_last_system(self) -> Optional[str]:
        return self.config["last_system"]

    def set_last_system(self, system_id: str) -> None:
        self.set("last_system", system_id)

    def get_auto_launch(self) -> bool:
        return self.config["auto_launch"]

    def get_always_show_menu_on_pickup(self) -> bool:
        return self.config["always_show_menu_on_pickup"]

    def get_scan_paths(self) -> List[str]:
        return [str((REPOSITORY_ROOT / Path(p).expanduser()).resolve()) for p in self.config["scan_paths"]]

    def add_scan_path(self, path: str) -> None:
        paths = self.get("scan_paths")
        if path not in paths:
            self.set("scan_paths", paths + [path])

    def update_available_systems(self, systems: List[Dict[str, str]]) -> None:
        # Discovery is a volatile snapshot, not a reason to overwrite saved state.
        self.config["available_systems"] = copy.deepcopy(systems)

    def get_bios_enter_hold_seconds(self) -> float:
        return 0.0

    def get_bios_exit_long_press_seconds(self) -> float:
        return self.config["bios_exit_long_press_seconds"]
