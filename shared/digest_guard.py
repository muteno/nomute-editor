#!/usr/bin/env python3
# digest_guard.py — 다이제스트(queue/*.md) 규격·자수 기계 린트 (비차단 · 분신술② NEW-1 · 260703)
#
# 왜: P1 길이 룰(Thread 450·IG 800·자유요약 850~1000)이 모델 '자가 추정'에만 의존 → 실측 괴리 −229~+88자
#     (Thread 상한 초과 4/17건이 "약 430/450" 표기로 통과 = 자가검증 무력화·실측 260702). 지침 3연속 길이
#     교정(v1.18.0/18.1/18.4)이 계측 부재로 계속 샜다 → 저장 직후 실측해 Actions 로그로 가시화.
# 검사(전부 경고만·exit 항상 0 = 비차단): ①블록별 실측 자수 vs 상한/목표선 ②자가표기↔실측 괴리(±60자↑)
#     ③분모 드리프트(Thread≠450·IG≠800 = 구버전 상한 잔존) ④IG 🔎 리드 마커 ⑤자유요약 내 ⚡ 혼입
#     ⑥# 제목 [속보]/[단독] 잔존·title 완전 복붙(IG 헤드 규칙 역가드). Fact 커버리지는 card_gate factcov 몫(별개).
# 사용: python3 shared/digest_guard.py <queue/xxx.md>   (analyze.sh가 저장 직후 호출 · 수동 점검도 동일)
import os, re, sys

def _blk(body, name):
    """### [<name> …] 헤더 다음 ```text 코드블록 본문(없으면 None)."""
    m = re.search(r"^###\s*\[" + re.escape(name) + r"[^\]]*\]\s*\n+```text\n(.*?)\n```", body, re.M | re.S)
    return m.group(1) if m else None

def _clen(s):
    return len(s.replace("\n", ""))   # 개행 제외 실측(분신술② 측정 기준과 동일)

def lint(path):
    raw = open(path, encoding="utf-8").read()
    warns = []
    fmm = re.search(r"^---\s*$(.*?)^---\s*$", raw, re.M | re.S)
    body = raw[fmm.end():] if fmm else raw
    title = ""
    if fmm:
        tm = re.search(r'^title:\s*"?(.*?)"?\s*$', fmm.group(1), re.M)
        title = (tm.group(1).strip() if tm else "")
    h1m = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    h1 = (h1m.group(1).strip() if h1m else "")

    # ① 블록별 실측 자수 + ②표기 괴리 + ③분모 드리프트 (+ ④⑤ 블록 내부 검사)
    for name, lo, hi, hard, denom_std in (("자유요약", 850, 1000, None, None),
                                          ("IG", 600, 800, None, 800),
                                          ("Thread", 0, 450, 500, 450)):
        b = _blk(body, name)
        if b is None:
            warns.append("[{}] 코드블록 미검출 — 골격(### [{} …] + ```text) 확인".format(name, name))
            continue
        n = _clen(b)
        hm = re.search(r"^###\s*\[" + re.escape(name) + r"[^\]\d]*?약?\s*(\d+)\s*(?:/\s*(\d+))?\s*자", body, re.M)
        claim = int(hm.group(1)) if hm else None
        denom = int(hm.group(2)) if (hm and hm.group(2)) else None
        if hi and n > hi:
            extra = ""
            if hard:
                extra = " ⛔플랫폼 하드 {} {}".format(hard, "초과!" if n > hard else "임박")
            warns.append("[{}] 실측 {}자 > 상한 {}자{} (자가표기 {})".format(name, n, hi, extra, claim if claim is not None else "없음"))
        elif lo and n < lo:
            warns.append("[{}] 실측 {}자 < 목표선 {}자 = 과소 활용 (자가표기 {})".format(name, n, lo, claim if claim is not None else "없음"))
        if claim is not None and abs(claim - n) >= 60:
            warns.append("[{}] 자가표기 {} vs 실측 {} = 괴리 {:+d}자".format(name, claim, n, n - claim))
        if denom_std and denom and denom != denom_std:
            warns.append("[{}] 분모 표기 {} ≠ 현행 상한 {} (구버전 상한 드리프트)".format(name, denom, denom_std))
        if name == "IG" and "🔎" not in b:
            warns.append("[IG] 🔎 리드 마커 없음(골격 누락)")
        if name == "자유요약" and "⚡" in b:
            warns.append("[자유요약] 코드블록 안에 ⚡ 출처 혼입(⚡는 IG·Thread 전용 — 복사 시 딸려 나감)")

    # ⑥ # 제목 = IG 헤드 역가드(원문 복붙·매체 태그)
    if h1:
        if re.search(r"\[(속보|단독|긴급|종합)\]", h1):
            warns.append("[# 제목] [속보]/[단독] 류 매체 태그 잔존 — IG 헤드 규칙(새로 짓기) 위반")
        if title and h1 == title:
            warns.append("[# 제목] frontmatter title(원문)과 완전 동일 = 복붙 — 후킹 헤드 미생성")

    base = os.path.basename(path)
    if warns:
        print("DIGEST_LINT ⚠️ {}건 — {}".format(len(warns), base))
        for w in warns:
            print("  ⚠️ " + w)
    else:
        print("DIGEST_LINT ✅ 규격·자수 통과 — " + base)
    return 0   # 비차단(경고 전용) — 하드 차단은 오탐 시 파이프라인을 세우므로 안 함(운영자 승인 전)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용: digest_guard.py <queue/xxx.md>"); sys.exit(0)
    try:
        sys.exit(lint(sys.argv[1]))
    except Exception as e:   # 린트 자체 오류가 분석 파이프라인을 깨지 않게(fail-soft)
        print("DIGEST_LINT ⚠️ 린트 실행 실패(무시): {}".format(e)); sys.exit(0)
