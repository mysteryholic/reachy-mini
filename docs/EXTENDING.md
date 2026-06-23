# Extending The ROBOTIS Interface

This MVP is a language-to-registered-action router, not a free-form VLA model.

To add a task:

1. Add a task entry in `tasks/omx_tasks.yaml`, or save one from `/robotis`.
2. Include trigger phrases that users will actually say.
3. Keep step types inside the supported schema.
4. Run `python scripts/check_task_catalog.py` and `python scripts/check_intent_resolver.py`.

To add a CLI command:

1. Add the executable command string under the target device in `config/robotis_devices.yaml`.
2. Add a command catalog entry in `config/robotis_commands.yaml`.
3. Use a `command_key`, never a user-provided shell string.
4. Keep `dry_run: true` until the target machine is verified.
5. Run `python scripts/check_cli_allowlist.py`.

## OMY Raspberry Pi path

OMY is expected to run through SSH into a Raspberry Pi, then inside a Docker
container:

```text
Reachy Mini App -> SSH -> OMY Raspberry Pi -> Docker container -> source ROS 2 setup -> ros2 launch
```

Edit `config/robotis_omy_raspberry_pi.yaml`:

- `host`
- `user`
- `container_name`
- `ros_setup_path`
- `working_directory`
- `commands.leader_follower`
- `commands.bringup`

Use `mode: "ssh_docker"` for the Docker path. Set `dry_run: false` only after
SSH and Docker access are verified.

## AI Worker Jetson Orin 32GB path

AI Worker is expected to run on Jetson Orin 32GB. It can use Docker or local
shell by changing `mode`:

- `ssh_docker`: SSH to Jetson, then `docker exec`, then source ROS setup.
- `ssh`: SSH to Jetson and run the sourced ROS command on the host shell.
- `local_shell`: run locally with `bash -lc`.

Edit `config/robotis_ai_worker_jetson.yaml`:

- `host`
- `user`
- `container_name`
- `ros_setup_path`
- `working_directory`
- `commands.bringup`
- `commands.teleop`
- `commands.stop`

Run `python scripts/check_ssh_docker_paths.py` after changing these values.

To add a device:

1. Implement a `RobotAdapter`.
2. Register it in `core/service.py`.
3. Update `config/robotis_devices.yaml`.
