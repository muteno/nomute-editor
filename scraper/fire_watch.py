#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ⑭-f 화재 재난문자 후속 추적 — 운영자 260803 "화재 알림이 나면, 15분, 그리고 30분 뒤에 각각 이를 검색해서
#   사상자가 있는지 확인하게끔. 있다면 긴급보도 큐로 바로 조사해서 큐잉".
#
# 왜 필요한가 = 재난문자는 **속보보다 빠르지만 사상자를 안 싣는다**(발령 시점엔 아무도 모른다). 사상자 확정은
#   15~30분 뒤 기사로 온다. 그 창을 사람이 지키고 있을 수 없어서, 발령을 원장에 걸어두고 시간이 차면 자동으로 되짚는다.
#
# 파이프라인 = 재난문자(viewer/sns_trends.json disaster[]) → 원장 등록 → +15분·+30분 되짚기 →
#              사상자 기사 발견 → pick_pending(수동픽과 동일 입구) → pending/ → news-analyze(요약·카드).
#
# ⚠️ 자동 과금 경로 — 픽 1건 = Opus 분석 1콜(구독 쿼터) + 썸네일($). auto_pick_breaking.py 의 가드를 그대로 계승:
#   ① 중대재난 문턱 = sns_trends.DIS_CRIT_MIN(77) 단일 원천 + 화재 계열 kind 한정(폭염·호우는 등록조차 안 됨)
#   ② 사건 단위 dedup — 같은 불이 인접 3개 구에 각각 발령되는 게 관례다(260803 실측: 울산 남구·중구·북구 = 삼산동 페인트공장 1건)
#   ③ 사건당 **1픽 영구**(원장 picked) + 일 상한(FIRE_DAY_CAP)
#   ④ 3축 동시 히트만 픽(지역 ∧ 화재어 ∧ 사상자어) — 하나라도 빠지면 무픽(오탐 = 헛 과금)
#   ⑤ 기사 발행시각 > 재난문자 발령시각 − 유예 = 발령 이전 기사(다른 사건)를 사상자 근거로 못 씀
#   ⑥ pick_pending 의 load_active dedup(이미 처리중/완료면 스킵 = 수동픽·자동픽과 충돌 0)
# 검색 = 1순위 viewer/candidates.json(레포가 15분마다 갱신 · 네트워크 0·과금 0) · 2순위 네이버 뉴스 검색
#   (NAVER_CLIENT_ID/SECRET 있을 때만 · 없으면 조용히 1순위만 = 현 동작 불변).
# 출력: stderr 요약 + stdout 마지막 줄 'PICKED=<n>'(워크플로가 커밋·분석발동 판단 — auto_pick_breaking 계약 동일).
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRENDS = ROOT / "viewer" / "sns_trends.json"
CAND = ROOT / "viewer" / "candidates.json"
LEDGER = ROOT / "push" / "fire_watch.json"   # 추적 원장 {사건키: {t0, kind, area, lm, text, done[], picked, hit}}
PICK = ROOT / "scraper" / "pick_pending.py"
KST = timezone(timedelta(hours=9))

# 되짚기 = **발령 후 WATCH_TTL_H 동안 매 런(15분)** — 운영자 260803 2차 개정.
#   ⚠ 구판 = 15·30분 두 회차로 끝(운영자 1차 지시 문면). 실제 보도 리듬을 못 따라간다:
#     운영자 실측 사례 = 08:20 사건(사망) → **10:00 보도** → 그때야 사람이 스크랩을 보고 안다.
#     구판은 08:50에 문을 닫아 그 10:00 보도를 **영영 못 잡는다**(놓침 = 이 기능의 존재 이유 상실).
#   화재·지진은 피해가 클 확률이 높아 보도성이 강하다(운영자) → 창을 넓히고, 대신 픽 가드로 과금을 막는다.
#   비용 = 수집함 스캔 로컬 0 · 네이버는 사건당 최대 24콜(6h/15분 · 일 25,000 한도 대비 무시 가능).
FIRST_CHECK_MIN = 5               # 발령 직후 5분은 스킵(그 시점 기사 = 사건 인지 자체가 없다 · 검색 낭비)
WATCH_TTL_H = int(os.environ.get("FIRE_WATCH_H", "6"))   # 추적 창 — 화재 사망 확정 보도는 통상 1~4시간(6h면 덮는다). 조정 = env 1줄
EVENT_GAP_MIN = 45                # 같은 사건 판정 창 — 같은 불의 인접 구 발령이 이 안에 들어온다(실측 08:41~09:04 = 23분)
FIRE_DAY_CAP = int(os.environ.get("FIRE_DAY_CAP", "6"))   # 일 픽 상한(과금 가드 · auto_pick_breaking 정신 계승)
ART_GRACE_MIN = 30                # 기사 발행이 발령보다 이만큼 앞서는 것까지는 같은 사건으로 인정(최초 인지 보도가 문자보다 빠른 경우)
NAVER_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

