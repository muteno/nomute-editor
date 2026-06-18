#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 속보 2차 판정 — viewer/candidates.json 의 속보후보(breaking_candidate)를 Claude(claude -p)
# 1콜 배치로 '긴급 속보인가' 판정 → breaking=true/false 확정.
# 사용자 확정 기준 = **급발(velocity) 사건만 push**(사고·화재·선고 등) / 행정·정책발표·의료정책 = 컷(수집함行).
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
CAND = ROOT / "viewer" / "candidates.json"
MODEL = os.environ.get("BREAKING_MODEL", "claude-opus-4-8")

RUBRIC = """너는 한국 뉴스 데스크의 속보 판정자다. 아래 사건 제목들이 각각 '긴급 속보(breaking news)'인지 판정하라.

[속보 O — 긴급·돌발 사건]
- 사고·화재·재난·폭발·붕괴·추락·침몰·정전·붕괴 등 돌발 사고
- 사망·부상·인명피해·실종 등 인적 피해
- 전국적 이목을 끈 대형 사건의 선고·판결·구속(대형 참사·연쇄·무차별·고위공직자급 — 개별 단일 사건 제외)
- 전쟁·테러·대형 강력범죄·충격적 사건
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

[속보 X — 긴급하지 않음(보도가치 있어도 '속보'는 아님 → 수집함에서 따로 봄)]
- 순수 행정 공지·보도자료·정책/제도 발표·개정 예고 (사건 발생 없음)
- 인터뷰·비전·계획·전망·분석·통계 발표
- 의료/복지 정책 발표(긴급 사건이 아닌 경우)
- 협회·기관 일상 운영(가입·예약·출시·개최·승인 등)
- 개별·단일 피의자 형사사건의 선고·판결·구형·항소심·기소·구속(전국적 대형·화제 아닌 일상 강력범죄 포함) — 규모·대중 주목 없으면 긴급 아님

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
    try:
        p = subprocess.run(
            ["claude", "-p", "--model", MODEL, "--effort", "max",
             "--disallowedTools",
             "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,WebFetch,WebSearch,Read,Glob,Grep",
             "--max-turns", "1"],
            input=prompt, capture_output=True, text=True, timeout=300)
    except Exception as e:  # noqa: BLE001
        return {}, 1, f"{type(e).__name__}: {e}"
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
    print(f"판정 대상 {len(pending)}건 (모델 {MODEL} · rubric {RUBRIC_VER})")
    items = [(str(i), c.get("title", "")) for i, c in enumerate(pending)]
    verdicts, rc, err = judge(items)
    if rc != 0 or not verdicts:
        # 실패 = 도장 안 찍음 → 다음 디스패치에서 재시도(조용한 누락 방지).
        print(f"::warning::속보 판정 실패(rc={rc}) — 다음 런 재시도. err={(err or '')[:300]}")
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
    CAND.write_text(json.dumps(cands, ensure_ascii=False), encoding="utf-8")
    print(f"판정 완료: 🚨속보 {nbreak}건 / 후보 {len(pending)}건 (rubric {RUBRIC_VER})")
    for i, c in enumerate(pending):
        if verdicts.get(str(i)):
            print(f"  🚨 {c.get('title', '')[:54]}")


if __name__ == "__main__":
    main()
