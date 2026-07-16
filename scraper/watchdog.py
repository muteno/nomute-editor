#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""파이프라인 무인 워치독 v1 (운영자 260713 "신설 ㄱ" — 분신술 평의회6·9 P1 봉합)

왜: 감시 지표(daily_health)는 운영자가 손수 돌릴 때만 보였다 — 수집 정지(외부 cron-job.org SPOF)·
판정 backlog·SNS 트렌드 stale·원장 파손을 "아무도 모르는 구간"이 구조적으로 열려 있었다(실측:
미판정 최근 40%). 이 스크립트가 4지표를 기계 점검해 임계 초과만 웹푸시로 알린다.

지표 5종(전부 읽기 전용 · LLM 0콜 · 과금 0):
  ① 수집 신선도 — candidates.json 최신 last_seen 나이 > WD_FRESH_MIN(기본 90분 = 15분 주기 6연속 실패)
  ② 판정 backlog — gate/breaking --count 합 > WD_BACKLOG(기본 250 · SSOT 재사용 = 자체 카운트 로직 0)
  ③ SNS stale — sns_trends.json updated 나이 > WD_SNS_MIN(기본 90분 = 30분 주기 3연속 실패)
     (+소스별 health.last_ok 24h+ 소스는 로그만 — 경보는 전체 파일 stale 한정 = 알림 피로 방지)
  ④ 원장 파손 — push/sent.json·autopick.json·subscriptions.json 존재하는데 JSON 파싱 실패
     (파손 = dedup 전멸·예산 재개방 계열 무음 리셋 위험[평의회9])
  ⑤ 채널 브리프 정체 — chan_brief.json updated 나이 > WD_BRIEF_MIN(기본 2160분=36h · 일 1회 06:25 크론
     1회 결번 + 12h 여유 · 운영자 260717 "감시 ㄱ" — 브리프 스텝 하드킬 3연속·이틀 정지를 눈으로만
     발견한 사고 봉합. cancelled 런은 실패 알림조차 안 남는 사각 = 산출물 나이로 감지가 정공)
  ⑥ UI 스모크 실패/정체 — scraper/obs/smoke_last.json(smoke-nightly.yml 관측 산출물)의 rc≠0 = 즉시,
     updated 나이 > WD_SMOKE_MIN(기본 1560분=26h · 일 1회 03:30 크론 1결번+2h 여유) = 정체 경보
     (운영자 260717 Q07 "ㄱㄱ" — 상비 스모크 4종은 세션이 손으로 돌릴 때만 살아있던 사각의 봉합.
      브리프 ⑤와 동일 정공법 = 산출물 나이·결과 감지)

알림: WATCHDOG_NOTIFY=1 일 때만 push_send.py --notify 재사용(중복 구현 0 · §📰-e 카나리아 —
  워크플로 schedule 기본 '0' = 관측/로그만 · dispatch 실측 후 승격). 지표별 쿨다운
  WD_COOLDOWN_MIN(기본 360분) = scraper/obs/watchdog_state.json 원장(원자 쓰기)으로 스팸 억제.
불변: 큐레이션 신호·임계·랭킹·판정 0 접촉(§1 보수성) · KST(§📐) · fail-soft(지표 하나 파손이
  다른 지표 점검을 못 죽임) · daily_health(수동 정밀)와 별개 축 = 대체 아님.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CAND = os.path.join(ROOT, "viewer", "candidates.json")
SNS = os.path.join(ROOT, "viewer", "sns_trends.json")
BRIEF = os.path.join(ROOT, "viewer", "chan_brief.json")
STATE = os.path.join(ROOT, "scraper", "obs", "watchdog_state.json")
SUBS_LEDGER = os.path.join(ROOT, "push", "subscriptions.json")   # 발송 사전 체크용(인덱스 의존 금지)
LEDGERS = [os.path.join(ROOT, "push", p) for p in ("sent.json", "autopick.json", "subscriptions.json")]

