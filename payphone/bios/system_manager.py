"""
System manager for discovering and loading phone systems.

Scans multiple directories for phone system implementations and
provides dynamic loading capabilities.
"""

import importlib
import importlib.util
import inspect
import json
import logging
import re
import sys
import types
from pathlib import Path
from typing import Dict, List, Optional, Type, Any

from ..core.system import PhoneSystemBase

logger = logging.getLogger(__name__)


def load_theme(theme_path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load a BIOS theme.json from a theme pack path.

    Args:
        theme_path: Filesystem path of a theme pack repo (contains theme/theme.json).

    Returns:
        Parsed theme dictionary, or None when no theme is configured or the file
        cannot be read.
    """
    if not theme_path:
        return None

    theme_file = Path(theme_path) / "theme.json"
    try:
        return json.loads(theme_file.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load theme %s: %s", theme_file, exc)
        return None


class SystemInfo:
    """Information about a discovered phone system"""

    def __init__(self, system_id: str, name: str, module_path: str,
                 class_name: str, description: str = "", version: str = "1.0.0"):
        self.id = system_id
        self.name = name
        self.module_path = module_path
        self.class_name = class_name
        self.description = description
        self.version = version

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "module_path": self.module_path,
            "class_name": self.class_name,
            "description": self.description,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'SystemInfo':
        """Create from dictionary"""
        return cls(
            system_id=data["id"],
            name=data["name"],
            module_path=data["module_path"],
            class_name=data["class_name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0")
        )


class SystemManager:
    """Manages discovery and loading of phone systems"""

    def __init__(self, scan_paths: Optional[List[str]] = None):
        """
        Initialize system manager.

        Args:
            scan_paths: List of directory paths to scan for phone systems
        """
        self.scan_paths = scan_paths or []
        self.discovered_systems: Dict[str, SystemInfo] = {}

    def discover_systems(self) -> Dict[str, SystemInfo]:
        """
        Scan configured paths for phone systems.

        Returns:
            Dictionary mapping system IDs to SystemInfo objects
        """
        logger.info(f"Scanning for phone systems in {len(self.scan_paths)} paths")
        self.discovered_systems = {}

        for path_str in self.scan_paths:
            path = Path(path_str).expanduser().resolve()
            if not path.exists():
                logger.debug(f"Path does not exist, skipping: {path}")
                continue

            logger.debug(f"Scanning: {path}")

            # Check if this is a phone_systems directory (contains multiple systems)
            if path.name == "phone_systems" and path.is_dir():
                self._scan_phone_systems_dir(path)
            # Check if this is a direct system directory (contains system.py)
            elif (path / "system.py").exists():
                self._scan_system_dir(path)
            # Check subdirectories
            elif path.is_dir():
                for subdir in path.iterdir():
                    if subdir.is_dir() and (subdir / "system.py").exists():
                        self._scan_system_dir(subdir)

        logger.info(f"Discovered {len(self.discovered_systems)} phone systems")
        return self.discovered_systems

    def _scan_phone_systems_dir(self, path: Path) -> None:
        """Scan a phone_systems directory for multiple systems"""
        for subdir in path.iterdir():
            if subdir.is_dir() and (subdir / "system.py").exists():
                self._scan_system_dir(subdir)

    def _scan_system_dir(self, path: Path) -> None:
        """
        Scan a single system directory.

        Looks for system.py and attempts to import classes inheriting from PhoneSystemBase.
        """
        system_file = path / "system.py"
        if not system_file.exists():
            return

        try:
            # Generate a unique import-safe module name while preserving the public system ID
            system_id = path.name
            module_id = self._module_id_for_system(system_id)
            module_name = f"phone_systems.{module_id}.system"
            added_paths = self._prepare_import_path(path, module_id)

            try:
                # Import from file path directly so plugin IDs can include characters like hyphens.
                spec = importlib.util.spec_from_file_location(module_name, system_file)
                if spec is None or spec.loader is None:
                    logger.warning(f"Could not create spec for {system_file}")
                    return

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                logger.debug(f"Imported from file: {system_file}")
            finally:
                self._cleanup_import_path(added_paths)

            # Find classes that inherit from PhoneSystemBase
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Accept class if:
                # 1. It's a PhoneSystemBase subclass
                # 2. It's not PhoneSystemBase itself
                # 3. Either it's defined in this module OR it's imported and defined in a related module
                is_valid_subclass = (issubclass(obj, PhoneSystemBase) and obj is not PhoneSystemBase)
                is_from_this_module = (obj.__module__ == module_name or
                                      obj.__module__.split('.')[-1] in ['tdtm_system', 'system'])

                if is_valid_subclass and is_from_this_module:

                    # Get metadata if available
                    metadata = self._get_system_metadata(obj)

                    system_info = SystemInfo(
                        system_id=system_id,
                        name=metadata.get("name", name),
                        module_path=module_name,
                        class_name=name,
                        description=metadata.get("description", ""),
                        version=metadata.get("version", "1.0.0")
                    )

                    self.discovered_systems[system_id] = system_info
                    logger.info(f"Discovered system: {system_info.name} ({system_id})")
                    break  # Only register first matching class per module

        except Exception as e:
            logger.error(f"Error scanning {path}: {e}", exc_info=True)

    def _module_id_for_system(self, system_id: str) -> str:
        """Return an import-safe module ID for a public system ID."""
        module_id = re.sub(r"\W", "_", system_id)
        if not module_id or module_id[0].isdigit():
            module_id = f"system_{module_id}"
        return module_id

    def _prepare_import_path(self, path: Path, module_id: str) -> List[str]:
        """Prepare temporary sys.path entries and parent packages for plugin imports."""
        added_paths = []
        resolved_path = path.resolve()
        for import_path in (path, resolved_path, resolved_path.parent):
            import_path_str = str(import_path)
            if import_path_str not in sys.path:
                sys.path.insert(0, import_path_str)
                added_paths.append(import_path_str)

        if "phone_systems" not in sys.modules:
            package = types.ModuleType("phone_systems")
            package.__path__ = []
            sys.modules["phone_systems"] = package

        package_name = f"phone_systems.{module_id}"
        if package_name not in sys.modules:
            package = types.ModuleType(package_name)
            package.__path__ = [str(path), str(resolved_path)]
            sys.modules[package_name] = package

        return added_paths

    def _cleanup_import_path(self, added_paths: List[str]) -> None:
        """Remove temporary sys.path entries added for plugin import."""
        for import_path in added_paths:
            try:
                sys.path.remove(import_path)
            except ValueError:
                pass

    def _get_system_metadata(self, system_class: Type[PhoneSystemBase]) -> Dict[str, str]:
        """
        Extract metadata from a system class.

        Checks for get_metadata() static method or class docstring.
        """
        metadata = {}

        # Try get_metadata() method
        if hasattr(system_class, 'get_metadata'):
            try:
                metadata = system_class.get_metadata()
                if isinstance(metadata, dict):
                    return metadata
            except Exception as e:
                logger.debug(f"Error calling get_metadata(): {e}")

        # Fall back to docstring
        if system_class.__doc__:
            metadata["description"] = system_class.__doc__.strip().split('\n')[0]

        return metadata

    def load_system(self, system_id: str) -> Optional[Type[PhoneSystemBase]]:
        """
        Load a phone system class by ID.

        Args:
            system_id: System identifier

        Returns:
            PhoneSystemBase subclass or None if not found
        """
        if system_id not in self.discovered_systems:
            logger.error(f"System not found: {system_id}")
            return None

        system_info = self.discovered_systems[system_id]

        try:
            # Import the module
            module = importlib.import_module(system_info.module_path)

            # Get the class
            system_class = getattr(module, system_info.class_name)

            if not issubclass(system_class, PhoneSystemBase):
                logger.error(f"{system_info.class_name} is not a PhoneSystemBase subclass")
                return None

            logger.info(f"Loaded system: {system_info.name}")
            return system_class

        except Exception as e:
            logger.error(f"Error loading system {system_id}: {e}", exc_info=True)
            return None

    def get_system_info(self, system_id: str) -> Optional[SystemInfo]:
        """Get information about a system"""
        return self.discovered_systems.get(system_id)

    def list_systems(self) -> List[SystemInfo]:
        """Get list of all discovered systems"""
        return list(self.discovered_systems.values())
