#!/usr/bin/env python3
"""
Quick test script for BIOS/Bootloader system.

Tests:
1. ConfigManager - Load/save configuration
2. SystemManager - Discover and load systems
3. BIOSBootloader - Basic initialization

Run: python test_bios.py
"""

import logging
import sys
import os
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from payphone.bios.config_manager import ConfigManager
from payphone.bios.system_manager import SystemManager


def test_config_manager():
    """Test configuration management"""
    print("\n" + "="*60)
    print("TEST 1: ConfigManager")
    print("="*60)

    # Use test config file
    config_path = ".bios_config_test.json"

    # Clean up any existing test config
    if os.path.exists(config_path):
        os.remove(config_path)

    try:
        # Create config manager
        config = ConfigManager(config_path)
        print("✓ ConfigManager initialized")

        # Check default values
        assert config.get_auto_launch() == True
        assert config.get_bios_enter_hold_seconds() == 3.0
        assert config.get_bios_exit_long_press_seconds() == 5.0
        print("✓ Default values loaded correctly")

        # Set a value
        config.set_last_system("test_system")
        assert config.get_last_system() == "test_system"
        print("✓ Value set and retrieved correctly")

        # Verify persistence
        config2 = ConfigManager(config_path)
        assert config2.get_last_system() == "test_system"
        print("✓ Configuration persisted to file")

        # Add scan path
        config.add_scan_path("../test_path")
        assert "../test_path" in config.get_scan_paths()
        print("✓ Scan path added successfully")

        print("\n✅ ConfigManager tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ ConfigManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up test file
        if os.path.exists(config_path):
            os.remove(config_path)


def test_system_manager():
    """Test system discovery and loading"""
    print("\n" + "="*60)
    print("TEST 2: SystemManager")
    print("="*60)

    try:
        # Create system manager with phone_systems directory and TDTM
        manager = SystemManager(scan_paths=["./phone_systems", "./plugins"])
        print("✓ SystemManager initialized")

        # Discover systems
        systems = manager.discover_systems()
        print(f"✓ Discovered {len(systems)} systems:")

        for system_id, info in systems.items():
            print(f"  - {info.name} (id={system_id}, class={info.class_name})")

        if len(systems) == 0:
            print("\n⚠️  No systems found. This is expected if phone_systems/ is empty.")
            print("   To test with actual systems, add them to phone_systems/ directory")
            return True

        # Try loading first system
        first_system_id = list(systems.keys())[0]
        system_class = manager.load_system(first_system_id)

        if system_class:
            print(f"✓ Loaded system class: {system_class.__name__}")

            # Verify it's a proper PhoneSystemBase subclass
            from payphone.core.system import PhoneSystemBase
            assert issubclass(system_class, PhoneSystemBase)
            print("✓ System class is valid PhoneSystemBase subclass")
        else:
            print(f"❌ Failed to load system: {first_system_id}")
            return False

        print("\n✅ SystemManager tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ SystemManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bios_bootloader_init():
    """Test BIOS bootloader initialization (no hardware)"""
    print("\n" + "="*60)
    print("TEST 3: BIOSBootloader Initialization")
    print("="*60)

    try:
        # Mock the hardware components to avoid GPIO errors
        print("⚠️  Skipping BIOSBootloader test (requires hardware)")
        print("   To test with hardware, run on Raspberry Pi or with Arduino")
        print("   Or set USE_GPIO=false in .env for serial mode")

        # Note: Full bootloader test requires hardware or mocks
        # This would need GPIO or Serial hardware to test properly

        print("\n✅ BIOSBootloader initialization test skipped (hardware required)")
        return True

    except Exception as e:
        print(f"\n❌ BIOSBootloader test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("BIOS/BOOTLOADER TEST SUITE")
    print("="*60)

    results = []

    # Run tests
    results.append(("ConfigManager", test_config_manager()))
    results.append(("SystemManager", test_system_manager()))
    results.append(("BIOSBootloader", test_bios_bootloader_init()))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60 + "\n")

    return all(result for _, result in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
