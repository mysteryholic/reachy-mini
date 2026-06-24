"""CLI commands for task management and testing."""

import sys
import logging
from pathlib import Path
from typing import Optional

from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog


def setup_logger(debug: bool = False) -> logging.Logger:
    """Setup logger for CLI."""
    log_level = "DEBUG" if debug else "INFO"
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(levelname)s: %(message)s",
    )
    return logging.getLogger(__name__)


def list_tasks_command() -> int:
    """List all available tasks in a formatted table."""
    catalog = TaskCatalog()
    tasks = catalog.list_tasks()

    if not tasks:
        print("No tasks found.")
        return 0

    print("\n" + "=" * 100)
    print("AVAILABLE TASKS".center(100))
    print("=" * 100)

    for task in tasks:
        print(f"\n  📋 Task Name: {task.name}")
        print(f"     Display Name: {task.display_name}")
        print(f"     Device: {task.device}")
        print(f"     Triggers: {', '.join(task.triggers)}")
        print(f"     Steps: {len(task.steps)} step(s)")

        for i, step in enumerate(task.steps, 1):
            print(f"       [{i}] {step.type}", end="")
            if step.type == "move_l":
                x, y, z = step.params.get("x"), step.params.get("y"), step.params.get("z")
                duration = step.params.get("duration", "default")
                print(f" → move to ({x}, {y}, {z}) in {duration}s")
            elif step.type == "gripper":
                command = step.params.get("command")
                print(f" → {command}")
            elif step.type == "wait":
                duration = step.params.get("duration", 0)
                print(f" → wait {duration}s")
            elif step.type == "say":
                text = step.params.get("text", "")
                print(f" → \"{text}\"")
            else:
                print()

    print("\n" + "=" * 100)
    print(f"Total: {len(tasks)} task(s)")
    print("=" * 100 + "\n")

    return 0


def describe_task_command(task_name: str) -> int:
    """Show detailed information about a specific task."""
    catalog = TaskCatalog()
    task = catalog.get(task_name)

    if task is None:
        print(f"❌ Task '{task_name}' not found.")
        print("\nAvailable tasks:")
        for t in catalog.list_tasks():
            print(f"  - {t.name}")
        return 1

    print("\n" + "=" * 80)
    print(f"TASK DETAILS: {task.name}".center(80))
    print("=" * 80)
    print(f"\n  Display Name: {task.display_name}")
    print(f"  Device Type: {task.device}")
    print(f"\n  Trigger Phrases:")
    for trigger in task.triggers:
        print(f"    • \"{trigger}\"")

    print(f"\n  Execution Steps ({len(task.steps)} total):")
    for i, step in enumerate(task.steps, 1):
        print(f"\n    Step {i}: {step.type.upper()}")
        if step.type == "move_l":
            print(f"      Position: x={step.params.get('x')}, y={step.params.get('y')}, z={step.params.get('z')}")
            duration = step.params.get("duration")
            if duration:
                print(f"      Duration: {duration}s")
        elif step.type == "gripper":
            print(f"      Command: {step.params.get('command')}")
        elif step.type == "wait":
            print(f"      Duration: {step.params.get('duration', 0)}s")
        elif step.type == "say":
            print(f"      Text: \"{step.params.get('text')}\"")

    print("\n" + "=" * 80 + "\n")
    return 0


def test_task_command(task_name: str, dry_run: bool = False) -> int:
    """Test a task (currently displays what would happen)."""
    catalog = TaskCatalog()
    task = catalog.get(task_name)

    if task is None:
        print(f"❌ Task '{task_name}' not found.")
        return 1

    print(f"\n{'🧪 TEST MODE' if dry_run else '▶️  EXECUTING'}: {task.name}")
    print("-" * 80)

    if task.device != "mock":
        print(f"\n⚠️  This task uses device: {task.device}")
        print("   This will execute REAL robot movements.")
        if not dry_run:
            response = input("\n   Continue? (yes/no): ").strip().lower()
            if response != "yes":
                print("   Cancelled.")
                return 0

    print(f"\n  Trigger phrases: {', '.join(task.triggers)}")
    print(f"  Steps to execute: {len(task.steps)}")

    print("\n  Preview of execution:")
    for i, step in enumerate(task.steps, 1):
        print(f"    [{i}] {step.type}", end="")
        if step.type == "move_l":
            x, y, z = step.params.get("x"), step.params.get("y"), step.params.get("z")
            duration = step.params.get("duration", "default")
            print(f" → move to ({x}, {y}, {z}) in {duration}s")
        elif step.type == "gripper":
            command = step.params.get("command")
            print(f" → {command} gripper")
        elif step.type == "wait":
            duration = step.params.get("duration", 0)
            print(f" → wait {duration}s")
        elif step.type == "say":
            text = step.params.get("text", "")
            print(f" → say: \"{text}\"")

    print("\n" + "-" * 80 + "\n")
    return 0


