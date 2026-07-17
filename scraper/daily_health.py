#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 일일 점검 — 수집함 파이프라인 ①수집건강 ②알고리즘 신호 ③롤백 검토를 한 화면에.
#   운영자가 '섹션 할일/상태' 물을 때(일일 1회) 메인이 먼저 돌려 보고 → docs/curation-algorithm.md §7/§8과 대조.
#   정본 루틴 = CLAUDE.md §🧠 "일일 점검". 읽기 전용(candidates.json 안 건드림).
# 사용: python3 scraper/daily_health.py
import json
import subprocess
import datetime as dt
from collections import Counter
from datetime import timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "viewer" / "candidates.json"
SUBS = ROOT / "push" / "subscriptions.json"
SCRIPTS = ROOT / ".github" / "scripts"
KST = timezone(timedelta(hours=9))
CHECKPOINT = "checkpoint/algo-260619-grade3-promote"   # 최신 알고리즘 분기 라벨(롤백 기준)


def age_h(s, now):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if not t.tzinfo:
            t = t.replace(tzinfo=timezone.utc)
        return (now - t).total_seconds() / 3600
    except Exception:
        return None


def count(script):
    try:
        r = subprocess.run(["python3", str(SCRIPTS / script), "--count"],
                           capture_output=True, text=True, timeout=40)
        return int((r.stdout or "").strip())
    except Exception:
        return None


def git(*args):
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args],
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def _get_tokenizer():
    """독점률용 토큰화 — knews_scraper 정본 우선, 실행 환경에 feedparser 없으면 폴백 미러(social_burst 선례).
    ⚠️ 미러는 knews tokenize/same_topic(overlap≥3 OR jaccard≥0.5)와 동기 유지(후속 = tokenize SSOT 모듈화 §7)."""
    try:
        import sys
        sys.path.insert(0, str(ROOT / "scraper"))
        from knews_scraper import tokenize, same_topic
        return tokenize, same_topic
    except Exception:
        import re
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


