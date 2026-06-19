#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 소셜 버스트 PoC(뼈대) — 한국 커뮤니티/소셜 hot-post를 교차소스로 묶어
#   '급발 공론화 이슈'(비정치: 가정불화·갑질·이웃분쟁·학폭 등)를 검출한다.
#
# 구조: ① 소스 어댑터(RSS/네이버) → 게시물 수집 ② 클러스터(knews tokenize·same_topic 재사용·드리프트0)
#       ③ 버스트 스코어(교차소스 폭 × 최신성) ④ 정치/노이즈 필터 → ⑤ 랭킹 JSON.
# 라이브 = Actions(열린 네트워크/키)에서. 로컬 코어 검증 = `python3 scraper/social_burst.py --sample`.
#
# 배선됨(260618): 뷰어 SNS 탭(메뉴2) = social_candidates.json 렌더. social-scan.yml이 viewer/로 커밋(라이브 서빙).
#    소스 = 이슈링크 어그리게이터(여러 커뮤니티 인기글 한 번에 = 교차소스 핵심) + 뽐뿌 RSS. 직접 커뮤 RSS는 대부분 차단(실측 260618).
#    출력 = scraper/out/social_candidates.json. 소스·임계 튜닝 = docs/social-burst.md.
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import re

# ⚠️ 소셜 전용 클러스터 임계(뉴스와 분리 · doc §33) — 짧은 커뮤 제목은 뉴스보다 토큰이 적어
# overlap=3이 너무 빡셈(명백한 '하이닉스+삼성전자' 교차도 미형성). 소셜은 overlap 2 + jaccard 0.4로 느슨.
SOCIAL_OVERLAP = int(os.environ.get("SOCIAL_OVERLAP", "2"))
SOCIAL_JACCARD = float(os.environ.get("SOCIAL_JACCARD", "0.4"))   # 0.33 시도→되돌림(260619): 적대적검증서 2토큰·1공유 별개사건 거짓병합("연예인 갑질"↔"식당 갑질") 재현 → 0.4 유지(volume은 소스 레버로). 더 느슨화 금지(짧은 제목 과병합).
_STOP = {"속보", "단독", "종합", "전문", "공식", "오늘", "내일", "관련", "기자", "영상", "사진", "실시간", "현재", "근황", "ㄷㄷㄷ",
         "추가", "폭로", "증언", "위협", "확산", "출동", "충격", "경악", "레전드", "논란", "소식", "일파만파", "수준", "정도", "클라스"}

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import knews_scraper as K   # 토큰 추출(tokenize)은 뉴스와 공유 = 드리프트0. 단 매칭(same_topic)은 소셜용으로 분리.
    tokenize = K.tokenize
except Exception:   # 로컬(feedparser 미설치) 폴백 — knews tokenize 미러.
    def tokenize(title):
        title = re.sub(r"\[[^\]]*\]", " ", title)
        title = re.sub(r"<[^>]+>", " ", title)
        return {t for t in re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}|[0-9]{2,}", title) if t not in _STOP}


def _jac(a, b):
    return len(a & b) / len(a | b) if (a and b) else 0.0


def same_topic(ta, tb):   # 소셜 전용(느슨) — overlap≥SOCIAL_OVERLAP OR jaccard≥SOCIAL_JACCARD.
    inter = len(ta & tb)
    return inter >= SOCIAL_OVERLAP or (inter > 0 and _jac(ta, tb) >= SOCIAL_JACCARD)

KST = timezone(timedelta(hours=9))
OUT = Path(__file__).resolve().parents[1] / "scraper" / "out" / "social_candidates.json"
MIN_SOURCES = int(os.environ.get("SOCIAL_MIN_SOURCES", "2"))   # 교차소스 ≥N = 공론화 신호(1개=단발)
FRESH_HOURS = float(os.environ.get("SOCIAL_FRESH_HOURS", "24"))

