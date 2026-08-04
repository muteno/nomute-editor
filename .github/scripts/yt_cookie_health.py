#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 유튜브 쿠키 생사 감시 — 「죽은 걸 운영자가 눌러봐야 아는」 축을 없앤다(운영자 260804 승인 "응 원장도 해주고").
#
# 왜: YT_T_COOKIES는 **수명이 유한하다**(유튜브가 열린 탭에서 쿠키를 수시 회전 · 실측 260804 = 03:14엔 인증
#   통과하던 쿠키가 06:36엔 사망). 그런데 죽어도 아무 신호가 없어서, 운영자가 유튜브를 받아보다 실패해야
#   비로소 알았다(= 필요한 순간에 못 쓴다). 정기로 재보고 죽으면 **미리** 알린다.
#
# 체인: watchdog 격 크론(yt-cookie-health.yml) → **이 스크립트** → ① whoami 실행(판정 정본 재사용 · 로직 복제 0)
#       → ② 원장 push/yt_cookie_health.json 누적 → ③ 연속 사망 시 shared/msg.py → 뷰어 알림메시지.
#
# 설계 원칙(전부 이 레포의 기존 사고에서 배운 것):
#  ① **판정 로직을 복제하지 않는다.** yt_cookie_whoami.py를 subprocess로 부르고 그 출력을 읽는다 —
#     두 벌이 되면 한쪽만 고쳐져 조용히 갈린다(brk_misfire → msg.py 호출 관례와 같은 축).
#  ② **알림 id는 회전한다**(`yt-cookie-dead-<연속회차>`). 고정 id면 뷰어 unread 판정이 id 축이라
#     메시지함을 **한 번 열면 영영 재점등이 안 된다**(brk_misfire 주석의 실측 교훈 그대로).
#  ③ **2회 연속부터 발화.** 1회성 네트워크 딸꾹질(홈 fetch 실패·일시 5xx)과 진짜 사망을 가른다
#     (insta 커버 결손 `none_streak` 2회 선례 동값). 12시간 주기 × 2 = 하루 안에 잡힌다.
#  ④ **살아나면 자동 해소**(clear + streak 0) — 사람이 알림을 지울 일이 없다.
#  ⑤ **fail-soft**: 어떤 예외도 rc=0. 감시기가 워크플로를 죽이면 원장이 못 쌓인다.
# 과금 0 — LLM 미사용. 원장 = 기계산출물(손편집 금지 · 값 변경 = 이 코드를 고쳐 재실행).
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent.parent
WHOAMI = ROOT / ".github" / "scripts" / "yt_cookie_whoami.py"
LEDGER = ROOT / "push" / "yt_cookie_health.json"   # 원장(기계산출물)
MSG_PY = ROOT / "shared" / "msg.py"
MSG_ID_BASE = "yt-cookie-dead"
DEAD_MIN = 2      # 이 횟수 연속 사망부터 발화(1회성 딸꾹질 제외)
KEEP = 90         # 원장 보존 회차(12시간 주기 = 약 45일)


def msg(*args):
    subprocess.run([sys.executable, str(MSG_PY)] + list(args), check=False)


def probe():
    """whoami 1회 실행 → (ok, why, acct). 판정 정본은 whoami 쪽 단독(여기선 읽기만)."""
    try:
        r = subprocess.run([sys.executable, str(WHOAMI)], capture_output=True, text=True,
                           timeout=180, env=dict(os.environ, REVEAL=""))
    except Exception as e:
        return None, f"감시기 실행 실패({type(e).__name__})", ""   # None = 판정 불가(연속 카운터 건드리지 않음)
    out = (r.stdout or "") + (r.stderr or "")
    acct = ""
    m = re.search(r"⑤ 계정: 채널명=(\S+) · 핸들=(\S+)", out)
    if m:
        acct = m.group(2)
    if r.returncode == 0:
        return True, "", acct
    # 실패 사유 = whoami가 이미 사람 말로 찍는다 → 첫 ::error:: 줄을 그대로 계승(문구 재창작 0)
    e = re.search(r"::error::(.+)", out)
    why = (e.group(1) if e else "쿠키 점검 실패").strip()
    # 사망 확정 = 쿠키 **자체**가 원인인 판정 4종(whoami의 ①②③④ bail 지점 그대로).
    #   ⚠ ①②를 뺐다가 로컬 시험에서 「시크릿 비어있음」이 '판정 불가'로 새는 걸 잡았다 —
    #     시크릿 공백·형식 깨짐은 네트워크 딸꾹질이 아니라 **가장 확실한 사망**이라 반드시 세야 한다.
    #   ⚠ 판정은 **why(= 그 실행이 실제로 멈춘 ::error:: 한 줄)만** 본다. out 전체를 보면 성공 구간의
    #     「① 시크릿: 있음」까지 걸려, ⑤ 파싱 실패(rc=2 = 진짜 '판정 불가')가 사망으로 오분류된다.
    for sig in ("① 시크릿:", "② 파싱:", "③ 진단:", "④ LOGGED_IN: false", "로그인 상태가 아님"):
        if sig in why:
            return False, why, acct
    return None, why, acct   # 그 밖(홈 fetch 실패·응답 구조 변경)만 '판정 불가' = 사망으로 안 센다(오경보 차단)


