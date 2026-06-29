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

Reachy Robotis는 Reachy Mini 대화 앱 위에 ROBOTIS 장비 실행 인터페이스를 얹은 프로젝트입니다. 현재 구현은 단순한 데모 채팅 앱을 넘어, 음성/텍스트/웹 UI 입력을 등록된 액션으로 해석하고 OMX, OMY, AI Worker, HX5 Hand, mock 장비의 워크플로 또는 명령을 실행하는 구조입니다.

현재의 큰 흐름은 다음과 같습니다.

```text
사용자 음성 / 텍스트 / 웹 UI
  -> Reachy Mini conversation app
  -> OpenAI 또는 Hugging Face realtime backend
  -> tool/function calling
  -> ROBOTIS intent resolver
  -> action / recipe / task / command catalog
  -> ActionExecutor
  -> device adapter
  -> SSH, Docker, ROS 2, HTTP bridge, mock transport
```

> ⚠️ 보안 경고
>
> 과거 빌드에서 `OPENAI_API_KEY`가 `src/reachy_robotis/.env`에 저장되고 로그나 검색 결과에 원문으로 노출된 적이 있습니다. 이미 노출된 키는 유출된 것으로 간주하고 반드시 폐기 후 재발급하세요: https://platform.openai.com/api-keys
>
> 현재 구현은 프로젝트 루트의 `.env`를 우선 사용하며, 기존 `src/reachy_robotis/.env`가 발견되면 루트 `.env`로 이관하려고 시도합니다. 로그, API 응답, UI에서는 키를 마스킹합니다. Hugging Face에서 OpenAI 키를 자동으로 가져오는 동작은 기본 비활성화되어 있고, `--allow-hf-key-fetch`를 명시했을 때만 켜집니다.

## 현재 구현 요약

- Python 패키지 이름은 `reachy_robotis`이고, CLI 엔트리포인트는 `reachy-robotis`입니다.
- 기본 앱은 Reachy Mini SDK의 `ReachyMini` 객체를 생성하고, `MovementManager`, `HeadWobbler`, camera worker, vision manager, realtime handler를 조립합니다.
- Gradio/FastAPI 기반 웹 모드에서는 `/chat`에 대화/음성 인터페이스를, `/robotis`에 ROBOTIS 제품 런처와 실행 API를 마운트합니다.
- headless 모드에서도 FastAPI settings app이 있으면 `/robotis` API와 패널을 붙이고, 로컬 오디오 스트림으로 Reachy Mini 마이크/스피커와 realtime backend를 연결합니다.
- ROBOTIS 실행 계층은 `TaskCatalog`, `CommandCatalog`, `ActionCatalog`, `RecipeCatalog`, `ConnectionRegistry`, `DeviceRegistry`, `TerminalSessionManager`, `ActionExecutor`로 나뉘어 있습니다.
- 장비별 어댑터는 `reachy`, `omx`, `omy`, `ai_worker`, `mock`을 지원합니다.
- 트랜스포트는 local/mock 외에 SSH, SSH+Docker, WebSocket, HTTP, OMX bridge 계층이 구현되어 있습니다.
- 설정과 워크플로는 YAML 파일로 정의되며, 웹 UI에서 일부 연결 정보와 워크플로를 저장/갱신할 수 있습니다.
- 테스트는 pytest 기반으로 connection registry, external loading, OpenAI realtime, background tool manager, audio head wobble, vision processor를 다룹니다.

## 설치

이 저장소는 `uv` 사용을 전제로 합니다.

```bash
uv sync
```

아래 실행 예시는 모두 `uv run ...` 형태로 적었습니다. `.venv`를 직접 활성화한 상태라면 앞의 `uv run`은 생략해도 됩니다.

개발 도구까지 설치하려면 다음 의존성 그룹을 사용합니다.

```bash
uv sync --group dev
```

선택 vision backend가 필요하면 pyproject의 extra를 설치합니다.

```bash
uv sync --extra local_vision
uv sync --extra yolo_vision
uv sync --extra mediapipe_vision
uv sync --extra all_vision
```