FRESH_MIN = float(os.environ.get("WD_FRESH_MIN", "120"))   # 90→120(승격 시 상향 · 실측 260713: 최근 7일 최대 무신규 갭 75분[심야]·90분 초과 0회 — 심야 소강 오탐 마진 확보 = 경고 신뢰 우선·감지 지연 +30분 수용)
BACKLOG = int(os.environ.get("WD_BACKLOG", "250"))
SNS_MIN = float(os.environ.get("WD_SNS_MIN", "90"))
BRIEF_MIN = float(os.environ.get("WD_BRIEF_MIN", "2160"))   # 36h = 일 1회(06:25 크론) 1회 결번 + 12h 여유 — 일 주기 지표라 분 단위 민감도 불요
SMOKE = os.path.join(ROOT, "scraper", "obs", "smoke_last.json")
SMOKE_MIN = float(os.environ.get("WD_SMOKE_MIN", "1560"))   # 26h = 일 1회(03:30 크론) 1결번 + 2h 여유(⑤ 산정 문법 계승)
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
            if out.returncode != 0:   # judge 크래시를 "0 = 정상"으로 위장하던 구멍 봉합(fable검5 R1) — 스킵+경고
                parts.append(f"{name.split('_')[0]} ?")
                print(f"::warning::watchdog {name} --count rc={out.returncode} — 카운트 스킵(judge 레인 자체 점검 필요)")
                continue
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


def check_brief():
    """⑤ 채널 브리프 정체 — 산출물(chan_brief.json) 나이로 감지(260717 사고: 브리프 스텝이 잡 timeout
    하드킬(cancelled)로 3연속 죽으면 실패 알림도 fail-soft 로그도 안 남아 이틀 정지를 운영자 눈이 발견).
    정체 원인은 두 갈래 다 커버: 생성 레인 사망 or 인스타 수집 정지(입력 동일 = 스킵이 계속) — 둘 다 점검 대상."""
    try:
        d = json.load(open(BRIEF, encoding="utf-8"))
        age = _age_min(d.get("updated"))
        if age is None or age > BRIEF_MIN:
            return (f"채널 브리프 정체 {('%.0f시간' % (age / 60)) if age is not None else '나이 불명'}"
                    f"(임계 {BRIEF_MIN / 60:.0f}h) — insta-fetch 브리프 스텝(cancelled/타임아웃)·인스타 수집 확인")
    except FileNotFoundError:
        return None   # 파일 자체가 없는 초기 상태 = 경보 아님(check_sns 관용구)
    except Exception as e:  # noqa: BLE001
        return f"chan_brief.json 파싱 실패({type(e).__name__})"
    return None


