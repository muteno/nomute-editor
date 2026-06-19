#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# scraper 출력(articles.json) → viewer/candidates.json 갱신 = 스크랩(수집함) 탭 데이터.
# 클러스터 대표만 추려 url 기준 누적·중복제거·보관기간(10일) 폐기·교차순·보관한도. 자동분석과 무관(수집만, 과금 0).
#   사용: python3 scraper/to_candidates.py [articles.json경로]
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scraper" / "out" / "articles.json"
DST = ROOT / "viewer" / "candidates.json"

# 용어 통일: 수집 수(긁은 기사 총량, knews_scraper) · 사건 수(중복 합친 distinct, 아래 kept) ·
#            보관한도(수집함에 들고 있는 최대 사건 수=CAP) · 보관기간(마지막 후속보도 후 폐기까지=TTL).
TTL_HOURS = int(os.environ.get("CAND_TTL_HOURS", "240"))  # 보관기간: 마지막 후속보도(last_report) 후 N시간 지나면 폐기(240=10일 · 260618 first_seen→last_report)
CAP = int(os.environ.get("CAND_CAP", "3000"))             # 보관한도: 수집함 최대 사건 수(10일치 여유 — 실제 컷은 보관기간이 함)
MIN_CROSS = int(os.environ.get("CAND_MIN_CROSS", "2"))    # 교차등장 최소 매체 수(2=2개 이상 매체에 뜬 것만 = 뉴스성)
# ── 속보(velocity·태그) 1차 게이트 — burst(15분 내 동시 매체) OR [속보] 제목 태그. 2차 내용판정은 별도(Claude breaking_judge). ──
BREAKING_BURST = int(os.environ.get("BREAKING_BURST", "3"))          # 속보 후보: burst 이 값 이상(다수 동시 보도)
BREAKING_TAG = re.compile(r"\[\s*(속보|상보|긴급)\s*\]")             # 제목 태그 = 1~2매체여도 속보 후보 → AI 내용검증(언론고시 기자 = 낚시 안 씀)
MEGA_MEMBERS = int(os.environ.get("BREAKING_MEGA_MEMBERS", "40"))    # 멤버 이상 = over-merge 의심 → 속보 제외
MEGA_CROSS = int(os.environ.get("BREAKING_MEGA_CROSS", "18"))        # 누적 매체 이상 = over-merge 의심 → 속보 제외
# grade3(대형 경중) 신선건 속보후보 승격 — burst<3 저속 새사고(어린이집 황화수소 등) 구제. 첫등장 N시간 내만.
GRADE3_PROMOTE_H = int(os.environ.get("BREAKING_GRADE3_PROMOTE_H", "4"))
# ── 별칭 승계(alias) — rep url이 점프(클러스터 split/멤버변동)해 새 url로 떠도, 직전 후보와 멤버
#    교집합이 충분하면 '같은 사건'으로 보고 이력(first_seen·report_count 등) 승계 + 옛것 회수(중복 차단).
#    url은 여전히 1차 키(원장·picked·동시성 무변). 보수적(false-merge 방지) · mega(over-merge) 제외 · 결정적. ──
ALIAS_MIN_SHARED = int(os.environ.get("CAND_ALIAS_MIN_SHARED", "2"))  # 공유 멤버 url 최소(다를수록 보수)
ALIAS_JACCARD = float(os.environ.get("CAND_ALIAS_JACCARD", "0.5"))    # 멤버집합 자카드 최소
REPORT_CAP = int(os.environ.get("CAND_REPORT_CAP", "60"))             # report_count 상한(블롭 증폭 방지·§보수성)

KST = timezone(timedelta(hours=9))
# 스크래퍼 영문 섹션 → 뷰어 카테고리(catBucket 호환: 정치→사회 매핑은 뷰어가 처리)
CAT_MAP = {"politics": "정치", "economy": "경제", "society": "사회",
           "international": "국제", "world": "국제", "diplomacy": "국제",
           "tech": "테크", "it": "테크", "science": "테크", "culture": "문화"}


def cat_ko(category):
    for tok in re.split(r"[,\s/]+", str(category or "").lower()):
        if tok in CAT_MAP:
            return CAT_MAP[tok]
    return ""


