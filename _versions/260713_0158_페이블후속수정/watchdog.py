#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""파이프라인 무인 워치독 v1 (운영자 260713 "신설 ㄱ" — 분신술 평의회6·9 P1 봉합)

왜: 감시 지표(daily_health)는 운영자가 손수 돌릴 때만 보였다 — 수집 정지(외부 cron-job.org SPOF)·
판정 backlog·SNS 트렌드 stale·원장 파손을 "아무도 모르는 구간"이 구조적으로 열려 있었다(실측:
미판정 최근 40%). 이 스크립트가 4지표를 기계 점검해 임계 초과만 웹푸시로 알린다.

지표 4종(전부 읽기 전용 · LLM 0콜 · 과금 0):
  ① 수집 신선도 — candidates.json 최신 last_seen 나이 > WD_FRESH_MIN(기본 90분 = 15분 주기 6연속 실패)
  ② 판정 backlog — gate/breaking --count 합 > WD_BACKLOG(기본 250 · SSOT 재사용 = 자체 카운트 로직 0)
  ③ SNS stale — sns_trends.json updated 나이 > WD_SNS_MIN(기본 90분 = 30분 주기 3연속 실패)
     (+소스별 health.last_ok 24h+ 소스는 로그만 — 경보는 전체 파일 stale 한정 = 알림 피로 방지)
  ④ 원장 파손 — push/sent.json·autopick.json·subscriptions.json 존재하는데 JSON 파싱 실패
     (파손 = dedup 전멸·예산 재개방 계열 무음 리셋 위험[평의회9])

알림: WATCHDOG_NOTIFY=1 일 때만 push_send.py --notify 재사용(중복 구현 0 · §📰-e 카나리아 —
  워크플로 schedule 기본 '0' = 관측/로그만 · dispatch 실측 후 승격). 지표별 쿨다운
  WD_COOLDOWN_MIN(기본 360분) = scraper/obs/watchdog_state.json 원장(원자 쓰기)으로 스팸 억제.
불변: 큐레이션 신호·임계·랭킹·판정 0 접촉(§1 보수성) · KST(§📐) · fail-soft(지표 하나 파손이
  다른 지표 점검을 못 죽임) · daily_health(수동 정밀)와 별개 축 = 대체 아님.
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CAND = os.path.join(ROOT, "viewer", "candidates.json")
SNS = os.path.join(ROOT, "viewer", "sns_trends.json")
STATE = os.path.join(ROOT, "scraper", "obs", "watchdog_state.json")
LEDGERS = [os.path.join(ROOT, "push", p) for p in ("sent.json", "autopick.json", "subscriptions.json")]

FRESH_MIN = float(os.environ.get("WD_FRESH_MIN", "90"))
BACKLOG = int(os.environ.get("WD_BACKLOG", "250"))
SNS_MIN = float(os.environ.get("WD_SNS_MIN", "90"))
COOLDOWN_MIN = float(os.environ.get("WD_COOLDOWN_MIN", "360"))
NOTIFY = (os.environ.get("WATCHDOG_NOTIFY") or "").strip() == "1"


def _age_min(iso):
    """ISO 문자열 → 현재 KST 대비 나이(분). 파싱 실패 = None(호출부가 보수 처리)."""
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=KST)
        return (datetime.now(KST) - t).total_seconds() / 60
    except Exception:  # noqa: BLE001
        return None


def check_collect():
    """① 수집 신선도 — 파일 없음/파싱 실패도 경보(수집이 죽었거나 파손 = 둘 다 봐야 할 상태)."""
    try:
        cands = json.load(open(CAND, encoding="utf-8"))
        ages = [a for c in cands if (a := _age_min(c.get("last_seen") or c.get("first_seen"))) is not None]
        newest = min(ages) if ages else 1e9   # 최신 항목 나이 = min (0분도 유효값 — falsy 함정 금지)
        if newest > FRESH_MIN:
            return f"수집 정체 {newest:.0f}분(임계 {FRESH_MIN:.0f}) — cron-job.org 타이머·scrape 레인 확인"
    except Exception as e:  # noqa: BLE001
        return f"candidates.json 읽기 실패({type(e).__name__}) — 수집 레인 점검"
    return None


