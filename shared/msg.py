#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# viewer/messages.json 에 '키(id) 있는' 운영자 메시지를 upsert/clear.
#   프론트(viewer/index.html loadMessages)가 매 로드 시 읽어 프로필 점등(hasmsg)+배지+msgpop 표시.
#   분석 도구(claude) 시스템성 실패(인증·쿼터)를 사용자에게 '작동할 때까지' 알리는 채널.
# 사용: python3 shared/msg.py set <id> "<text>"   /   python3 shared/msg.py clear <id>
#   같은 id 는 항상 1건만(중복 누적 방지) — set=교체삽입(최신 위로), clear=제거.
import json
import os
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "viewer", "messages.json")
TTL_MS = 24 * 3600 * 1000   # 메시지 자동 만료 = 기록(t) 기준 24h(운영자 260623). 'level' 알림은 t 도장 → 만료. 레거시(t 없음)는 보존.


def now_ms():
    return int(datetime.now(KST).timestamp() * 1000)


def prune(d):
    # 24h 지난 항목 자동 삭제(쓸 때마다 = msg.py 는 분석 런마다 호출되니 파일이 알아서 정리됨). t 없는 레거시는 유지.
    cut = now_ms() - TTL_MS
    return [m for m in d if not isinstance(m, dict) or m.get("t") is None or m.get("t", 0) >= cut]


def load():
    try:
        d = json.load(open(P, encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def save(d):
    os.makedirs(os.path.dirname(P), exist_ok=True)
    with open(P, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)


def main():
    if len(sys.argv) < 3:
        print("usage: msg.py set|clear <id> [text]", file=sys.stderr)
        return 1
    cmd, mid = sys.argv[1], sys.argv[2]
    before = load()
    # 같은 id 제거(dedupe) — clear 면 이걸로 끝, set 이면 새로 맨 위 삽입.
    d = [m for m in before if not (isinstance(m, dict) and m.get("id") == mid)]
    if cmd == "set":
        text = sys.argv[3] if len(sys.argv) > 3 else ""
        level = sys.argv[4] if len(sys.argv) > 4 else ""   # 선택: "warn"=노란 점등·노란 제목(수집 실패 등) / 빈값=기본
        m = {"id": mid, "text": text, "ts": datetime.now(KST).strftime("%m/%d %H:%M"), "t": now_ms()}
        if level:
            m["level"] = level
        d.insert(0, m)
    elif cmd == "clear":
        pass  # 위에서 같은 id 제거 완료 — 아래 prune + 변경시에만 저장
    else:
        print(f"unknown cmd: {cmd}", file=sys.stderr)
        return 1
    d = prune(d)   # 24h 만료 자동 삭제(쓸 때마다 정리)
    if cmd == "clear" and d == before:
        return 0   # 제거할 것도 만료될 것도 없음 — 파일 무변경(불필요 커밋 방지)
    save(d)
    print(f"messages: {cmd} {mid} → {len(d)}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
