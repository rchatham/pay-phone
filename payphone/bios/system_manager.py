"""
System manager for discovering and loading phone systems.

Scans multiple directories for phone system implementations and
provides dynamic loading capabilities.
"""

import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type, Any

from ..core.system import PhoneSystemBase

logger = logging.getLogger(__name__)


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
            # Generate a unique module name
            system_id = path.name
            module_name = f"phone_systems.{system_id}.system"

            # Try importing as a package first (if installed)
            try:
                spec = importlib.util.find_spec(module_name)
                if spec is not None:
                    module = importlib.import_module(module_name)
                    logger.debug(f"Imported as package: {module_name}")
                else:
                    raise ImportError("Not a package")
            except ImportError:
                # Import from file path directly
                spec = importlib.util.spec_from_file_location(module_name, system_file)
                if spec is None or spec.loader is None:
                    logger.warning(f"Could not create spec for {system_file}")
                    return

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                logger.debug(f"Imported from file: {system_file}")

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
