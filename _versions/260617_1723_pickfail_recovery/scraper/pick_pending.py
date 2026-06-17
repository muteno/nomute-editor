#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 뷰어 '고르기'(픽) 1건 → pending/ 적재(분석 파이프라인 입구). to_pending 의 dedup·정규화·포맷 재사용.
#   env PICK_URL = 고른 기사 url. 이미 처리된(seen ∪ pending ∪ failed ∪ queue) url 이면 스킵(NEW=0).
#   출력: stderr 요약 + stdout 마지막 줄 'NEW=<0|1>'(워크플로가 커밋·분석발동 판단).
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knews_scraper import normalize_link              # 정규화 단일 원천(수집기와 동일 판정)
from to_pending import load_seen, PENDING, LEDGER      # dedup·경로 재사용(DRY)

KST = timezone(timedelta(hours=9))


def main():
    url = (os.environ.get("PICK_URL") or "").strip()
    if not url.startswith(("http://", "https://")):
        print("PICK_URL 없음/무효 — 스킵", file=sys.stderr)
        print("NEW=0")
        return
    key = normalize_link(url)
    if key in load_seen():
        print(f"이미 처리됨(중복) — 스킵: {url}", file=sys.stderr)
        print("NEW=0")
        return
    PENDING.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(KST).strftime("%y%m%d-%H%M%S")
    name = f"{stamp}-pick-{os.urandom(2).hex()}.txt"   # 동시 픽 충돌 방지 random 접미
    (PENDING / name).write_text(url + "\n", encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(key + "\n")
    print(f"픽 적재: {name} ← {url}", file=sys.stderr)
    print("NEW=1")


if __name__ == "__main__":
    main()
