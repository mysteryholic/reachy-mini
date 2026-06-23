# ROBOTIS VLA Interface - UI Binding Audit Report

생성: 2026-06-22
상태: **CRITICAL - 많은 UI 버튼이 실제로 동작하지 않음**

---

## 1. Dashboard & Status Cards

| Button ID | Label | Frontend Handler | API Route | Backend Handler | Adapter Method | Status |
|-----------|-------|------------------|-----------|-----------------|-----------------|--------|
| `dashboard_status_refresh` | Refresh | js_refresh_status | GET `/robotis/status` | `status()` | N/A | ✅ Working |
| `dashboard_ui_summary` | UI Summary | js_load_summary | GET `/robotis/ui/summary` | `ui_summary()` | N/A | ✅ Working |
| `device_status_omx` | OMX Status Card | ws_request_device_status | WS `/robotis/ws` | `_handle_device_status` | N/A | ❓ Unknown |
| `device_status_omy` | OMY Status Card | ws_request_device_status | WS `/robotis/ws` | `_handle_device_status` | N/A | ❓ Unknown |
| `device_status_ai_worker` | AI Worker Status | ws_request_device_status | WS `/robotis/ws` | `_handle_device_status` | N/A | ❓ Unknown |

---

## 2. Action Catalog

| Button ID | Label | Frontend Handler | API Route | Backend Handler | Adapter Method | Status |
|-----------|-------|------------------|-----------|-----------------|-----------------|--------|
| `catalog_list_tasks` | Load Tasks | js_list_tasks | GET `/robotis/actions` | `actions()` | N/A | ✅ Working |
| `catalog_run_task_{name}` | Run Task | js_run_task | POST `/robotis/actions/run` | `actions_run()` | `run_task()` | ✅ Working (mock only) |
| `catalog_run_command_{name}` | Run Command | js_run_command | POST `/robotis/actions/run` | `actions_run()` | `run_command()` | ⚠️ OMY/AI Worker partial |
| `catalog_preview_command` | Preview Command | js_preview_command | GET `/robotis/commands/preview/{device}/{key}` | `command_preview()` | N/A | ❓ Unknown |

---

## 3. Intent Resolver Panel

| Button ID | Label | Frontend Handler | API Route | Backend Handler | Adapter Method | Status |
|-----------|-------|------------------|-----------|-----------------|-----------------|--------|
| `intent_input_text` | Resolve Intent | js_resolve_intent | POST `/robotis/intent/resolve` | `intent_resolve()` | varies | ✅ API works but routing broken |
| `intent_run_resolved` | Run Resolved | js_run_resolved_action | POST `/robotis/actions/run` | `actions_run()` | varies | ✅ API works but adapter support varies |
| `intent_stop_trigger` | "멈춰" | N/A (voice) | implicit | should route to `/robotis/stop` | `stop()` | ❌ **NOT CONNECTED** |
| `intent_torque_off_trigger` | "토크 꺼줘" | N/A (voice) | implicit | should route to torque_off | `torque_off()` | ❌ **NOT IMPLEMENTED** |
| `intent_kill_trigger` | "다 꺼줘" | N/A (voice) | implicit | should route to kill | `kill_processes()` | ❌ **NOT IMPLEMENTED** |

---

## 4. OMX Manual Task Builder

| Button ID | Label | Frontend Handler | API Route | Backend Handler | Adapter Method | Status |
|-----------|-------|------------------|-----------|-----------------|-----------------|--------|
| `omx_task_name_input` | Task Name | js_update_preview | (local) | N/A | N/A | ✅ Working |
| `omx_step_add_movel` | Add Move L | js_add_step | (local) | N/A | N/A | ✅ Working |
| `omx_step_add_gripper` | Add Gripper | js_add_step | (local) | N/A | N/A | ✅ Working |
| `omx_step_add_wait` | Add Wait | js_add_step | (local) | N/A | N/A | ✅ Working |
| `omx_task_save` | Save Task | js_save_task | POST `/robotis/tasks/save` | `tasks_save()` | N/A | ✅ Working |
| `omx_task_dry_run` | Dry Run | N/A | N/A | N/A | N/A | ❌ **NOT IMPLEMENTED** |
| `omx_workspace_preview` | Workspace Preview | N/A | N/A | N/A | N/A | ❌ **NOT IMPLEMENTED** |
| `omx_named_pose_select` | Named Pose | N/A | N/A | N/A | N/A | ❌ **NOT IMPLEMENTED** |
| `omx_position_current` | Current Pose | js_request_current_pose | GET `/robotis/devices/omx/pose` | `get_current_pose()` | N/A | ❌ **NOT IMPLEMENTED** |

