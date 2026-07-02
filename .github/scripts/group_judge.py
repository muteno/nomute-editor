#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 사건 묶기 판정(group_judge) — 토큰 클러스터링서 갈라진 '같은 사건' 후보 그룹을 Claude가 확정(YES/NO).
#   운영자 260702: "자동 병합 안 해도 오차 없이 묶이게" → 기계(same_topic)가 후보 그룹만 추리고,
#   AI가 '같은 실제 사건'인지 확정해야만 뷰어가 병합 표시(mergeDecorate 파이프 재사용 = 수동 병합과 동일 대우).
#   렉시컬 단독 병합은 금지 선례(260625 autopick: 안산↔청주 폭발 0.40 오접합) — AI 백스톱이 이 판정의 존재 이유.
# 모델 = opus 4.8 기본(운영자 260702 "탄탄하게" — autopick _ai_same과 동일 판정유형 선례) · --safe-mode 지원 · 폴오버 SSOT(claude_py) 경유.
# 도장 = 각 멤버 entry에 group_rubric(그룹구성해시+룰버전) → 같은 구성 재판정 0 · 멤버 변동 시 해시 바뀌어 자동 재판정.
#   YES → 멤버 전원에 group_id(대표 url) / NO → 도장만(group_id 제거) = 뷰어 병합 억제.
# 사용:
#   python3 group_judge.py --count    # 미판정 그룹 수만 출력(게이트용, claude 미호출)
#   python3 group_judge.py            # 판정 + candidates.json 도장(원자 쓰기)
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # .github/scripts → repo root
sys.path.insert(0, str(ROOT / "shared"))
from claude_py import run_claude   # 쿼터 한도 시 대체 계정 자동 전환(account failover · SSOT · gate_judge와 동일 경로)  # noqa: E402

CAND = ROOT / "viewer" / "candidates.json"
MODEL = os.environ.get("GROUP_MODEL", "claude-opus-4-8")   # 사건 동일성 = 정밀 판정(장소·주체 구분) — opus 기본(운영자 260702 · sonnet 강등 스위치 = 이 env)
EFFORT = os.environ.get("GROUP_EFFORT", "").strip()
SAFE = os.environ.get("GROUP_SAFE", "0").strip().lower() not in ("0", "false", "no", "")
MAX_PER_RUN = int(os.environ.get("GROUP_MAX_PER_RUN", "20"))   # 한 런 판정 그룹 상한(배치 1콜)
MIN_CROSS = int(os.environ.get("GROUP_MIN_CROSS", "3"))        # 그룹 대상 최소 cross(2 단발 잡음까지 묶는 건 낭비 — 파편화는 다매체 사건 문제)
MAX_SIZE = int(os.environ.get("GROUP_MAX_SIZE", "8"))          # 그룹 크기 상한 — 초과 = over-merge 의심(knews MEGA 정신·실측 x90 호남반도체 chain) → 판정 제외.
#   실제 파편화(260628 진단)는 3~6장 규모 — 상한 8이면 제목 전부를 프롬프트에 실어 판정 신뢰↑ + 거대 병합(cross 폭발·카드 수십 장 접힘) 원천 차단.

RUBRIC = """너는 한국 뉴스 데스크의 사건 동일성 판정자다. 아래 각 그룹의 기사 제목들이 전부 '같은 실제 사건'(같은 시간·장소·주체의 단일 사건 또는 그 직접 후속보도)을 다루면 YES, 하나라도 다른 사건이면 NO로 판정하라.
- 주의: 템플릿이 같아도 장소·주체가 다르면 다른 사건이다(예: "안산 공장 폭발" vs "청주 공장 폭발" = NO).
- 같은 사건의 후속·반응·상보(사망자 증가, 수사 착수, 정부 반응)는 YES.
- 확신이 없으면 NO(보수 — 잘못 묶는 것보다 안 묶는 게 낫다).
출력은 각 그룹당 정확히 한 줄, `G<번호>: YES` 또는 `G<번호>: NO` 형식만. 다른 텍스트 금지."""
RUBRIC_VER = hashlib.sha256(RUBRIC.encode("utf-8")).hexdigest()[:12]

# ── tokenize/same_topic — knews_scraper 정본 우선, 폴백 미러(daily_health._get_tokenizer 선례 · feedparser 없는 환경 대비) ──
def _get_matcher():
    try:
        sys.path.insert(0, str(ROOT / "scraper"))
        from knews_scraper import tokenize, same_topic
        return tokenize, same_topic
    except Exception:
        stop = {"속보", "단독", "종합", "포토", "영상", "인터뷰", "오늘", "내일", "오전", "오후",
                "기자", "그래픽", "사진", "코멘트", "전망", "관련", "현장", "이것", "그것",
                "공식", "전체", "주요", "기사"}

        def tokenize(title):
            t = re.sub(r"\[[^\]]*\]", " ", title or "")
            t = re.sub(r"<[^>]+>", " ", t)
            return {x for x in re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}|[0-9]{2,}", t) if x not in stop}

        def same_topic(ta, tb):
            inter = len(ta & tb)
            if inter == 0:
                return False
            if inter >= 3:
                return True
            return inter / len(ta | tb) >= 0.5

        return tokenize, same_topic