## 환경 변수

루트 `.env` 또는 쉘 환경변수로 설정합니다.

```bash
cp .env.example .env
```

주요 값은 다음과 같습니다.

- `BACKEND_PROVIDER`: `huggingface` 또는 `openai`. 기본값은 `huggingface`입니다.
- `OPENAI_API_KEY`: `BACKEND_PROVIDER=openai`일 때 필요합니다.
- `HF_TOKEN`: Hugging Face realtime backend 사용 시 필요할 수 있습니다. `hf auth login`으로도 설정할 수 있습니다.
- `MODEL_NAME`: OpenAI backend에서 사용할 realtime 모델입니다. 기본값은 `gpt-realtime`입니다.
- `LOCAL_VISION_MODEL`: `--local-vision` 사용 시 로컬 vision 모델입니다. 기본값은 `HuggingFaceTB/SmolVLM2-2.2B-Instruct`입니다.
- `ROBOTIS_CLI_DRY_RUN`: `1`이면 실제 명령 대신 dry-run 성격으로 실행합니다. `0`이면 dry-run을 끕니다.
- `GRADIO_SERVER_NAME`, `GRADIO_SERVER_PORT`: 웹 서버 host/port를 바꿉니다. 기본 port는 `7860`입니다.
- `REACHY_MINI_SKIP_DOTENV`: `.env` 자동 로딩을 건너뜁니다.
- `REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY`, `REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY`, `AUTOLOAD_EXTERNAL_TOOLS`: 외부 personality/tool 로딩에 사용합니다.

## 실행

시뮬레이터 또는 실제 Reachy Mini daemon이 먼저 필요합니다.

```bash
uv run reachy-mini-daemon --sim
```

웹 UI를 실행합니다.

```bash
uv run reachy-robotis --gradio
```

브라우저에서 다음 주소를 사용합니다.

- `http://localhost:7860/chat`: Reachy Mini 음성/채팅 인터페이스
- `http://localhost:7860/robotis`: ROBOTIS 제품 런처
- `http://localhost:7860/robotis/health`: 상태 확인 API

headless 모드는 다음처럼 실행합니다.

```bash
uv run reachy-robotis
```

시뮬레이션 상태가 감지되고 `--gradio`가 없으면 앱이 Gradio 모드를 자동으로 켭니다.

자주 쓰는 옵션은 다음과 같습니다.

```bash
uv run reachy-robotis --gradio --debug
uv run reachy-robotis --no-camera
uv run reachy-robotis --head-tracker yolo
uv run reachy-robotis --head-tracker mediapipe
uv run reachy-robotis --local-vision
uv run reachy-robotis --robot-name <daemon과-같은-robot-name>
uv run reachy-robotis --allow-hf-key-fetch
```

종료는 `Ctrl+C`입니다. 종료 시 movement manager, head wobbler, camera worker, vision manager를 멈추고 robot media/client 연결을 닫습니다.

## CLI

`src/reachy_robotis/main.py`는 일부 하위 명령을 먼저 처리합니다.

```bash
uv run reachy-robotis list-tasks
uv run reachy-robotis describe-task <task_name>
uv run reachy-robotis test-task <task_name>
uv run reachy-robotis chat
uv run reachy-robotis --help
```

`chat` 모드는 음성 없이 텍스트로 등록된 task trigger나 task name을 실행해 보는 용도입니다.

```text
>> list
>> describe push_box_custom
>> push the box
>> push_box_custom
>> status
>> exit
```

주의: `test-task`는 현재 실제 로봇 실행기라기보다 작업 내용을 미리 보여주는 preview 성격입니다. `device`가 `mock`이 아니면 실제 움직임 가능성을 경고합니다.

## 웹 UI

### `/chat`

Realtime 대화 UI입니다. 현재 구현은 FastRTC `Stream`과 `OpenaiRealtimeHandler`를 사용합니다.

