from __future__ import annotations

import os

from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
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
