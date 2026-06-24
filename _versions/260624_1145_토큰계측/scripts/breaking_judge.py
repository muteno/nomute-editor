#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 속보 2차 판정 — viewer/candidates.json 의 속보후보(breaking_candidate)를 Claude(claude -p)
# 1콜 배치로 '긴급 속보인가' 판정 → breaking=true/false 확정.
# 사용자 확정 기준 = **급발(velocity) 사건만 push**(사고·화재·재난 등 / 개별 형사 선고·사법결과는 전국적 대형 아니면 컷 — RUBRIC 260618) / 행정·정책발표·의료정책 = 컷(수집함行).
#
# 드리프트 차단(analyze.sh guidelines_version 철학과 동일): RUBRIC 내용 해시를 breaking_rubric 으로
# 도장 → RUBRIC 한 바이트라도 바뀌면 같은 사건이 '미판정'으로 되살아나 재판정된다(조용한 stale 차단).
#
# 모드:
#   python3 breaking_judge.py            # 미판정 후보 판정 → candidates.json 갱신
#   python3 breaking_judge.py --count    # 미판정(재판정 포함) 후보 수만 출력(게이트용, claude 미호출)
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # .github/scripts → repo root
sys.path.insert(0, str(ROOT / "shared"))
from claude_py import run_claude   # 쿼터 한도 시 대체 계정 자동 전환(account failover · SSOT)  # noqa: E402
CAND = ROOT / "viewer" / "candidates.json"
MODEL = os.environ.get("BREAKING_MODEL", "claude-opus-4-8")
CHUNK = int(os.environ.get("BREAKING_CHUNK", "40"))             # 한 Claude 콜당 제목 수(작을수록 출력 truncation 0 — gate_judge와 동일·후보 풀 커져도 절단 0)
MAX_PER_RUN = int(os.environ.get("BREAKING_MAX_PER_RUN", "80")) # 한 런당 판정 상한(타임아웃 전 완료·커밋 보장 — 나머지는 self-gate 재디스패치가 점진 처리)

RUBRIC = """너는 한국 뉴스 데스크의 속보 판정자다. 아래 사건 제목들이 각각 '긴급 속보(breaking news)'인지 판정하라.

[속보 O — 긴급·돌발 사건]
- 사고·화재·재난·폭발·붕괴·추락·침몰·정전·붕괴 등 돌발 사고
- 사망·부상·인명피해·실종 등 인적 피해 — **단 사고·화재·재난·다수피해 기인**(개별·단일 강력범죄의 소수 피해는 아래 🔪 게이트)
- 전국적 이목을 끈 대형 사건의 선고·판결·구속(대형 참사·연쇄·무차별·고위공직자급 — 개별 단일 사건 제외)
- 테러·대형 강력범죄·충격적 사건 (⚠️ 전쟁·해외 군사충돌은 아래 🌐 해외 게이트 적용)
- 급박한 정치·경제 충격(긴급 발표, 폭락, 디폴트 등)

⚠️ 가장 중요 — '사건 본질' 우선 판정:
제목이 '당국 조사·감독·수사·대응·처벌·착수' 같은 행정 동사를 앞세워도, 그 바탕에
사고·화재·사망·피해·범죄가 **실제로 발생**했으면 속보(O)다. 행정 동사에 휘둘리지 말고
"무슨 일이 벌어졌나(사건 발생 여부)"로 판정하라.
  예) "또 끼임사고…노동부 기획감독 착수" → 끼임사고가 발생함 = O
  예) "OO 화재 났는데 소방당국 조사" → 화재 발생 = O
⚠️ 단, '긴급'은 **방금 터진 사건 + (대형·다수 피해·전국적 주목)**이다. 개별·단일 피의자의 일상
형사사건(살인·살인미수·폭행·사기 등)은 사안이 중대해도 **규모·대중 주목이 없으면 긴급이 아니다(X)**.
특히 **선고·판결·구형·항소심·기소·구속영장 등 '사법 절차 결과'**는 이미 지난 개별 사건의 후속(급발 아님)
이라 → 전국적 대형 사건(대형 참사·연쇄·무차별·고위공직자 등)이 아니면 X(수집함에서 일반 기사로 본다).

🌐 **해외 군사·전쟁·국제충돌 게이트 (운영자 260622 — 너무 빈번해 피로):**
외국 영토·외국 간 군사충돌·교전·공습·폭격·미사일·드론·격추·포격 등은
**사망 10명 이상이 제목에 명시**됐거나 **한국 직접영향(한국인·교민·재외국민·한국기업·한국군 피해/연루)**일 때만 O.
그 외(소규모·사망수 미명시·한국 무관)는 **X**. (단 **전면전 발발·대규모 침공 개시·선전포고** 등 전쟁 *자체의 시작*은 규모 자명 = O.)
  예) "이스라엘 공습 5명 사망"(10명↓) → X · "모스크바향 드론 59대 격추"(사망 미명시) → X · "가자 공습 12명 사망"(10명+) → O · "한국인 인질 피살"(한국영향) → O

🔪 **개별 강력범죄 소수피해 게이트:**
살인·사기·폭행·보이스피싱 등 **개별·단일 사건의 소수(수명) 사망/피해**는 **다수·무차별·연쇄·전국적 공분/화제**가 아니면 **X**(사망이 있어도).
⚠️ 단 **사고·화재·재난·붕괴·중독 등 *사고성***은 그대로 O(이 게이트 미적용).
  예) "보이스피싱 모자 숨진채"·"흉기 휘두르고 자해" → 개별 = X · "어린이집 황화수소 9명 후송" → 다수·사고 = O

[속보 X — 긴급하지 않음(보도가치 있어도 '속보'는 아님 → 수집함에서 따로 봄)]
- 순수 행정 공지·보도자료·정책/제도 발표·개정 예고 (사건 발생 없음)
- 인터뷰·비전·계획·전망·분석·통계 발표
- 의료/복지 정책 발표(긴급 사건이 아닌 경우)
- 협회·기관 일상 운영(가입·예약·출시·개최·승인 등)
- 개별·단일 피의자 형사사건의 선고·판결·구형·항소심·기소·구속(전국적 대형·화제 아닌 일상 강력범죄 포함) — 규모·대중 주목 없으면 긴급 아님
- 해외 군사·전쟁·국제충돌 중 사망 10명 미만(또는 미명시)·한국 무관 (🌐 게이트)
- 개별·단일 강력범죄의 소수 사망/피해 — 다수·무차별·전국화제 아닌 것 (🔪 게이트)
- 당국 제재·조사·감독·과징금·시정명령 등 규제/행정 조치(실제 사고·사망·화재 발생 없는 것 — 공정위·국세청·금감원·당국 처분 등)

규칙: 각 사건을 정확히 한 줄씩, "<번호>\\t<YES|NO>" 형식으로만 출력한다(설명·머리말 금지).
"""
RUBRIC_VER = hashlib.sha256(RUBRIC.encode("utf-8")).hexdigest()[:12]


