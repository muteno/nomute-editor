#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 일일 점검 — 수집함 파이프라인 ①수집건강 ②알고리즘 신호 ③롤백 검토를 한 화면에.
#   운영자가 '섹션 할일/상태' 물을 때(일일 1회) 메인이 먼저 돌려 보고 → docs/curation-algorithm.md §7/§8과 대조.
#   정본 루틴 = CLAUDE.md §🧠 "일일 점검". 읽기 전용(candidates.json 안 건드림).
# 사용: python3 scraper/daily_health.py
import json
import subprocess
import datetime as dt
from collections import Counter
from datetime import timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "viewer" / "candidates.json"
SUBS = ROOT / "push" / "subscriptions.json"
SCRIPTS = ROOT / ".github" / "scripts"
KST = timezone(timedelta(hours=9))
CHECKPOINT = "checkpoint/algo-260619-grade3-promote"   # 최신 알고리즘 분기 라벨(롤백 기준)


def age_h(s, now):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if not t.tzinfo:
            t = t.replace(tzinfo=timezone.utc)
        return (now - t).total_seconds() / 3600
    except Exception:
        return None


def count(script):
    try:
        r = subprocess.run(["python3", str(SCRIPTS / script), "--count"],
                           capture_output=True, text=True, timeout=40)
        return int((r.stdout or "").strip())
    except Exception:
        return None