---

## 5. OMX Hand Teleop

| Button ID | Label | Frontend Handler | API Route | Backend Handler | Adapter Method | Status |
|-----------|-------|------------------|-----------|-----------------|-----------------|--------|
| `teleop_start_session` | Start Teleop | js_start_teleop | WS or POST | `start_teleop()` | `start_teleop()` | ✅ Partial (WS unclear) |
| `teleop_stop_session` | Stop Teleop | js_stop_teleop | WS or POST | `stop_teleop()` | `stop_teleop()` | ✅ Partial |
| `teleop_target_pos_x` | Target X | js_send_teleop_target | WS `/robotis/ws` | `handle_teleop_target()` | `handle_teleop_target()` | ⚠️ WS unclear |
| `teleop_target_pos_y` | Target Y | js_send_teleop_target | WS `/robotis/ws` | `handle_teleop_target()` | `handle_teleop_target()` | ⚠️ WS unclear |
| `teleop_target_pos_z` | Target Z | js_send_teleop_target | WS `/robotis/ws` | `handle_teleop_target()` | `handle_teleop_target()` | ⚠️ WS unclear |
| `teleop_gripper_open` | Gripper Open | js_send_teleop_gripper | WS `/robotis/ws` | `handle_teleop_target()` | `handle_teleop_target()` | ⚠️ WS unclear |
| `teleop_gripper_close` | Gripper Close | js_send_teleop_gripper | WS `/robotis/ws` | `handle_teleop_target()` | `handle_teleop_target()` | ⚠️ WS unclear |

---

## 6. Remote Robot CLI Control

### OMY Raspberry Pi

| Button ID | Label | Frontend Handler | API Route | Backend Handler | Adapter Method | Transport | Status |
|-----------|-------|------------------|-----------|-----------------|-----------------|-----------|--------|
| `omy_command_bringup` | Bringup | js_run_command | POST `/robotis/actions/run` | `actions_run()` | `run_command()` | **MISSING** | ❌ **NO SSH TRANSPORT** |
| `omy_command_leader_follower` | Leader Follower | js_run_command | POST `/robotis/actions/run` | `actions_run()` | `run_command()` | **MISSING** | ❌ **NO SSH TRANSPORT** |
| `omy_command_stop` | Stop | js_run_command | POST `/robotis/actions/run` | `actions_run()` | `run_command()` | **MISSING** | ❌ **NO SSH TRANSPORT** |
| `omy_status_host` | Host | (display only) | N/A | N/A | N/A | N/A | ✅ Shows `192.168.50.56` |
| `omy_status_container` | Container | (display only) | N/A | N/A | N/A | N/A | ✅ Shows `omy_ros2` |
| `omy_status_last_command` | Last Command | (display only) | N/A | N/A | N/A | N/A | ⚠️ May not update |

### AI Worker Jetson Orin 32GB

