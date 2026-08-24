from pathlib import Path

from payphone.bios.config_manager import ConfigManager
from payphone.bios.system_manager import SystemManager
from payphone.core.system import PhoneSystemBase


def test_default_pickup_enters_menu(tmp_path):
    config = ConfigManager(str(tmp_path / "bios.json"))

    assert config.get_auto_launch() is False
    assert config.get_always_show_menu_on_pickup() is True
    assert config.get_bios_enter_hold_seconds() == 0.0


def test_existing_config_migrates_to_show_menu_on_pickup(tmp_path):
    config_path = tmp_path / "bios.json"
    config_path.write_text('{"auto_launch": true, "bios_enter_hold_seconds": 3.0}')

    config = ConfigManager(str(config_path))

    assert config.get_auto_launch() is True
    assert config.get_always_show_menu_on_pickup() is True


def test_system_manager_discovers_hyphenated_plugin_without_leaking_sys_path(tmp_path, monkeypatch):
    plugins_dir = tmp_path / "plugins"
    plugin_dir = plugins_dir / "bm-info-line"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "system.py").write_text(
        "from payphone.core import PhoneSystemBase, PhoneTree\n"
        "class TestSystem(PhoneSystemBase):\n"
        "    @staticmethod\n"
        "    def get_metadata():\n"
        "        return {'name': 'Hyphen Plugin'}\n"
        "    def setup_phone_tree(self):\n"
        "        return PhoneTree('')\n"
    )

    original_path = list(__import__("sys").path)
    manager = SystemManager(scan_paths=[str(plugins_dir)])
    systems = manager.discover_systems()

    assert systems["bm-info-line"].name == "Hyphen Plugin"
    assert "bm-info-line" not in systems["bm-info-line"].module_path
    assert __import__("sys").path == original_path
    assert issubclass(manager.load_system("bm-info-line"), PhoneSystemBase)