def check_backlog():
    """② 판정 backlog — 카운트 SSOT = judge 스크립트 --count(자체 재구현 금지·§📰-f 정신)."""
    total, parts = 0, []
    for name in ("breaking_judge.py", "gate_judge.py"):
        try:
            out = subprocess.run([sys.executable, os.path.join(ROOT, ".github", "scripts", name), "--count"],
                                 capture_output=True, text=True, timeout=120,
                                 env={**os.environ, "TRANS_ON": os.environ.get("TRANS_ON", "1")})
            n = int((out.stdout or "0").strip().splitlines()[-1])
            total += n
            parts.append(f"{name.split('_')[0]} {n}")
        except Exception:  # noqa: BLE001 — 카운트 실패 = 이 지표만 건너뜀(fail-soft)
            parts.append(f"{name.split('_')[0]} ?")
    if total > BACKLOG:
        return f"미판정 backlog {total}건({' · '.join(parts)} · 임계 {BACKLOG}) — judge 레인 적체"
    return None


def check_sns():
    """③ SNS stale — 전체 파일 나이만 경보 · 소스별 last_ok 노후는 로그(피로 방지)."""
    try:
        d = json.load(open(SNS, encoding="utf-8"))
        age = _age_min(d.get("updated"))
        for k, h in (d.get("health") or {}).items():   # 소스별 관측(260713 신설 필드 · 경보 아님)
            if not h.get("off") and h.get("last_ok"):
                la = _age_min(h["last_ok"])
                if la is not None and la > 1440:
                    print(f"  [관측] SNS 소스 '{k}' 마지막 성공 {la / 60:.0f}시간 전")
        if age is None or age > SNS_MIN:
            return f"SNS 트렌드 정체 {('%.0f분' % age) if age is not None else '나이 불명'}(임계 {SNS_MIN:.0f}) — sns-trends 레인 확인"
    except FileNotFoundError:
        return None   # 파일 자체가 없는 초기 상태 = 경보 아님
    except Exception as e:  # noqa: BLE001
        return f"sns_trends.json 파싱 실패({type(e).__name__})"
    return None


def check_ledgers():
    """④ 원장 파손 — 존재하는데 JSON 깨짐 = 무음 리셋(dedup 전멸·예산 재개방) 위험 신호."""
    bad = []
    for p in LEDGERS:
        if not os.path.exists(p):
            continue
        try:
            json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            bad.append(os.path.basename(p))
    if bad:
        return f"푸시 원장 파손: {', '.join(bad)} — 중복 발송·재과금 위험(복구 필요)"
    return None


def _load_state():
    try:
        return json.load(open(STATE, encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}


def _save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(STATE), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)   # 원자 쓰기(부분쓰기 파손 방지 — 평의회9 원장 원칙 자기적용)


def main():
    checks = {"collect": check_collect, "backlog": check_backlog, "sns": check_sns, "ledger": check_ledgers}
    alerts = {}
    for key, fn in checks.items():
        try:
            msg = fn()
        except Exception as e:  # noqa: BLE001 — 지표 하나가 전체를 못 죽임
            msg = None
            print(f"::warning::watchdog {key} 점검 자체 실패(스킵): {e}")
        if msg:
            alerts[key] = msg
            print(f"⚠ [{key}] {msg}")
        else:
            print(f"✅ [{key}] 정상")
    if not alerts:
        print("워치독: 전 지표 정상")
        return
    if not NOTIFY:
        print(f"워치독: 이상 {len(alerts)}건 — 관측 모드(WATCHDOG_NOTIFY≠1)라 알림 미발송(§📰-e 카나리아)")
        return
    st = _load_state()
    now = datetime.now(KST)
    due = {k: m for k, m in alerts.items()
           if (_age_min(st.get(k, "")) or 1e9) > COOLDOWN_MIN}
    if not due:
        print(f"워치독: 이상 {len(alerts)}건 전부 쿨다운({COOLDOWN_MIN:.0f}분) 내 — 재알림 억제")
        return
    body = " / ".join(due.values())[:110]
    rc = subprocess.run([sys.executable, os.path.join(ROOT, ".github", "scripts", "push_send.py"),
                         "--notify", "🩺 파이프라인 이상", body, "--tag", "nomute-watchdog", "--url", "/"],
                        timeout=180).returncode
    if rc == 0:
        for k in due:
            st[k] = now.isoformat(timespec="seconds")
        _save_state(st)
        print(f"워치독: 알림 발송 {len(due)}건 + 쿨다운 도장")
    else:
        print(f"::warning::watchdog 알림 발송 실패(rc={rc}) — 도장 안 찍음(다음 런 재시도)")


if __name__ == "__main__":
    main()