# ── 소스(어댑터) — RSS가 가장 안정적(SSR·무인증). URL은 라이브(Actions)에서 실측·확정 필요. ──
# (소스명, RSS URL) · 비정치·생활/이슈 게시판 위주. 막히면 docs의 어그리게이터/네이버로 대체.
RSS_SOURCES = [
    ("클리앙",   os.environ.get("RSS_CLIEN",   "https://rss.clien.net/service/board/park")),
    ("뽐뿌",     os.environ.get("RSS_PPOMPPU", "https://www.ppomppu.co.kr/rss.php?id=freeboard")),
    ("보배드림", os.environ.get("RSS_BOBAE",   "https://www.bobaedream.co.kr/rss/best.php")),
    ("디시",     os.environ.get("RSS_DC",      "https://gall.dcinside.com/board/rss/?id=dcbest")),   # 디시 실시간베스트(260619 추가·운영자 요청). ⚠️ 직접커뮤=데이터센터 IP 차단 가능(클리앙·보배처럼) → 0건이면 RSS_DC env로 교체/cookie 필요. 라이브 로그서 '디시 RSS' 건수 확인.
    # ⚠️ 실측(260618): 클리앙·보배 RSS는 차단/경로폐기(0건) — 직접 RSS는 뽐뿌만 생존. 교차소스는 어그리게이터로 확보(아래).
]

# ── 어그리게이터(이슈링크) — 여러 커뮤니티 인기글을 한 페이지서 모아줌 = 교차소스(≥2)의 핵심 공급원. ──
# 직접 커뮤니티 RSS가 대부분 차단(403/430)이라(실측 260618), 한 번 긁어 다중 소스를 얻는 이 경로가 사실상 정본.
ISSUELINK_URLS = [u.strip() for u in os.environ.get(
    "ISSUELINK_URLS", "https://www.issuelink.co.kr/,https://www.issuelink.co.kr/community,https://www.issuelink.co.kr/community?page=2"
).split(",") if u.strip()]   # 홈(인기 top10) + /community(100건·13커뮤) + page2(더 많은 교차 후보·260619 수집량↑). 막힌 페이지는 graceful skip(status≠200 continue)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
# rel='<코드>-<id>' 의 커뮤니티 코드 → 표시 이름. 미등록 코드는 코드 그대로(여전히 distinct 소스로 카운트).
COMMUNITY_NAMES = {
    "fmkorea": "에펨코리아", "mlbpark": "엠팍", "theqoo": "더쿠", "clien": "클리앙", "bobae": "보배드림",
    "ppomppu": "뽐뿌", "ruliweb": "루리웹", "82cook": "82쿡", "instiz": "인스티즈", "dcinside": "디시",
    "todayhumor": "오유", "humoruniv": "웃대", "humorbest": "웃대", "natepann": "네이트판", "inven": "인벤",
    "slrclub": "SLR", "slr": "SLR", "ygosu": "와이고수", "etoland": "이토랜드", "ppomppued": "뽐뿌",
}

# 정치 컷 — 사용자 요구: 비정치 공론화만. 제목에 아래 키워드 있으면 제외.
POLITICS = ["대통령", "국회", "여당", "야당", "정당", "선거", "대선", "총선", "의원", "장관",
            "청와대", "민주당", "국민의힘", "탄핵", "개헌", "정부", "외교", "북한", "미사일", "검찰총장"]
# 노이즈 컷 — 공론화 아님(홍보·후기·질문·거래).
NOISE = ["후기", "추천좀", "질문", "구매", "할인", "이벤트", "공구", "나눔", "인증", "대란", "특가"]


def is_political(title):
    return any(p in title for p in POLITICS)


def is_noise(title):
    return any(n in title for n in NOISE)


def _age_h(ts, now):
    if not ts:
        return 999.0
    try:
        return max(0.0, (now - ts).total_seconds() / 3600)
    except Exception:
        return 999.0


