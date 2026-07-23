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
# NO-only 저엔트로피 chain 차단(260713 · 분신술 10인 + 7일 gold-standard 검증 만장 OK): AI가 'NO'(이질 그룹) 판정한
#   그룹만 이 최상급어를 토큰에서 제거해 내부 재클러스터 → 서로 다른 사건을 붙이던 glue(역대·최대) 절단 → 동질 코어 분리
#   후 재판정. 현 YES 병합은 group_no 미보유라 트리거 안 걸림 = 손실 0(구조적 보장). knews STOPWORDS 미접촉(cross/클러스터/랭킹 무영향).
#   최소셋 {역대,최대}만(7일 실측: 최고=폭염 동일사건 파손·불가 / 수출·억달러 등 도메인어=사건 식별자라 절대 미포함 / V2·V3 확장 무이득).
#   롤백 = env GROUP_EXTRA_STOP="" (빈값 = 재클러스터 전면 OFF = 종전 동작). 정본 근거 = docs/curation-algorithm.md §7·§8 ▶ 260713.
EXTRA_STOP = frozenset(w for w in os.environ.get("GROUP_EXTRA_STOP", "역대,최대").split(",") if w.strip())

RUBRIC = """너는 한국 뉴스 데스크의 사건 동일성 판정자다. 아래 각 그룹의 기사 제목들이 전부 '같은 실제 사건'(같은 시간·장소·주체의 단일 사건 또는 그 직접 후속보도)을 다루면 YES, 하나라도 다른 사건이면 NO로 판정하라.
- 주의: 템플릿이 같아도 장소·주체가 다르면 다른 사건이다(예: "안산 공장 폭발" vs "청주 공장 폭발" = NO).
- 같은 *단일 사건*의 직접 후속·반응·상보(사망자 수 갱신, 그 사건 수사 착수, 그 사건에 대한 즉각 반응)는 YES.
- ⚠️ 같은 토픽·같은 정국이라도 **다른 국면은 다른 사건 = NO**(260703 조이기 — 국면이 따로 보여야 뉴스 가치가 산다): 다른 날의 별개 발언·회동·발표, 파생 효과(재난 → 관련 상품 시황), 반대 방향 시황(폭락 ↔ 다음 날 반등), 같은 분야의 다른 지표·이벤트(증시 시황 vs 고용 지표), 같은 인물의 다른 사안·다른 날 발언. 실측 오례: "뉴욕증시 반도체주 하락"과 "미 6월 고용 증가" = NO / "유럽 폭염"과 "중국산 에어컨 판매 폭증" = NO / "코스피 역대급 폭락"과 "코스피 3%대 반등" = NO.
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


def _components(pool, toks, same_topic):
    """same_topic union-find → 컴포넌트(각각 멤버 인덱스 리스트)."""
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
        byroot.setdefault(find(i), []).append(i)
    return list(byroot.values())


def build_groups(cands):
    """cross≥MIN_CROSS 후보를 same_topic union-find로 그룹핑 → 크기 2~MAX_SIZE 그룹 리스트(cross 내림 정렬).
    NO-only 재클러스터(EXTRA_STOP): 전원 group_no==그 그룹키(=이 구성 그대로 AI-NO 판정된 이질 그룹)인 컴포넌트만
    EXTRA_STOP(역대·최대) 제거 토큰으로 내부 재클러스터해 동질 코어 리프를 방출. group_no 없는(=현 YES 병합/미판정)
    컴포넌트는 절대 미접촉 → 현 YES 병합 손실 0(구조적 보장). EXTRA_STOP 빈값이면 종전 1패스 동작."""
    tokenize, same_topic = _get_matcher()
    pool = [c for c in cands if (c.get("cross") or 0) >= MIN_CROSS and c.get("url") and (c.get("title") or "").strip()]
    toks = [tokenize(c.get("title") or "") for c in pool]
    leaves = []
    for comp in _components(pool, toks, same_topic):
        members = [pool[i] for i in comp]
        kG = group_key(members) if (EXTRA_STOP and len(members) >= 2) else None
        if kG is not None and all(m.get("group_no") == kG for m in members):
            sub_toks = [toks[i] - EXTRA_STOP for i in comp]   # 이 그룹 내부만 최상급어 제거 재클러스터(멱등·엣지 단조감소)
            for sub in _components(members, sub_toks, same_topic):
                if 2 <= len(sub) <= MAX_SIZE:
                    leaves.append([members[s] for s in sub])
        elif 2 <= len(members) <= MAX_SIZE:
            leaves.append(members)
    groups = [sorted(ms, key=lambda c: (-(c.get("cross") or 0), c.get("url") or "")) for ms in leaves]
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
    cmd = ["claude", "-p"]   # ⚠️ 첫 요소 = 실행파일(run_claude가 subprocess.run(args)로 그대로 실행 — gate_judge 패턴 · 카나리아 2차서 누락 실측 FileNotFoundError '--model')
    if SAFE:
        cmd += ["--safe-mode"]
    cmd += ["--model", MODEL]
    if EFFORT:
        cmd += ["--effort", EFFORT]
    cmd += ["--disallowedTools",
            "Write,Edit,NotebookEdit,Bash,Task,WebFetch,WebSearch,Read,Glob,Grep",
            "--max-turns", "1"]
    p, rc, err = run_claude(cmd, prompt, timeout=300, source="group")   # source = 토큰 계측 shard(metrics)
    if p is None or rc != 0:
        print(f"::warning::group_judge claude rc={rc} — 이번 런 스킵({(err or '')[:160]})")
        return {}
    verdicts = {}
    for m in re.finditer(r"^\s*G(\d+)\s*:\s*(YES|NO)\s*$", p.stdout or "", re.M | re.I):
        idx = int(m.group(1))
        if 1 <= idx <= len(groups):
            verdicts[idx - 1] = m.group(2).upper() == "YES"
    return verdicts


def main():
    cands = json.loads(CAND.read_text(encoding="utf-8"))
    if EXTRA_STOP:
        # 백필: 정착 NO 그룹(판정됨·미병합)에 write-once group_no 주입 → build_groups 재클러스터 트리거
        #   (배포 즉시 자가치유 · 멤버변동 대기 불요). write-once = 이후 서브코어가 YES로 바뀌어도 유지 = churn 방지.
        for c in cands:
            if c.get("group_rubric") and not c.get("group_id") and not c.get("group_no"):
                c["group_no"] = c["group_rubric"]
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
                if EXTRA_STOP and not e.get("group_no"):   # write-once = 재클러스터 트리거(서브코어 YES로 바뀌어도 유지 = churn 방지)
                    e["group_no"] = k
        yes += 1 if verdicts[i] else 0
        no += 0 if verdicts[i] else 1
    _fd, _tmp = tempfile.mkstemp(dir=str(CAND.parent), suffix=".tmp")
    with os.fdopen(_fd, "w", encoding="utf-8") as _f:
        _f.write(json.dumps(cands, ensure_ascii=False))
    os.replace(_tmp, CAND)
    print(f"사건 묶기: 판정 {len(verdicts)}/{len(todo)}그룹 (YES {yes} · NO {no}) · 모델 {MODEL}{' · safe' if SAFE else ''}")


if __name__ == "__main__":
    main()