| Button ID | Label | Frontend Handler | API Route | Backend Handler | Adapter Method | Transport | Status |
|-----------|-------|------------------|-----------|-----------------|-----------------|-----------|--------|
| `ai_worker_command_bringup` | Bringup | js_run_command | POST `/robotis/actions/run` | `actions_run()` | `run_command()` | **MISSING** | ❌ **NO SSH TRANSPORT** |
| `ai_worker_command_teleop` | Teleop | js_run_command | POST `/robotis/actions/run` | `actions_run()` | `run_command()` | **MISSING** | ❌ **NO SSH TRANSPORT** |
| `ai_worker_command_stop` | Stop | js_run_command | POST `/robotis/actions/run` | `actions_run()` | `run_command()` | **MISSING** | ❌ **NO SSH TRANSPORT** |
| `ai_worker_status_host` | Host | (display only) | N/A | N/A | N/A | N/A | ✅ Shows `192.168.50.57` |
| `ai_worker_status_container` | Container | (display only) | N/A | N/A | N/A | N/A | ✅ Shows `ai_worker_ros2` |
| `ai_worker_status_last_error` | Last Error | (display only) | N/A | N/A | N/A | N/A | ⚠️ May not display actual error |

---

## 7. Rosbag Motions

| Button ID | Label | Frontend Handler | API Route | Backend Handler | Adapter Method | Status |
|-----------|-------|------------------|-----------|-----------------|-----------------|--------|
| `rosbag_list` | List Bags | js_list_bags | GET `/robotis/rosbags` | `list_rosbags()` | N/A | ❌ **NOT IMPLEMENTED** |
| `rosbag_play_{key}` | Play Bag | js_play_bag | POST `/robotis/rosbags/play` | `play_rosbag()` | `play_bag()` | ❌ **NOT IMPLEMENTED** |
| `rosbag_stop` | Stop Bag | js_stop_bag | POST `/robotis/rosbags/stop` | `stop_rosbag()` | `stop_bag()` | ❌ **NOT IMPLEMENTED** |

---

## 8. Demo Flow

| Button ID | Label | Frontend Handler | API Route | Backend Handler | Adapter Method | Status |
|-----------|-------|------------------|-----------|-----------------|-----------------|--------|
| `demo_run_full` | Run Full Demo | js_run_demo_flow | POST `/robotis/demo/run` | `run_demo_flow()` | varies | ⚠️ No prechecks, can fail silently |
| `demo_step_1_jarvis` | Jarvis Intro | js_run_demo_step | POST `/robotis/demo/step/1` | `demo_step_jarvis()` | N/A (mock) | ✅ Working |
| `demo_step_2_omx_task` | OMX Task | js_run_demo_step | POST `/robotis/demo/step/2` | `demo_step_omx_task()` | `run_task()` | ⚠️ Jitter issue |
| `demo_step_3_omx_teleop` | OMX Teleop | js_run_demo_step | POST `/robotis/demo/step/3` | `demo_step_omx_teleop()` | `start_teleop()` | ✅ Partial |
| `demo_step_4_omy_leader` | OMY Leader | js_run_demo_step | POST `/robotis/demo/step/4` | `demo_step_omy_leader()` | `run_command()` | ❌ **NO SSH** |
| `demo_step_5_ai_worker` | AI Worker | js_run_demo_step | POST `/robotis/demo/step/5` | `demo_step_ai_worker()` | `run_command()` | ❌ **NO SSH** |
| `demo_step_6_outro` | Outro | js_run_demo_step | POST `/robotis/demo/step/6` | `demo_step_outro()` | N/A (mock) | ✅ Working |
| `demo_flow_status` | Status Display | (display only) | N/A | N/A | N/A | ❓ May not show step status |

---

## 9. Soft Stop & Safety

