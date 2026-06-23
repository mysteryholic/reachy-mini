# ROBOTIS Task Catalog

Tasks are step-based robot behaviors defined in YAML files. They live in `tasks/*.yaml` and are loaded by `TaskCatalog`.

## Quick Start

**List all available tasks:**
```bash
./reachy-robotis list-tasks
```

**Describe a specific task:**
```bash
./reachy-robotis describe-task <task_name>
```

**Test a task (preview mode - no execution):**
```bash
./reachy-robotis test-task <task_name>
```

**Interactive Chat Mode (text-only testing):**
```bash
./reachy-robotis chat
```

Chat mode examples:
```
>> list                           # Show all tasks
>> describe push_box_custom       # Get task details
>> 박스 치워줘                    # Execute by trigger phrase
>> status                         # Show last result
>> exit                           # Exit chat
```

## Step Types

Every task is composed of steps. Supported step types:

| Type | Purpose | Parameters | Example |
|------|---------|------------|---------|
| `move_l` | Move robot arm to position | `x`, `y`, `z` (required), `duration` (optional) | `{"x": 0.18, "y": 0.10, "z": 0.18, "duration": 0.5}` |
| `gripper` | Control gripper | `command`: `"open"` or `"close"` | `{"command": "close"}` |
| `wait` | Pause execution | `duration` (seconds) | `{"duration": 1.0}` |
| `say` | Speak text (mock/demo) | `text` (required) | `{"text": "Hello"}` |

## Example Task Definition

```yaml
{
  "tasks": [
    {
      "name": "push_box_custom",
      "display_name": "Push Box Custom",
      "triggers": ["박스 치워줘", "박스 밀어"],
      "device": "omx",
      "steps": [
        {"type": "move_l", "params": {"x": 0.18, "y": 0.10, "z": 0.18, "duration": 0.5}},
        {"type": "gripper", "params": {"command": "close"}},
        {"type": "move_l", "params": {"x": 0.24, "y": 0.10, "z": 0.18, "duration": 0.5}},
        {"type": "gripper", "params": {"command": "open"}}
      ]
    }
  ]
}
```

## Task Configuration

Each task must have:
- **name**: Internal identifier (lowercase, underscores)
- **display_name**: Human-readable name
- **triggers**: List of voice/text commands that activate this task
- **device**: Target device (`"mock"` for simulation, `"omx"` for real robot)
- **steps**: Array of execution steps

## Device Types

- **mock**: Simulation mode (safe for testing)
- **omx**: Real robot control (requires connected hardware)

## Creating Custom Tasks

1. Edit or create a `.yaml` file in `tasks/`
2. Define task fields (see example above)
3. Reload the app or manually trigger task reload
4. Use CLI to verify: `reachy-robotis list-tasks`

The file format is JSON-compatible YAML so it works even before `PyYAML` is installed.

