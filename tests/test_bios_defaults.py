from payphone.bios.config_manager import ConfigManager


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
