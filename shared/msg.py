#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 운영자/시스템 알림을 messages/<id>.json (git 추적 = 빌드 '입력')에 upsert/clear.
#   build-viewer.mjs 가 messages/*.{md,json} → viewer/messages.json(빌드 '산출물')로 합쳐
#   빌드하며 t·level 필드를 보존한다. 프론트(viewer/index.html loadMessages)가 그 messages.json 을
#   매 로드 시 읽어 프로필 점등(hasmsg/haswarn)+배지+msgpop 표시.
#   분석 도구(claude) 시스템성 실패(인증·쿼터)를 사용자에게 '작동할 때까지' 알리는 채널.
#
#   ⚠️ viewer/messages.json 에 '직접' 쓰면 안 됨(260711 회귀 복구): 그 파일은 .gitignore 된 빌드
#      산출물이라 `git add viewer/messages.json` 이 조용히 무시(=커밋·배포 안 됨) + 다음 배포 빌드가
#      messages/*.md 에서 재생성하며 덮어씀. 그래서 알림이 메시지함에 '안 들어오던' 버그였다.
#      → 입력 디렉터리(messages/)에 파일로 써서 워크플로 `git add -A messages` 로 커밋 → 배포 빌드가
#        viewer/messages.json 으로 합성 → 반영. (수동 messages/*.md 와 같은 정식 경로로 통일.)
#
# 사용: python3 shared/msg.py set <id> "<text>" [level]   /   python3 shared/msg.py clear <id>
#   같은 id = 파일 1개(messages/<id>.json) = 자연 dedupe — set=파일 덮어쓰기, clear=파일 삭제.
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
MSG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "messages")
TTL_MS = 24 * 3600 * 1000   # 메시지 자동 만료 = 기록(t) 기준 24h(운영자 260623). msg.py 가 t 도장한 항목만
#                             만료 대상 — 수동 md·t 없는 json(레거시)은 보존(사용자가 직접 지울 때까지).


def now_ms():
    return int(datetime.now(KST).timestamp() * 1000)


def path_for(mid):
    # id → 안전한 파일명(경로 주입·구분자 차단). 원본 id 는 파일 '내용'(id 필드)에 보존.
    # ⚠️ 이 sanitize 는 비단사(non-injective) — 서로 다른 id 가 같은 파일명으로 접힐 수 있다(예: `a/b`·`a_b`).
    #    현 호출자 id 는 전부 FS-safe 슬러그(`fail-<서버생성 stem>`)라 충돌 무발생. 훗날 id 를 '사용자 자유입력'으로
    #    넓히면 그때 해시 접미로 고유화할 것(안 그러면 다른 id 가 남의 메시지 파일을 덮어쓰기/삭제할 수 있음).
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", mid) or "msg"
    return os.path.join(MSG_DIR, safe + ".json")


def prune():
    # msg.py 가 쓴 단일객체(+t) json 중 24h 지난 것 삭제(쓸 때마다 = msg.py 는 분석 런마다 호출되니
    # 알아서 정리됨). 수동 md·배열 json·t 없는 json 은 손대지 않음(레거시·운영자 파일 보존).
    cut = now_ms() - TTL_MS
    try:
        names = os.listdir(MSG_DIR)
    except FileNotFoundError:
        return
    for n in names:
        if not n.endswith(".json"):
            continue
        p = os.path.join(MSG_DIR, n)
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and isinstance(d.get("t"), (int, float)) and d["t"] < cut:
            try:
                os.remove(p)
            except OSError:
                pass


def main():
    if len(sys.argv) < 3:
        print("usage: msg.py set|clear <id> [text] [level]", file=sys.stderr)
        return 1
    cmd, mid = sys.argv[1], sys.argv[2]
    os.makedirs(MSG_DIR, exist_ok=True)
    p = path_for(mid)
    if cmd == "set":
        text = sys.argv[3] if len(sys.argv) > 3 else ""
        level = sys.argv[4] if len(sys.argv) > 4 else ""   # 선택: "warn"=노란 점등·노란 제목(수집 실패 등) / 빈값=기본
        m = {"id": mid, "text": text, "ts": datetime.now(KST).strftime("%m/%d %H:%M"), "t": now_ms()}
        if level:
            m["level"] = level
        with open(p, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False)
        prune()   # 24h 만료 자동 삭제(쓸 때마다 정리)
        print(f"messages: set {mid} → {os.path.relpath(p)}")
        return 0
    elif cmd == "clear":
        existed = os.path.exists(p)
        if existed:
            try:
                os.remove(p)
            except OSError:
                pass
        prune()
        print(f"messages: clear {mid} → {'removed' if existed else 'absent'}")
        return 0
    else:
        print(f"unknown cmd: {cmd}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
