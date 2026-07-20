#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tbs_scraper.py — 오늘의베스트(todaybeststory.com) 공개 API 수집기 (A안 · 독립 실행 모듈)

역할
  todaybeststory.com 백엔드가 이미 크롤해 둔 22개 커뮤니티 베스트글을
  공개 API(/api/v2)로 그대로 받아온다. 원본 커뮤니티를 직접 긁지 않으므로
  차단 위험 없이 전 커뮤니티 균일 스키마·실시간 데이터를 확보한다.
  (B안 = 원본 직접 크롤 전환 대비: 가공점수 popularityScore에 종속되지 않도록
   추천·비추·댓글·조회 '원값'을 그대로 저장한다 — 스키마 무중단 전환용)

출력
  viewer/tbs_data.json : 커뮤니티별 최신 베스트글 (KST 시각·원값 메타 포함)

사용 예
  python3 tbs_scraper.py                 # 기본: 커뮤니티당 최신 30건
  python3 tbs_scraper.py --limit 50      # 커뮤니티당 50건
  python3 tbs_scraper.py --out ../viewer/tbs_data.json

의존성
  pip install requests

주의
  외부 서비스 의존(A안) — 끊기면 이 모듈만 죽고 다른 파이프라인엔 영향 없음.
  전 커뮤니티 실패 시 rc=1 (기존 tbs_data.json은 덮지 않고 보존 = fail-soft).
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# ── 설정 ────────────────────────────────────────────────────────────
BASE = "https://todaybeststory.com/api/v2"
KST = timezone(timedelta(hours=9))  # 러너 UTC 대비 KST 강제 (CLAUDE.md [12])
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
# 저쪽 서버가 콜드 쿼리에 20초+ 걸리고 같은 URL 재요청은 캐시로 빨라짐 → 긴 타임아웃 + 재시도
TIMEOUT = 60
RETRY = 3
WORKERS = 4

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "viewer" / "tbs_data.json"


def log(msg):
    print(f"[tbs] {msg}", file=sys.stderr)


def get_json(session, url, params=None):
    last = None
    for i in range(RETRY + 1):
        try:
            r = session.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001 — 재시도 후 상위에서 판단
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def to_kst(iso_str):
    """API의 UTC ISO 시각 → 'YYYY-MM-DD HH:MM' KST 문자열."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_str


def fetch_community_posts(session, com, limit):
    cid = com["communityId"]
    data = get_json(
        session,
        f"{BASE}/communities/{cid}/posts",
        params={"page": 1, "limit": limit, "sort": "latest"},
    )
    items = data.get("items") or []
    posts = []
    for x in items:
        posts.append({
            "title": x.get("postTitle"),
            "url": x.get("postUrl"),
            "desc": x.get("postDesc") or "",
            "time": to_kst(x.get("postDatetime")),
            "writer": x.get("postWriterName"),
            # 원값 보존(가공점수 비종속 · B안 전환 대비)
            "up": x.get("upvoteCount"),
            "down": x.get("downvoteCount"),
            "comment": x.get("commentCount"),
            "read": x.get("readCount"),
            "score": x.get("popularityScore"),
        })
    return {
        "id": cid,
        "name": com.get("communityName"),
        "site": com.get("communityUrl"),
        "total": data.get("total"),
        "posts": posts,
    }


def main():
    ap = argparse.ArgumentParser(description="todaybeststory 공개 API 수집 (A안)")
    ap.add_argument("--limit", type=int, default=30, help="커뮤니티당 최신 글 수 (기본 30)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="출력 JSON 경로")
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/json"})

    coms = [c for c in get_json(session, f"{BASE}/communities") if c.get("useYn") == "Y"]
    log(f"커뮤니티 {len(coms)}개 · 커뮤니티당 {args.limit}건 수집 시작")

    results, failed = [], []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_community_posts, session, c, args.limit): c for c in coms}
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                r = fut.result()
                if r["posts"]:
                    results.append(r)
                    log(f"  ✓ {r['name']} {len(r['posts'])}건 (누적 {r['total']:,})")
                else:
                    failed.append(c["communityId"])
                    log(f"  ∅ {c['communityName']} 빈 응답")
            except Exception as e:  # noqa: BLE001
                failed.append(c["communityId"])
                log(f"  ✗ {c['communityName']} 실패: {e}")

    if not results:
        log("전 커뮤니티 실패 — 기존 산출물 보존, rc=1")
        return 1

    # 원본 /communities 순서 유지(임의 재정렬 없음)
    order = {c["communityId"]: i for i, c in enumerate(coms)}
    results.sort(key=lambda r: order.get(r["id"], 999))

    out = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "source": "todaybeststory.com /api/v2 (A안 · 공개 API)",
        "failed": failed,
        "communities": results,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(out_path)
    total_posts = sum(len(r["posts"]) for r in results)
    log(f"완료: {len(results)}/{len(coms)} 커뮤니티 · 글 {total_posts}건 → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