# 등록 대상 = 화재 계열(운영자 "화재 알림") — 폭발·붕괴는 사상자 확인 축이 화재와 동일해 동승.
#   지진은 비대상: 이미 quakeMsgs(뷰어 경보)가 담당하고, 사상자 추적 대상으로 지목된 축이 아니다(스코프 밖 = 조용히 미등록).
FIRE_KINDS = ("화재", "산불", "폭발", "붕괴")
FIRE_WORD = re.compile(r"화재|불길|산불|폭발|붕괴|화염|연소|진화")
# 사상자어 — '있는지 확인'의 판정축. 부상·사망·수색까지 넓게(놓침이 오탐보다 비싼 안전 축) ·
#   ⚠ '피해 없음'·'인명피해는 없'은 아래 NEG로 컷(그 문장이 바로 사상자어를 포함한다).
CASUALTY = re.compile(r"사망|숨져|숨진|숨졌|사상자|부상|중상|경상|인명\s?피해|심정지|매몰|고립|실종|참변|화상|질식|대피\s?중\s?부상|중태")
NEG = re.compile(r"인명\s?피해[는은]?\s?(없|미발생)|사상자[는은]?\s?(없|미발생)|다친\s?사람[은는]?\s?없|부상자[는은]?\s?없")


def jload(p, dflt):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return dflt


def ts(s):
    """ISO8601 → epoch초. 실패 = 0."""
    try:
        d = datetime.fromisoformat(str(s or "").strip().replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=KST)).timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def crit_of(d):
    """중대재난 여부 — 수집기 crit 1순위 · 구 데이터는 sev 역산(뷰어 disCrit와 같은 사다리)."""
    if d.get("crit") is not None:
        return bool(d.get("crit"))
    sev = d.get("sev")
    return isinstance(sev, (int, float)) and sev > 0 and int(sev % 1000) // 10 >= 77


def places(d):
    """이 발령의 지역어 집합 — 기사 매칭 키. 광역 접미(광역시·특별자치도 등)를 떼서 기사 표기와 맞춘다.
    area = '울산광역시 북구' → {울산, 북구} · 본문 '삼산동 페인트공장' → 동/읍/면 지명도 수확(기사가 동名으로 쓴다)."""
    out = set()
    for tok in str(d.get("area") or "").split():
        t = re.sub(r"(특별자치도|특별자치시|특별시|광역시|자치도|자치시)$", "", tok).strip()
        if len(t) >= 2 and not t.startswith("외"):
            out.add(t)
    for m in re.findall(r"[가-힣]{2,4}(?:동|읍|면|리)(?![가-힣])", str(d.get("text") or "")):
        out.add(m)
    return {p for p in out if len(p) >= 2}


def wide_of(d):
    """광역 단위(시·도) — 같은 불의 인접 구 발령을 묶는 축. '울산광역시 북구' → '울산'."""
    w = re.sub(r"(특별자치도|특별자치시|특별시|광역시|자치도|자치시).*$", "", str(d.get("area") or "")).split()
    return (w[0] if w else "미상")[:6]