def check_smoke():
    """⑥ UI 스모크 실패/정체 — smoke-nightly가 커밋한 관측 파일로 감지(⑤ check_brief 관용구 미러).
    rc≠0 = 스모크 FAIL(드리프트·회귀 검출) 즉시 경보 · 나이 초과 = 나이틀리 레인 자체 사망(cancelled 사각) 경보."""
    try:
        d = json.load(open(SMOKE, encoding="utf-8"))
        age = _age_min(d.get("updated"))
        if d.get("rc") not in (0, "0"):
            return f"UI 스모크 FAIL(rc={d.get('rc')}) — {str(d.get('fail') or '')[:160]} (smoke-nightly 런 로그 확인)"
        if age is None or age > SMOKE_MIN:
            return (f"UI 스모크 정체 {('%.0f시간' % (age / 60)) if age is not None else '나이 불명'}"
                    f"(임계 {SMOKE_MIN / 60:.0f}h) — smoke-nightly.yml 레인(cancelled/타임아웃) 확인")
    except FileNotFoundError:
        return None   # 초기 상태(첫 나이틀리 전) = 경보 아님(⑤ 관용구)
    except Exception as e:  # noqa: BLE001
        return f"smoke_last.json 파싱 실패({type(e).__name__})"
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
    checks = {"collect": check_collect, "backlog": check_backlog, "sns": check_sns, "ledger": check_ledgers,
              "brief": check_brief, "smoke": check_smoke}
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
    # SNS stale 메시지함 점등/해제(운영자 260714 승인 한 수) — 웹푸시(쿨다운 6h)와 별개로 뷰어 프로필에
    #   상시 상태 표시: stale이면 단일 슬롯(wd-sns) set(재실행 = 덮어쓰기 = 스팸 0) · 정상 복귀면 clear.
    #   fail-soft(메시지함 실패가 점검·발송을 못 죽임) · 커밋은 워크플로 원장 스텝이 messages/ 동반 add.
    if NOTIFY:
        try:
            mp = os.path.join(ROOT, "shared", "msg.py")
            if alerts.get("sns"):
                subprocess.run([sys.executable, mp, "set", "wd-sns", alerts["sns"], "warn"], timeout=30)
            else:
                subprocess.run([sys.executable, mp, "clear", "wd-sns"], timeout=30)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::watchdog 메시지함 점등 실패(무시): {e}")
    if not alerts:
        print("워치독: 전 지표 정상")
        return
    if not NOTIFY:
        print(f"워치독: 이상 {len(alerts)}건 — 관측 모드(WATCHDOG_NOTIFY≠1)라 알림 미발송(§📰-e 카나리아)")
        return
    st = _load_state()
    now = datetime.now(KST)

    def _cool_age(k):
        a = _age_min(st.get(k, ""))
        return a if a is not None else 1e9   # 0.0분도 유효값(or-falsy 함정 금지 — fable검5 R4·check_collect과 동일 원칙)

    due = {k: m for k, m in alerts.items() if _cool_age(k) > COOLDOWN_MIN}
    if not due:
        print(f"워치독: 이상 {len(alerts)}건 전부 쿨다운({COOLDOWN_MIN:.0f}분) 내 — 재알림 억제")
        return
    # 발송 가능 사전 체크(fable검5 R2) — push_send는 구독자 0·VAPID 없음도 rc=0 "생략"이라,
    # 미발송인데 쿨다운 도장을 찍고 6h 억제하던 semantics 오류 봉합: 불가 상태 = 도장 없이 로그만.
    try:
        _subs_ok = bool(json.load(open(SUBS_LEDGER, encoding="utf-8")))
    except Exception:  # noqa: BLE001
        _subs_ok = False
    if not _subs_ok or not (os.environ.get("VAPID_PRIVATE_KEY") or "").strip():
        print(f"워치독: 이상 {len(due)}건 — 구독자/VAPID 부재로 발송 불가(도장 미기록·다음 런 재시도)")
        return
    body = " / ".join(due.values())[:110]
    try:
        out = subprocess.run([sys.executable, os.path.join(ROOT, ".github", "scripts", "push_send.py"),
                              "--notify", "🩺 파이프라인 이상", body, "--tag", "nomute-watchdog", "--url", "/"],
                             capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:   # fable검5 R5 — 타임아웃 트레이스백으로 잡 red 방지(도장 미기록 = 안전측)
        print("::warning::watchdog 알림 발송 타임아웃(180s) — 도장 안 찍음(다음 런 재시도)")
        return
    m = re.search(r"발송: (\d+)/", out.stdout or "")   # push_send 최종 요약 줄 = 발송 성공 계약(≥1이라야 실발송)
    if out.returncode == 0 and m and int(m.group(1)) >= 1:
        for k in due:
            st[k] = now.isoformat(timespec="seconds")
        _save_state(st)
        print(f"워치독: 알림 발송 {len(due)}건 + 쿨다운 도장")
    else:
        print(f"::warning::watchdog 알림 미발송(rc={out.returncode} · {(out.stdout or '').strip()[-80:]}) — 도장 안 찍음(다음 런 재시도)")


if __name__ == "__main__":
    main()