def git(*args):
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args],
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def main():
    now = dt.datetime.now(timezone.utc)
    nowk = now.astimezone(KST)
    try:
        c = json.loads(CAND.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ candidates.json 로드 실패: {e}")
        return
    print(f"═══ 일일 점검 · {nowk:%Y-%m-%d %H:%M} KST · 후보풀 {len(c)}건 ═══\n")

    # ─────────── ① 수집 건강 ───────────
    ages = [age_h(x.get("first_seen"), now) for x in c]
    valid = [a for a in ages if a is not None]
    newest = min(valid) if valid else None
    fresh4 = sum(1 for a in valid if a < 4)
    fresh24 = sum(1 for a in valid if a < 24)
    print("① 수집 건강")
    if newest is None:
        print("  ⚠️ 수집시각(first_seen) 불명 — 스크랩 점검 필요")
    else:
        f = "✅" if newest < 2 else ("⚠️" if newest < 6 else "❌")
        print(f"  {f} 최신 수집 {newest:.1f}h 전 · 최근4h {fresh4}건 · 최근24h {fresh24}건"
              + ("  (←2h 넘으면 스크랩 지연 의심)" if newest >= 2 else ""))
    nb, ng = count("breaking_judge.py"), count("gate_judge.py")
    if nb is not None and ng is not None:
        f = "✅" if (nb + ng) < 120 else "⚠️"
        print(f"  {f} 미판정 backlog: 속보 {nb} · 경중 {ng} (>120 누적이면 판정 적체 의심)")
    else:
        print("  ⚠️ backlog 카운트 실패(judge 스크립트 점검)")
    try:
        subs = json.loads(SUBS.read_text(encoding="utf-8"))
        print(f"  · 웹푸시 구독자 {len(subs) if isinstance(subs, list) else '?'}명")
    except Exception:
        print("  · 웹푸시 구독자 0명(또는 미생성)")
    # RSS 피드 건강 원장(scraper/obs/feed_health.json 안정본 — 죽은피드 구성 변화시 scrape가 갱신 · 무음 드리프트 방지 260702)
    try:
        fh = json.loads((ROOT / "scraper" / "obs" / "feed_health.json").read_text(encoding="utf-8"))
        # 원소 dict 정규화 — 부분 손상 시 요약줄 출력 후 순회서 터져 '생존'+'원장없음' 이중출력 모순 방지(평의회 260702)
        deadf = [x for x in (fh.get("dead_feeds") or []) if isinstance(x, dict)]
        zomb = [x for x in (fh.get("zombie_feeds") or []) if isinstance(x, dict)]
        okn = fh.get("ok") or 0   # null도 0 표시(리터럴 None 방지) — 임계·표시 기준은 리스트 길이로 단일화
        f = "✅" if len(deadf) <= 5 else "⚠️"
        print(f"  {f} RSS 피드 생존 {okn}/{okn + len(deadf)} (죽음 {len(deadf)})"
              + ("  (←죽음 6↑ = feeds.csv 정리 검토)" if len(deadf) > 5 else ""))
        for x in deadf[:5]:
            print(f"      ✗ {x.get('publisher', '?')} {x.get('title', '')}")
        if len(deadf) > 5:
            print(f"      … 외 {len(deadf) - 5}개 (scraper/obs/feed_health.json)")
        if zomb:   # 응답은 오는데 갱신 멈춘 피드(JTBC 2024-10 멈춤 실측 케이스) — 주간 니치 피드는 일시 오탐 가능
            print(f"  🧟 좀비 피드(응답 OK·24h 발행 0) {len(zomb)}개: "
                  + " · ".join(f"{x.get('publisher', '?')} {x.get('title', '')}" for x in zomb[:4])
                  + (" …" if len(zomb) > 4 else ""))
    except Exception:
        print("  · 피드 건강 원장 없음(다음 scrape 런부터 생성)")

    # ─────────── ② 알고리즘 신호 ───────────
    gd = Counter(x.get("grade") for x in c)
    brk = [x for x in c if x.get("breaking")]
    brk24 = [x for x in brk if (age_h(x.get("first_seen"), now) or 99) < 24]
    bc = sum(1 for x in c if x.get("breaking_candidate"))
    # 승격 구제분(저burst grade3 신선) = compare_collected.promoted_guess와 동일 정의
    promo = [x for x in c if (x.get("grade") or 0) >= 3 and x.get("breaking_candidate")
             and (x.get("burst") or 0) < 3 and "[속보]" not in (x.get("title") or "")
             and "[긴급]" not in (x.get("title") or "")]
    urg = [x for x in brk if (x.get("grade") or 0) >= 2 and (age_h(x.get("first_seen"), now) or 99) < 4]
    print("\n② 알고리즘 신호")
    print(f"  · grade 분포 {{0:{gd.get(0,0)} 1:{gd.get(1,0)} 2:{gd.get(2,0)} 3:{gd.get(3,0)} 미채점:{gd.get(None,0)}}}")
    print(f"  · breaking 확정 {len(brk)}(24h내 {len(brk24)}) · breaking_candidate {bc} · ⬆️저burst승격 {len(promo)}")
    f = "✅" if len(urg) < 8 else "⚠️"
    print(f"  {f} 현재 🚨긴급자격(breaking&grade≥2&<4h) {len(urg)}건"
          + ("  (←8↑면 긴급 과다 의심)" if len(urg) >= 8 else ""))
    print(f"  → 심층 비교: python3 scraper/compare_collected.py  (어제↔오늘 낮 승격·긴급 분포)")

    # ─────────── ③ 롤백 검토 ───────────
    print("\n③ 롤백 검토")
    print(f"  · 알고리즘 분기 라벨 = {CHECKPOINT} (검증완 기준점)")
    git("fetch", "origin", "main", "-q")
    log = git("log", "--oneline", "-15", "origin/main")
    kws = ("긴급", "수집함", "큐레이션", "breaking", "grade", "승격", "푸시", "candidates",
           "scrape", "rubric", "랭킹", "배지", "누적", "신규")
    hits = [ln for ln in log.splitlines() if any(k in ln for k in kws)]
    print(f"  · 최근 큐레이션 관련 커밋(origin/main, 최대 15 중):")
    for ln in hits[:8]:
        print(f"      {ln}")
    if not hits:
        print("      (최근 15커밋에 큐레이션 변경 없음)")
    print(f"  · 롤백 방법: git revert <커밋> 또는 git diff {CHECKPOINT}..origin/main 으로 분기 후 변경 검토")
    print(f"             · _versions/ 백업 폴더에서 개별 파일 복원")
    print("\n[판단] ①②에 ⚠️/❌ 있으면 원인 추적 → 알고리즘 변경 탓이면 ③으로 롤백 검토."
          " 깨끗하면 '수집·알고리즘 정상, 롤백 불요' 보고.")


if __name__ == "__main__":
    main()
