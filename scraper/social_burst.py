#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 소셜 버스트 PoC(뼈대) — 한국 커뮤니티/소셜 hot-post를 교차소스로 묶어
#   '급발 공론화 이슈'(비정치: 가정불화·갑질·이웃분쟁·학폭 등)를 검출한다.
#
# 구조: ① 소스 어댑터(RSS/네이버) → 게시물 수집 ② 클러스터(knews tokenize·same_topic 재사용·드리프트0)
#       ③ 버스트 스코어(교차소스 폭 × 최신성) ④ 정치/노이즈 필터 → ⑤ 랭킹 JSON.
# 라이브 = Actions(열린 네트워크/키)에서. 로컬 코어 검증 = `python3 scraper/social_burst.py --sample`.
#
# ⚠️ 아직 뷰어 수집함에 미배선(PoC). 출력 = scraper/out/social_candidates.json (별개 레인).
#    배선·소스확정·튜닝은 docs/social-burst.md 참조.
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import knews_scraper as K   # 라이브(Actions): tokenize·same_topic 재사용 = 클러스터 단일 출처(드리프트0)
    tokenize, same_topic = K.tokenize, K.same_topic
except Exception:   # 로컬(feedparser 미설치) 폴백 — knews 미러. ⚠️ 정본은 knews_scraper, 라이브는 위 import가 탐.
    import re
    _STOP = {"속보", "단독", "종합", "전문", "공식", "오늘", "내일", "관련", "기자", "영상", "사진"}
    _OVL = int(os.environ.get("CLUSTER_MIN_OVERLAP", "3"))

    def tokenize(title):
        title = re.sub(r"\[[^\]]*\]", " ", title)
        title = re.sub(r"<[^>]+>", " ", title)
        return {t for t in re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}|[0-9]{2,}", title) if t not in _STOP}

    def _jac(a, b):
        return len(a & b) / len(a | b) if (a and b) else 0.0

    def same_topic(ta, tb):
        inter = len(ta & tb)
        return inter >= _OVL or (inter > 0 and _jac(ta, tb) >= 0.5)

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
    # TODO(라이브 실측 후 추가): 82쿡 인기글·네이트판 톡톡·디시 실북·인스티즈 등 RSS/SSR.
]

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
    toks = [tokenize(p.get("title", "")) for p in posts]
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


def fetch_live(now):
    """RSS 소스에서 게시물 수집(라이브). feedparser 필요. 막히면 빈 리스트 → docs 참조해 소스 교체."""
    try:
        import feedparser  # noqa: F401
    except Exception:
        print("::warning::feedparser 미설치 — `pip install feedparser` (Actions). 빈 결과.")
        return []
    import feedparser
    posts = []
    for name, url in RSS_SOURCES:
        if not url:
            continue
        try:
            d = feedparser.parse(url)
            for e in d.entries[:40]:
                title = (getattr(e, "title", "") or "").strip()
                if not title:
                    continue
                ts = None
                if getattr(e, "published_parsed", None):
                    ts = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).astimezone(KST)
                posts.append({"title": title, "source": name,
                              "url": getattr(e, "link", "") or "", "ts": ts})
        except Exception as ex:  # noqa: BLE001
            print(f"::warning::{name} RSS 실패: {ex}")
    return posts


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
