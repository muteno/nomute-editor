#!/usr/bin/env python3
"""trigger_gate.py — 자가 체크인·예약 실행 차단 게이트 (PreToolUse · MCP 스케줄 도구 · [8] 기계화 · 운영자 260725 Q521).

[8]: 지시 없는 루틴·예약·크론·'1시간 뒤 확인' 자가 체크인 금지 — 실측 = 5일간 트리거 31발 누적 = 토큰 유출.
승인은 채팅 대화 문답만 인정(AskUserQuestion 팝업 수락 ≠ 승인)이라 `ask` 팝업제는 이 축에서 애초에 무효 → deny.
- bg_gate.py(백그라운드 Bash 차단)와 같은 문법·같은 판정. 그쪽이 Bash 축, 이쪽이 스케줄 축이다.
- 대상 아님(다른 도구·입력 파싱 실패) = 무의견(출력 없이 종료) → 기존 권한 흐름 그대로(오차단 0).
- 운영자가 대화로 승인한 경우 = 이 훅을 settings.json에서 잠시 떼고 실행(bg_gate와 동일 운용).
등재 = `.claude/settings.json` hooks.PreToolUse(matcher = 아래 _BLOCKED와 같은 정규식).
"""
import json
import re
import sys

# 스케줄·예약·자가 체크인 계열만. 서버 접두어(Claude_Code_Remote/claude-code-remote)는 표기 흔들림이 있어 느슨하게.
_BLOCKED = re.compile(
    r"(send_later|create_trigger|fire_trigger|CronCreate|ScheduleWakeup)$",
    re.I,
)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    name = data.get("tool_name") or ""
    if not _BLOCKED.search(name):
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "[8] 자가 체크인·예약 금지 — 지시 없는 스케줄은 자리를 비운 사이에 토큰을 태운다"
                "(실측 260717: 5일 31발). PR 사후 감시 기본값 = 이벤트 웹훅 구독까지만(스케줄 0). "
                "지금 할 수 있는 일이면 지금 하고, 정말 예약이 필요하면 {무엇을·왜·언제 끝나는지} 1줄로 "
                "채팅에 제안만 남기고 계속 진행하라 — 운영자가 대화로 승인하면 그때 실행한다."
            ),
        }
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
