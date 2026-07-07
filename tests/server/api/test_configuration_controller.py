from icon.server.api.configuration_controller import (
    ConfigurationController,
    parse_config_key,
)


def test_update_config_option() -> None:
    controller = ConfigurationController()
    original_port = controller.get_config()["server"]["port"]
    target_port = original_port + 1
    controller.update_config_option("server.port", target_port)
    updated_port = controller.get_config()["server"]["port"]
    assert updated_port == target_port


def test_parse_config_key() -> None:
    nested_key = "hardware.devices[1].id"
    path = parse_config_key(nested_key)
    assert path == ["hardware", "devices", 1, "id"]