- 음성 입출력
- 텍스트 채팅 주입
- 대화 transcript 저장
- text chat 중 오디오 입력 mute 처리
- Hugging Face backend는 16 kHz PCM, OpenAI backend는 24 kHz PCM으로 샘플레이트를 맞춤
- tool/function calling을 통해 Reachy Mini tool과 ROBOTIS tool 실행
- Gradio personality UI 연결

### `/robotis`

ROBOTIS 제품/워크플로 런처입니다.

- 제품 카드 기반 런처
- 연결 정보 저장
- 연결 테스트
- workflow 실행/정지
- 마지막 실행 결과와 stdout/stderr tail 표시
- 전체 stop
- WebSocket 기반 1초 주기 상태 갱신
- camera snapshot/object detection API
- task 저장/삭제/export API
- recipe 저장/삭제/실행/정지 API
- connection profile 조회/저장/테스트 API
- device별 allowlist command 실행 API

현재 UI의 주요 API는 다음과 같습니다.

```text
GET    /robotis/health
GET    /robotis/status
GET    /robotis/ui/summary
GET    /robotis/actions
POST   /robotis/actions/run
POST   /robotis/intent/resolve
POST   /robotis/stop
POST   /robotis/actions/cancel
GET    /robotis/products
POST   /robotis/products/{product_id}/connection
POST   /robotis/products/{product_id}/test
PUT    /robotis/products/{product_id}/workflows/{workflow_id}
POST   /robotis/products/{product_id}/workflows/{workflow_id}
GET    /robotis/connections
POST   /robotis/connections/{connection_id}
POST   /robotis/connections/{connection_id}/test
GET    /robotis/recipes
POST   /robotis/recipes/{recipe_id}
POST   /robotis/recipes/{recipe_id}/run
POST   /robotis/recipes/{recipe_id}/stop
GET    /robotis/sessions
POST   /robotis/sessions/{session_id}/stop
GET    /robotis/camera/status
GET    /robotis/camera/snapshot
GET    /robotis/camera/detections
WS     /robotis/ws
WS     /robotis/omx/teleop
WS     /robotis/omx/task
```

## ROBOTIS 실행 구조

ROBOTIS 쪽 실행은 `get_robotis_executor()`에서 한 번 조립되는 process-wide executor가 담당합니다.

구성 요소:

- `DeviceRegistry`: `config/robotis_devices.yaml`을 읽어 장비별 mode, host, user, container, allowlisted command를 관리합니다.
- `ConnectionRegistry`: `config/robotis_connections.yaml`의 SSH/Docker 연결 프로필을 관리합니다. API 응답에는 비밀값을 노출하지 않습니다.
- `TaskCatalog`: `tasks/*.yaml`의 수동 task를 로드합니다.
- `CommandCatalog`: 등록 command를 로드합니다.
- `ActionCatalog`: `config/robotis_actions.yaml`의 trigger 기반 action을 로드합니다.
- `RecipeCatalog`: `config/robotis_recipes.yaml`의 multi-terminal workflow를 로드합니다.
- `ProductPresetCatalog`: `config/robotis_product_presets.yaml`의 제품 프리셋을 설치하고 action/recipe/connection을 보강합니다.
- `TerminalSessionManager`: recipe의 terminal들을 start order 순서로 실행하고, stop 시 역순으로 정지합니다.
- `IntentResolver`: 사용자 문장을 task, command, action, recipe trigger로 해석합니다.
- `ActionExecutor`: 해석 결과를 실제 adapter와 transport로 dispatch합니다.

지원 adapter:

- `ReachyAdapter`: Reachy Mini conversation app 쪽 동작
- `OMXAdapter`: OMX task, bridge, teleop, command 실행
- `OMYAdapter`: OMY Raspberry Pi/ROS workflow 실행
- `AIWorkerAdapter`: Jetson Orin AI Worker workflow 실행
- `MockAdapter`: 실제 하드웨어 없는 테스트 흐름

지원 transport:

- `MockTransport`
- `CLITransport`
- `ConnectionTransport`
- `SSHDockerTransport`
- `SSHLocalTransport`
- `HTTPTransport`
- `WebSocketTransport`
- `OMXBridgeTransport`

## 설정 파일

