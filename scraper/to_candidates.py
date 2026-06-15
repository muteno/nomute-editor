#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# scraper 출력(articles.json) → viewer/candidates.json 갱신 = 스크랩(수집함) 탭 데이터.
# 클러스터 대표만 추려 url 기준 누적·중복제거·TTL(48h) 탈락·교차순·상한. 자동분석과 무관(수집만, 과금 0).
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

TTL_HOURS = int(os.environ.get("CAND_TTL_HOURS", "48"))   # 등장 후 N시간 지나면 수집함에서 탈락
CAP = int(os.environ.get("CAND_CAP", "80"))               # 수집함 최대 노출 수
MIN_CROSS = int(os.environ.get("CAND_MIN_CROSS", "2"))    # 교차등장 최소 매체 수(2=2개 이상 매체에 뜬 것만 = 뉴스성)

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
        fresh[url] = {
            "id": url, "url": url,
            "title": a.get("title") or "",
            "media": a.get("publisher") or "",
            "cat": cat_ko(a.get("category")),
            "cross": a.get("cross_score") or 0,
            "published": a.get("published") or "",
        }

    merged = dict(existing)
    for url, c in fresh.items():
        c["first_seen"] = merged[url].get("first_seen", nowiso) if url in merged else nowiso
        merged[url] = {**merged.get(url, {}), **c}

    def age_h(c):
        try:
            return (now - datetime.fromisoformat(c.get("first_seen") or nowiso)).total_seconds() / 3600
        except Exception:
            return 0.0

    kept = [c for c in merged.values() if age_h(c) <= TTL_HOURS]
    kept.sort(key=lambda c: (c.get("cross") or 0, c.get("published") or ""), reverse=True)
    kept = kept[:CAP]

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
    print(f"candidates.json: {len(kept)}건 (신규수집 {len(fresh)} · 기존 {len(existing)} · TTL {TTL_HOURS}h · 교차≥{MIN_CROSS})")


if __name__ == "__main__":
    main()
