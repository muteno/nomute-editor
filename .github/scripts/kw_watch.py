#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kw_watch.py — 키워드 알림 서버 감시 + 웹푸시(운영자 260727 "키워드 알림 발견 시 웹 알림 오게해줘").

왜: 뷰어의 키워드 알림(Q493/Q623)은 **인앱 토스트**라 앱을 열고 있을 때 60초 폴링으로만 떴다.
    "놓치지 않게 반복 알림"이 목적인데 정작 앱을 안 켜면 침묵하는 구조 = 목적과 어긋남.
    수집 러너는 30분마다 어차피 돌고 있으니, 거기서 같은 매칭을 돌려 **웹푸시**로 밀면 앱을 닫아도 온다.

무엇을(뷰어 규칙 100% 미러 — 판정이 두 곳에서 갈리면 안 된다):
  · 감시 원문 = 국내(tbs_data 커뮤 베스트글 제목 + social_candidates 제목·출처) + 해외(sns_trends의
    reddit·hackernews·bsky·bsky_trends·xtrends)  ← viewer/index.html `kwDocs()`
  · 매칭 = "A+B+C" = **한 글 안에** 전 토큰 포함(대소문자·공백 정규화)  ← 같은 파일 `kwMatch()`
  · 발송 리듬 = 첫 발견 1회 + 24시간 동안 3시간마다(버킷 0~8)  ← 같은 파일 KW_BUCKET_MS·KW_MAX_BUCKET
  · 대상 = settings/app.json 의 kwAlertOn=true 이고 done=false 인 항목(체크 = 중단 = 여기서도 즉시 반영)

어떻게(부작용 최소):
  · 발송 = push_send.py --notify 재사용(중복 구현 0 · 구독자·VAPID·죽은구독 정리 전부 그쪽 계약).
  · dedup 원장 = push/kw_sent.json {슬러그: {first: epoch, sent: [버킷…]}} — **settings/app.json은 안 건드린다**
    (그 파일은 Pages Function이 GitHub API로 쓰는 계정 SSOT라, 러너가 같이 쓰면 병합 레이스가 난다.
     '첫 발견 시각'을 이 원장이 따로 들고 있으면 뷰어 hit 필드와 독립적으로 버킷을 셀 수 있다.)
  · fail-soft — 파일 없음·파싱 실패·발송 실패가 수집 파이프를 못 죽인다(항상 rc=0).

env: VAPID_PRIVATE_KEY·VAPID_SUBJECT(push_send.py가 소비) · KW_PUSH_DRY=1 = 실발송 없이 판정만 출력.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SETTINGS = ROOT / "settings" / "app.json"
TBS = ROOT / "viewer" / "tbs_data.json"
SNS = ROOT / "viewer" / "sns_trends.json"
SOC = ROOT / "viewer" / "social_candidates.json"
LEDGER = ROOT / "push" / "kw_sent.json"
PUSH = ROOT / ".github" / "scripts" / "push_send.py"

BUCKET_S = 3 * 3600        # 3시간(뷰어 KW_BUCKET_MS 미러)
MAX_BUCKET = 8             # 24h = 8버킷(뷰어 KW_MAX_BUCKET 미러)
GRACE_S = 30 * 60          # 종료 여유 30분(뷰어 동일)
DRY = (os.environ.get("KW_PUSH_DRY") or "").strip() == "1"


def jload(p, d):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return d


def norm(s):
    """뷰어 kwNorm 미러 — 소문자 + 연속공백 1칸 + 트림."""
    return re.sub(r"\s+", " ", str(s or "").lower()).strip()


def slug(s):
    """뷰어 kwSlug 미러 — 원장 키(한글 보존)."""
    v = re.sub(r"[^a-z0-9가-힣]+", "-", norm(s)).strip("-")[:60]
    return v or "kw"


def docs():
    """감시 원문 = 글 1건이 배열 1칸(뷰어 kwDocs 미러 · 합본 문자열 금지 = 딴 글끼리 AND 오탐 차단)."""
    out = []

    def put(s):
        v = norm(s)
        if v:
            out.append(v)

    for r in jload(SOC, []) or []:
        if isinstance(r, dict):
            src = r.get("sources")
            put((r.get("title") or "") + " " + (" ".join(src) if isinstance(src, list) else ""))
    for c in (jload(TBS, {}) or {}).get("communities") or []:
        for p in (c or {}).get("posts") or []:
            if isinstance(p, dict):
                put(p.get("title"))
    t = jload(SNS, {}) or {}
    for p in t.get("reddit") or []:
        put((p or {}).get("title"))
    for p in t.get("hackernews") or []:
        put(((p or {}).get("title") or "") + " " + ((p or {}).get("ko") or ""))
    for p in t.get("bsky") or []:
        put((p or {}).get("text"))
    for p in t.get("bsky_trends") or []:
        put(((p or {}).get("query") or "") + " " + ((p or {}).get("ko") or ""))
    for p in t.get("xtrends") or []:
        put((p or {}).get("query"))
    return out


