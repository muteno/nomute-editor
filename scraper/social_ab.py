#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 소셜 A/B 회귀 검증기 — social_burst.py 튜닝(임계·대표 선정·배점) 전후를 '동일 재료(corpus)'로 돌려
#   회귀 없이 바뀌었는지 실측한다(Q417 어긋남 진단→Q427 대표=최신 글 수술 때 쓴 검증 패턴의 상비화 · 운영자 260722 "한 수 반영").
# 비교축: A = 기준 코드(기본 origin/main:scraper/social_burst.py) · B = 워킹트리 social_burst.py
#   → 같은 kept·now·src_total로 cluster_and_score만 A/B 실행(수집기 차이는 비교축 아님 = 재료 고정이 공정성의 핵심).
# 판정 출력: ① 행수·정렬 ② 불변식(burst·age_h·sources·posts 인덱스 페어) ③ 대표(제목·링크) 변경 행
#   ④ B측 대표 계약 = '링크 글 나이 ≈ 칩 age_h'(Q427 최신 글 대표 · 허용오차 0.11h=반올림 0.1h 마진) 위반 행.
# 읽기 전용(레포 파일·산출 json 안 건드림) · rc=0(진단 도구 — 판정은 출력, 게이트 아님).
#
# 사용:
#   python3 scraper/social_ab.py                      # 라이브 수집 1회 → A/B 비교(네트워크 필요 · Actions/로컬)
#   python3 scraper/social_ab.py --save-corpus f.json # 이번 재료(필터 후 kept)를 저장 = 재현 고정
#   python3 scraper/social_ab.py --corpus f.json      # 저장 재료로 비교(무네트워크·결정론 — 튜닝 반복은 이 모드)
#   python3 scraper/social_ab.py --base <git-ref>     # 기준 코드 지정(기본 origin/main)
# ⚠️ 수동 실행 전용 — 훅·pre-commit·CI 편입 금지(라이브 모드 = 네트워크 발사 · smoke 상비 원칙과 동일 축).
import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SB_REL = "scraper/social_burst.py"


def _load(py_path, name):
    """social_burst 모듈을 이름 충돌 없이 로드(main()은 __main__ 가드라 실행 안 됨)."""
    spec = importlib.util.spec_from_file_location(name, py_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod


def _load_base(ref):
    txt = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{SB_REL}"],
                         capture_output=True, text=True)
    if txt.returncode != 0:
        sys.exit(f"기준 코드 로드 실패: git show {ref}:{SB_REL} → {txt.stderr.strip()}")
    with tempfile.NamedTemporaryFile("w", suffix="_social_burst_base.py", delete=False) as f:
        f.write(txt.stdout)
        return _load(f.name, "social_ab_base")


def _corpus_live(B):
    """라이브 수집 1회 → main()과 동일한 컷(정치·노이즈·공론화 게이트) 후 kept 반환(수집·필터는 B 기준)."""
    now = datetime.now(B.KST)
    posts = B.fetch_live(now)
    def _txt(p): return p.get("title", "") + " " + p.get("desc", "")
    kept = [p for p in posts
            if not B.is_political(_txt(p))
            and not B.is_noise(p["title"], p.get("source", ""))
            and (not B.TOPIC_GATE or B.is_controversy(_txt(p)))]
    return now, kept


def main():
    ap = argparse.ArgumentParser(description="social_burst A/B 회귀 검증(동일 재료 전후 비교)")
    ap.add_argument("--base", default="origin/main", help="기준 코드 git ref(기본 origin/main)")
    ap.add_argument("--corpus", help="저장 재료 json으로 비교(무네트워크)")
    ap.add_argument("--save-corpus", help="이번 재료를 json으로 저장(재현 고정)")
    args = ap.parse_args()

    B = _load(str(REPO / SB_REL), "social_ab_head")
    A = _load_base(args.base)

    if args.corpus:
        D = json.load(open(args.corpus))
        now = datetime.fromisoformat(D["now"])
        kept = [{**p, "ts": datetime.fromisoformat(p["ts"]) if p.get("ts") else None} for p in D["kept"]]
        print(f"재료 = {args.corpus} (kept {len(kept)}건 · now {D['now'][:16]})")
    else:
        now, kept = _corpus_live(B)
        print(f"재료 = 라이브 수집(필터 후 kept {len(kept)}건)")
    if args.save_corpus:
        ser = [{**p, "ts": p["ts"].isoformat() if p.get("ts") else None} for p in kept]
        json.dump({"now": now.isoformat(), "kept": ser}, open(args.save_corpus, "w"), ensure_ascii=False)
        print(f"재료 저장 → {args.save_corpus}")

    src_total = Counter(p["source"] for p in kept)
    rows_a = A.cluster_and_score(kept, now, src_total)
    rows_b = B.cluster_and_score(kept, now, src_total)
    ts_of = {p["url"]: p["ts"] for p in kept if p.get("url") and p.get("ts")}
    def _age(u):
        return round((now - ts_of[u]).total_seconds() / 3600, 1) if u in ts_of else None

    print(f"\nA = {args.base} · B = 워킹트리 — 클러스터 A {len(rows_a)}행 / B {len(rows_b)}행"
          + ("" if len(rows_a) == len(rows_b) else " ⚠ 행수 다름(임계·병합 구조 변경)"))
    n = min(len(rows_a), len(rows_b))
    inv_bad = [i for i in range(n) if any(rows_a[i][k] != rows_b[i][k] for k in ("burst", "age_h", "sources", "posts"))]
    rep_chg = [i for i in range(n) if rows_a[i]["url"] != rows_b[i]["url"] or rows_a[i]["title"] != rows_b[i]["title"]]
    print(("✅" if not inv_bad else "⚠") + f" 불변식(burst·age_h·sources·posts) 동일 {n - len(inv_bad)}/{n}행"
          + (f" — 다른 행 idx {inv_bad}(점수·구조 튜닝 시 여기로 나타남)" if inv_bad else " — 점수·랭킹 무영향"))
    print(f"· 대표(제목/링크) 변경 {len(rep_chg)}행")
    for i in rep_chg:
        a, b = rows_a[i], rows_b[i]
        print(f"  [{'·'.join(b['sources'])}] 칩 {b['age_h']}h")
        print(f"    A: 링크나이={_age(a['url'])}h | {a['title'][:40]} | {a['url'][:60]}")
        print(f"    B: 링크나이={_age(b['url'])}h | {b['title'][:40]} | {b['url'][:60]}")
    viol = [r for r in rows_b if r["url"] in ts_of and abs(_age(r["url"]) - r["age_h"]) > 0.11]
    print(("✅" if not viol else "⚠") + f" B 대표 계약(링크 글 나이=칩 age_h · Q427) 위반 {len(viol)}행"
          + (f" — {[r['title'][:24] for r in viol]}" if viol else ""))


if __name__ == "__main__":
    main()