현재 핵심 설정은 `src/reachy_robotis/config/` 아래에 있습니다.

```text
robotis_devices.yaml          장비별 기본 mode, host, user, container, command allowlist
robotis_connections.yaml      SSH/Docker 연결 프로필
robotis_actions.yaml          음성/텍스트 trigger -> action 매핑
robotis_recipes.yaml          multi-terminal workflow 정의
robotis_product_presets.yaml  제품 카드, 기본 연결, workflow preset
robotis_commands.yaml         command catalog
robotis_omy_raspberry_pi.yaml OMY 관련 별도 설정
robotis_ai_worker_jetson.yaml AI Worker 관련 별도 설정
```

기본 YAML에는 개발 환경에서 쓰던 IP, 사용자명, container 이름이 들어 있습니다. 실제 장비에서는 `/robotis` UI에서 연결 정보를 저장하거나 YAML을 환경에 맞게 수정해야 합니다.

## 제품 프리셋

현재 `robotis_product_presets.yaml`에는 다음 제품군이 정의되어 있습니다.

- `omx`: OMX bringup, MoveIt, GUI, demo rosbag workflow
- `omy`: OMY AI teleoperation, MoveIt, GUI, demo rosbag workflow
- `ai_worker`: AI Worker BG2/SG2 workflow
- `hx5_hand`: HX5 Hand container start workflow

프리셋은 connection, Docker mode, ROS distro/setup, workflow terminal 목록을 함께 제공합니다. `/robotis` UI의 제품 카드에서 host/user/auth를 저장하면 해당 connection profile과 product state가 갱신됩니다.

## Task, Action, Recipe 차이

### Task

Task는 단계 기반 로봇 동작입니다. 예시는 `src/reachy_robotis/tasks/omx_tasks.yaml`의 `push_box_custom`입니다.

```yaml
{
  "name": "push_box_custom",
  "display_name": "Push Box Custom",
  "triggers": ["push the box", "clear the box"],
  "device": "omx",
  "steps": [
    {"type": "move_l", "params": {"x": 0.18, "y": 0.10, "z": 0.18, "duration": 0.5}},
    {"type": "gripper", "params": {"command": "close"}}
  ]
}
```

지원되는 대표 step은 `move_l`, `gripper`, `wait`, `say`입니다.

### Action

Action은 사용자 trigger와 실행 방법을 연결합니다. `robotis_actions.yaml`에서 정의합니다.

실행 method 예시:

- `start_recipe`
- `stop_recipe`
- `run_command`
- `run_manual_task`
- `start_hand_teleop`
- `stop_all`

### Recipe

Recipe는 하나 이상의 terminal command를 실행하는 workflow입니다. 각 terminal에는 `connection_id`, `command_type`, `command`, `run_mode`, `start_order`, `wait_after_start_sec`, `stop_command`가 들어갑니다.

`run_mode`는 foreground 또는 detached 형태로 쓰이며, stop은 recipe terminal의 역순으로 수행됩니다.

## Command 실행과 안전장치

- 웹 UI/API에서 임의 shell command를 직접 실행하는 것이 아니라 YAML에 등록된 allowlisted command key 또는 recipe terminal command를 실행합니다.
- `ConnectionRegistry`는 password/key 정보를 API 응답에서 숨깁니다.
- product connection 저장 시 host/user/auth/key_path가 UI 상태와 round-trip되는지 확인합니다.
- connection test는 TCP, SSH, container, ROS 단계로 나뉩니다.
- device별 stop, torque-off, kill, global stop API가 있습니다.
- `ROBOTIS_CLI_DRY_RUN`과 장비별 `dry_run` 설정으로 실제 실행 여부를 제어합니다.

## Camera와 Vision

카메라는 `--no-camera`가 없을 때 `CameraWorker`로 초기화됩니다.

- `--head-tracker yolo`: `reachy_robotis.vision.yolo_head_tracker.HeadTracker`
- `--head-tracker mediapipe`: `reachy_mini_toolbox.vision.HeadTracker`
- `--local-vision`: 로컬 vision manager 초기화
- 기본 vision 설명은 gpt-realtime vision 사용으로 로그에 남습니다.

