#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 속보 2차 판정 — viewer/candidates.json 의 '미판정 속보후보'(breaking_candidate=true 이고
# 아직 'breaking' 키 없음)를 Claude(claude -p) 1콜 배치로 '긴급 속보인가' 판정 → breaking=true/false 확정.
# 사용자 확정 기준 = **급발(velocity) 사건만 push** (사고·화재·선고 등) / 행정·정책발표·의료정책 = 컷(수집함行).
# 호출: breaking-judge.yml 에서 CLAUDE_CODE_OAUTH_TOKEN 환경으로 실행(claude CLI 필요).
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # .github/scripts → repo root
CAND = ROOT / "viewer" / "candidates.json"
MODEL = os.environ.get("BREAKING_MODEL", "claude-opus-4-8")

RUBRIC = """너는 한국 뉴스 데스크의 속보 판정자다. 아래 사건 제목들이 각각 '긴급 속보(breaking news)'인지 판정하라.

[속보 O — 긴급·돌발 사건만]
- 사고·화재·재난·폭발·붕괴·추락·침몰·정전 등 돌발 사고
- 사망·인명피해·실종 등 대형 인적 피해
- 주요 법원 선고·판결·구속·체포(중대 사건)
- 전쟁·테러·대형 강력범죄·충격적 사건
- 급박한 정치·경제 충격(긴급 발표, 폭락, 디폴트 등)

[속보 X — 긴급하지 않음(보도가치 있어도 '속보'는 아님 → 수집함에서 따로 봄)]
- 행정 공지·보도자료·정책/제도 발표·개정 예고
- 인터뷰·비전·계획·전망·분석·통계 발표
- 의료/복지 정책 발표(긴급 사건이 아닌 경우)
- 협회·기관 일상 운영(가입·예약·출시·개최·승인 등)

규칙: 각 사건을 정확히 한 줄씩, "<번호>\\t<YES|NO>" 형식으로만 출력한다(설명·머리말 금지).
"""


def judge(items):
    """items=[(idx_str, title)] → ({idx_str: bool}, rc, stderr)."""
    listing = "\n".join(f"{i}\t{t}" for i, t in items)
    prompt = f"{RUBRIC}\n[사건 목록]\n{listing}\n\n[판정 출력]"
    try:
        p = subprocess.run(
            ["claude", "-p", "--model", MODEL,
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
        k = k.strip()
        v = v.strip().upper()
        if v.startswith("Y"):
            verdicts[k] = True
        elif v.startswith("N"):
            verdicts[k] = False
    return verdicts, p.returncode, p.stderr


def main():
    cands = json.loads(CAND.read_text(encoding="utf-8"))
    pending = [c for c in cands
               if c.get("breaking_candidate") and "breaking" not in c]
    if not pending:
        print("미판정 속보후보 없음 — 종료")
        return
    print(f"판정 대상 {len(pending)}건 (모델 {MODEL})")
    items = [(str(i), c.get("title", "")) for i, c in enumerate(pending)]
    verdicts, rc, err = judge(items)
    if rc != 0 or not verdicts:
        # 실패 = breaking 미설정 유지 → 다음 디스패치에서 재시도(조용한 누락 방지).
        print(f"::warning::속보 판정 실패(rc={rc}) — 다음 런 재시도. err={ (err or '')[:300] }")
        sys.exit(0)
    nbreak = 0
    for i, c in enumerate(pending):
        v = verdicts.get(str(i))
        if v is None:
            continue  # 누락분은 미판정 유지(다음 런 재시도)
        c["breaking"] = bool(v)       # pending 은 cands 원소 참조 → 직접 반영
        if v:
            nbreak += 1
    CAND.write_text(json.dumps(cands, ensure_ascii=False), encoding="utf-8")
    print(f"판정 완료: 🚨속보 {nbreak}건 / 후보 {len(pending)}건")
    for i, c in enumerate(pending):
        if verdicts.get(str(i)):
            print(f"  🚨 {c.get('title', '')[:54]}")


if __name__ == "__main__":
    main()
