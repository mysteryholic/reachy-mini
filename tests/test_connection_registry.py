from __future__ import annotations

import os

from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog
from reachy_robotis.robotis_interface.core.yaml_loader import load_mapping
from reachy_robotis.robotis_interface.transports.connection_transport import ConnectionTransport


def test_empty_password_is_saved_as_blank_password(tmp_path):
    config_path = tmp_path / "robotis_connections.yaml"
    secrets_path = tmp_path / "robotis_secrets.yaml"
    registry = ConnectionRegistry(path=config_path, secrets_path=secrets_path)

    base_connection = {
        "display_name": "OpenMANIPULATOR-X",
        "target": "omx",
        "host": "192.168.1.10",
        "port": 22,
        "user": "robotis",
        "auth": {
            "method": "password",
            "password": "robotis-password",
            "key_path": "",
            "password_env": "",
        },
    }

    saved = registry.save_connection("omx", base_connection)
    assert saved.has_password is True
    assert load_mapping(secrets_path)["passwords"] == {"omx": "robotis-password"}

    cleared_connection = {
        **base_connection,
        "auth": {
            **base_connection["auth"],
            "password": "",
        },
    }

    saved = registry.save_connection("omx", cleared_connection)

    assert saved.has_password is True
    assert saved.password() == ""
    assert load_mapping(secrets_path)["passwords"] == {"omx": ""}

    env, askpass_path = ConnectionTransport(saved)._subprocess_environment()
    try:
        assert env is not None
        assert env["REACHY_SSH_PASSWORD"] == ""
        assert askpass_path is not None
    finally:
        if askpass_path:
            os.unlink(askpass_path)


def test_switching_to_ssh_key_clears_saved_password(tmp_path):
    config_path = tmp_path / "robotis_connections.yaml"
    secrets_path = tmp_path / "robotis_secrets.yaml"
    registry = ConnectionRegistry(path=config_path, secrets_path=secrets_path)

    registry.save_connection(
        "omx",
        {
            "display_name": "OpenMANIPULATOR-X",
            "target": "omx",
            "host": "192.168.1.10",
            "port": 22,
            "user": "robotis",
            "auth": {
                "method": "password",
                "password": "robotis-password",
                "key_path": "",
                "password_env": "",
            },
        },
    )

    saved = registry.save_connection(
        "omx",
        {
            "display_name": "OpenMANIPULATOR-X",
            "target": "omx",
            "host": "192.168.1.10",
            "port": 22,
            "user": "robotis",
            "auth": {
                "method": "ssh_key",
                "password": "",
                "key_path": "~/.ssh/id_ed25519",
                "password_env": "",
            },
        },
    )

    assert saved.has_password is False
    assert load_mapping(secrets_path)["passwords"] == {}


def test_product_connection_form_values_survive_reload(tmp_path):
    config_path = tmp_path / "robotis_connections.yaml"
    secrets_path = tmp_path / "robotis_secrets.yaml"
    registry = ConnectionRegistry(path=config_path, secrets_path=secrets_path)
    presets = ProductPresetCatalog(connection_state_path=tmp_path / "product_connections.yaml")

    cases = {
        "omx": {
            "host": "",
            "user": "",
            "auth_method": "password",
            "password": "",
            "key_path": "",
        },
        "omy": {
            "host": "omy.local",
            "user": "",
            "auth_method": "ssh_key",
            "password": "",
            "key_path": "",
        },
        "ai_worker": {
            "host": "192.168.50.57",
            "user": "robotis",
            "auth_method": "ssh_key",
            "password": "",
            "key_path": "~/.ssh/custom_ai_worker",
        },
        "hx5_hand": {
            "host": "hand.local",
            "user": "",
            "auth_method": "password",
            "password": "",
            "key_path": "",
        },
    }

    for product_id, form in cases.items():
        connection_id, connection = presets.connection_payload(
            product_id,
            host=form["host"],
            port=22,
            user=form["user"],
            auth={
                "method": form["auth_method"],
                "password": form["password"],
                "key_path": form["key_path"],
                "password_env": "",
            },
        )
        registry.save_connection(connection_id, connection)
        presets.save_connection_state(product_id, form)

    reloaded = ConnectionRegistry(path=config_path, secrets_path=secrets_path)
    for product_id in cases:
        connection_id, payload = presets.connection_payload(product_id)
        reloaded.apply_preset(connection_id, payload)
    products = {item["product_id"]: item for item in presets.public_products(reloaded)}

    for product_id, form in cases.items():
        product = products[product_id]
        assert product["host"] == form["host"]
        assert product["user"] == form["user"]
        assert product["auth_method"] == form["auth_method"]
        assert product["key_path"] == form["key_path"]
        assert product["password"] == form["password"]

    assert products["omx"]["has_password"] is True
    assert products["hx5_hand"]["has_password"] is True
    assert products["omy"]["has_password"] is False
    assert products["ai_worker"]["has_password"] is False


def test_product_connection_state_overrides_profile_defaults(tmp_path):
    config_path = tmp_path / "robotis_connections.yaml"
    secrets_path = tmp_path / "robotis_secrets.yaml"
    state_path = tmp_path / "robotis_product_connections.yaml"
    registry = ConnectionRegistry(path=config_path, secrets_path=secrets_path)
    presets = ProductPresetCatalog(connection_state_path=state_path)

    connection_id, connection = presets.connection_payload(
        "omy",
        host="old-host",
        port=22,
        user="old-user",
        auth={
            "method": "ssh_key",
            "password": "",
            "key_path": "~/.ssh/old_key",
            "password_env": "",
        },
    )
    registry.save_connection(connection_id, connection)
    presets.save_connection_state(
        "omy",
        {
            "host": "",
            "port": 22,
            "user": "",
            "auth_method": "ssh_key",
            "key_path": "",
        },
    )

    product = next(item for item in presets.public_products(registry) if item["product_id"] == "omy")

    assert product["host"] == ""
    assert product["user"] == ""
    assert product["auth_method"] == "ssh_key"
    assert product["key_path"] == ""


def test_ssh_key_path_is_displayed_raw_but_executed_expanded(tmp_path):
    config_path = tmp_path / "robotis_connections.yaml"
    secrets_path = tmp_path / "robotis_secrets.yaml"
    registry = ConnectionRegistry(path=config_path, secrets_path=secrets_path)

    profile = registry.save_connection(
        "omy",
        {
            "display_name": "OMY",
            "target": "omy",
            "host": "omy.local",
            "port": 22,
            "user": "robotis",
            "auth": {
                "method": "ssh_key",
                "password": "",
                "key_path": "~/.ssh/omy_key",
                "password_env": "",
            },
        },
    )

    argv = ConnectionTransport(profile).build_argv("true", command_type="host")
    assert profile.to_public_mapping()["key_path"] == "~/.ssh/omy_key"
    assert "-i" in argv
    assert os.path.expanduser("~/.ssh/omy_key") in argv
