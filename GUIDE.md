# Reachy Robotis - 완전 사용 가이드

## 🎯 주요 개선 사항

### 1️⃣ Task 카탈로그 명확화
- ✅ 어떤 task가 뭘 하는지 한눈에 보기
- ✅ Task 상세 정보 확인
- ✅ 실행 전 미리 보기

### 2️⃣ 안전한 테스트 모드
- ✅ 채팅 모드 - 음성 인식 없이 텍스트로 테스트
- ✅ 미리보기 모드 - 실제 실행 전에 어떤 동작을 할지 확인
- ✅ Mock 디바이스 - 실제 로봇 없이 시뮬레이션

### 3️⃣ 로봇 연결 제어
- ✅ 명시적인 연결/해제
- ✅ 연결 상태 확인
- ✅ 종료 시 안전하게 모터 해제

### 4️⃣ 간단한 CLI 인터페이스
- ✅ 복잡한 웹 UI 없이도 모든 기능 사용 가능
- ✅ 터미널에서 직접 task 관리

---

## 🚀 사용 방법

### 1단계: 준비

```bash
# 1. 로봇 daemon 시작 (다른 터미널에서)
reachy-mini-daemon --sim

# 2. 프로젝트 디렉토리로 이동
cd /home/pollen/reachy_robotis

# 3. CLI 명령 테스트
./reachy-robotis list-tasks
```

### 2단계: Task 탐색

```bash
# 모든 task 보기
./reachy-robotis list-tasks

# 특정 task 상세 정보
./reachy-robotis describe-task push_box_custom

# 실행 전에 어떤 동작을 할지 미리 보기
./reachy-robotis test-task push_box_custom
```

**출력 예시:**
```
📋 Task Name: push_box_custom
   Display Name: Push Box Custom
   Device: omx
   Triggers: 박스 치워줘, 박스 밀어, ...
   Steps: 4 step(s)
     [1] move_l → move to (0.18, 0.1, 0.18) in 0.5s
     [2] gripper → close
     [3] move_l → move to (0.24, 0.1, 0.18) in 0.5s
     [4] gripper → open
```

### 3단계: 채팅 모드로 테스트 (음성 없이)

```bash
# 채팅 모드 시작
./reachy-robotis chat

# 터미널에서 입력
>> list                          # 모든 task 보기
>> describe push_box_custom      # task 상세 정보
>> 박스 치워줘                   # trigger phrase로 실행
>> push_box_custom               # task 이름으로 실행  
>> status                        # 마지막 실행 결과 확인
>> exit                          # 종료
```

**채팅 모드 명령:**
| 명령 | 설명 |
|------|------|
| `list` | 모든 task 나열 |
| `describe <name>` | task 상세 정보 |
| `status` | 마지막 실행 결과 |
| `help` | 명령 도움말 |
| `exit` | 채팅 모드 종료 |

### 4단계: 앱 실행

#### 옵션 A: 웹 인터페이스 (추천)
```bash
./reachy-robotis --gradio
# http://localhost:7860/ 에서 접속 가능
# - 채팅/음성 인터페이스
# - ROBOTIS 제어판 (/robotis)
```

#### 옵션 B: 헤드리스 모드 (API만)
```bash
./reachy-robotis
# FastAPI 서버만 실행 (포트 8000)
```

---

## 🔌 로봇 연결/해제

### 웹 UI에서
1. ROBOTIS 제어판 열기
2. "Connect" 버튼 클릭 (🟢 Connected 표시)
3. Task 실행
4. "Disconnect" 버튼 클릭 (🔴 Disconnected, 모터 자동 해제)

### API로 제어
```bash
# 로봇 연결
curl -X POST http://localhost:8000/robotis/connect

# 로봇 해제 (안전한 종료)
curl -X POST http://localhost:8000/robotis/disconnect

# 연결 상태 확인
curl http://localhost:8000/robotis/connection/status
```

### Python 코드에서
```python
from reachy_robotis.robotis_interface.core.service import get_robotis_executor
import asyncio

executor = get_robotis_executor()
loop = asyncio.new_event_loop()

# 연결
result = loop.run_until_complete(executor.connect())
print(result.message)  # "로봇이 연결되었습니다..."

# 해제
result = loop.run_until_complete(executor.disconnect())
print(result.message)  # "로봇이 안전하게 종료되었습니다..."
```