def matched(kw, ds):
    """뷰어 kwMatch 미러 — 한 글이 전 토큰(+ 구분)을 다 품어야 참."""
    ts = [x.strip() for x in norm(kw).split("+") if x.strip()]
    if not ts:
        return False
    return any(all(t in d for t in ts) for d in ds)


def send(kw, bucket):
    """발송 = push_send.py --notify 재사용. 실패해도 파이프 안 깸(rc 무시·로그만)."""
    body = f"«{kw}» 가 커뮤니티에 떴어요" + ("" if bucket == 0 else f" (재알림 {bucket * 3}시간째)")
    if DRY:
        print(f"  [드라이런] 발송 생략 — {body}")
        return True
    try:
        r = subprocess.run([sys.executable, str(PUSH), "--notify", "🔔 키워드 발견", body,
                            "--url", "/", "--tag", "nomute-kw"],
                           capture_output=True, text=True, timeout=180)
        print((r.stdout or "").strip()[-400:])
        if r.returncode != 0:
            print(f"::warning::kw 푸시 rc={r.returncode} — {(r.stderr or '')[-200:]}", file=sys.stderr)
        return r.returncode == 0
    except Exception as e:  # noqa: BLE001
        print(f"::warning::kw 푸시 실패(무시): {e}", file=sys.stderr)
        return False


def main():
    st = jload(SETTINGS, {}) or {}
    if st.get("kwAlertOn") is not True:
        print("키워드 알림 OFF — 감시 생략")
        return
    items = [i for i in (st.get("kwItems") or []) if isinstance(i, dict) and i.get("kw") and not i.get("done")]
    if not items:
        print("감시 대상 키워드 없음(전부 체크됐거나 미등록)")
        return

    ds = docs()
    if not ds:
        print("::warning::감시 원문 0건 — 수집 산출물 확인(tbs_data·sns_trends)")
        return

    led = jload(LEDGER, {})
    if not isinstance(led, dict):
        led = {}
    now = int(time.time())
    changed, fired = False, 0

    for it in items:
        kw = it["kw"]
        key = slug(kw)
        hit = matched(kw, ds)
        rec = led.get(key) if isinstance(led.get(key), dict) else None

        if not rec:
            if not hit:
                print(f"  · «{kw}» 미매칭(대기)")
                continue
            led[key] = {"first": now, "sent": [0], "kw": kw}   # 첫 발견 = 즉시 1회
            changed = True
            fired += 1
            print(f"  🔔 «{kw}» 첫 발견 — 푸시")
            send(kw, 0)
            continue

        el = now - int(rec.get("first") or now)
        if el > MAX_BUCKET * BUCKET_S + GRACE_S:
            continue   # 24h 경과 = 반복 종료(뷰어와 동일 · 원장은 남겨 재발견 시 중복 방지)
        due = el // BUCKET_S
        if 1 <= due <= MAX_BUCKET and due not in (rec.get("sent") or []):
            if not hit:
                print(f"  · «{kw}» 버킷{due} 도래했으나 지금은 원문에서 사라짐 — 발송 생략")
                continue
            rec.setdefault("sent", []).append(int(due))
            changed = True
            fired += 1
            print(f"  🔔 «{kw}» 재알림 버킷{due}(+{due * 3}h) — 푸시")
            send(kw, int(due))

    if changed and not DRY:   # ⚠ 드라이런은 원장을 남기지 않는다 — 남기면 '이미 보냈다'로 도장돼 진짜 첫 발송이 영영 스킵된다
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ kw_watch: 감시 {len(items)}건 · 원문 {len(ds)}글 · 발송 {fired}건{' (드라이런)' if DRY else ''}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 — 감시 실패가 수집 파이프를 못 죽인다
        print(f"::warning::kw_watch 자체 실패(무시): {type(e).__name__} {e}", file=sys.stderr)