def _dominance(cands, now):
    """독점률 = 누적칼럼 근사 상위30 중 최대 단일사건 점유%(도배 재발 감지 · 260702 fable패널 수정안).
    풀 = 누적자격 미러(나이≥4h AND [cross≥8 OR 긴급 OR followEnters]) · 정렬 = cross^1.3×timeAcc(13·3.0).
    뷰어 scScore 근사(gradeW·긴급부스트 생략 — 실측 교집합 27/30·평시 3%). 상수는 §★ 정본과 짝(변경 시 갱신).
    반환 (점유%, 건수, 대표제목) 또는 None(풀<15 = 심야 표본 부족·판정 유보)."""
    pool = []
    for c in cands:
        a = age_h(c.get("published"), now)
        if a is None or a < 0:                      # 발행 없음/미래 오기록 → 수집시각 폴백
            a = age_h(c.get("first_seen"), now)
        if a is None or a < 4:
            continue
        g = c.get("grade")
        brk = bool(c.get("breaking")) and (g is None or (g or 0) >= 2)
        fol = (c.get("cross") or 0) >= 4 and (c.get("report_count") or 0) >= 6 and g != 0
        if (c.get("cross") or 0) >= 8 or brk or fol:
            pool.append((c, a))
    if len(pool) < 15:
        return None
    scored = sorted(pool, key=lambda x: ((x[0].get("cross") or 0) ** 1.3) / (1 + (x[1] / 13) ** 3.0),
                    reverse=True)[:30]
    top = [c for c, _ in scored]
    tokenize, same_topic = _get_tokenizer()
    toks = [tokenize(c.get("title") or "") for c in top]
    parent = list(range(len(top)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            if toks[i] and toks[j] and same_topic(toks[i], toks[j]):
                parent[find(j)] = find(i)
    groups = Counter(find(i) for i in range(len(top)))
    root, size = groups.most_common(1)[0]
    return size / len(top) * 100, size, (top[root].get("title") or "")


def main():
    now = dt.datetime.now(timezone.utc)
    nowk = now.astimezone(KST)
    try:
        c = json.loads(CAND.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ candidates.json 로드 실패: {e}")
        return
    print(f"═══ 일일 점검 · {nowk:%Y-%m-%d %H:%M} KST · 후보풀 {len(c)}건 ═══\n")

    # ─────────── ① 수집 건강 ───────────
    ages = [age_h(x.get("first_seen"), now) for x in c]
    valid = [a for a in ages if a is not None]
    newest = min(valid) if valid else None
    fresh4 = sum(1 for a in valid if a < 4)
    fresh24 = sum(1 for a in valid if a < 24)
    print("① 수집 건강")
    if newest is None:
        print("  ⚠️ 수집시각(first_seen) 불명 — 스크랩 점검 필요")
    else:
        f = "✅" if newest < 2 else ("⚠️" if newest < 6 else "❌")
        print(f"  {f} 최신 수집 {newest:.1f}h 전 · 최근4h {fresh4}건 · 최근24h {fresh24}건"
              + ("  (←2h 넘으면 스크랩 지연 의심)" if newest >= 2 else ""))
    nb, ng = count("breaking_judge.py"), count("gate_judge.py")
    if nb is not None and ng is not None:
        f = "✅" if (nb + ng) < 120 else "⚠️"
        print(f"  {f} 미판정 backlog: 속보 {nb} · 경중 {ng} (>120 누적이면 판정 적체 의심)")
    else:
        print("  ⚠️ backlog 카운트 실패(judge 스크립트 점검)")
    try:
        subs = json.loads(SUBS.read_text(encoding="utf-8"))
        print(f"  · 웹푸시 구독자 {len(subs) if isinstance(subs, list) else '?'}명")
    except Exception:
        print("  · 웹푸시 구독자 0명(또는 미생성)")
    # RSS 피드 건강 원장(scraper/obs/feed_health.json 안정본 — 죽은피드 구성 변화시 scrape가 갱신 · 무음 드리프트 방지 260702)
    try:
        fh = json.loads((ROOT / "scraper" / "obs" / "feed_health.json").read_text(encoding="utf-8"))
        # 원소 dict 정규화 — 부분 손상 시 요약줄 출력 후 순회서 터져 '생존'+'원장없음' 이중출력 모순 방지(평의회 260702)
        deadf = [x for x in (fh.get("dead_feeds") or []) if isinstance(x, dict)]
        zomb = [x for x in (fh.get("zombie_feeds") or []) if isinstance(x, dict)]
        okn = fh.get("ok") or 0   # null도 0 표시(리터럴 None 방지) — 임계·표시 기준은 리스트 길이로 단일화
        f = "✅" if len(deadf) <= 5 else "⚠️"
        print(f"  {f} RSS 피드 생존 {okn}/{okn + len(deadf)} (죽음 {len(deadf)})"
              + ("  (←죽음 6↑ = feeds.csv 정리 검토)" if len(deadf) > 5 else ""))
        for x in deadf[:5]:
            print(f"      ✗ {x.get('publisher', '?')} {x.get('title', '')}")
        if len(deadf) > 5:
            print(f"      … 외 {len(deadf) - 5}개 (scraper/obs/feed_health.json)")
        if zomb:   # 응답은 오는데 갱신 멈춘 피드(JTBC 2024-10 멈춤 실측 케이스) — 주간 니치 피드는 일시 오탐 가능
            print(f"  🧟 좀비 피드(응답 OK·24h 발행 0) {len(zomb)}개: "
                  + " · ".join(f"{x.get('publisher', '?')} {x.get('title', '')}" for x in zomb[:4])
                  + (" …" if len(zomb) > 4 else ""))
        # orphan 피드 경보(260703 분신술 §7④): 생존(비dead·비zombie)인데 최근 7일 '대표(rep) 후보' 0
        #  = 무성과 피드가 '생존 151' healthy 집계에 은폐되던 것 표면화. ⚠️ '수집 0' 아님 — 멤버로 cross
        #  기여는 가능(KED글로벌 = followEnters 4번째 매체 pivotal → 제거 금지 · §8 260703). 기지(baseline)는 정보줄·신규만 ⚠️.
        try:
            import csv
            pubs = Counter()
            with (ROOT / "scraper" / "feeds.csv").open(encoding="utf-8") as fp:
                for row in csv.DictReader(fp):
                    p = (row.get("publisher") or "").strip()
                    if p:
                        pubs[p] += 1
            bad = Counter((x.get("publisher") or "").strip() for x in deadf + zomb)
            alive_pubs = {p for p, n in pubs.items() if bad.get(p, 0) < n}   # 피드 1개라도 생존하면 alive
            reps7 = Counter((x.get("media") or "").strip() for x in c
                            if (age_h(x.get("first_seen"), now) or 999) < 168)
            orphan = sorted(p for p in alive_pubs if reps7.get(p, 0) == 0)
            KNOWN_ORPHAN = {"KED글로벌", "NYT코리아"}   # baseline(§8 260703 실측 — 신규 등장분만 경보)
            if orphan:
                new_o = [p for p in orphan if p not in KNOWN_ORPHAN]
                flag = "⚠️" if new_o else "·"
                print(f"  {flag} orphan 피드(생존·7일 대표후보 0) {len(orphan)}곳: " + " · ".join(orphan[:6])
                      + (" …" if len(orphan) > 6 else "")
                      + ("  ← 신규 orphan = 수집되는데 후보 전무(클러스터·피드 점검)" if new_o
                         else "  (기지 — 멤버 cross 기여형·제거 금지 §8 260703)"))
        except Exception as e:
            print(f"  · orphan 계산 실패(비치명): {e}")
    except Exception:
        print("  · 피드 건강 원장 없음(다음 scrape 런부터 생성)")

    # ─────────── ② 알고리즘 신호 ───────────
    gd = Counter(x.get("grade") for x in c)
    brk = [x for x in c if x.get("breaking")]
    brk24 = [x for x in brk if (age_h(x.get("first_seen"), now) or 99) < 24]
    bc = sum(1 for x in c if x.get("breaking_candidate"))
    # 승격 구제분(저burst grade3 신선) = compare_collected.promoted_guess와 동일 정의
    promo = [x for x in c if (x.get("grade") or 0) >= 3 and x.get("breaking_candidate")
             and (x.get("burst") or 0) < 3 and "[속보]" not in (x.get("title") or "")
             and "[긴급]" not in (x.get("title") or "")]
    urg = [x for x in brk if (x.get("grade") or 0) >= 2 and (age_h(x.get("first_seen"), now) or 99) < 4]
    print("\n② 알고리즘 신호")
    print(f"  · grade 분포 {{0:{gd.get(0,0)} 1:{gd.get(1,0)} 2:{gd.get(2,0)} 3:{gd.get(3,0)} 미채점:{gd.get(None,0)}}}")
    print(f"  · breaking 확정 {len(brk)}(24h내 {len(brk24)}) · breaking_candidate {bc} · ⬆️저burst승격 {len(promo)}")
    f = "✅" if len(urg) < 8 else "⚠️"
    print(f"  {f} 현재 🚨긴급자격(breaking&grade≥2&<4h) {len(urg)}건"
          + ("  (←8↑면 긴급 과다 의심)" if len(urg) >= 8 else ""))
    # ⚡이슈 배지 계기판(260702 정적 10 확정·fable 4인 — 캘린더 재측정 폐지의 대가로 지불하는 상시 감시 1줄 · §8 260702)
    #  근사 = viewer issCross의 badgeJunk(정형컷 정규식 4종) 미반영(3본째 미러 회피·±3건) — cross·grade·grade3우회·나이창만.
    #  나이 = max(발행, first_seen) 근사(scBadgeType 동일 원칙). 상한 경보 = 재인플레(남발 재발) · 하한 0 = 과조임/수집장애 의심.
    def _iss_age(x):
        a1, a2 = age_h(x.get("published"), now), age_h(x.get("first_seen"), now)
        cand = [v for v in (a1, a2) if v is not None]
        return max(cand) if cand else None
    def _iss_ok(x):
        g, cr = x.get("grade"), (x.get("cross") or 0)
        return (g is None or g >= 2) and (cr >= 10 or (g == 3 and cr >= 8))
    issq = [x for x in c if _iss_ok(x) and (_iss_age(x) or 99) >= 4 and (_iss_age(x) or 99) < 24]
    resv = [x for x in c if (x.get("grade") is None or (x.get("grade") or 0) >= 2) and x.get("grade") != 3
            and 8 <= (x.get("cross") or 0) <= 9 and (_iss_age(x) or 99) >= 4 and (_iss_age(x) or 99) < 24]
    f = "⚠️" if (len(issq) >= 30 or len(issq) == 0) else "✅"
    print(f"  {f} ⚡이슈배지 자격(근사·badgeJunk 미반영 ±3) {len(issq)}건 · cr8~9 저수지 {len(resv)}건"
          + ("  (←30↑ = 재인플레 의심 → §8 260702 실측환산 절차로 임계 재조정)" if len(issq) >= 30 else "")
          + ("  (←0 = 과조임/수집장애 의심)" if len(issq) == 0 else "  (기준 260702=13~20 · 저수지 급증 = 다음 인플레 전조)"))
    # OUT 아웃라이어 감쇠하한 계기판(260706 §8 — §1 보수성: '완화'엔 상시 측정+상한 경보가 짝 · 배지 계기판 선례)
    #  근사 = viewer 파이프 *순서* 재현: scDedup(동일제목·12h내 우세 1장) → group_id 병합·_rankCross 댐핑.
    #  ⚠️ scDedup 생략 금지(260706 심야 정정): 빼먹으면 동일제목 파편이 합산에 살아남아 과보고(cr44 아티팩트 — 실파이프는 cr30·g1 = 무자격 · §8 정정).
    #  badgeJunk(정형컷)·수동병합(localStorage)·검색동결은 미반영(±1). 기준 = 0~5 정상(도입 스냅샷 실측 2 — 장윤기·정보통신망법) · ≥6 = 과발동 조사(§8 260706) · 강건 z(중앙값+MAD)·풀<15 OFF = viewer 동값.
    try:
        def _oa(x):   # 나이(h) 근사 — published 우선·없으면 first_seen(scTs 요지)
            v = age_h(x.get("published"), now)
            return v if v is not None else age_h(x.get("first_seen"), now)
        _rep, cd = {}, []
        for x in c:   # scDedup 재현: 동일 정규화 제목 AND 나이차 <12h = 우세(cross→rc) 1장만
            k = "".join((x.get("title") or "").split()).lower()
            if not k:
                cd.append(x)
                continue
            pi = _rep.get(k)
            if pi is not None and abs((_oa(x) or 999) - (_oa(cd[pi]) or 999)) < 12:
                if ((x.get("cross") or 0), (x.get("report_count") or 0)) > ((cd[pi].get("cross") or 0), (cd[pi].get("report_count") or 0)):
                    cd[pi] = x
                continue
            _rep[k] = len(cd)
            cd.append(x)
        grp = {}
        for x in cd:
            gid = x.get("group_id")
            if gid:
                grp.setdefault(gid, []).append(x)
        merged, dropped = {}, set()
        for gid, cards in grp.items():
            if len(cards) < 2:
                continue
            anchor = next((x for x in cards if x.get("url") == gid), None) or max(cards, key=lambda x: x.get("cross") or 0)
            summed = sum(x.get("cross") or 0 for x in cards)
            base = anchor.get("cross") or 0
            cap = base * 1.5   # MERGE_DAMP_RATIO 1.5·GAIN 0.75 = viewer mergeDecorate 동값
            rank = summed if summed <= cap else cap + (summed - cap) * 0.75
            grades = [x.get("grade") for x in cards if x.get("grade") is not None]
            merged[id(anchor)] = {**anchor, "cross": summed, "_rank": rank,
                                  "report_count": max((x.get("report_count") or 0) for x in cards),
                                  "grade": max(grades) if grades else anchor.get("grade")}
            dropped.update(id(x) for x in cards if x is not anchor)
        pool = [merged.get(id(x), x) for x in cd if id(x) not in dropped]
        xs = sorted(v for v in ((x.get("_rank") or x.get("cross") or 0) for x in pool) if v >= 8)
        def _med(a):
            m = len(a) // 2
            return a[m] if len(a) % 2 else (a[m - 1] + a[m]) / 2
        if len(xs) < 15:
            print("  · OUT 감쇠하한: 통계 풀 <15 (콜드스타트) — 완화 OFF 상태")
        else:
            med = _med(xs)
            sd = max(1.4826 * _med(sorted(abs(v - med) for v in xs)), 2)
            outs = [x for x in pool
                    if (_iss_age(x) or 99) < 24 and (x.get("report_count") or 0) >= 6 and _iss_ok(x)
                    and ((x.get("_rank") or x.get("cross") or 0) - med) / sd >= 2.5]
            f = "✅" if len(outs) < 6 else "⚠️"
            print(f"  {f} OUT 감쇠하한 발동(근사·badgeJunk/수동병합 미반영) {len(outs)}건 (med {med:.1f}·σr {sd:.2f})"
                  + ("  (←6↑ = 과발동 → §8 260706 임계 재검토)" if len(outs) >= 6 else "  (기준 0~5 · 도입 스냅샷 실측 2)"))
            for x in outs[:3]:
                print(f"      · z{(((x.get('_rank') or x.get('cross') or 0) - med) / sd):.1f} cr{x.get('cross')} rc{x.get('report_count')} {str(x.get('title') or '')[:36]}")
    except Exception as e:
        print(f"  · OUT 계기판 계산 실패(비치명): {e}")
    # 긴급부스트 신선창 계기판(260717 §8 — 24h 풀 ×3.0 폐지 → 1~6h 이징 전환의 실전 궤적 축적 · OUT 계기판 선례)
    #  근사 = scScore 6항 중 dedup·병합(_rankCross)·픽/확인·OUT하한 미반영(±) — cross^1.3·timeAcc·연속보도·경중·신곡선부스트·ageMul만 재현.
    #  부스트 창 <6h·이징 g12 = viewer BOOST_RAMP_END_H·BOOST_EASE_G 동값(§★ — 곡선 재조정 시 여기도 동기). 나이 = max(발행,first_seen).
    #  기준 = '12h+ 긴급 top5 잔존' 0(신선창 전환 취지 — 운영자 3회 육안 포착 패턴의 기계화) · ≥1 = 곡선 무력화/타항 부양 의심 → §8 260717 재점검.
    try:
        import math
        def _ba(x):   # 발행 우선 나이(timeAcc 축·scTs 요지)
            v = age_h(x.get("published"), now)
            return v if v is not None else age_h(x.get("first_seen"), now)
        def _brk_ok(x):
            g = x.get("grade")
            return bool(x.get("breaking")) and (g is None or g >= 2)
        def _scr(x):   # 누적 scScore 근사(신곡선 부스트 포함)
            cr = x.get("cross") or 0
            rk = _iss_age(x) or 99
            ta = 1 / (1 + (max(_ba(x) or 99, 0) / 13) ** 3.0)
            fol = 1 + 0.5 * math.log2(1 + (x.get("report_count") or 0))
            g = x.get("grade")
            gw = 1.0 if g is None else {0: 0.5, 1: 0.7, 2: 1.0, 3: 1.8}.get(g, 1.0)
            bb = 1.0
            if _brk_ok(x) and rk < 6:
                if rk < 1:
                    bb = 3.0
                else:
                    s = lambda v: 1 / (1 + math.exp(-v))
                    t = (rk - 1) / 5
                    bb = 1 + 2 * (s(12 * (.5 - t)) - s(-6)) / (s(6) - s(-6))
            am = 0.12 + 0.88 / (1 + math.exp((rk - 13) / 3.8))
            return cr ** 1.3 * ta * fol * gw * bb * am
        cum = [x for x in c if (_ba(x) or 0) >= 4 and ((x.get("cross") or 0) >= 8 or _brk_ok(x)
               or ((x.get("cross") or 0) >= 4 and (x.get("report_count") or 0) >= 6 and x.get("grade") != 0))]
        brks = [x for x in cum if _brk_ok(x)]
        fresh = [x for x in brks if (_iss_age(x) or 99) < 6]
        top5 = sorted(cum, key=_scr, reverse=True)[:5]
        linger = [x for x in top5 if _brk_ok(x) and (_iss_age(x) or 0) >= 12]
        f = "⚠️" if linger else "✅"
        print(f"  {f} 긴급부스트 신선창: 누적 breaking {len(brks)}건 · 부스트 수혜(<6h) {len(fresh)}건 · 12h+ top5 잔존(근사) {len(linger)}건"
              + ("  (←잔존 = 신곡선 무력화/타항 부양 의심 → §8 260717 재점검)" if linger
                 else "  (기준 잔존 0 · 260717 신선창 전환)"))
        for x in linger[:2]:
            print(f"      · {(_iss_age(x) or 0):.1f}h cr{x.get('cross')} rc{x.get('report_count')} {str(x.get('title') or '')[:36]}")
    except Exception as e:
        print(f"  · 부스트 계기판 계산 실패(비치명): {e}")
    # 독점률(도배 재발 감지 — 6/28형 '단일사건 상단 도배'를 숫자로 · ≥30%면 §7 접기(fold)안 검토 신호)
    try:
        dom = _dominance(c, now)
        if dom is None:
            print("  · 독점률: 누적자격 풀 <15 (심야 표본 부족) — 판정 유보")
        else:
            pct, size, title = dom
            flag = "⚠️" if pct >= 30 else "·"
            print(f"  {flag} 독점률(누적 상위30 최대 단일사건): {pct:.0f}%({size}건)"
                  + (f"  ← 도배 의심 · §7 접기안 검토 — {title[:28]}" if pct >= 30 else "  (기준 3~13% 정상 · 6/28형 도배 = 75%)"))
    except Exception as e:
        print(f"  · 독점률 계산 실패(비치명): {e}")
    # 묻힘 계측(외신·국제 · 260703 분신술 §7①): AI확정 대형(grade3)인데 4h+ 에서 누적 3경로(cross≥8/긴급/
    #  followEnters) 전부 미충족 = 두 칼럼 미노출. §1 "중요한 게 묻히면 안 됨" 유일 자동감시 — breaking 문체
    #  가드 등 개선의 before/after 토대(임계·자동조치 없음 = 순수 계측 · 정본 §8 260703). 나이 = 발행 우선·수집 폴백(_dominance 동일).
    try:
        def _intl(x):
            return (x.get("cat") == "국제") or bool(x.get("title_ko"))
        def _cum_ok(x):
            g = x.get("grade")
            brk = bool(x.get("breaking")) and (g is None or (g or 0) >= 2)
            fol = (x.get("cross") or 0) >= 4 and (x.get("report_count") or 0) >= 6 and g != 0
            return (x.get("cross") or 0) >= 8 or brk or fol
        buried, b2 = [], 0
        for x in c:
            if not _intl(x):
                continue
            a = age_h(x.get("published"), now)
            if a is None or a < 0:
                a = age_h(x.get("first_seen"), now)
            if a is None or a < 4 or _cum_ok(x):
                continue
            if x.get("grade") == 3:
                buried.append(x)
            elif x.get("grade") == 2:
                b2 += 1
        print(f"  · 묻힘(외신·국제 4h+ 누적 미진입): grade3 {len(buried)}건 · grade2 {b2}건"
              + "  (기준 260703 g3=19 — 개선 효과·급증 감시용 게이지)")
        for x in buried[:3]:
            print(f"      ◦ {(x.get('title_ko') or x.get('title') or '')[:38]} (cr{x.get('cross') or 0}·rc{x.get('report_count') or 0})")
    except Exception as e:
        print(f"  · 묻힘 계측 실패(비치명): {e}")
    print(f"  → 심층 비교: python3 scraper/compare_collected.py  (어제↔오늘 낮 승격·긴급 분포)")

    # ─────────── ③ 롤백 검토 ───────────
    print("\n③ 롤백 검토")
    print(f"  · 알고리즘 분기 라벨 = {CHECKPOINT} (검증완 기준점)")
    git("fetch", "origin", "main", "-q")
    log = git("log", "--oneline", "-15", "origin/main")
    kws = ("긴급", "수집함", "큐레이션", "breaking", "grade", "승격", "푸시", "candidates",
           "scrape", "rubric", "랭킹", "배지", "누적", "신규")
    hits = [ln for ln in log.splitlines() if any(k in ln for k in kws)]
    print(f"  · 최근 큐레이션 관련 커밋(origin/main, 최대 15 중):")
    for ln in hits[:8]:
        print(f"      {ln}")
    if not hits:
        print("      (최근 15커밋에 큐레이션 변경 없음)")
    print(f"  · 롤백 방법: git revert <커밋> 또는 git diff {CHECKPOINT}..origin/main 으로 분기 후 변경 검토")
    print(f"             · _versions/ 백업 폴더에서 개별 파일 복원")
    print("\n[판단] ①②에 ⚠️/❌ 있으면 원인 추적 → 알고리즘 변경 탓이면 ③으로 롤백 검토."
          " 깨끗하면 '수집·알고리즘 정상, 롤백 불요' 보고.")


if __name__ == "__main__":
    main()