def cluster_and_score(posts, now):
    """posts=[{title,source,url,ts}] → 클러스터별 버스트 랭킹 rows."""
    n = len(posts)
    toks = [tokenize(p.get("title", "")) - _STOP for p in posts]   # 소셜 chatter(추가·폭로·근황 등) 제거 → 특정 명사로 매칭(과병합 방지·러너 knews tokenize에도 적용)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        if not toks[i]:
            continue
        for j in range(i + 1, n):
            if toks[j] and same_topic(toks[i], toks[j]):
                parent[find(j)] = find(i)

    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    rows = []
    for members in clusters.values():
        srcs = sorted({posts[m]["source"] for m in members})
        tss = [posts[m].get("ts") for m in members if posts[m].get("ts")]
        newest = max(tss) if tss else None
        age = _age_h(newest, now)
        recency = max(0.0, 1.0 - age / FRESH_HOURS)               # 최근일수록 1.0 → 0
        burst = len(srcs) * 2 + len(members) + recency * 3        # 교차소스 폭(가중2) + 게시물수 + 최신성(가중3)
        rep = min(members, key=lambda m: posts[m].get("ts") or now)   # 최초 보도 = 대표
        rows.append({
            "title": posts[rep]["title"],
            "url": posts[rep].get("url", ""),
            "sources": srcs,
            "source_count": len(srcs),
            "posts": len(members),
            "age_h": round(age, 1),
            "burst": round(burst, 2),
        })
    rows.sort(key=lambda r: (r["source_count"], r["burst"]), reverse=True)
    return rows


def _parse_reltime(s, now):
    """'2 시간, 48 분전' / '37 분전' / '1 일전' → 대략 ts(now - age). 못 읽으면 now."""
    import re
    d = re.search(r"(\d+)\s*일", s)
    h = re.search(r"(\d+)\s*시간", s)
    m = re.search(r"(\d+)\s*분", s)
    age = (int(d.group(1)) * 24 if d else 0) + (int(h.group(1)) if h else 0) + (int(m.group(1)) / 60 if m else 0)
    return now - timedelta(hours=age)


def fetch_issuelink(now):
    """어그리게이터(이슈링크) — 여러 커뮤니티 인기글을 모아줌 = 교차소스 확보의 핵심.
       ISSUELINK_URLS의 페이지(홈+/community) 전부 긁어 합침. 각 행 <a rel='<community>-<id>' href=...>제목</a>
       + second_date '(N 시간, M 분전)'. source=원 커뮤니티."""
    import re
    import html as _html
    try:
        import requests
    except Exception:
        print("::warning::requests 미설치 — 이슈링크 생략")
        return []
    posts = []
    for page in ISSUELINK_URLS:
        try:
            r = requests.get(page, headers={"User-Agent": UA, "Referer": "https://www.google.com/"}, timeout=20)
            if r.status_code != 200 or not r.text:
                print(f"::warning::이슈링크 {page} status {r.status_code}")
                continue
            t = r.text
        except Exception as ex:  # noqa: BLE001
            print(f"::warning::이슈링크 {page} fetch 실패: {ex}")
            continue
        for row in re.split(r"<tr[ >]", t):
            am = re.search(r"<a\s+rel=['\"]([a-z0-9]+)-[^'\"]+['\"]\s+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", row, re.S | re.I)
            if not am:
                continue
            src, url, inner = am.groups()
            title = _html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
            title = re.sub(r"\s*\[\d+\]\s*$", "", title).strip()   # 말미 댓글수 [11] 제거
            if len(title) < 4:
                continue
            tm = re.search(r"\(([^)]*?(?:시간|분|일)[^)]*?)\)", row)
            ts = _parse_reltime(tm.group(1), now) if tm else now
            if not url.startswith("http"):
                url = "https://www.issuelink.co.kr" + url
            posts.append({"title": title, "source": COMMUNITY_NAMES.get(src, src), "url": url, "ts": ts})
    print(f"이슈링크: {len(posts)}건 · {len({p['source'] for p in posts})}개 커뮤니티 ({len(ISSUELINK_URLS)}p)")
    return posts


def fetch_rss(now):
    """직접 RSS(살아있는 소스만 · feedparser). 막힌 소스(클리앙·보배 등)는 조용히 빈 피드."""
    try:
        import feedparser
    except Exception:
        print("::warning::feedparser 미설치 — RSS 생략")
        return []
    posts = []
    for name, url in RSS_SOURCES:
        if not url:
            continue
        before = len(posts)
        try:
            d = feedparser.parse(url, agent=UA, referrer="https://www.google.com/")   # 브라우저 UA — DC 등 봇 UA 차단 회피 시도(260619)
            for e in d.entries[:60]:   # 인테이크 상향(40→60·260619 수집량↑) — 뽐뿌 등 생존 RSS서 더 많이
                title = (getattr(e, "title", "") or "").strip()
                if not title:
                    continue
                ts = None
                if getattr(e, "published_parsed", None):
                    ts = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).astimezone(KST)
                posts.append({"title": title, "source": name, "url": getattr(e, "link", "") or "", "ts": ts})
            print(f"{name} RSS: {len(posts) - before}건")   # 소스별 건수 — DC 등 차단여부 라이브 확인용(0건=차단/경로폐기)
        except Exception as ex:  # noqa: BLE001
            print(f"::warning::{name} RSS 실패: {ex}")
    return posts


