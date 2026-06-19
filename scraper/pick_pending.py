#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 뷰어 '고르기'(픽) 1건 → pending/ 적재(분석 파이프라인 입구). to_pending 의 dedup·정규화·포맷 재사용.
#   env PICK_URL = 고른 기사 url. 이미 처리된(seen ∪ pending ∪ failed ∪ queue) url 이면 스킵(NEW=0).
#   출력: stderr 요약 + stdout 마지막 줄 'NEW=<0|1>'(워크플로가 커밋·분석발동 판단).
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knews_scraper import normalize_link              # 정규화 단일 원천(수집기와 동일 판정)
from to_pending import load_seen, PENDING, LEDGER      # dedup·경로 재사용(DRY)

KST = timezone(timedelta(hours=9))


def main():
    url = (os.environ.get("PICK_URL") or "").strip()
    # 제목(수집기 메타) = fetch 차단 매체일 때 분석기가 같은 사건의 접근 가능한 다른 매체를
    # WebSearch 로 찾는 단서. 개행 제거(파일 2번째 줄로 들어가므로 한 줄 보장).
    title = " ".join((os.environ.get("PICK_TITLE") or "").split()).strip()[:300]
    # alt = 같은 사건 다른 매체 url(cluster_members·공백구분) — 원매체 차단(403) 시 analyze 가
    # 대체 fetch 소스로 씀(item3). 한 줄 보장(공백정규화)·방어 절제. 없으면 줄 생략(하위호환).
    # 토큰별 재검증(방어심층 — 수동 workflow_dispatch 가 pick.js 검증 우회 시 대비): http(s) 도메인만
    # 통과(IP리터럴·비도메인 거부 → analyze 의 fetch 가 SSRF·글로브 타깃 받는 것 차단).
    alt_re = re.compile(r"^https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:[:/]|$)")
    alt = " ".join(t for t in (os.environ.get("PICK_ALT") or "").split() if alt_re.match(t))[:1500]
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
    # 1줄 = URL(불변·dedup·analyze 가 head -n1 로 읽음), 2줄 = '# title: …'(선택·analyze 단서),
    # 3줄 = '# alt: …'(선택·대체 fetch url). 폰공유/스크래퍼 자동분은 2·3줄이 없어 동작 동일(하위호환).
    body = url + "\n" + (f"# title: {title}\n" if title else "") + (f"# alt: {alt}\n" if alt else "")
    (PENDING / name).write_text(body, encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(key + "\n")
    print(f"픽 적재: {name} ← {url}", file=sys.stderr)
    print("NEW=1")


if __name__ == "__main__":
    main()
