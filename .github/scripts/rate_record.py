#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 뷰어 스크랩 관심도(★1~5)·픽 → scraper/ratings.jsonl 에 한 줄씩 누적(append-only 원장).
# 트리거: Pages Function /api/rate → rate.yml. 분석·취향학습용 라벨 데이터(누적이 곧 데이터).
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
LEDGER = Path(__file__).resolve().parent.parent.parent / "scraper" / "ratings.jsonl"


def main():
    score = int(re.sub(r"\D", "", os.environ.get("R_SCORE", "0") or "0") or "0")
    score = max(0, min(5, score))
    rec = {
        "ts": datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S%z"),
        "id": (os.environ.get("R_ID", "") or "")[:200],
        "url": (os.environ.get("R_URL", "") or "")[:400],
        "title": (os.environ.get("R_TITLE", "") or "")[:300],
        "score": score,
        "picked": (os.environ.get("R_PICKED", "") or "").lower() in ("1", "true", "yes"),
        "memo": (os.environ.get("R_MEMO", "") or "")[:200],
    }
    if not rec["id"] and not rec["url"]:
        print("빈 레코드 — 스킵")
        return
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"적재: score={rec['score']} picked={rec['picked']} memo={'Y' if rec['memo'] else '-'} | {rec['title'][:40]}")


if __name__ == "__main__":
    main()