def fetch_live(now):
    """라이브 수집 = 어그리게이터(이슈링크·다중 커뮤니티) + 직접 RSS(뽐뿌 등). (source, 제목) 중복 제거."""
    import re
    posts = fetch_issuelink(now) + fetch_rss(now)
    seen, out = set(), []
    for p in posts:
        key = (p["source"], re.sub(r"\s+", "", p.get("title", ""))[:40])
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    print(f"라이브 수집 합계: {len(out)}건 · {len({p['source'] for p in out})}개 소스")
    return out


def sample_posts(now):
    """코어 로직 자가검증용 표본 — 공론화 2건(교차소스) + 정치1·노이즈1(필터돼야 함)."""
    def t(h):
        return now - timedelta(hours=h)
    return [
        # 공론화 A: 층간소음 흉기 위협 — 3개 소스(클러스터·고버스트·통과)
        {"title": "아파트 층간소음 갈등 끝에 윗집 흉기 위협 영상 확산", "source": "클리앙", "url": "u1", "ts": t(2)},
        {"title": "층간소음 흉기 위협 그 아파트 주민 추가 폭로",       "source": "뽐뿌",   "url": "u2", "ts": t(1)},
        {"title": "층간소음 흉기 사건 경찰 출동 영상 퍼짐",             "source": "보배드림", "url": "u3", "ts": t(3)},
        # 공론화 B: 직장 갑질 폭로 — 2개 소스(통과)
        {"title": "유명 프랜차이즈 직장 갑질 폭로 글 일파만파",         "source": "클리앙", "url": "u4", "ts": t(5)},
        {"title": "그 프랜차이즈 갑질 폭로 추가 증언 나와",            "source": "보배드림", "url": "u5", "ts": t(4)},
        # 정치(필터돼야): 대통령/국회
        {"title": "대통령 국회 시정연설 여야 충돌",                   "source": "클리앙", "url": "u6", "ts": t(1)},
        # 노이즈(필터돼야): 할인/공구
        {"title": "에어팟 프로 역대급 할인 공구 후기",                "source": "뽐뿌",   "url": "u7", "ts": t(1)},
        # 단발(소스 1개 → MIN_SOURCES 미달로 컷)
        {"title": "우리 동네 길고양이 사료 나눔 모임",                "source": "클리앙", "url": "u8", "ts": t(2)},
    ]


def main():
    ap = argparse.ArgumentParser(description="소셜 버스트 PoC — 비정치 공론화 이슈 교차소스 검출")
    ap.add_argument("--sample", action="store_true", help="네트워크 없이 표본으로 코어 검증")
    ap.add_argument("--min-sources", type=int, default=MIN_SOURCES, help="교차소스 최소 수(기본 2)")
    args = ap.parse_args()
    now = datetime.now(KST)

    posts = sample_posts(now) if args.sample else fetch_live(now)
    kept = [p for p in posts if not is_political(p["title"]) and not is_noise(p["title"])]
    rows = cluster_and_score(kept, now)
    rows = [r for r in rows if r["source_count"] >= args.min_sources]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"소셜 버스트{' [sample]' if args.sample else ''}: 수집 {len(posts)} → 정치/노이즈 컷 후 {len(kept)} "
          f"→ 공론화 후보 {len(rows)} (교차소스≥{args.min_sources}) → {OUT}")
    for r in rows[:10]:
        print(f"  🔥 burst {r['burst']} · {r['source_count']}소스 · {r['age_h']}h · "
              f"{r['title'][:48]}  [{', '.join(r['sources'])}]")


if __name__ == "__main__":
    main()
