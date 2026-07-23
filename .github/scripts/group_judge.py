#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 사건 묶기 판정(group_judge) — 토큰 클러스터링서 갈라진 '같은 사건' 후보 그룹을 Claude가 확정(YES/NO).
#   운영자 260702: "자동 병합 안 해도 오차 없이 묶이게" → 기계(same_topic)가 후보 그룹만 추리고,
#   AI가 '같은 실제 사건'인지 확정해야만 뷰어가 병합 표시(mergeDecorate 파이프 재사용 = 수동 병합과 동일 대우).
#   렉시컬 단독 병합은 금지 선례(260625 autopick: 안산↔청주 폭발 0.40 오접합) — AI 백스톱이 이 판정의 존재 이유.
# 모델 = opus 4.8 기본(운영자 260702 "탄탄하게" — autopick _ai_same과 동일 판정유형 선례) · --safe-mode 지원 · 폴오버 SSOT(claude_py) 경유.
# 도장 = 각 멤버 entry에 group_rubric(그룹구성해시+룰버전) → 같은 구성 재판정 0 · 멤버 변동 시 해시 바뀌어 자동 재판정.
#   YES → 멤버 전원에 group_id(대표 url) / NO → 도장만 = 뷰어 병합 억제(단 기존 YES 코어의 group_id는 보존 — 260723 연좌 해제 방지).
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
# 후속 속보 부착(260723 경산 방화 실측: 같은 사건 속보 후속이 각각 cross=2 클러스터로 갈라져 풀(cross≥3) 원천 배제
#   → AI 판정 기회 0 → 운영자 수기 병합 4건). 저cross도 풀에 넣되 앵커(cross≥MIN_CROSS) 있는 컴포넌트만 판정
#   = 'cross 2 단발 잡음끼리' 그룹은 종전대로 배제(원 취지 보존). 롤백 = env GROUP_MIN_ATTACH=3(=MIN_CROSS = 종전 동작).
MIN_ATTACH = int(os.environ.get("GROUP_MIN_ATTACH", "2"))
# 한글 부분어 매칭(260723 동반): 붙여쓰기·조사 변형(경산아파트↔경산+아파트 · 관리실서↔관리실 · 폭발추정사고↔폭발+추정)이
#   정확일치 교집합을 0으로 만들어 같은 사건이 안 이어지던 갭 — 한글 토큰 한정 일대일 탐욕 포함 매칭으로 보강(숫자·영문 제외 =
#   '20'⊂'2026' 류 오폭 차단). 임계는 same_topic과 동일(3개 또는 자카드 0.5) · 최종 확정은 종전대로 AI(오병합 백스톱 불변).
#   knews tokenize/same_topic 미접촉 = cross/클러스터/랭킹 무영향(260713 EXTRA_STOP과 동일 블라스트 반경). 롤백 = env GROUP_SUBTOK=0.
#   ⚠️ 부분어는 '저cross 부착 단계'에만 쓴다(평의회2 260723): 앵커끼리 부분어로 이어붙이면 클린 그룹이 >MAX_SIZE 블롭에
#   삼켜져 판정권을 잃는 순손실(실측 13그룹) — 앵커 1패스는 종전 same_topic(정확일치) 그대로.
SUBTOK = os.environ.get("GROUP_SUBTOK", "1").strip().lower() not in ("0", "false", "no", "")   # 빈값 = OFF(SAFE 파싱과 정합 — 평의회4)
# NO 판정 시 기존 YES 코어 group_id 보존(연좌 해제 방지 · 자기 앵커가 현 그룹에 실존할 때만 = 확장→축소 sticky 차단 — 평의회1).
#   롤백 = env GROUP_KEEP_YES=0(종전 'NO=전원 group_id 해제' 복원).
KEEP_YES = os.environ.get("GROUP_KEEP_YES", "1").strip().lower() not in ("0", "false", "no", "")

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


_HAN = re.compile(r"^[가-힣]+$")


def _han_sorted(tk):
    """토큰셋 → 정렬 한글 토큰 리스트(핫루프 밖 1회 사전계산용 — 평의회3: 쌍마다 재계산이 비용의 전부[27배]였음)."""
    return [t for t in sorted(tk) if _HAN.match(t)]


def _sub_match(ta, tb, ha=None, hb=None):
    """정확 교집합 + 한글 부분어 일대일 탐욕 매칭 수(결정론 = 정렬 순회 · 한쪽 토큰당 1회만 소비 = 긴 복합어 1개가 여러 매치로 뻥튀기 금지).
    ha/hb = 사전계산 _han_sorted(미제공 시 자체 계산 — 시뮬·재클러스터 폴백)."""
    inter = ta & tb
    n = len(inter)
    if n >= 3:
        return n
    if ha is None:
        ha = _han_sorted(ta)
    if hb is None:
        hb = _han_sorted(tb)
    used = set()
    for a in ha:
        if a in inter:
            continue
        for b in hb:
            if b not in used and b not in inter and (a in b or b in a):
                used.add(b)
                n += 1
                break
        if n >= 3:
            break   # 임계 도달 = 확정(조기 종료 — O(n²) 핫루프 비용 절감)
    return n