def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def main():
    arts = load_json(SRC, [])
    now = datetime.now(KST)
    nowiso = now.strftime("%Y-%m-%dT%H:%M:%S%z")

    # 기존 후보(url → entry) — first_seen(등장시각) 보존해 TTL 누적
    existing = {c["url"]: c for c in load_json(DST, []) if isinstance(c, dict) and c.get("url")}

    # 신규 = 클러스터 대표 + 교차 MIN_CROSS 이상
    fresh = {}
    for a in arts:
        if not a.get("is_cluster_rep"):
            continue
        if (a.get("cross_score") or 0) < MIN_CROSS:
            continue
        url = a.get("link") or ""
        if not url:
            continue
        burst = a.get("burst") or 0
        cross = a.get("cross_score") or 0
        size = a.get("cluster_size") or 0
        mega = size > MEGA_MEMBERS or cross > MEGA_CROSS   # over-merge 의심(대표 신뢰 불가)
        bp = a.get("breaking_pick") or {}   # 메이저 픽(PICK_PRIORITY 조선>…>연합) — 다수 보도 시 제일 메이저를 대표 표시(미디어오늘 등 군소 대신). url/dedup 은 최초보도 유지.
        has_breaking_tag = bool(BREAKING_TAG.search((a.get("title") or "") + " " + (bp.get("title") or "")))   # 제목 [속보]/[상보]/긴급 = 속보 확률↑(언론고시 기자는 낚시 안 씀) → breaking 후보로 AI 내용검증
        fresh[url] = {
            "id": url, "url": url,
            "title": bp.get("title") or a.get("title") or "",
            "media": bp.get("media") or a.get("publisher") or "",
            "cat": cat_ko(a.get("category")),
            "cross": cross,
            "published": a.get("published") or "",
            "burst": burst,
            "arts": size,   # 클러스터 기사 수(cluster_size) — 증가 = 새 기사가 또 붙음(같은 매체 1곳이여도) = 연속보도 신호(report_count 산출용)
            # 속보 1차 후보(velocity·태그) — 2차 내용판정(Claude breaking_judge)이 breaking 을 확정한다. 다수 동시(burst≥N) OR [속보] 태그 = 후보 → AI 검증.
            "breaking_candidate": bool((burst >= BREAKING_BURST or has_breaking_tag) and not mega),
            "breaking_pick": a.get("breaking_pick") or None,
            "cluster_members": a.get("cluster_members") or [],   # 별칭승계 입력(rep url 점프 추적)
        }

    # ── 별칭 승계 준비 — 멤버 보유·non-mega 기존 후보만 별칭 풀(결정적 정렬). 1:1(claimed)·보수 임계. ──
    def _members(e):
        return set(e.get("cluster_members") or [])

    def _is_mega(e):
        return (e.get("arts") or 0) > MEGA_MEMBERS or (e.get("cross") or 0) > MEGA_CROSS

    alias_pool = [(u, e) for u, e in sorted(existing.items())
                  if _members(e) and not _is_mega(e)]
    claimed = set()

    def find_aliases(c, self_url):
        """c와 임계 통과하는 모든 기존(다른·미청구·비fresh) url 리스트(jac 내림·url 결정적). 전부 claim.
           = merge 잔류중복 + 동시성 부활중복까지 흡수(self-heal)."""
        cm = _members(c)
        if not cm or _is_mega(c):
            return []
        hits = []
        for u, e in alias_pool:
            if u == self_url or u in fresh or u in claimed:   # 자기·살아있는 rep·이미 흡수 제외
                continue
            shared = len(cm & _members(e))
            if shared < ALIAS_MIN_SHARED:
                continue
            jac = shared / len(cm | _members(e))
            if jac < ALIAS_JACCARD:
                continue
            hits.append((jac, u))
        hits.sort(key=lambda t: (-t[0], t[1]))    # jac 내림차·url 사전 = 결정적
        for _, u in hits:
            claimed.add(u)
        return [u for _, u in hits]

    merged = dict(existing)
    superseded = {}   # 흡수된 옛 url → 살아남는 url(회수 대상)
    for url, c in sorted(fresh.items()):          # 결정적 순회
        prev = merged.get(url)
        # 별칭은 새 url(rep 점프)에만 — 기존(활성) url엔 미적용 = 활성 distinct 후보 오회수 차단(§보수성).
        aliases = find_aliases(c, url) if prev is None else []
        is_alias = bool(aliases)
        if is_alias:                              # 새 url = rep 점프 → best(jac최대)로 이력 승계
            prev = existing.get(aliases[0], {})
        prev = prev or {}
        c["first_seen"] = prev.get("first_seen", nowiso)
        # last_seen = 마지막 '후속'(cross 증가) 시각. 신규/성장=now, 아니면 유지(뷰어 최신성 감쇠용).
        grew = (not prev) or ((c.get("cross") or 0) > (prev.get("cross") or 0))
        c["last_seen"] = nowiso if grew else (prev.get("last_seen") or c["first_seen"])
        c["seen_count"] = (prev.get("seen_count") or 0) + 1
        # report_count = '또 보도된'(arts 증가) 사이클 수 = 연속보도 가점(상한 REPORT_CAP=블롭 증폭 방지).
        grew_arts = (not prev) or ((c.get("arts") or 0) > (prev.get("arts") or 0))
        c["last_report"] = nowiso if grew_arts else (prev.get("last_report") or c["first_seen"])
        c["report_count"] = min(REPORT_CAP, (prev.get("report_count") or 0) + (1 if grew_arts else 0))
        # 안정 사건키 = 최초 rep url(별칭 통해 승계) — obs 시계열이 rep 점프에도 사건을 잇게(연속성).
        # url은 여전히 1차 키(원장·picked·동시성 무변) · event_key는 가산 그룹라벨일 뿐.
        c["event_key"] = prev.get("event_key") or (aliases[0] if is_alias else url)
        entry = {**prev, **c}                     # prev의 grade/breaking 도장 등 보존 + c가 최신 덮음
        if is_alias:                              # 별칭=다른 url(제목 다를 수 있음) → AI rubric 비워 재판정 유도(stale 도장 전파 차단)
            entry.pop("grade_rubric", None)
            entry.pop("breaking_rubric", None)
        merged[url] = entry
        for au in aliases:                        # 임계 통과한 옛 엔트리 전부 회수(merge 잔류·부활 중복 제거)
            superseded[au] = url

    # 별칭으로 흡수된 옛 엔트리 회수 = 중복 카드 제거(이력은 살아남는 url이 승계). 살아있는 rep는 보존.
    for old_url in superseded:
        if old_url not in fresh:
            merged.pop(old_url, None)

    # grade3 신선건 → 속보 후보 승격: burst<3 저속 새 사고(어린이집 황화수소 등 = 대형 경중인데 동시보도
    #   적어 velocity 게이트 못 넘던 건) 구제. 직전 사이클 gate_judge가 grade=3 도장 + first_seen<N시간이면
    #   breaking_candidate=True로 올려 breaking_judge 2차 내용판정 라인에 태운다(승격≠확정 — AI가 최종 결정).
    #   non-mega·신선만 · breaking_rubric 미손댐(갓 승격건은 rubric 없음→1회 판정·도장 후 재판정 안 됨=루프 차단).
    for c in merged.values():
        if (c.get("grade") or 0) >= 3 and not c.get("breaking_candidate") and not _is_mega(c):
            try:
                fs = (now - datetime.fromisoformat(c.get("first_seen") or nowiso)).total_seconds() / 3600
            except Exception:
                fs = 999
            if fs < GRADE3_PROMOTE_H:
                c["breaking_candidate"] = True

    # 속보 강등(만료): burst 가 1차 게이트(≥BREAKING_BURST) 밑으로 떨어진 사건은 굳은 breaking 플래그 해제.
    # burst 2 vs 3 = 넘사벽 — 급증 끝난 사건이 🚨로 눌어붙던 버그 차단. rubric 도 비워 재급증 시 재판정.
    # ⚠️ 위 grade3 승격분은 breaking_candidate=True라 여기서 안 깎임(승격 우선 → 강등 순서 = 의도).
    for c in merged.values():
        if not c.get("breaking_candidate"):
            c.pop("breaking", None)
            c.pop("breaking_rubric", None)

    def age_h(c):   # TTL 기준 = last_report(마지막 실제 후속보도) — 별칭 상속한 '현재 보도 중' 카드가
        try:        #   옛 first_seen 때문에 즉시 만료되던 버그 차단. 후속 끊긴 죽은 건만 N시간 후 폐기.
            ref = c.get("last_report") or c.get("last_seen") or c.get("first_seen") or nowiso
            return (now - datetime.fromisoformat(ref)).total_seconds() / 3600
        except Exception:
            return 0.0

    kept = [c for c in merged.values() if age_h(c) <= TTL_HOURS]
    kept.sort(key=lambda c: (c.get("cross") or 0, c.get("published") or ""), reverse=True)
    kept = kept[:CAP]

    nbreak = sum(1 for c in kept if c.get("breaking_candidate"))
    DST.parent.mkdir(parents=True, exist_ok=True)
    # 원자 쓰기(temp→os.replace) — 쓰기 중 중단 시 candidates.json 절단=전체 이력 소실 방지(데이터 정합성 최우선).
    import tempfile
    _fd, _tmp = tempfile.mkstemp(dir=str(DST.parent), suffix=".tmp")
    with os.fdopen(_fd, "w", encoding="utf-8") as _f:
        _f.write(json.dumps(kept, ensure_ascii=False))
    os.replace(_tmp, DST)
    print(f"수집함: 사건 {len(kept)}건 (신규 {len(fresh)} · 기존 {len(existing)}) · "
          f"보관한도 {CAP} · 보관기간 {TTL_HOURS}h(약 {TTL_HOURS // 24}일) · 교차≥{MIN_CROSS} · "
          f"🚨속보후보(burst≥{BREAKING_BURST}) {nbreak}건")


if __name__ == "__main__":
    main()
