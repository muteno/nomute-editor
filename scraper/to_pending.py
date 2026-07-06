#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
to_pending.py — 스크래퍼 산출(top_urls.txt)을 분석 파이프라인 입구(pending/)로 적재.

  scraper/out/top_urls.txt 의 URL을, 기존 Termux 공유분과 똑같은 포맷
  ( pending/<YYMMDD-HHMMSS>-<NN>.txt · 내용 = URL 한 줄 + 선택 '# alt: …' )으로 떨군다.
  '# alt:' = 같은 사건 cluster_members(스크래퍼 클러스터) — 원매체 차단(403) 시 analyze 가
  대체매체로 본문 회수(픽 경로와 통일 · 엔진=analyze.sh:164~ · 운영자 260629). 없으면 url만(하위호환).
  이미 본 URL(중복)은 건너뛴다 — 같은 주요 기사가 매 수집마다 재분석되는 낭비 방지.

중복 판정 'seen' = 다음의 합집합(정규화 URL 기준):
  - scraper/seen_urls.txt              적재 원장(append-only, 추적됨)
  - pending/*.txt, pending/failed/*.txt 큐에 있거나 실패 격리된 것
  - queue/*.md 의 url: frontmatter      이미 분석 완료된 것

새 URL만 pending/ 에 쓰고 seen_urls.txt 에 append. 새거 없으면 아무것도 안 만든다.
출력: stderr 요약 + stdout 마지막 줄 'NEW=<n>' (워크플로가 커밋 여부 판단에 사용).

이 스크립트는 ② 연결 글루다(① 수집=knews_scraper, ③ 분석=analyze.sh). 정규화 로직은
knews_scraper.normalize_link 단일 원천을 재사용해 URL 동일성 판정이 수집기와 어긋나지 않게 한다.
"""
import glob
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knews_scraper import normalize_link  # 정규화 단일 원천(DRY) — 수집기와 동일 판정

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent  # 레포 루트
TOP = ROOT / "scraper" / "out" / "top_urls.txt"
ART = ROOT / "scraper" / "out" / "articles.json"   # cluster_members 출처(knews_scraper 산출 · to_pending 실행 전 존재)
LEDGER = ROOT / "scraper" / "seen_urls.txt"
PENDING = ROOT / "pending"
QUEUE = ROOT / "queue"

# 같은 사건 대체매체 url 검증 = pick_pending.py 와 동일 패턴(http(s) 도메인만 · 셸/글로브/개행 주입 차단)
_ALT_RE = re.compile(r"^https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:[:/]|$)")


def load_alts():
    """url(link) → '# alt:' 문자열 = 같은 사건 cluster_members(검증 도메인 url·자기 제외·1500자 cap).
    스크래퍼가 articles.json 에 박은 클러스터를 RSS 자동경로(to_pending)에도 픽 경로처럼 심어,
    차단매체(403) 자동수집분도 analyze 가 대체매체로 본문 회수하게 한다(엔진=analyze.sh · 운영자 260629)."""
    alts = {}
    try:
        arts = json.loads(ART.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return alts   # articles.json 없거나 깨짐 = url만(하위호환·graceful)
    if not isinstance(arts, list):
        return alts
    for a in arts:
        if not isinstance(a, dict):
            continue
        link = (a.get("link") or "").strip()
        members = a.get("cluster_members") or []
        if not link or not isinstance(members, list):
            continue
        # ⚠️ _ALT_RE 는 ^앵커(접두)만 검사 → 개행/공백 포함 문자열도 prefix 매칭됨(가짜 '# body:'/'# alt:' 마커 라인 주입 벡터).
        #   그래서 공백/개행(\s) 있는 멤버는 *통째 거부*(실 cluster_members=normalize_link 출력이라 공백 없음·방어심층).
        toks = [m for m in members
                if isinstance(m, str) and m != link and not re.search(r"\s", m) and _ALT_RE.match(m)]
        if toks:
            alts[link] = " ".join(toks)[:1500]
    return alts


def load_seen():
    """이미 시스템에 들어왔던 URL(정규화) 집합 — 원장 ∪ pending ∪ failed ∪ queue."""
    seen = set()
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                seen.add(normalize_link(line))
    for p in glob.glob(str(PENDING / "*.txt")) + glob.glob(str(PENDING / "failed" / "*.txt")):
        try:
            lines = Path(p).read_text(encoding="utf-8").splitlines()
            if lines and lines[0].strip():
                seen.add(normalize_link(lines[0].strip()))
        except OSError:
            pass
    for p in glob.glob(str(QUEUE / "*.md")):
        try:
            for line in Path(p).read_text(encoding="utf-8").splitlines()[:12]:
                m = re.match(r'\s*url:\s*"?([^"\s]+)"?', line)
                if m:
                    seen.add(normalize_link(m.group(1)))
                    break
        except OSError:
            pass
    return seen


def load_active():
    """재픽(수동 PICK) 차단용 = 현재 처리중(pending 비-failed) ∪ 완료(queue)만.
    ⚠️ 실패(pending/failed)·원장(ledger)은 제외 → 한 번 실패한 url을 운영자가 다시 픽 가능(영구차단 해제·운영자 260620 분신술 ⓐ③).
    in-flight면 막아 중복발사 가드 / 실패하면 재픽 허용. 스크래퍼 자동경로의 영구 dedup(load_seen)은 불변(별개)."""
    active = set()
    for p in glob.glob(str(PENDING / "*.txt")):   # PENDING/*.txt = top-level만(failed/ 하위는 glob 미포함 = 자동 제외)
        try:
            lines = Path(p).read_text(encoding="utf-8").splitlines()
            if lines and lines[0].strip():
                active.add(normalize_link(lines[0].strip()))
        except OSError:
            pass
    for p in glob.glob(str(QUEUE / "*.md")):
        try:
            for line in Path(p).read_text(encoding="utf-8").splitlines()[:12]:
                m = re.match(r'\s*url:\s*"?([^"\s]+)"?', line)
                if m:
                    active.add(normalize_link(m.group(1)))
                    break
        except OSError:
            pass
    return active


def main():
    if not TOP.exists():
        print("top_urls.txt 없음 — 수집 결과 없음", file=sys.stderr)
        print("NEW=0")
        return
    urls = [u.strip() for u in TOP.read_text(encoding="utf-8").splitlines() if u.strip()]
    seen = load_seen()

    new = []
    for u in urls:
        key = normalize_link(u)
        if key in seen:
            continue
        seen.add(key)  # 같은 배치 내 중복도 방지
        new.append(u)

    if new:
        PENDING.mkdir(parents=True, exist_ok=True)
        alts = load_alts()   # url → '# alt:'(같은 사건 cluster_members) · 차단매체 403 시 analyze 대체 fetch 소스
        stamp = datetime.now(KST).strftime("%y%m%d-%H%M%S")
        for i, u in enumerate(new, 1):
            alt = alts.get(u, "")
            content = u + "\n" + (f"# alt: {alt}\n" if alt else "")   # alt 비면 url만(폰공유·하위호환 동일)
            (PENDING / f"{stamp}-{i:02d}.txt").write_text(content, encoding="utf-8")
        with LEDGER.open("a", encoding="utf-8") as f:
            for u in new:
                f.write(normalize_link(u) + "\n")

    print(f"수집 {len(urls)}건 중 신규 {len(new)}건 적재 / 중복 {len(urls) - len(new)}건 스킵",
          file=sys.stderr)
    print(f"NEW={len(new)}")


if __name__ == "__main__":
    main()