def event_key(d, led):
    """사건키 — 같은 불의 인접 구 다중 발령을 한 건으로 묶는다.
    ⚠ 고정 슬롯(t0 // 45분) 금지 — 경계에 걸리면 23분 차이도 갈린다(260803 실측: 울산 삼산동 페인트공장 1건이
      08:48/09:04로 분리 → 같은 불을 두 번 추적·두 번 큐잉할 뻔). **기존 원장 항목과의 근접 매칭**이 정본."""
    kind, t = (d.get("kind") or "화재"), ts(d.get("time"))
    head = wide_of(d)
    for k, v in led.items():
        if not isinstance(v, dict) or v.get("wide") != head or v.get("kind") != kind:
            continue
        if abs((v.get("t0") or 0) - t) <= EVENT_GAP_MIN * 60:
            return k
    return f"{head}|{kind}|{datetime.fromtimestamp(t or 0, KST).strftime('%y%m%d-%H%M')}"


def hit_article(a, ev):
    """기사 1건이 이 사건의 '사상자 확인'인가 — 3축(지역 ∧ 화재어 ∧ 사상자어) 동시 + 발행시각 정합."""
    title = " ".join(str(a.get("title") or "").split())
    if not title:
        return False
    if NEG.search(title):          # "인명피해 없어" = 확인됐으나 사상자 0 → 긴급큐 대상 아님
        return False
    if not (FIRE_WORD.search(title) and CASUALTY.search(title)):
        return False
    if not any(p in title for p in ev.get("places") or []):
        return False
    pt = ts(a.get("published")) or ts(a.get("first_seen"))
    if pt and pt < ev["t0"] - ART_GRACE_MIN * 60:   # 발령보다 한참 앞선 기사 = 다른 사건
        return False
    return True


def naver_news(q, limit=20):
    """2순위 검색 — 네이버 뉴스(키 없으면 []). candidates 는 15분 주기라 '방금 뜬' 속보가 아직 없을 수 있다."""
    if not (NAVER_ID and NAVER_SECRET):
        return []
    try:
        u = ("https://openapi.naver.com/v1/search/news.json?display=" + str(limit) +
             "&sort=date&query=" + urllib.parse.quote(q))
        rq = urllib.request.Request(u, headers={"X-Naver-Client-Id": NAVER_ID,
                                                "X-Naver-Client-Secret": NAVER_SECRET})
        with urllib.request.urlopen(rq, timeout=12) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        out = []
        for it in (j.get("items") or []):
            link = (it.get("originallink") or it.get("link") or "").strip()   # 원문 링크 우선 = 분석기 fetch 대상
            if not link.startswith("http"):
                continue
            out.append({"url": link, "title": re.sub(r"<[^>]+>|&quot;|&amp;|&lt;|&gt;", " ", it.get("title") or ""),
                        "published": it.get("pubDate") or ""})
        return out
    except Exception as e:  # noqa: BLE001
        print(f"::warning::네이버 뉴스 검색 실패(스킵): {e}", file=sys.stderr)
        return []


def search(ev):
    """사상자 기사 찾기 — 1순위 레포 수집함(무과금) → 없으면 2순위 네이버(키 있을 때). 첫 히트 1건 반환(없으면 None)."""
    for a in jload(CAND, []):
        if isinstance(a, dict) and hit_article(a, ev):
            return {"url": a.get("url") or a.get("id") or "", "title": a.get("title") or "",
                    "src": "수집함", "alt": " ".join((a.get("cluster_members") or [])[:6])}
    q = (sorted(ev.get("places") or [], key=len, reverse=True)[:1] or ["화재"])[0] + " " + (ev.get("kind") or "화재")
    for a in naver_news(q):
        if hit_article(a, ev):
            return {"url": a["url"], "title": a["title"], "src": "네이버", "alt": ""}
    return None