---

## 🛑 안전한 종료

### 채팅 모드에서
```
>> exit
```

### 앱 실행 중
```
Ctrl+C
```

**자동으로 실행되는 작업:**
1. ✅ 모든 진행 중인 동작 중지
2. ✅ 모든 모터 안전하게 해제
3. ✅ 로봇 daemon과 연결 해제
4. ✅ 모든 리소스 정리

---

## 📋 Task 생성 및 관리

### 새로운 Task 만들기

`tasks/omx_tasks.yaml` 또는 `tasks/demo_flow.yaml` 편집:

```yaml
{
  "tasks": [
    {
      "name": "my_new_task",
      "display_name": "My Custom Task",
      "triggers": ["custom command", "다른 명령어"],
      "device": "omx",
      "steps": [
        {"type": "move_l", "params": {"x": 0.2, "y": 0.1, "z": 0.15, "duration": 1.0}},
        {"type": "gripper", "params": {"command": "close"}},
        {"type": "wait", "params": {"duration": 0.5}},
        {"type": "gripper", "params": {"command": "open"}},
        {"type": "say", "params": {"text": "작업 완료!"}}
      ]
    }
  ]
}
```

### 생성 후 검증
```bash
./reachy-robotis list-tasks
./reachy-robotis describe-task my_new_task
./reachy-robotis test-task my_new_task
```

---

## 🎮 Step 타입 가이드

| Step | 파라미터 | 예시 |
|------|---------|------|
| **move_l** | x, y, z, duration(optional) | `{"x": 0.2, "y": 0.1, "z": 0.15, "duration": 1.0}` |
| **gripper** | command: "open" \| "close" | `{"command": "close"}` |
| **wait** | duration (초) | `{"duration": 1.0}` |
| **say** | text | `{"text": "안녕하세요"}` |

---

## 💡 Workflow 예시

### 시나리오 1: Task 검증 (음성 없이)

```bash
# 1. 터미널 1: Daemon 시작
reachy-mini-daemon --sim

# 2. 터미널 2: 새로운 task 생성
# tasks/omx_tasks.yaml 편집

# 3. 검증
./reachy-robotis list-tasks
./reachy-robotis describe-task my_task
./reachy-robotis test-task my_task

# 4. 채팅으로 테스트
./reachy-robotis chat
>> my_task
>> status
>> exit
```

### 시나리오 2: 실제 로봇에서 task 실행

```bash
# 1. Daemon 시작 (실제 로봇 연결)
reachy-mini-daemon

# 2. 앱 시작
./reachy-robotis --gradio

# 3. 웹 브라우저에서
# - ROBOTIS 제어판에서 Connect 클릭
# - Task 실행
# - Disconnect 클릭 (모터 해제)

# 또는 채팅으로
./reachy-robotis chat
>> 박스 치워줘
>> status
>> exit
```

---

## 🐛 문제 해결

### 문제: "Connection timeout" 에러
```bash
# 원인: Daemon이 실행 중이지 않음
# 해결:
reachy-mini-daemon --sim  # 다른 터미널에서
```

### 문제: Task가 실행되지 않음
```bash
# 원인: Task가 등록되지 않았음
# 확인:
./reachy-robotis describe-task <name>

# 문제가 있다면 파일 재확인
cat tasks/omx_tasks.yaml
```

### 문제: 로봇이 계속 움직임
```bash
# 원인: Disconnect 하지 않음
# 해결:
curl -X POST http://localhost:8000/robotis/disconnect
```

---

## 📚 추가 정보

- **TASKS.md** - Task 정의 상세 가이드
- **README.md** - 전체 프로젝트 문서
- **config/robotis_devices.yaml** - 디바이스 설정

---

## ✅ 체크리스트

- [ ] Daemon 실행 중
- [ ] `./reachy-robotis list-tasks` 작동 확인
- [ ] 새로운 task 추가
- [ ] `./reachy-robotis chat` 으로 테스트
- [ ] 앱 시작 (`./reachy-robotis --gradio`)
- [ ] Connect/Disconnect 작동 확인
- [ ] Ctrl+C로 안전하게 종료

---

완료! 🎉 이제 안전하고 명확한 방식으로 로봇을 제어할 수 있습니다.
