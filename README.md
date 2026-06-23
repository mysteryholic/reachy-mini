---
title: Reachy Robotis
emoji: 🤖
colorFrom: purple
colorTo: gray
sdk: static
pinned: false
tags:
  - reachy_mini
  - reachy_mini_python_app
---

# Reachy Robotis

A task-based control interface for Reachy Mini robot. This app lets you define robot behaviors as composable tasks and trigger them via speech, text, or the web UI.

> ⚠️ **보안 경고 / Security warning**
> 과거 빌드에서 `OPENAI_API_KEY`가 `src/reachy_robotis/.env`에 저장되고 로그/`grep` 결과에 원문이 노출된 적이 있습니다.
> 이미 노출된 키는 유출된 것으로 간주하고 **반드시 폐기 후 재발급**하세요: https://platform.openai.com/api-keys
> 이제 키는 프로젝트 루트 `/.env`에만 저장되며, 로그·API 응답·UI에서는 항상 `sk-proj-...87IA` 형태로 마스킹됩니다.
> `OPENAI_API_KEY`는 프로젝트 루트 `.env` 또는 환경변수로만 설정하세요. HuggingFace 자동 키 다운로드는 기본 비활성화이며 `--allow-hf-key-fetch` 플래그로만 동작합니다.

## What is Reachy Robotis?

This is a Reachy Mini based VLA-like robot task interface template. It is not a finished multi-robot control framework and does not train Vision-Language-Action models. The intended flow is deliberately bounded:

```
user speech / chat / web UI input
  ↓
resolve a registered trigger phrase
  ↓
run a registered task or allowlisted CLI command
  ↓
report the result through Reachy Mini
```

## Quick Start

### 1. Install

```bash
uv sync
reachy-mini-daemon --sim  # in another terminal (simulator mode)
```

### 2. Explore Available Tasks

Before running anything, see what tasks are available:

```bash
./reachy-robotis list-tasks           # Show all tasks
./reachy-robotis describe-task <name> # Show task details
./reachy-robotis test-task <name>     # Preview what a task does (no execution)
./reachy-robotis chat                 # Interactive chat mode - test tasks via text
```

### 3. Test Tasks with Chat Mode

Chat mode lets you test tasks **without voice recognition** - perfect for verification:

```bash
./reachy-robotis chat
>> list                          # Show available tasks
>> 박스 치워줘                    # Execute task by trigger phrase
>> push_box_custom               # Or by task name
>> status                        # Check last execution result
>> exit                          # Exit chat mode
```

### 4. Start the Full App

**Option A: Web Interface (recommended)**
```bash
./reachy-robotis --gradio
# Opens web UI at http://localhost:7860/
```

**Option B: Headless Mode**
```bash
./reachy-robotis
```

### 5. Control Robot Connection

The robot daemon automatically connects when the app starts. To safely control the connection:

**Web Interface:**
- Connection button in ROBOTIS panel
- Shows 🟢 Connected / 🔴 Disconnected status

**Programmatic API:**
```bash
# Connect to robot
curl -X POST http://localhost:8000/robotis/connect

# Disconnect and safely stop all motors
curl -X POST http://localhost:8000/robotis/disconnect

# Check connection status
curl http://localhost:8000/robotis/connection/status
```

### 6. Stop the App

Press `Ctrl+C` in the terminal. The app will:
1. Stop all ongoing movements
2. Release all motors gracefully
3. Disconnect from robot daemon
4. Close connections cleanly

## Task Management

### Available Tasks

Tasks are defined in `tasks/*.yaml`:
- `demo_flow.yaml` - Mock/simulation tasks (safe, no real hardware)
- `omx_tasks.yaml` - Real robot tasks (requires hardware)

Each task has:
- **Trigger phrases** - Voice/text commands that activate it
- **Steps** - Sequence of robot actions (move, gripper, wait, speak)
- **Device type** - `mock` (simulator) or `omx` (real hardware)

### Create a New Task

1. Edit `tasks/omx_tasks.yaml` or `tasks/demo_flow.yaml`
2. Add a new task definition:
   ```yaml
   {
     "name": "my_task",
     "display_name": "My Custom Task",
     "triggers": ["do something", "perform action"],
     "device": "omx",
     "steps": [
       {"type": "move_l", "params": {"x": 0.2, "y": 0.1, "z": 0.15, "duration": 1.0}},
       {"type": "gripper", "params": {"command": "close"}},
       {"type": "say", "params": {"text": "Done!"}}
     ]
   }
   ```
3. Verify: `reachy-robotis describe-task my_task`

See [TASKS.md](docs/TASKS.md) for full documentation.

## Web Interface

When running with `--gradio`, the app provides:

- **Main chat interface** at `/` - Talk to Reachy Mini
- **ROBOTIS control panel** at `/robotis` - Task management and debugging

## Hardware Configuration

The app supports multiple hardware targets:

- **Raspberry Pi + Reachy Mini**: `config/robotis_omy_raspberry_pi.yaml`
- **Jetson Orin (AI Worker)**: `config/robotis_ai_worker_jetson.yaml`

Both support `ssh_docker` mode for remote execution.

## Advanced Configuration

### Customize the App Behavior

Use the `src/reachy_robotis/profiles/_reachy_robotis_locked_profile` folder:
- Edit instructions: `_reachy_robotis_locked_profile/instructions.txt`
- Edit available tools: `_reachy_robotis_locked_profile/tools.txt`
- Create custom tools by subclassing the `Tool` class

### Important Files to Customize

- `README.md` - This file
- `index.html` - Hugging Face Spaces landing page
- `src/reachy_robotis/static/index.html` - Web app parameters

## Troubleshooting

### "Connection timeout: Failed to connect to Reachy Mini daemon"

Make sure the daemon is running in another terminal:
```bash
reachy-mini-daemon --sim
```

### Task not executing?

1. Check if task is registered: `reachy-robotis list-tasks`
2. Verify syntax: `reachy-robotis describe-task <task_name>`
3. Ensure device type matches your setup (`mock` for simulator, `omx` for real hardware)

### App crashes on shutdown?

Press `Ctrl+C` again to force shutdown. The app should gracefully close connections.

## Documentation

- [TASKS.md](docs/TASKS.md) - Complete task reference
- [EXTENDING.md](docs/EXTENDING.md) - How to extend the app
- [DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) - Example demonstrations

## See Also

The original README from the conversation app is in [README_OLD.md](README_OLD.md).
# reachy-mini