def build_groups(cands):
    """cross≥MIN_CROSS 후보를 same_topic union-find로 그룹핑 → 크기≥2 그룹 리스트(각각 멤버 entry 리스트·cross 내림 정렬)."""
    tokenize, same_topic = _get_matcher()
    pool = [c for c in cands if (c.get("cross") or 0) >= MIN_CROSS and c.get("url") and (c.get("title") or "").strip()]
    toks = [tokenize(c.get("title") or "") for c in pool]
    parent = list(range(len(pool)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(pool)):
        if not toks[i]:
            continue
        for j in range(i + 1, len(pool)):
            if toks[j] and same_topic(toks[i], toks[j]):
                parent[find(j)] = find(i)
    byroot = {}
    for i in range(len(pool)):
        byroot.setdefault(find(i), []).append(pool[i])
    groups = [sorted(ms, key=lambda c: (-(c.get("cross") or 0), c.get("url") or "")) for ms in byroot.values() if 2 <= len(ms) <= MAX_SIZE]
    groups.sort(key=lambda g: -(g[0].get("cross") or 0))   # 큰 사건 먼저(상한 컷 시 대형 우선)
    return groups


def group_key(members):
    """그룹 구성 해시 — 멤버 url 정렬 join(구성 바뀌면 해시 변경 = 자동 재판정)."""
    urls = sorted(m.get("url") or "" for m in members)
    return hashlib.sha256(("|".join(urls) + RUBRIC_VER).encode("utf-8")).hexdigest()[:12]


def pending_groups(cands):
    """미판정(도장 없음/구성 변경) 그룹만."""
    out = []
    for g in build_groups(cands):
        k = group_key(g)
        if all(m.get("group_rubric") == k for m in g):
            continue   # 전원 현재 구성 도장 = 판정 완료
        out.append((k, g))
    return out


def judge(groups):
    """배치 1콜 판정 → {그룹인덱스: True/False}. 파서 엄격(G<n>: YES/NO만 인정 — 그 외 = 미판정 스킵)."""
    lines = []
    for i, (_, g) in enumerate(groups, 1):
        titles = "\n".join(f"  - {(m.get('title') or '').strip()[:90]}" for m in g)   # MAX_SIZE≤8이라 전 멤버 제시(부분 제시 오판 차단)
        lines.append(f"G{i}:\n{titles}")
    prompt = RUBRIC + "\n\n" + "\n".join(lines)
    args = ["--model", MODEL, "-p"]
    if EFFORT:
        args += ["--effort", EFFORT]
    if SAFE:
        args += ["--safe-mode"]
    p, rc, err = run_claude(args, prompt, timeout=300)
    if rc != 0:
        print(f"::warning::group_judge claude rc={rc} — 이번 런 스킵({(err or '')[:160]})")
        return {}
    verdicts = {}
    for m in re.finditer(r"^\s*G(\d+)\s*:\s*(YES|NO)\s*$", p or "", re.M | re.I):
        idx = int(m.group(1))
        if 1 <= idx <= len(groups):
            verdicts[idx - 1] = m.group(2).upper() == "YES"
    return verdicts


def main():
    cands = json.loads(CAND.read_text(encoding="utf-8"))
    todo = pending_groups(cands)
    if "--count" in sys.argv:
        print(len(todo))
        return
    if not todo:
        print("미판정 그룹 없음")
        return
    todo = todo[:MAX_PER_RUN]
    verdicts = judge(todo)
    if not verdicts:
        print("판정 결과 없음(파싱 0 또는 claude 실패) — 도장 안 박음(다음 런 재시도)")
        return
    by_url = {c.get("url"): c for c in cands if c.get("url")}
    yes = no = 0
    for i, (k, g) in enumerate(todo):
        if i not in verdicts:
            continue   # 이 그룹만 미판정 유지(파서 엄격)
        rep = g[0].get("url")   # 대표 = cross 최대(정렬 첫째)
        for m in g:
            e = by_url.get(m.get("url"))
            if not e:
                continue
            e["group_rubric"] = k
            if verdicts[i]:
                e["group_id"] = rep
            else:
                e.pop("group_id", None)
        yes += 1 if verdicts[i] else 0
        no += 0 if verdicts[i] else 1
    _fd, _tmp = tempfile.mkstemp(dir=str(CAND.parent), suffix=".tmp")
    with os.fdopen(_fd, "w", encoding="utf-8") as _f:
        _f.write(json.dumps(cands, ensure_ascii=False))
    os.replace(_tmp, CAND)
    print(f"사건 묶기: 판정 {len(verdicts)}/{len(todo)}그룹 (YES {yes} · NO {no}) · 모델 {MODEL}{' · safe' if SAFE else ''}")


if __name__ == "__main__":
    main()
