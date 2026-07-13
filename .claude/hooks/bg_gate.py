#!/usr/bin/env python3
"""bg_gate.py — 백그라운드 실행 차단 게이트 (PreToolUse · Bash · 실행 계약 7 · 운영자 260713 개정).

§백그라운드: 백그라운드는 운영자가 명시로 시킬 때만 — 자발 금지. Bash `run_in_background=true`는 기계 차단(deny).
- 구 `ask` 팝업 승인제 폐지: 10세션 병행에서 팝업은 놓치면 세션 정지 = 드래프트 방치 원인(운영자 실증).
- 백그라운드 아님·Bash 아님·입력 파싱 실패 = 무의견(출력 없이 종료) → 기존 권한 흐름 그대로(오차단 0).
- 롤백 = "deny"를 "ask"로 원복(1줄).
등재 = `.claude/settings.json` hooks.PreToolUse(matcher "Bash").
"""
import json
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") != "Bash":
        return
    tool_input = data.get("tool_input") or {}
    if not tool_input.get("run_in_background"):
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "§백그라운드(실행 계약 7) — 자발 백그라운드 금지. 포그라운드로 실행하거나(장시간 = timeout 상향), 진짜 상주가 필요하면 {무엇을·왜} 1줄 제안만 남기고 계속 진행하라(운영자 명시 지시가 오면 그때 실행). 장기 파이프라인은 GitHub Actions 경로가 정본.",
        }
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