`/robotis/camera/snapshot`은 최신 프레임에 object detection bounding box를 그려 JPEG로 반환합니다. `/robotis/camera/detections`는 마지막 snapshot inference 결과를 JSON으로 반환합니다.

## Personality와 Tool 로딩

현재 `LOCKED_PROFILE`은 `_reachy_robotis_locked_profile`로 설정되어 있습니다. 따라서 기본적으로 내장 locked profile의 instructions와 tools를 사용합니다.

tool 로딩 흐름:

- profile의 `tools.txt`를 읽습니다.
- `SystemTool`에 정의된 시스템 tool을 추가합니다.
- profile module에서 먼저 찾고, 없으면 `reachy_robotis.tools`에서 찾습니다.
- 외부 tools directory와 `AUTOLOAD_EXTERNAL_TOOLS`가 설정되어 있으면 추가 tool을 자동 로드할 수 있습니다.
- 외부 profile/tool 이름이 내장 이름과 충돌하면 명시적인 오류를 냅니다.

대표 tool 파일:

```text
tools/run_robotis_action.py
tools/resolve_robotis_intent.py
tools/list_robotis_actions.py
tools/list_robot_commands.py
tools/list_robot_connections.py
tools/test_robot_connection.py
tools/task_status.py
tools/task_cancel.py
tools/move_head.py
tools/head_tracking.py
tools/camera.py
tools/dance.py
```

## 코드 구조

```text
src/reachy_robotis/
  main.py                         앱/CLI 엔트리포인트
  cli.py                          task CLI와 text-only chat mode
  config.py                       env, backend, profile, tool 경로 설정
  openai_realtime.py              realtime 음성/텍스트 handler
  console.py                      headless LocalStream과 settings API
  gradio_personality.py           Gradio personality UI
  headless_personality*.py        headless personality 저장/적용 API
  camera_worker.py                Reachy camera frame worker
  moves.py                        Reachy movement manager
  audio/                          speech tapper, head wobbler
  vision/                         object detector, processors, YOLO tracker
  tools/                          function-calling tool 구현
  profiles/                       built-in locked profile
  config/                         ROBOTIS YAML 설정
  tasks/                          task YAML
  static/                         chat/settings frontend
  robotis_interface/
    adapters/                     장비별 adapter
    core/                         catalog, resolver, executor, registry, session manager
    transports/                   CLI/SSH/Docker/HTTP/WebSocket/mock transport
    web/                          /robotis FastAPI routes와 static panel
```

## 테스트

현재 테스트는 `tests/` 아래에 있습니다.

```bash
uv run pytest
```

개별 테스트 예시:

```bash
uv run pytest tests/test_connection_registry.py
uv run pytest tests/test_openai_realtime.py
uv run pytest tests/tools/test_background_tool_manager.py
uv run pytest tests/vision/test_processors.py
```

정적 검사 도구는 pyproject에 설정되어 있습니다.

```bash
uv run ruff check src tests
uv run mypy
```

## 현재 주의할 점

- 이 프로젝트는 완성된 범용 multi-robot framework라기보다 Reachy Mini 앱에서 ROBOTIS 장비 workflow를 실행하기 위한 통합 인터페이스입니다.
- 실제 VLA 모델을 학습하거나 배포하지 않습니다. 등록된 trigger, task, action, recipe, command를 해석하고 실행합니다.
- 기본 장비 설정에는 개발용 IP와 container 이름이 들어 있으므로 실제 네트워크에 맞게 수정해야 합니다.
- `docs/` 디렉터리는 현재 저장소에 없습니다. 예전 README에 있던 `docs/TASKS.md`, `docs/EXTENDING.md`, `docs/DEMO_SCRIPT.md` 링크는 현재 구현 상태와 맞지 않아 제거했습니다.
- 실제 로봇 연결에서 `dry_run`을 끄면 SSH/Docker/ROS 명령과 로봇 움직임이 실행될 수 있습니다. 장비 주변 안전을 먼저 확인하세요.
