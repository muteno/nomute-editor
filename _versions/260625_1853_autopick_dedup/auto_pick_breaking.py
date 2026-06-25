#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 긴급 grade≥3 자동 픽 — candidates.json 의 새 isBreaking(breaking·grade≥3·cross≥2·<4h) 사건을
# 자동으로 pending/ 적재(분석 입구) → news-analyze 발동(요약·카드 자동 생성). breaking-judge.yml 이 판정 직후 호출.
# ⚠️⚠️ 자동 과금 경로 — 픽 1건 = Opus 분석 1콜(구독 쿼터) + Gemini 썸네일 3장($). 보수적 다중 가드:
#   ① grade≥3 (대형·다수피해만 · 운영자 260622 — push 의 grade≥2 보다 엄격 = 자동픽 ⊆ push 의도)
#   ② cross≥2(다매체 검증) ③ first_seen·published *둘 다* <4h (운영자 260623 — first_seen=갓 감지 + 발행도 신선해야:
#      발행 16h stale 건이 방금 수집됐다고 자동분석 들어가던 것 차단 · published 없는 매체는 first_seen 만으로 폴백)
#   ④ 사건당 1회 영구 dedup(push/autopick.json — event_key/url **+ 제목해시** 다중키 = url 점프에도 안정 ·
#      실패해도 재픽 안 함 · push_send.dedup_keys 와 동일 키셋) ⑤ 런/일 상한
#   ⑥ pick_pending 의 load_active dedup(이미 처리중/완료면 스킵 = 수동픽과 충돌 0 · PICK_URL=c.url 로 수동픽과 동일 키).
# 픽 경로(pick_pending.py)를 그대로 재사용 — pending 작성·seen_urls 적재·dedup 단일 원천(DRY).
# 출력: stderr 요약 + stdout 마지막 줄 'PICKED=<n>'(워크플로가 커밋·분석발동 판단). 정본 = CLAUDE.md §🚨 + docs/curation-algorithm §8.
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "viewer" / "candidates.json"
LEDGER = ROOT / "push" / "autopick.json"   # 자동픽 원장 {key: iso_kst} — 사건당 다중키(대표+제목해시) 영구 dedup + 일 상한 카운트
PICK = ROOT / "scraper" / "pick_pending.py"
KST = dt.timezone(dt.timedelta(hours=9))

FAST_MAX_H = 4                                                        # 최신만(푸시·토스트와 동일 단일상수 정신)
MIN_GRADE = int(os.environ.get("AUTOPICK_MIN_GRADE", "3"))           # grade≥3 (운영자 260622 — 대형 긴급만)
MIN_CROSS = int(os.environ.get("AUTOPICK_MIN_CROSS", "2"))           # 다매체 검증(오발 가드 · push 정신)
MAX_PER_RUN = int(os.environ.get("AUTOPICK_MAX_PER_RUN", "2"))       # 런당 상한(버스트 캡)
MAX_PER_DAY = int(os.environ.get("AUTOPICK_MAX_PER_DAY", "8"))       # 일 상한(안전밸브 · KST 기준)
DRY = "--dry-run" in sys.argv


def jload(p, d):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def age_h(c):
    # ⚠️ 자동픽 창 = '우리가 방금 감지'(first_seen·KST) 기준. push_send 는 published 우선이나, published 는
    # syndication 지연으로 stale(실측: breaking 후보 43%가 도착 시점에 이미 published-age >4h) → 적시 긴급이
    # 자동분석서 누락. 자동픽 의도 = "갓 감지한 대형 긴급" → first_seen 우선(없으면 published 폴백).
    s = c.get("first_seen") or c.get("published") or ""
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            t = dt.datetime.strptime(s.replace("Z", "+0000")[:25 if "+" in s else 19], f)
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            return (time.time() - t.timestamp()) / 3600
        except Exception:
            pass
    return None


def pub_age_h(c):
    # 발행나이(published·KST) — 자동픽 '둘 다 4h내' 게이트용(운영자 260623). 발행 16h stale 건이 first_seen 방금이라
    # 자동분석(요약+썸네일) 진입하던 것 차단. published 없으면 None → first_seen 만으로(발행시각 없는 매체 = 기존 폴백 유지).
    s = c.get("published") or ""
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            t = dt.datetime.strptime(s.replace("Z", "+0000")[:25 if "+" in s else 19], f)
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            return (time.time() - t.timestamp()) / 3600
        except Exception:
            pass
    return None


def ekeys(c):
    # 자동픽 원장 다중키 = 대표(event_key/id/url) + 제목해시(t:…). push_send.dedup_keys 와 동일 키셋.
    # 제목해시가 'event_key=url 디폴트 → 대표 url 점프 → 키 갈림' 구멍을 메움(같은 헤드라인이면 url 달라도 같은 키 → 재픽 차단).
    ks = []
    k = c.get("event_key") or c.get("id") or c.get("url")
    if k:
        ks.append(str(k))
    t = re.sub(r"\s+", "", c.get("title") or "")
    if t:
        ks.append("t:" + hashlib.md5(t.encode("utf-8")).hexdigest()[:16])
    return ks


