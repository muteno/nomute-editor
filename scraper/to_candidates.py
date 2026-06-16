#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# scraper 출력(articles.json) → viewer/candidates.json 갱신 = 스크랩(수집함) 탭 데이터.
# 클러스터 대표만 추려 url 기준 누적·중복제거·보관기간(10일) 폐기·교차순·보관한도. 자동분석과 무관(수집만, 과금 0).
#   사용: python3 scraper/to_candidates.py [articles.json경로]
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scraper" / "out" / "articles.json"
DST = ROOT / "viewer" / "candidates.json"

# 용어 통일: 수집 수(긁은 기사 총량, knews_scraper) · 사건 수(중복 합친 distinct, 아래 kept) ·
#            보관한도(수집함에 들고 있는 최대 사건 수=CAP) · 보관기간(등장 후 폐기까지 시간=TTL).
TTL_HOURS = int(os.environ.get("CAND_TTL_HOURS", "240"))  # 보관기간: 등장 후 N시간 지나면 폐기(240=10일)
CAP = int(os.environ.get("CAND_CAP", "3000"))             # 보관한도: 수집함 최대 사건 수(10일치 여유 — 실제 컷은 보관기간이 함)
MIN_CROSS = int(os.environ.get("CAND_MIN_CROSS", "2"))    # 교차등장 최소 매체 수(2=2개 이상 매체에 뜬 것만 = 뉴스성)
# ── 속보(velocity) 1차 게이트 — burst(15분 내 동시 매체) 기반. 2차 내용판정은 별도(Claude). ──
BREAKING_BURST = int(os.environ.get("BREAKING_BURST", "3"))          # 속보 후보: burst 이 값 이상
MEGA_MEMBERS = int(os.environ.get("BREAKING_MEGA_MEMBERS", "40"))    # 멤버 이상 = over-merge 의심 → 속보 제외
MEGA_CROSS = int(os.environ.get("BREAKING_MEGA_CROSS", "18"))        # 누적 매체 이상 = over-merge 의심 → 속보 제외

KST = timezone(timedelta(hours=9))
# 스크래퍼 영문 섹션 → 뷰어 카테고리(catBucket 호환: 정치→사회 매핑은 뷰어가 처리)
CAT_MAP = {"politics": "정치", "economy": "경제", "society": "사회",
           "international": "국제", "world": "국제", "diplomacy": "국제",
           "tech": "테크", "it": "테크", "science": "테크", "culture": "문화"}


def cat_ko(category):
    for tok in re.split(r"[,\s/]+", str(category or "").lower()):
        if tok in CAT_MAP:
            return CAT_MAP[tok]
    return ""


def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def main():
    arts = load_json(SRC, [])
    now = datetime.now(KST)
    nowiso = now.strftime("%Y-%m-%dT%H:%M:%S%z")

    # 기존 후보(url → entry) — first_seen(등장시각) 보존해 TTL 누적
    existing = {c["url"]: c for c in load_json(DST, []) if isinstance(c, dict) and c.get("url")}

    # 신규 = 클러스터 대표 + 교차 MIN_CROSS 이상
    fresh = {}
    for a in arts:
        if not a.get("is_cluster_rep"):
            continue
        if (a.get("cross_score") or 0) < MIN_CROSS:
            continue
        url = a.get("link") or ""
        if not url:
            continue
        burst = a.get("burst") or 0
        cross = a.get("cross_score") or 0
        size = a.get("cluster_size") or 0
        mega = size > MEGA_MEMBERS or cross > MEGA_CROSS   # over-merge 의심(대표 신뢰 불가)
        fresh[url] = {
            "id": url, "url": url,
            "title": a.get("title") or "",
            "media": a.get("publisher") or "",
            "cat": cat_ko(a.get("category")),
            "cross": cross,
            "published": a.get("published") or "",
            "burst": burst,
            # 속보 1차 후보(velocity) — 2차 내용판정(Claude)이 breaking 을 확정한다.
            "breaking_candidate": bool(burst >= BREAKING_BURST and not mega),
            "breaking_pick": a.get("breaking_pick") or None,
        }

    merged = dict(existing)
    for url, c in fresh.items():
        prev = merged.get(url, {})
        c["first_seen"] = prev.get("first_seen", nowiso)
        # last_seen = 마지막 '후속'(distinct 매체 = cross 증가) 시각. 신규 or cross 성장이면 now,
        #            아니면 기존 유지. 뷰어가 (now - last_seen)으로 중요도 신선도를 감쇠(후속 끊기면 하강).
        grew = (not prev) or ((c.get("cross") or 0) > (prev.get("cross") or 0))
        c["last_seen"] = nowiso if grew else (prev.get("last_seen") or c["first_seen"])
        merged[url] = {**prev, **c}

    # 속보 강등(만료): burst 가 1차 게이트(≥BREAKING_BURST) 밑으로 떨어진 사건은 굳은 breaking 플래그 해제.
    # burst 2 vs 3 = 넘사벽 — 급증 끝난 사건이 🚨로 눌어붙던 버그 차단. rubric 도 비워 재급증 시 재판정.
    for c in merged.values():
        if not c.get("breaking_candidate"):
            c.pop("breaking", None)
            c.pop("breaking_rubric", None)

    def age_h(c):
        try:
            return (now - datetime.fromisoformat(c.get("first_seen") or nowiso)).total_seconds() / 3600
        except Exception:
            return 0.0

    kept = [c for c in merged.values() if age_h(c) <= TTL_HOURS]
    kept.sort(key=lambda c: (c.get("cross") or 0, c.get("published") or ""), reverse=True)
    kept = kept[:CAP]

    nbreak = sum(1 for c in kept if c.get("breaking_candidate"))
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
    print(f"수집함: 사건 {len(kept)}건 (신규 {len(fresh)} · 기존 {len(existing)}) · "
          f"보관한도 {CAP} · 보관기간 {TTL_HOURS}h(약 {TTL_HOURS // 24}일) · 교차≥{MIN_CROSS} · "
          f"🚨속보후보(burst≥{BREAKING_BURST}) {nbreak}건")


if __name__ == "__main__":
    main()
