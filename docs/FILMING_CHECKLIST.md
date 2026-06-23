# Filming Checklist

- Open `/robotis` before filming and confirm all devices show a status card.
- Keep OMY and AI Worker in `dry_run: true` unless the hardware is ready.
- Confirm `"박스 치워줘"` resolves to `task:push_box_custom`.
- Confirm `"OMY 켜줘"` resolves to `command:omy_leader_follower`.
- Confirm `"AI Worker로 일 시키자"` resolves to `command:ai_worker_bringup`.
- Capture one clear shot of the Action Catalog.
- Capture one clear shot of the OMX Task Builder saving a trigger phrase.
- Have `/robotis/stop` ready as Soft Stop.
- If hardware is unavailable, use `mock_full_demo_flow` as the fallback.