def chat_mode_command() -> int:
    """Interactive chat mode for testing tasks without voice."""
    from reachy_robotis.robotis_interface.core.service import get_robotis_executor
    import asyncio
    import sys

    executor = get_robotis_executor()

    print("\n" + "=" * 80)
    print("💬 CHAT MODE: Text-Only Task Testing".center(80))
    print("=" * 80)
    print("\n  Type task names or trigger phrases to execute them.")
    print("  Commands:")
    print("    • list          - Show all available tasks")
    print("    • describe      - Show task details")
    print("    • status        - Show execution status")
    print("    • help          - Show this help")
    print("    • exit, quit    - Exit chat mode")
    print("\n  Example:")
    print("    >> push the box")
    print("    >> push_box_custom")
    print("    >> list")
    print("\n" + "=" * 80 + "\n")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        while True:
            try:
                sys.stdout.write(">> ")
                sys.stdout.flush()
                user_input = sys.stdin.readline().strip()

                if not user_input:
                    continue
            except (EOFError, KeyboardInterrupt):
                break

            if user_input.lower() in ("exit", "quit"):
                print("\n👋 Exiting chat mode...\n")
                break

            if user_input.lower() == "help":
                print("\n📖 Available commands:")
                print("  • <task_name>       - Execute task by name")
                print("  • <trigger_phrase>  - Execute task by trigger phrase")
                print("  • list              - Show all tasks")
                print("  • describe <name>   - Show task details")
                print("  • status            - Show last execution status")
                print("  • help              - Show this help")
                print("  • exit              - Exit chat mode\n")
                continue

            if user_input.lower() == "list":
                tasks = executor.task_catalog.list_tasks()
                if not tasks:
                    print("\n❌ No tasks found.\n")
                    continue
                print(f"\n📋 Available Tasks ({len(tasks)}):")
                for task in tasks:
                    triggers = ", ".join(task.triggers[:2])
                    print(f"   • {task.name:<25} | {task.display_name:<30} | {triggers}")
                print()
                continue

            if user_input.lower().startswith("describe"):
                parts = user_input.split(None, 1)
                if len(parts) < 2:
                    print("   Usage: describe <task_name>\n")
                    continue
                task_name = parts[1]
                task = executor.task_catalog.get(task_name)
                if not task:
                    print(f"   ❌ Task '{task_name}' not found\n")
                    continue
                print(f"\n   📋 {task.display_name}")
                print(f"      Device: {task.device}")
                print(f"      Triggers: {', '.join(task.triggers)}")
                print(f"      Steps: {len(task.steps)}")
                for i, step in enumerate(task.steps, 1):
                    print(f"        [{i}] {step.type}")
                print()
                continue

            if user_input.lower() == "status":
                snapshot = executor.ui_snapshot()
                print(f"\n📊 Status:")
                print(f"   Last Command: {snapshot.get('last_voice_command') or '(none)'}")
                print(f"   Last Action: {snapshot.get('last_resolved_action') or '(none)'}")
                print(f"   Last Result: {snapshot.get('last_execution_result') or '(none)'}")
                print(f"   Success: {'✅' if snapshot.get('last_execution_ok') else '❌'}")
                print(f"   Connected: {'🟢 Yes' if snapshot.get('connected') else '🔴 No'}\n")
                continue

            print(f"\n   ⏳ Executing: {user_input}...")
            try:
                result = loop.run_until_complete(executor.run_resolved_text(user_input))
                status = "✅" if result.ok else "❌"
                print(f"   {status} {result.message or result.error}\n")
            except Exception as e:
                print(f"   ❌ Error: {e}\n")

    except KeyboardInterrupt:
        print("\n\n👋 Chat mode interrupted.\n")
    finally:
        loop.close()

    return 0


def show_help() -> int:
    """Show help message."""
    help_text = """
╔════════════════════════════════════════════════════════════════════════╗
║           Reachy Mini ROBOTIS - Task Management CLI                   ║
╚════════════════════════════════════════════════════════════════════════╝

USAGE:
  reachy-robotis <command> [options]

COMMANDS:
  list-tasks              Show all available tasks
  describe-task <name>    Show details about a specific task
  test-task <name>        Test a task (preview mode)
  chat                    Interactive chat mode (text-only testing)

EXAMPLES:
  reachy-robotis list-tasks
  reachy-robotis describe-task push_box_custom
  reachy-robotis test-task jarvis_intro
  reachy-robotis chat

Run 'reachy-robotis <command> --help' for more information.

START THE APP:
  reachy-robotis --gradio      Start web interface
  reachy-robotis               Start headless mode (requires settings_app)

ROBOT CONTROL:
  Connection & execution are handled by daemon (reachy-mini-daemon)
  Current state:
    ✅ CONNECTING: Daemon auto-connects when app starts
    ⚙️  EXECUTING: Tasks run when triggered
    🛑 DISCONNECTING: Daemon auto-disconnects when app closes (motors released)

  Chat mode lets you test tasks via text without voice recognition.

SHUTDOWN:
  Press Ctrl+C to gracefully stop the app. All motors will be released.
"""
    print(help_text)
    return 0