def needs_judging(c):
    """속보후보이고, 아직 현재 RUBRIC 버전으로 판정되지 않았으면 True(미판정 or rubric 변경)."""
    return bool(c.get("breaking_candidate")) and c.get("breaking_rubric") != RUBRIC_VER


def judge(items):
    """items=[(idx_str, title)] → ({idx_str: bool}, rc, stderr)."""
    listing = "\n".join(f"{i}\t{(t or '').replace(chr(9), ' ').replace(chr(10), ' ').replace(chr(13), ' ')}" for i, t in items)   # 탭/개행 제거(idx 매핑 보호)
    prompt = f"{RUBRIC}\n[사건 목록]\n{listing}\n\n[판정 출력]"
    p, rc, err = run_claude(
        ["claude", "-p", "--model", MODEL, "--effort", "max",
         "--disallowedTools",
         "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,WebFetch,WebSearch,Read,Glob,Grep",
         "--max-turns", "1"],
        prompt, timeout=300)   # 쿼터 한도면 대체 계정 1회 전환·재시도(account failover)
    if p is None:
        return {}, rc, err
    verdicts = {}
    for line in (p.stdout or "").splitlines():
        if "\t" not in line:
            continue
        k, _, v = line.partition("\t")
        v = v.strip().upper()
        if v.startswith("Y"):
            verdicts[k.strip()] = True
        elif v.startswith("N"):
            verdicts[k.strip()] = False
    return verdicts, p.returncode, p.stderr


def main():
    cands = json.loads(CAND.read_text(encoding="utf-8"))
    pending = [c for c in cands if needs_judging(c)]

    if "--count" in sys.argv:           # 게이트용 — 숫자만 출력, claude 미호출
        print(len(pending))
        return

    if not pending:
        print("미판정 속보후보 없음 — 종료")
        return
    total = len(pending)
    pending.sort(key=lambda c: c.get("first_seen") or "", reverse=True)   # 최신(최근 등장) 먼저 판정 → 갓 뜬 속보 우선
    pending = pending[:MAX_PER_RUN]   # 이번 런 상한 — 나머지는 다음 디스패치(self-gate)가 이어 판정(점진 클리어)
    print(f"판정 대상 {len(pending)}건 (전체 미판정 {total} · 모델 {MODEL} · rubric {RUBRIC_VER} · 청크 {CHUNK})")
    verdicts = {}
    for start in range(0, len(pending), CHUNK):       # 청크별 독립 콜 — 일부 실패해도 나머지 도장
        chunk = pending[start:start + CHUNK]
        items = [(str(start + j), c.get("title", "")) for j, c in enumerate(chunk)]
        v, rc, err = judge(items)
        if rc != 0 or not v:
            print(f"::warning::청크 {start}~ 속보 판정 실패(rc={rc}) — 미도장 유지(다음 런 재시도). err={(err or '')[:200]}")
            continue
        verdicts.update(v)
    if not verdicts:
        # 전 청크 실패 = 도장 안 찍음 → 다음 디스패치에서 재시도(조용한 누락 방지).
        print("::warning::속보 판정 전 청크 실패 — 다음 런 재시도")
        sys.exit(0)
    nbreak = 0
    for i, c in enumerate(pending):
        v = verdicts.get(str(i))
        if v is None:
            continue  # 누락분 = 미도장 유지(다음 런 재시도)
        c["breaking"] = bool(v)            # pending 은 cands 원소 참조 → 직접 반영
        c["breaking_rubric"] = RUBRIC_VER  # 판정 도장(이 rubric 버전으로 판정됨)
        if v:
            nbreak += 1
    import tempfile, os                          # 원자 쓰기 — 절단 시 candidates.json 전체 이력 소실 방지(to_candidates와 일관)
    _fd, _tmp = tempfile.mkstemp(dir=str(CAND.parent), suffix=".tmp")
    with os.fdopen(_fd, "w", encoding="utf-8") as _f:
        _f.write(json.dumps(cands, ensure_ascii=False))
    os.replace(_tmp, CAND)
    print(f"판정 완료: 🚨속보 {nbreak}건 / 후보 {len(pending)}건 (rubric {RUBRIC_VER})")
    for i, c in enumerate(pending):
        if verdicts.get(str(i)):
            print(f"  🚨 {c.get('title', '')[:54]}")


if __name__ == "__main__":
    main()
