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
    # 닫는 '---' 누락 회귀 카나리아(260704 실측 '중국인 렌터카' — LLM이 frontmatter 닫는 표식 생략 → 뷰어 메타 raw 노출).
    #   생성측(ask/analyze.sh) awk가 이미 닫는 '---'를 보증하므로 정상 파이프라인에선 안 뜸 → 뜨면 그 awk 회귀 신호.
    #   비차단(lint는 return 0 유지) = 저장은 이미 끝난 시점이라 차단 무의미·자동수정(awk)이 정본 방어. 로그 조기발견용.
    if raw.lstrip().startswith("---") and len(re.findall(r"^---\s*$", raw, re.M)) < 2:
        warns.append("frontmatter 닫는 '---' 누락 — 뷰어 메타 raw 노출 위험(생성측 awk 보증 회귀 의심)")
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

# ── 분량 가드(SUMMARY_LEN_GUARD · 260705 · 기본 OFF 카나리아) ─────────────────────────────
# 왜: #1552(effort max→high) 후 IG 630→540자·Thread 415→347자 급감(자유요약 무손상 = 압축 단계만 부실 ·
#     진단 = docs/작업이력.md 260705). 보강 임계 = 지침 목표선 하단(IG 600·Thread 390) — lint 완충 550과
#     별개 축(lint = 경고 소음 억제·guard = 재작성 발동, 값 다름 = 의도). 결빈약(자유요약<800) = 면제(지침
#     "짧음의 근거 = 원문 결 부족" 존중). 호출 = shared/summary_repair.sh (ask.sh·analyze.sh 공용).
REPAIR_IG_LO, REPAIR_TH_LO, REPAIR_FREE_MIN = 600, 390, 800

def repair_check(path):
    """보강 필요 판정 — 'REPAIR ig=N thread=N free=N' 또는 'OK …'/'SKIP …' 1줄. 항상 exit 0(fail-soft)."""
    raw = open(path, encoding="utf-8").read()
    fmm = re.search(r"^---\s*$(.*?)^---\s*$", raw, re.M | re.S)
    body = raw[fmm.end():] if fmm else raw
    vals = {}
    for n in ("자유요약", "IG", "Thread"):
        b = _blk(body, n)
        if b is None:
            print("SKIP {} 블록 미검출".format(n)); return 0
        vals[n] = _clen(b)
    if vals["자유요약"] < REPAIR_FREE_MIN:
        print("OK 결빈약 면제 ig={} thread={} free={}".format(vals["IG"], vals["Thread"], vals["자유요약"])); return 0
    tag = "REPAIR" if (vals["IG"] < REPAIR_IG_LO or vals["Thread"] < REPAIR_TH_LO) else "OK"
    print("{} ig={} thread={} free={}".format(tag, vals["IG"], vals["Thread"], vals["자유요약"]))
    return 0

def _nums(s):
    return set(re.findall(r"\d{2,}", s.replace(",", "")))   # 2자리+ 숫자 토큰(쉼표 정규화 — '5,000'='5000')

def splice(path, cand_path):
    """보강 후보의 IG/Thread 코드블록 '내용'만 검증 후 원본에 이식(헤더·📊 줄·frontmatter 불변 ·
    헤더 자수 라벨은 실측으로 갱신). 블록별 독립 판정 — 검증 실패 블록 = 원본 유지(fail-soft·항상 exit 0).
    후보 펜스는 ```text·``` 둘 다 허용(평의회4 — 언어태그 누락 변동성 흡수 · 원본은 항상 ```text라 무영향).
    Thread 상한·분모 = 현행 450(v1.18.4 정본) — 구 /500 표기 파일도 보강 성공 시 /450로 정규화(lint 드리프트 교정과 동방향)."""
    raw = open(path, encoding="utf-8").read()
    raw_orig = raw
    cand = open(cand_path, encoding="utf-8").read()
    src_nums = _nums(raw_orig)   # 날조 경량 가드 기준 = 원본 다이제스트 전체(frontmatter·자유요약 포함)
    results = []
    for name, hi, hard in (("IG", 800, None), ("Thread", 450, 500)):
        pat = re.compile(r"(^###\s*\[" + name + r"[^\]]*\]\s*\n+```(?:text)?\n)(.*?)(\n```)", re.M | re.S)
        mc, mt = pat.search(cand), pat.search(raw)
        if not mc or not mt:
            results.append("{}: 블록 미검출(후보 {}·원본 {}) — 유지".format(name, bool(mc), bool(mt))); continue
        new, old = mc.group(2), mt.group(2)
        n_new, n_old = _clen(new), _clen(old)
        why = []
        if n_new <= n_old: why.append("증가 아님 {}→{}".format(n_old, n_new))
        if n_new > hi: why.append("상한 {} 초과({})".format(hi, n_new))
        if hard and _clen_hard(new) > hard: why.append("개행 포함 {} > 플랫폼 하드 {}".format(_clen_hard(new), hard))
        if name == "IG" and "🔎" not in new: why.append("🔎 리드 누락")
        if "⚡" not in new and "ⓔ" not in new: why.append("⚡/ⓔ 출처 줄 누락")
        if bool(_DISCLAIMER.search(old)) != bool(_DISCLAIMER.search(new)): why.append("면책 줄 유무 불일치(소실/무단 삽입)")   # 대칭 검증(평의회2 — 역방향 무단 삽입도 차단)
        ofl, nfl = old.strip().split("\n", 1)[0].strip(), new.strip().split("\n", 1)[0].strip()
        if ofl != nfl: why.append("제목 줄 변경")   # 헤드 원문 보존 강제(평의회2·4)
        fab = sorted(x for x in (_nums(new) - _nums(old)) if x not in src_nums)
        if fab: why.append("원본에 없는 숫자 도입({})".format("·".join(fab[:3])))   # 날조 경량 가드(평의회4 — 오탐=원본 유지라 안전)
        if why:
            results.append("{}: 검증 실패({}) — 유지".format(name, " · ".join(why))); continue
        raw = raw[:mt.start(2)] + new + raw[mt.end(2):]
        raw = re.sub(r"^###\s*\[" + name + r"[^\]]*\]", "### [{} — {}/{}자]".format(name, n_new, hi), raw, count=1, flags=re.M)
        results.append("{}: {}→{}자 보강".format(name, n_old, n_new))
    if raw != raw_orig:   # 원자적 쓰기 + 무변경 시 무접촉(평의회2 — truncate 창 제거)
        tmp = path + ".tmp"
        open(tmp, "w", encoding="utf-8").write(raw)
        os.replace(tmp, path)
    print("SPLICE " + " · ".join(results))
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용: digest_guard.py [--repair-check|--splice <후보>] <queue/xxx.md>"); sys.exit(0)
    try:
        if sys.argv[1] == "--repair-check" and len(sys.argv) >= 3:
            sys.exit(repair_check(sys.argv[2]))
        if sys.argv[1] == "--splice" and len(sys.argv) >= 4:
            sys.exit(splice(sys.argv[2], sys.argv[3]))
        sys.exit(lint(sys.argv[1]))
    except Exception as e:   # 린트·가드 자체 오류가 분석 파이프라인을 깨지 않게(fail-soft)
        print("DIGEST_LINT ⚠️ 실행 실패(무시): {}".format(e)); sys.exit(0)
