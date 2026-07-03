#!/usr/bin/env python3
# digest_guard.py — 다이제스트(queue/*.md) 규격·자수 기계 린트 (비차단 · 분신술② NEW-1 · 260703 · 검증5 정밀화)
#
# 왜: P1 길이 룰(Thread 450·IG 800·자유요약 850~1000)이 모델 '자가 추정'에만 의존 → 실측 괴리 −229~+88자
#     (Thread 상한 초과 4/17건이 "약 430/450" 표기로 통과 = 자가검증 무력화·실측 260702). 지침 3연속 길이
#     교정(v1.18.0/18.1/18.4)이 계측 부재로 계속 샜다 → 저장 직후 실측해 Actions 로그로 가시화.
# 검사(전부 비차단·exit 항상 0): ⚠️급 = 상한 초과(하드 500은 개행 포함 실카운트)·⚡ 혼입·제목 복붙/[속보] 잔존
#     / ℹ️급(정보성) = 과소 활용·자가표기 괴리·분모 드리프트 — 2단 분리로 진짜 신호가 안 묻히게(검증5).
# 카운트 기준 = 개행 제외(분신술② 실측·PROJECT_MEMORY 사례와 정합) · 면책 줄("⚠️ 본문 내용은…")은 지침
#     규정("면책 줄은 글자수 카운트 제외")대로 빼고 센다 · 플랫폼 하드 500 판정만 개행 포함(Threads 실카운트 통설).
# 사용: python3 shared/digest_guard.py <queue/xxx.md>   (analyze.sh·ask.sh가 저장 직후 호출 · 수동 점검 동일)
import os, re, sys

_DISCLAIMER = re.compile(r"^⚠️ 본문 내용은.*$", re.M)   # 편향 가드 면책 한 줄(지침: 카운트 제외)

def _blk(body, name):
    """### [<name> …] 헤더 다음 ```text 코드블록 본문(없으면 None)."""
    m = re.search(r"^###\s*\[" + re.escape(name) + r"[^\]]*\]\s*\n+```text\n(.*?)\n```", body, re.M | re.S)
    return m.group(1) if m else None

def _clen(s):
    return len(_DISCLAIMER.sub("", s).replace("\n", ""))   # 개행·면책 제외 실측

def _clen_hard(s):
    # 플랫폼 하드 상한 판정 = 물리 총량(면책 줄도 실제 게시물에 포함되므로 안 뺌·개행 포함 — 재검증11)
    return len(s)

def _claim(body, name):
    """헤더의 자가표기 자수·분모 추출 — '약 460/500자'·'728/800자'·'936자' 대응.
    미치환 플레이스홀더(N/800자)는 claim=None(오파싱 방지·검증5)."""
    hm = re.search(r"^###\s*\[" + re.escape(name) + r"[^\]]*?약?\s*([\d,]+|N)\s*(?:/\s*([\d,]+))?\s*자", body, re.M)
    if not hm:
        return None, None
    c = hm.group(1)
    claim = None if c == "N" else int(c.replace(",", ""))
    denom = int(hm.group(2).replace(",", "")) if hm.group(2) else None
    return claim, denom

def lint(path):
    raw = open(path, encoding="utf-8").read()
    warns, infos = [], []
    fmm = re.search(r"^---\s*$(.*?)^---\s*$", raw, re.M | re.S)
    body = raw[fmm.end():] if fmm else raw
    title = title_ko = ""
    if fmm:
        tm = re.search(r'^title:\s*"?(.*?)"?\s*$', fmm.group(1), re.M)
        title = (tm.group(1).strip() if tm else "")
        tk = re.search(r'^title_ko:\s*"?(.*?)"?\s*$', fmm.group(1), re.M)
        title_ko = (tk.group(1).strip() if tk else "")
    h1m = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    h1 = (h1m.group(1).strip() if h1m else "")

    # 블록별: 실측 자수(개행·면책 제외) vs 상한/목표선 + 자가표기 괴리 + 분모 드리프트
    # IG 하한 550(지침 목표선 600에서 완충 — 600이면 최근 17건 중 10건 경고 = 늑대소년·검증9 실측 → 550이면 4건).
    for name, lo, hi, hard, denom_std in (("자유요약", 850, 1000, None, None),
                                          ("IG", 550, 800, None, 800),
                                          ("Thread", 390, 450, 500, 450)):
        b = _blk(body, name)
        if b is None:
            infos.append("[{}] 코드블록 미검출 — 골격(### [{} …] + ```text) 확인".format(name, name))
            continue
        n = _clen(b)
        claim, denom = _claim(body, name)
        if hi and n > hi:
            warns.append("[{}] 실측 {}자 > 상한 {}자 (자가표기 {})".format(name, n, hi, claim if claim is not None else "없음"))
        elif lo and n < lo:
            infos.append("[{}] 실측 {}자 < 완충 하한 {}자 = 과소 활용 의심 (자가표기 {})".format(name, n, lo, claim if claim is not None else "없음"))
        if hard and _clen_hard(b) > hard:   # 플랫폼 하드 상한 = 개행 포함 실카운트로 판정(검증5)
            warns.append("[{}] ⛔ 개행 포함 {}자 > 플랫폼 하드 {} — 게시 시 잘림 위험".format(name, _clen_hard(b), hard))
        if claim is not None and abs(claim - n) >= 60:
            infos.append("[{}] 자가표기 {} vs 실측 {} = 괴리 {:+d}자".format(name, claim, n, n - claim))
        if denom_std and denom and denom != denom_std:
            infos.append("[{}] 분모 표기 {} ≠ 현행 상한 {} (구버전 상한 드리프트)".format(name, denom, denom_std))
        if name == "IG" and "🔎" not in b:
            infos.append("[IG] 🔎 리드 마커 없음(골격 누락)")
        if name == "자유요약" and "⚡" in b:
            warns.append("[자유요약] 코드블록 안에 ⚡ 출처 혼입(⚡는 IG·Thread 전용 — 복사 시 딸려 나감)")

    # # 제목 = IG 헤드 역가드(원문·번역 복붙 + 매체 태그) — title_ko(외신 번역)와도 대조(검증5)
    if h1:
        if re.search(r"\[(속보|단독|긴급|종합)\]", h1):
            warns.append("[# 제목] [속보]/[단독] 류 매체 태그 잔존 — IG 헤드 규칙(새로 짓기) 위반")
        if (title and h1 == title) or (title_ko and h1 == title_ko):
            warns.append("[# 제목] frontmatter title{}과 완전 동일 = 복붙 의심(후킹 헤드 미생성 또는 title 원문 보존 위반 — 둘 중 하나)".format("_ko" if (title_ko and h1 == title_ko) else ""))

    base = os.path.basename(path)
    if warns or infos:
        print("DIGEST_LINT {} ⚠️{}건 ℹ️{}건 — {}".format("⚠️" if warns else "ℹ️", len(warns), len(infos), base))
        for w in warns:
            print("  ⚠️ " + w)
        for i in infos:
            print("  ℹ️ " + i)
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