def eligible(c):
    if not c.get("breaking"):
        return False
    g = c.get("grade")
    if g is None or (g or 0) < MIN_GRADE:               # 미채점(None)은 보류 — push 와 동일(가역 아닌 자동 과금이라 보수적)
        return False
    if (c.get("cross") or 0) < MIN_CROSS:
        return False
    a = age_h(c)
    if a is None or a < 0 or a >= FAST_MAX_H:           # 미래(오기록)·4h+ 제외 (first_seen=갓 감지)
        return False
    pa = pub_age_h(c)                                   # 발행도 4h내여야(운영자 260623): 발행 16h stale 건이 first_seen 방금이라 긴급 자동분석 진입하던 것 차단. 발행 무효(None)=first_seen 만으로(폴백)
    if pa is not None and pa >= FAST_MAX_H:
        return False
    return True


def pick_url(c):
    # PICK_URL = 후보 대표 url(c.url) = 뷰어 '고르기'(수동픽)가 보내는 키와 동일 → pick_pending 의 load_active dedup 가
    # 수동·자동 같은 사건을 같은 키로 봐서 중복 분석 0. 보수 메이저 픽(breaking_pick.url)은 fetch 폴백으로 alt 에 넣음(접근성↑).
    u = c.get("url") or c.get("id") or ""
    return u if u.startswith(("http://", "https://")) else ""


def main():
    cands = jload(CAND, [])
    items = cands if isinstance(cands, list) else (cands.get("items", cands.get("candidates", [])) if isinstance(cands, dict) else [])
    led = jload(LEDGER, {})
    if not isinstance(led, dict):
        led = {}
    now = dt.datetime.now(KST)
    stamp = now.isoformat(timespec="seconds")

    def _age_days(iso):
        try:
            return (now - dt.datetime.fromisoformat(iso)).total_seconds() / 86400
        except Exception:
            return 0

    led = {k: v for k, v in led.items() if _age_days(v) < 2}      # 48h+ 원장 정리(비대 방지)
    today = now.strftime("%Y-%m-%d")
    # 일 카운트 = 사건당 1건(대표키만 셈 · 제목해시 t: 키 제외 = 사건당 2키여도 1로 카운트).
    today_n = sum(1 for k, v in led.items() if not str(k).startswith("t:") and str(v).startswith(today))

    picks = [c for c in items if isinstance(c, dict) and eligible(c) and not any(k in led for k in ekeys(c))]
    picks.sort(key=lambda c: c.get("first_seen") or "", reverse=True)   # 갓 뜬 것 우선
    print(f"자격 {len(picks)}건(grade≥{MIN_GRADE}·cross≥{MIN_CROSS}·<{FAST_MAX_H}h·미픽) · 오늘 자동픽 {today_n}/{MAX_PER_DAY}", file=sys.stderr)

    n = 0
    for c in picks:
        if n >= MAX_PER_RUN:
            print(f"런 상한({MAX_PER_RUN}) 도달 — 나머지 다음 런", file=sys.stderr)
            break
        if today_n + n >= MAX_PER_DAY:
            print(f"일 상한({MAX_PER_DAY}) 도달 — 자동픽 보류", file=sys.stderr)
            break
        url = pick_url(c)
        if not url.startswith(("http://", "https://")):
            continue
        title = c.get("title") or ""
        bp = (c.get("breaking_pick") or {}).get("url")
        alts = ([bp] if isinstance(bp, str) else []) + [u for u in (c.get("cluster_members") or c.get("alt_urls") or []) if isinstance(u, str)]
        alt = " ".join(u for u in alts if u and u != url)[:1500]   # breaking_pick(메이저·접근성↑) + 클러스터 — PICK_URL(c.url) 자신 제외
        if DRY:
            print(f"  [dry] 자동픽 후보: grade{c.get('grade')} cross{c.get('cross')} age{age_h(c):.1f}h | {title[:40]} | {url}", file=sys.stderr)
            for k in ekeys(c):
                led[k] = stamp
            n += 1
            continue
        env = dict(os.environ, PICK_URL=url, PICK_TITLE=title, PICK_ALT=alt)
        out = subprocess.run([sys.executable, str(PICK)], env=env, capture_output=True, text=True)
        sys.stderr.write(out.stderr)
        if out.returncode != 0:   # pick_pending 크래시(deps·IO) = 미처리 → 원장 기록 X = 다음 런 재시도(크래시는 pending 미작성 = 과금 0 · 48h 무분석 차단 방지)
            print(f"  ⚠ pick_pending 실패(rc={out.returncode}) — 원장 미기록·다음 런 재시도: {title[:36]}", file=sys.stderr)
            continue
        for k in ekeys(c):   # 정상 종료(픽=NEW=1 또는 이미처리=NEW=0)만 다중키 기록 = 재픽·재평가 차단(url 점프 포함)
            led[k] = stamp
        if "NEW=1" in (out.stdout or ""):
            n += 1
            print(f"  ✅ 자동픽: grade{c.get('grade')} {title[:40]}", file=sys.stderr)
        else:
            print(f"  ↷ 스킵(이미 처리중/완료): {title[:40]}", file=sys.stderr)

    if not DRY:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"PICKED={n}")


if __name__ == "__main__":
    main()