| Button ID | Label | Frontend Handler | API Route | Backend Handler | Adapter Method | Status |
|-----------|-------|------------------|-----------|-----------------|-----------------|--------|
| `soft_stop_all` | 🛑 Soft Stop All | js_soft_stop_all | POST `/robotis/stop` | `stop()` | `stop()` (all adapters) | ✅ API exists but may not work for all |
| `device_stop_omx` | Stop OMX | js_device_stop | POST `/robotis/devices/omx/stop` | **MISSING** | `stop()` | ❌ **ENDPOINT NOT IMPLEMENTED** |
| `device_stop_omy` | Stop OMY | js_device_stop | POST `/robotis/devices/omy/stop` | **MISSING** | `stop()` | ❌ **ENDPOINT NOT IMPLEMENTED** |
| `device_stop_ai_worker` | Stop AI Worker | js_device_stop | POST `/robotis/devices/ai_worker/stop` | **MISSING** | `stop()` | ❌ **ENDPOINT NOT IMPLEMENTED** |
| `device_torque_off_omx` | Torque Off OMX | js_device_torque_off | POST `/robotis/devices/omx/torque-off` | **MISSING** | **NOT IMPLEMENTED** | ❌ **METHOD NOT IMPLEMENTED** |
| `device_torque_off_omy` | Torque Off OMY | js_device_torque_off | POST `/robotis/devices/omy/torque-off` | **MISSING** | **NOT IMPLEMENTED** | ❌ **METHOD NOT IMPLEMENTED** |
| `device_torque_off_ai_worker` | Torque Off AI W | js_device_torque_off | POST `/robotis/devices/ai_worker/torque-off` | **MISSING** | **NOT IMPLEMENTED** | ❌ **METHOD NOT IMPLEMENTED** |
| `device_kill_omx` | Kill OMX | js_device_kill | POST `/robotis/devices/omx/kill` | **MISSING** | **NOT IMPLEMENTED** | ❌ **METHOD NOT IMPLEMENTED** |
| `device_kill_omy` | Kill OMY | js_device_kill | POST `/robotis/devices/omy/kill` | **MISSING** | **NOT IMPLEMENTED** | ❌ **METHOD NOT IMPLEMENTED** |
| `device_kill_ai_worker` | Kill AI Worker | js_device_kill | POST `/robotis/devices/ai_worker/kill` | **MISSING** | **NOT IMPLEMENTED** | ❌ **METHOD NOT IMPLEMENTED** |

---

## Summary

### ✅ Working (9)
- Dashboard refresh
- UI summary
- Task list
- Task save
- Mock task execution
- Mock demo flow steps

### ⚠️ Partial / Unclear (8)
- Device status (WS unclear)
- OMY/AI Worker command (no SSH transport)
- Teleop (WS unclear, OMX only)
- Demo flow prechecks missing
- Last command/error display may not update

### ❌ Not Implemented / Broken (28+)
- **SSH/Docker Transport** (blocks OMY, AI Worker)
- **Torque Off endpoints** (3 devices × 1 endpoint = 3)
- **Device stop endpoints** (3 devices × 1 endpoint = 3)
- **Device kill endpoints** (3 devices × 1 endpoint = 3)
- **Dry run validation**
- **Workspace preview**
- **Named pose presets**
- **Current pose fetching**
- **Rosbag commands** (list, play, stop)
- **Intent stop/torque_off/kill routing**
- **Demo Flow prechecks**
- **OMX duplicate guard**
- **Action cancel**

---

## Critical Issues

### 1. **No SSH/Docker Transport**
- OMY와 AI Worker 명령이 실제로 실행되지 않음
- Remote Robot CLI Control이 동작하지 않음
- Transport 구현 필요

### 2. **Incomplete Stop/Torque Off/Kill**
- 로봇을 켜기만 하고 끌 수 없음
- 많은 endpoint가 구현되지 않음
- 모든 adapter에서 `torque_off()`, `kill_processes()` 메서드 없음

### 3. **OMX Task Jitter**
- Demo Flow에서 OMX motion이 unstable
- stable_preset이 config에는 있지만 실제로 적용되지 않음
- Manual task 중심으로 변경 필요

### 4. **No Validation or Feedback**
- Dry run 없음
- Workspace preview 없음
- 에러가 UI에 명확히 표시되지 않음

---

## Next Steps

1. **Stop/Torque Off 구현** (우선순위 1)
   - API endpoints 추가
   - Adapter 메서드 구현
   
2. **SSH/Docker Transport 구현** (우선순위 2)
   - SSHDockerTransport
   - SSHLocalTransport
   
3. **OMX 안정화** (우선순위 3)
   - Duplicate guard
   - Jitter workaround
   
4. **UX 개선** (우선순위 4)
   - Workspace preview
   - Named poses
   - Dry run