def notify(ev, art):
    """사상자 확인 = **그 자리에서 알린다**(운영자 260803 "이 같은 상황을 더 빨리 알려고 하는거지").
    구판은 큐잉만 했다 = 운영자가 큐를 열어봐야 안다. 08:20 사건의 10:00 사망 보도를 기계가 10:15에 잡아도,
    사람이 큐를 안 보면 '더 빨리'가 실현되지 않는다 → 채널 2개로 즉시 밀어낸다:
      ⓐ 웹푸시(push_send · 폰 알림) — 앱을 안 켜고 있어도 온다. tag 'nomute-fire' = 재난 축 전용 자리.
      ⓑ 메시지함 점등(msg.py · 단일 슬롯 fire-<사건키>) — 푸시를 놓쳐도 앱에 남는다 + 프로필 경고 점등.
    둘 다 fail-soft — 알림 실패가 큐잉·원장을 죽이지 않는다(watchdog 관용구 계승)."""
    head = f"🔥 {ev.get('kind') or '화재'} 사상자 확인" + (f" · {ev['lm']}" if ev.get("lm") else "")
    body = f"{ev.get('area') or ''} — {art['title'][:80]}"
    try:
        subprocess.run([sys.executable, str(ROOT / "shared" / "msg.py"), "set",
                        "fire-" + re.sub(r"[^A-Za-z0-9._-]", "_", str(ev.get("wide") or "") + str(int(ev.get("t0") or 0))),
                        f"{head}\n{body}\n\n발령 +{int((datetime.now(KST).timestamp() - (ev.get('t0') or 0)) / 60)}분 만에 확인 — 긴급보도 큐로 넘겼어요.",
                        "warn"], timeout=30)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::메시지함 점등 실패(무시): {e}", file=sys.stderr)
    try:
        out = subprocess.run([sys.executable, str(ROOT / ".github" / "scripts" / "push_send.py"),
                              "--notify", head, body[:110], "--tag", "nomute-fire", "--url", "/?dis=1"],
                             capture_output=True, text=True, timeout=180)
        m = re.search(r"발송: \d+/\d+", out.stdout or "")   # push_send 최종 요약 줄 = 실발송 계약(watchdog 판정 미러)
        print("  📣 " + (m.group(0) if m else "발송 생략(구독자·VAPID 없음)"), file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::웹푸시 실패(무시): {e}", file=sys.stderr)


def do_pick(ev, art):
    """긴급보도 큐 적재 — 수동픽·자동픽과 **같은 입구**(pick_pending.py · PICK_URL 키 동일 = dedup 정합)."""
    env = dict(os.environ, PICK_URL=art["url"], PICK_TITLE=" ".join(str(art["title"]).split())[:300],
               PICK_ALT=art.get("alt") or "")
    r = subprocess.run([sys.executable, str(PICK)], env=env, capture_output=True, text=True)
    sys.stderr.write(r.stderr or "")
    ok = r.returncode == 0 and (r.stdout or "").strip().splitlines()[-1:] == ["NEW=1"]
    print(f"  {'✅ 큐잉' if ok else '· 스킵(중복·실패)'} [{art['src']}] {art['title'][:60]}", file=sys.stderr)
    return ok


def main():
    now = datetime.now(KST).timestamp()
    led = jload(LEDGER, {})
    if not isinstance(led, dict):
        led = {}
    trends = jload(TRENDS, {})
    dis = [d for d in (trends.get("disaster") or []) if isinstance(d, dict)]

    # ① 등록 — 화재 계열 중대재난만. 사건 단위(인접 구 다중 발령 = 1건)로 최초 발령 시각을 t0로 고정.
    added = 0
    for d in dis:
        if (d.get("kind") or "") not in FIRE_KINDS or not crit_of(d):
            continue
        t0 = ts(d.get("time"))
        if not t0 or now - t0 > WATCH_TTL_H * 3600:   # 옛 스냅샷으로 부팅해도 지난 사건을 새로 추적하지 않는다
            continue
        k = event_key(d, led)
        cur = led.get(k)
        if cur is None:
            led[k] = {"t0": t0, "kind": d.get("kind") or "화재", "wide": wide_of(d), "area": d.get("area") or "",
                      "lm": d.get("lm") or "", "text": (d.get("text") or "")[:200],
                      "places": sorted(places(d)), "done": [], "picked": 0,
                      "reg": datetime.fromtimestamp(now, KST).isoformat(timespec="seconds")}
            added += 1
            print(f"🔥 추적 등록: {k} · {d.get('area')} · {(d.get('text') or '')[:40]}", file=sys.stderr)
        else:
            cur["t0"] = min(cur.get("t0") or t0, t0)                       # 최초 발령 기준(되짚기 시계는 첫 문자부터)
            cur["places"] = sorted(set(cur.get("places") or []) | places(d))   # 인접 구 발령이 지역어를 넓혀준다
            if d.get("lm") and not cur.get("lm"):
                cur["lm"] = d["lm"]

    # ② 되짚기 — 추적 창(WATCH_TTL_H) 안이면 **매 런** 사상자 검색. 러너가 15분 정본 타이머라 곧 15분 해상도.
    #   회차(15·30) 개념을 버린 이유 = 위 상수 주석의 08:20→10:00 사례. 창이 열려 있는 동안은 계속 본다.
    picked, today = 0, datetime.fromtimestamp(now, KST).strftime("%Y-%m-%d")
    cap = led.get("_cap") if isinstance(led.get("_cap"), dict) else {}
    cap_used = int(cap.get(today) or 0)   # 일 상한 카운터 = 원장 본문과 분리(TTL 정리에 쓸려나가면 상한이 매시간 초기화된다)
    for k, ev in sorted(led.items(), key=lambda kv: (kv[1] or {}).get("t0") or 0 if isinstance(kv[1], dict) else 0):
        if k == "_cap" or not isinstance(ev, dict) or ev.get("picked") or not ev.get("t0"):
            continue
        el = (now - ev["t0"]) / 60.0
        if el < FIRST_CHECK_MIN:
            continue
        ev["checks"] = int(ev.get("checks") or 0) + 1   # 되짚기 횟수(원장 로그 — 몇 번 만에 잡혔나 = 다음 튜닝 근거)
        print(f"🔎 되짚기 {k} (+{int(el)}분 · {ev['checks']}회차) — 사상자 검색", file=sys.stderr)
        art = search(ev)
        if not art or not art.get("url"):
            print("  · 사상자 기사 없음", file=sys.stderr)
            continue
        ev["hit"] = {"url": art["url"], "title": art["title"], "src": art["src"], "at_min": int(el)}
        notify(ev, art)   # ⚠ 큐잉보다 **먼저** 알린다 — 운영자가 알아야 하는 건 '사상자 확인' 그 자체(과금 가드에 막혀도 알림은 간다)
        if cap_used >= FIRE_DAY_CAP:
            print(f"::warning::일 픽 상한({FIRE_DAY_CAP}) 도달 — 큐잉 보류(원장에 근거는 남김): {art['title'][:50]}", file=sys.stderr)
            continue
        if do_pick(ev, art):
            ev["picked"] = 1
            ev["picked_at"] = datetime.fromtimestamp(now, KST).isoformat(timespec="seconds")
            picked += 1
            cap_used += 1
        else:
            ev["picked"] = 1   # 중복(이미 처리중·완료)도 이 사건은 종결 — 같은 사건으로 두 번 두드리지 않는다
            ev["picked_at"] = datetime.fromtimestamp(now, KST).isoformat(timespec="seconds")

    # ③ 정리 — TTL 지난 항목 제거(파일 무한 성장 차단 · 지난 사건 재등록은 ①의 TTL 게이트가 막는다)
    cap[today] = cap_used
    led = {k: v for k, v in led.items()
           if k != "_cap" and isinstance(v, dict) and now - (v.get("t0") or 0) <= WATCH_TTL_H * 3600}
    led["_cap"] = {d: c for d, c in cap.items() if d >= (datetime.fromtimestamp(now, KST) - timedelta(days=2)).strftime("%Y-%m-%d")}   # 최근 2일치만
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"fire-watch: 추적 {len(led) - 1}건(신규 {added}) · 큐잉 {picked}건 · 오늘 픽 {cap_used}/{FIRE_DAY_CAP}", file=sys.stderr)
    print(f"PICKED={picked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