def _event_score(ta, tb, same_topic, ha=None, hb=None):
    """부착 랭킹용 매칭 강도(0 = 다른 사건 · 1~3 캡): same_topic(정본 유지) 통과 = 3 · 실패 시에만 부분어 보강 — 임계 동일(3개 또는 자카드 0.5)."""
    if same_topic(ta, tb):
        return 3
    if not SUBTOK:
        return 0
    n = _sub_match(ta, tb, ha, hb)
    if n >= 3:
        return 3
    if n and n / len(ta | tb) >= 0.5:
        return n
    return 0


def _same_event(ta, tb, same_topic, ha=None, hb=None):
    return _event_score(ta, tb, same_topic, ha, hb) > 0


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
    """2단 그룹핑(260723 평의회 하드닝): ①앵커끼리 종전 정확일치 union-find 그대로(기존 그룹 구조 불변) ②저cross
    후속 속보는 최강 매칭 '단일' 컴포넌트 부착만(부분어는 이 단계 한정) → 크기 2~MAX_SIZE 그룹 리스트(cross 내림 정렬).
    NO-only 재클러스터(EXTRA_STOP): 전원 group_no==그 그룹키(=이 구성 그대로 AI-NO 판정된 이질 그룹)인 컴포넌트만
    EXTRA_STOP(역대·최대) 제거 토큰으로 내부 재클러스터해 동질 코어 리프를 방출. group_no 없는(=현 YES 병합/미판정)
    컴포넌트는 절대 미접촉 → 현 YES 병합 손실 0(구조적 보장). EXTRA_STOP 빈값이면 종전 1패스 동작."""
    tokenize, same_topic = _get_matcher()

    def match(ta, tb):
        return _same_event(ta, tb, same_topic)

    def ok(c):
        return c.get("url") and (c.get("title") or "").strip()

    # ── 1패스: 앵커(cross≥MIN_CROSS)끼리 = 종전 same_topic(정확일치) union-find '그대로' — 기존 판정 그룹 구조 불변 보장
    #   (부분어를 앵커 간에도 쓰면 클린 그룹이 >MAX_SIZE 블롭에 삼켜져 판정권 상실 = 순손실 실측 13그룹 — 평의회2 260723) ──
    anchors = [c for c in cands if (c.get("cross") or 0) >= MIN_CROSS and ok(c)]
    atoks = [tokenize(c.get("title") or "") for c in anchors]
    comps = [[(anchors[i], atoks[i], _han_sorted(atoks[i])) for i in cc]
             for cc in _components(anchors, atoks, same_topic)]
    # ── 2패스: 저cross 후속 속보 부착 — 각 아이템은 '최강 매칭 단일' 컴포넌트에만 편입(컴포넌트 간 union 구조적 불가 =
    #   브리지·블롭 차단 · MAX_SIZE 좌석 내 선착 = 앵커 코어 판정권 보존 · 저cross 체인[속보A→속보B→앵커]은 반복 부착 수렴) ──
    if MIN_ATTACH < MIN_CROSS:
        low = sorted((c for c in cands if MIN_ATTACH <= (c.get("cross") or 0) < MIN_CROSS and ok(c)),
                     key=lambda c: (-(c.get("cross") or 0), c.get("url") or ""))
        ltoks = [tokenize(c.get("title") or "") for c in low]
        lhan = [_han_sorted(tk) for tk in ltoks]
        left = [i for i in range(len(low)) if ltoks[i]]
        for _ in range(3):
            still = []
            for li in left:
                best = None   # (매칭강도, 대상 cross) 최대 — 동률 = 먼저 만난 컴포넌트(순회 결정론)
                for mem in comps:
                    if len(mem) >= MAX_SIZE:
                        continue
                    for m, tk, hk in mem:
                        s = _event_score(ltoks[li], tk, same_topic, lhan[li], hk)
                        if s and (best is None or (s, m.get("cross") or 0) > best[0]):
                            best = ((s, m.get("cross") or 0), mem)
                if best is None:
                    still.append(li)
                else:
                    best[1].append((low[li], ltoks[li], lhan[li]))
            if len(still) == len(left):
                break
            left = still
    # ── 리프 방출(컴포넌트 전원 앵커 1패스 발원 = 저cross끼리 잡음 그룹 원천 불가) ──
    leaves = []
    for mem in comps:
        members = [m for m, _, _ in mem]
        kG = group_key(members) if (EXTRA_STOP and len(members) >= 2) else None
        if kG is not None and all(m.get("group_no") == kG for m in members):
            sub_toks = [tk - EXTRA_STOP for _, tk, _ in mem]   # 이 그룹 내부만 최상급어 제거 재클러스터(멱등·엣지 단조감소)
            for sub in _components(members, sub_toks, match):
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
            elif KEEP_YES and e.get("group_id") and any((x.get("url") or "") == e.get("group_id") for x in g):
                pass   # NO여도 기존 YES 코어 보존(260723) — 확장 구성 NO = 신규 부착 거부일 뿐 연좌 해제 금지.
                #   협소화(평의회1): 자기 앵커 url이 '현 그룹 안에 실존'할 때만(확장→축소 사이클의 sticky-NO 엣지 차단).
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