def load():
    try:
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("runs"), list):
            return d
    except Exception:
        pass
    return {"_meta": {"dead_streak": 0, "alert_id": "", "last_ok": "", "last_run": ""}, "runs": []}


def main():
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    ok, why, acct = probe()
    led = load()
    meta = led.setdefault("_meta", {})
    led["runs"].append({"t": now, "ok": ok, "why": why[:200], "acct": acct})
    led["runs"] = led["runs"][-KEEP:]
    meta["last_run"] = now

    if ok is True:
        meta["dead_streak"] = 0
        meta["last_ok"] = now
        if acct:
            meta["acct"] = acct
        if meta.get("alert_id"):
            msg("clear", meta["alert_id"])   # 살아나면 자동 해소(사람이 지울 일 0)
            meta["alert_id"] = ""
        print(f"[쿠키] 정상 · 계정={acct or '(미표기)'} · 연속사망 0")
    elif ok is False:
        meta["dead_streak"] = int(meta.get("dead_streak") or 0) + 1
        n = meta["dead_streak"]
        print(f"[쿠키] 사망 · 연속 {n}회 · {why[:80]}")
        if n >= DEAD_MIN:
            mid = f"{MSG_ID_BASE}-{n}"   # 건수 접미 회전(고정 id = 한 번 열면 영구 실명 · brk_misfire 교훈)
            prev = meta.get("alert_id")
            if prev and prev != mid:
                msg("clear", prev)
            body = (f"유튜브 받기용 쿠키가 죽었어요(연속 {n}회 · 마지막 정상 {meta.get('last_ok') or '기록 없음'}"
                    + (f" · 계정 {meta.get('acct')}" if meta.get("acct") else "") + ").\n"
                    f"사유: {why[:120]}\n"
                    "고치는 법(3동작): ① 시크릿 창에서 유튜브 로그인 → ② 주소창에 youtube.com/robots.txt 이동 후 "
                    "쿠키 내보내기(Get cookies.txt LOCALLY) → 창 닫기 → ③ GitHub Settings ▸ Secrets ▸ Actions 의 "
                    "YT_T_COOKIES 교체(youtube.com 줄만 · 48KB 상한).\n"
                    "확인: Actions ▸ yt-cookie-whoami ▸ Run workflow → 「④ LOGGED_IN: true」면 복구. "
                    "⚠ 로그인 창을 열어둔 채 내보내면 쿠키가 회전해 몇 시간 만에 또 죽어요(260804 실측).")
            msg("set", mid, body, "warn")
            meta["alert_id"] = mid
    else:
        print(f"[쿠키] 판정 불가(연속 카운터 유지) · {why[:80]}")   # 네트워크 딸꾹질 = 사망으로 안 센다

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, LEDGER)   # 원자적 교체(부분 기록 차단 · vidl_run result.json 관례)
    print(f"원장: {LEDGER.relative_to(ROOT)} · 회차 {len(led['runs'])}건")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:   # fail-soft — 감시기가 워크플로를 죽이면 원장이 못 쌓인다
        print(f"::warning::쿠키 감시 실패(비치명): {type(e).__name__} {str(e)[:120]}")
        sys.exit(0)
