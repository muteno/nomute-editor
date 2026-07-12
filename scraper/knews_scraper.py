#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
knews_scraper.py — 한국 주요 뉴스 RSS 스크래퍼 (독립 실행 모듈)

역할
  검증된 언론사 RSS 피드를 긁어 '주요 기사'를 선별한다.
  '주요도'는 여러 매체에 교차 등장하는 정도 + 최신성으로 판정한다.
  봇 탐지가 걸린 HTML을 뚫는 대신, 애초에 공개된 RSS만 사용한다 → 차단 위험 0.

출력
  articles.json : 수집된 전체 기사 (주요도 점수·대표이미지 포함, 주요도순 정렬)
  top_urls.txt  : 주요도 상위 기사의 원문 URL 목록
                  (다음 단계 — GitHub pending/ 에 꽂아 분석 파이프라인에 연결할 용도)

사용 예
  python3 knews_scraper.py                          # 기본: 주요 섹션, 최근 24h
  python3 knews_scraper.py --hours 12 --min-cross 2 # 12시간 + 2개 매체 이상 교차한 것만
  python3 knews_scraper.py --categories all         # 전 섹션
  python3 knews_scraper.py --categories politics,economy
  python3 knews_scraper.py --feeds feeds.csv --out ./out

의존성
  pip install feedparser requests

주의
  feeds.csv 의 RSS 주소는 출처(knews-rss) 기준 2023-10이라 일부는 죽어 있을 수 있다.
  죽은 피드는 자동으로 건너뛰고 stderr 로그에 표시된다. 살아있는 것만으로 동작한다.
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
import feedparser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stock_filter import is_excluded_title  # 증권/시황 노이즈 수집 제외(SSOT · 운영자 260701)

# ── 설정 ────────────────────────────────────────────────────────────
# 평범한 브라우저로 위장. RSS는 봇 차단이 거의 없지만,
# User-Agent 없는 raw 요청만 막는 서버가 있어 최소한의 위장을 둔다.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# '주요 기사' 기본 섹션 — 연예/스포츠/생활/문화 등 연성 뉴스 제외
DEFAULT_CATEGORIES = {"_all_", "politics", "economy", "society", "international"}

# 제목 토큰화 시 버릴 불용어 (오탐 줄이기용, 필요시 보강)
STOPWORDS = {
    "속보", "단독", "종합", "포토", "영상", "인터뷰", "오늘", "내일", "오전", "오후",
    "기자", "그래픽", "사진", "코멘트", "전망", "관련", "현장", "이것", "그것",
    "공식", "전체", "주요", "기사",
}

FEED_DELAY = 0.4    # 피드 간 딜레이(초) — 서버 매너
REQ_TIMEOUT = 10    # 요청 타임아웃(초)
# 교차등장 판정: 핵심 명사 교집합이 이 개수 이상이면 같은 토픽으로 본다.
# 2→3 (260616): inter=2 단일링크가 정치 공통어(이란·선관위·국힘…)로 무관 기사를 transitive
# chaining → 거대블롭(실측 980개=45%·cross20). 3 요구하면 블롭 980→126·cross20→16, 후보는
# 오히려 100→179(블롭이 삼키던 진짜 사건들이 드러남). 짧은 제목은 JACCARD_BACKUP이 보완해 recall 유지.
MIN_TOKEN_OVERLAP = int(os.environ.get("CLUSTER_MIN_OVERLAP", "3"))
# 겹침이 1개뿐일 때 보조로 쓰는 자카드 임계값(짧은 제목 보정)
JACCARD_BACKUP = float(os.environ.get("CLUSTER_JACCARD", "0.5"))


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", file=sys.stderr)


# ── 피드 로딩 ────────────────────────────────────────────────────────
def load_feeds(csv_path, categories):
    """feeds.csv → 대상 피드 목록. categories=None 이면 전체.
    행별 가드(260713 평의회1) — 수기 유지 CSV라 한 행 결손(컬럼 누락·비따옴표 콤마)이 KeyError로
    런 전체를 0건 산출로 죽이던 것을 결손 행 skip+경고로 격리(fetch_feed의 피드 단위 격리와 짝)."""
    feeds = []
    with open(csv_path, encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):   # 2 = 헤더 다음 실제 행번호
            try:
                if not (row.get("publisher") and (row.get("url") or "").startswith("http")):
                    log(f"feeds.csv {i}행 결손 skip(publisher/url): {dict(row)}")
                    continue
                cats = set((row.get("categories") or "").split("|"))
                if categories is None or (cats & categories):
                    feeds.append(row)
            except Exception as e:  # noqa: BLE001 — 행 단위 격리(전체 크래시 방지)
                log(f"feeds.csv {i}행 파싱 실패 skip: {e}")
    return feeds


# ── 텍스트 처리 ──────────────────────────────────────────────────────
# 링크에서 떼어낼 추적 파라미터. 쿼리 전체를 지우면 서울신문(newsView.php?id=…)처럼
# 기사 식별자가 쿼리에 든 매체는 전 기사가 한 URL로 뭉개져 대량 오중복제거된다.
# → 추적용 키만 골라 떼고 ?id= 같은 기능성 파라미터는 보존한다.
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "igshid", "spm", "ref", "ref_src", "cid", "ncid",
}


def normalize_link(url):
    """링크 정규화 — 추적 파라미터·프래그먼트만 제거(식별자 쿼리는 보존)해 중복 판정 정확도↑."""
    url = (url or "").strip()
    parts = urlsplit(url)
    if parts.scheme and parts.scheme.lower() not in ("http", "https"):
        return ""    # http(s)만 허용 — 오염 RSS의 javascript:/data: 링크가 candidates.json→뷰어 <a href>로 흐르는 DOM-XSS 차단(앵글9·근본방벽)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if k.lower() not in _TRACKING_PARAMS]
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), ""))
    return url.rstrip("/")


# 일부 매체(예: 프레시안) RSS는 엔티티의 '&'를 흘려 'ldquo;'처럼 이름만 남긴 깨진
# 형태로 제목을 내보낸다. 그대로 두면 제목이 깨질 뿐 아니라 'ldquo'·'hellip' 등이
# tokenize 에서 가짜 공통 토큰이 돼 무관한 기사들이 거짓 교차클러스터로 묶인다.
# → '&'를 복원해 unescape 한다. (?<!&) 로 이미 정상인 엔티티는 건드리지 않는다.
_BARE_ENTITY = re.compile(
    r"(?<!&)(amp|quot|apos|nbsp|lt|gt|ldquo|rdquo|lsquo|rsquo|"
    r"hellip|middot|mdash|ndash|laquo|raquo|deg|copy|reg|trade|"
    r"uarr|darr|larr|rarr|harr);"
)


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")     # 태그 제거
    s = _BARE_ENTITY.sub(r"&\1;", s)          # 깨진 엔티티 '&' 복원
    s = html.unescape(s)                       # 엔티티 → 실제 문자(" " ' ' … · 등)
    return re.sub(r"\s+", " ", s).strip()


def tokenize(title):
    """제목 → 핵심 토큰 집합 (교차등장 유사도용)."""
    title = re.sub(r"\[[^\]]*\]", " ", title)   # [속보] 같은 머리표 제거
    title = re.sub(r"<[^>]+>", " ", title)
    # 한글/영문/숫자를 각각 분리 추출 — "2500선"이 "2500"+"선"으로 갈려
    # 매체 간 숫자 공통 토큰(예: 코스피 '2500')이 제대로 매칭된다. 1글자는 버림.
    tokens = re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}|[0-9]{2,}", title)
    return {t for t in tokens if t not in STOPWORDS}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def same_topic(ta, tb):
    """두 제목 토큰집합이 같은 사건을 가리키는가."""
    inter = len(ta & tb)
    if inter == 0:
        return False
    if inter >= MIN_TOKEN_OVERLAP:
        return True
    return jaccard(ta, tb) >= JACCARD_BACKUP


# ── 수집 ────────────────────────────────────────────────────────────
def fetch_feed(feed):
    """단일 피드 수집. 네트워크 예외는 1회 재시도(1.5s 텀) — 간헐 타임아웃 1건에도 dead_feeds
    구성이 요동해 obs 안정본(커밋 생략)이 무력화되던 것 방지(260702 평의회: transient 이중실패 확률 ≈ p²).
    실패 시 None + 로그. (bozo/빈피드 = 콘텐츠 문제라 재시도 안 함.)"""
    url = feed["url"]
    for attempt in (1, 2):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT)
            r.raise_for_status()
            parsed = feedparser.parse(r.content)
            if parsed.bozo and not parsed.entries:
                log(f"  ⚠ 파싱불가/빈피드: {feed['publisher']} {feed['title']}")
                return None
            return parsed
        except Exception as e:
            if attempt == 1:
                time.sleep(1.5)
                continue
            log(f"  ✗ 실패({type(e).__name__}): {feed['publisher']} {feed['title']} — {url}")
            return None


def parse_time(entry):
    """발행시각 → aware datetime(UTC). 없으면 None."""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
    return None


# ── 대표 이미지 추출 ─────────────────────────────────────────────────
# RSS 안에 든 이미지만 본다 — 원문 HTML 페이지는 안 긁음(차단위험 0 원칙 유지).
_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
_IMG_EXT_RE = re.compile(r"\.(?:jpe?g|png|gif|webp)(?:[?#]|$)", re.I)


def extract_image(entry):
    """RSS 항목 대표 이미지 URL. 우선순위 enclosure → media:content → media:thumbnail → 본문 <img>.
    (nomute 홈페이지 fetchRSS 로직 차용. 단 원문 og:image 폴백은 RSS-only·차단위험 때문에 일부러 뺌.)"""
    for enc in entry.get("enclosures") or []:
        href = enc.get("href") or enc.get("url")
        if href and ((enc.get("type") or "").startswith("image") or _IMG_EXT_RE.search(href)):
            return href
    for mc in entry.get("media_content") or []:
        url = mc.get("url")
        if url and (mc.get("medium") == "image"
                    or (mc.get("type") or "").startswith("image")
                    or _IMG_EXT_RE.search(url)):
            return url
    for mt in entry.get("media_thumbnail") or []:
        if mt.get("url"):
            return mt["url"]
    blobs = [entry.get("summary") or ""]
    blobs += [c.get("value") or "" for c in (entry.get("content") or [])]
    for blob in blobs:
        m = _IMG_SRC_RE.search(blob)
        if m:
            return m.group(1)
    return None


def collect(feeds, hours):
    """모든 피드를 긁어 기사 리스트 생성 (시간필터 + 중복제거). 피드별 건강(health) 원장도 함께 반환."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    seen = set()
    articles = []
    ok, dead = 0, 0
    health = []   # 피드별 {publisher,title,url,ok,n} — 죽은 피드가 stderr로만 사라지던 무음 드리프트 방지(260702)

    for feed in feeds:
        parsed = fetch_feed(feed)
        time.sleep(FEED_DELAY)
        if parsed is None:
            dead += 1
            health.append({"publisher": feed["publisher"], "title": feed["title"],
                           "url": feed["url"], "ok": False, "n": 0, "fresh": 0})
            continue
        ok += 1
        # fresh = 시간창 내(또는 시각 미상) 엔트리 수 — fetch 되고 n>0인데 fresh=0이면 '좀비'(콘텐츠 갱신 멈춘 피드).
        # 실증: JTBC fs.jtbc RSS가 응답·형식 유효인데 2024-10에서 멈춰 수집 기여 0(260702 실측).
        fresh = 0
        for e in parsed.entries:
            pt = parse_time(e)
            if pt is None or pt >= cutoff:
                fresh += 1
        health.append({"publisher": feed["publisher"], "title": feed["title"],
                       "url": feed["url"], "ok": True, "n": len(parsed.entries), "fresh": fresh})
        for e in parsed.entries:
            link = normalize_link(e.get("link", ""))
            if not link or link in seen:
                continue
            title = strip_tags(e.get("title", ""))
            if is_excluded_title(title):   # 증권/시황 노이즈 = 수집 제외(stock_filter SSOT · 운영자 260701)
                continue
            pub = parse_time(e)
            if pub and pub < cutoff:
                continue
            seen.add(link)
            articles.append({
                "title": title,
                "link": link,
                "publisher": feed["publisher"],
                "category": feed["categories"],
                "published": pub.isoformat() if pub else None,
                "summary": strip_tags(e.get("summary", ""))[:200],
                "image": extract_image(e),
            })

    log(f"피드 결과: 성공 {ok} / 죽음 {dead} / 수집 수 {len(articles)}건")
    return articles, health


# ── 주요도 산정 (교차등장) ───────────────────────────────────────────
# burst = 한 사건(클러스터)을 BURST_WINDOW_MIN 분 안에 동시 보도한 서로 다른 매체 수.
# cross(24h 누적)와 분리된 '동시성/속도' 지표 — 속보 1차 게이트(to_candidates 에서 burst≥3).
BURST_WINDOW_MIN = 15
# 대표 매체 픽 순위: 보수 메이저(조선>동아) → 중도·중진보 메이저 → 경제 메이저 → 지상파 → 통신사 →
# (미등재=최하·최초보도 폴백). 운영자 요구(260622): 다매체 이슈에서 원문 링크가 통신사(뉴시스)·외딴 군소로
# 튀지 말고 '풀텍스트 종합 메이저'를 먼저 잇게 = 조선/동아 보수메이저 → 중진보 메이저 순. 통신사(연합·뉴시스)는
# 풀텍스트지만 종합지·지상파 다음(군소보단 위). 미등재 매체는 _pick_rank 가 최하(len) → 자동 후순위.
# ⚠️ url/dedup/event_key/cross/클러스터링은 불변 — 이 순위는 '대표 표시·원문 링크' 픽에만 영향(주변부).
# ⚠️ 중앙일보·한국일보 = 현재 '유령'(feeds.csv 피드 0개 — 중앙 RSS는 공식 종료 페이지 실측·한국일보 RSS 미확인 = 260702).
#   수집 0이라 픽 매칭도 0(무해 dead entry). 목록엔 유지 — 미래 재수집(신규 피드·네이버API 등) 시 순위 자동 복원.
PICK_PRIORITY = [
    "조선일보", "동아일보", "중앙일보", "세계일보", "국민일보",   # 보수 메이저(종합·풀텍스트)
    "한국일보", "서울신문", "한겨레신문", "경향신문",            # 중도·중진보 메이저(종합·풀텍스트)
    "한국경제", "매일경제", "이데일리",                          # 경제 메이저
    "SBS", "MBC", "노컷뉴스",                                   # 지상파·방송
    "연합뉴스", "뉴시스",                                       # 통신사(풀텍스트 통신 — 종합지·지상파 다음)
]


def _pick_rank(pub):
    return PICK_PRIORITY.index(pub) if pub in PICK_PRIORITY else len(PICK_PRIORITY)


def _burst(members, articles):
    """멤버 발행시각을 BURST_WINDOW_MIN 슬라이딩 윈도우로 훑어 동시 매체(distinct) 최대치."""
    pts = []
    for m in members:
        p = articles[m].get("published")
        if not p:
            continue
        try:
            pts.append((datetime.fromisoformat(p), articles[m]["publisher"]))
        except ValueError:
            continue
    pts.sort(key=lambda x: x[0])
    best = 0
    for i, (t0, _) in enumerate(pts):
        pubs = set()
        for t, pb in pts[i:]:
            if (t - t0).total_seconds() > BURST_WINDOW_MIN * 60:
                break
            pubs.add(pb)
        if len(pubs) > best:
            best = len(pubs)
    return best


def score_crosspost(articles):
    """유사 제목끼리 Union-Find 로 묶고, 클러스터 내 '고유 매체 수'를 주요도로."""
    n = len(articles)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    toks = [tokenize(a["title"]) for a in articles]
    # O(n²) — RSS 기사 수백 건 규모라 충분히 빠르다.
    for i in range(n):
        if not toks[i]:
            continue
        for j in range(i + 1, n):
            if toks[j] and same_topic(toks[i], toks[j]):
                union(i, j)

    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    for members in clusters.values():
        pubs = {articles[m]["publisher"] for m in members}
        score = len(pubs)  # 몇 개 매체에 떴나 = 주요도
        # 클러스터 대표 = 가장 먼저 보도한 기사(최초 발) — 빈 시각은 뒤로
        rep = min(members, key=lambda m: (articles[m]["published"] is None,
                                          articles[m]["published"] or "",
                                          articles[m].get("link") or ""))   # url 막타이브레이크=결정적(rep 흔들림↓)
        burst = _burst(members, articles)
        # 속보 픽 = 보수메이저 우선(조선>동아…) — 없으면 최초보도.
        # ⚠️ 대표와 '동일 토픽'인 멤버로만 한정 = transitive chaining 오병합(무관 기사가 한
        #   클러스터에 섞임)일 때 엉뚱한 기사를 픽하는 것 차단(예: '서울대 10개'↔'삼성전기 10배').
        sub = [m for m in members
               if m == rep or (toks[rep] and toks[m] and same_topic(toks[rep], toks[m]))]
        pick = min(sub, key=lambda m: (_pick_rank(articles[m]["publisher"]),
                                       articles[m]["published"] is None,
                                       articles[m]["published"] or ""))
        for m in members:
            articles[m]["cross_score"] = score
            articles[m]["cluster_size"] = len(members)
            articles[m]["is_cluster_rep"] = (m == rep)
            articles[m]["burst"] = burst
        articles[rep]["breaking_pick"] = {
            "url": articles[pick]["link"],
            "media": articles[pick]["publisher"],
            "title": articles[pick]["title"],
        }
        # 클러스터 멤버 url 직렬화(정렬=결정적·가산) — to_candidates 별칭승계의 입력.
        # rep url이 점프해도 멤버 교집합으로 '같은 사건' 추적(클러스터링 경계·cross 불변, 데이터만 추가).
        # mega(over-merge 의심·별칭 비대상, >40)는 미직렬화 = 페이로드 절감 + 정합.
        articles[rep]["cluster_members"] = sorted(
            {articles[m].get("link") for m in members if articles[m].get("link")}) if len(members) <= 40 else []
    return articles


# ── 메인 ────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="한국 주요 뉴스 RSS 스크래퍼")
    ap.add_argument("--feeds", default=str(Path(__file__).resolve().parent / "feeds.csv"),
                    help="피드 목록 CSV(기본=스크립트 옆 feeds.csv — CWD 무관)")
    ap.add_argument("--out", default=".", help="출력 디렉토리")
    ap.add_argument("--hours", type=int, default=24, help="최근 N시간 기사만 수집")
    ap.add_argument("--categories", default="major",
                    help="'major'(주요섹션) | 'all'(전체) | 'politics,economy' 식 지정")
    ap.add_argument("--min-cross", type=int, default=1,
                    help="top_urls.txt 에 넣을 최소 교차등장 매체 수")
    ap.add_argument("--top", type=int, default=30, help="top_urls.txt 최대 개수")
    args = ap.parse_args()

    if args.categories == "major":
        cats = DEFAULT_CATEGORIES
    elif args.categories == "all":
        cats = None
    else:
        cats = set(args.categories.split(","))

    feeds = load_feeds(args.feeds, cats)
    log(f"대상 피드 {len(feeds)}개 (카테고리: {args.categories})")

    articles, health = collect(feeds, args.hours)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # 피드 건강 원장 — 죽은 피드 관측 가능화(scrape.yml이 안정본을 scraper/obs/로 복사 → daily_health가 리포트).
    # 전 피드 죽음(articles 0)일 때가 제일 중요한 순간이라 조기 return *앞*에 쓴다. 시각 = KST(§📐 🕘).
    # ⚠️ 원장 쓰기 = 비치명(try) — 관측층 IO 실패가 코어(articles.json→candidates 갱신)를 못 막게(260702 평의회).
    try:
        kst = timezone(timedelta(hours=9))
        (out / "feed_health.json").write_text(json.dumps({
            "ts": datetime.now(kst).isoformat(timespec="seconds"),
            "ok": sum(1 for h in health if h["ok"]),
            "dead": sum(1 for h in health if not h["ok"]),
            "feeds": health,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        # obs 커밋용 안정본 — ts·n·fresh(매 런 변동 필드) 제외 = 죽은/좀비 '구성'이 바뀔 때만 내용 변화.
        # 안 그러면 밤(뉴스 없어 candidates 변동 0) 런의 '커밋 생략'이 전부 커밋으로 바뀜(+68커밋/일 노이즈).
        # zombie = 응답·형식 유효(ok·n>0)인데 시간창 내 발행 0 = 갱신 멈춘 피드(주간 니치 피드는 일시 오탐 가능 — 정보성).
        (out / "feed_health_obs.json").write_text(json.dumps({
            "ok": sum(1 for h in health if h["ok"]),
            "dead": sum(1 for h in health if not h["ok"]),
            "dead_feeds": [{"publisher": h["publisher"], "title": h["title"], "url": h["url"]}
                           for h in health if not h["ok"]],
            "zombie_feeds": [{"publisher": h["publisher"], "title": h["title"], "url": h["url"]}
                             for h in health if h["ok"] and h["n"] > 0 and h["fresh"] == 0],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log(f"feed_health 기록 실패(비치명·계속): {e}")

    if not articles:
        log("수집된 기사 없음 — 피드 URL이 죽었거나 시간범위 내 기사가 없음")
        return

    articles = score_crosspost(articles)
    articles.sort(key=lambda a: (a["cross_score"], a["published"] or ""), reverse=True)

    (out / "articles.json").write_text(
        json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")

    # pending 연결용: 클러스터 대표 + 교차등장 임계 충족 기사의 URL만
    top = [a for a in articles
           if a["cross_score"] >= args.min_cross and a.get("is_cluster_rep")][:args.top]
    (out / "top_urls.txt").write_text(
        "\n".join(a["link"] for a in top), encoding="utf-8")

    log(f"저장 완료 → {out/'articles.json'} ({len(articles)}건), "
        f"{out/'top_urls.txt'} ({len(top)}건)")

    print(f"\n=== 주요 기사 TOP {min(15, len(articles))} ===")
    for a in articles[:15]:
        flag = "🔥" if a["cross_score"] >= 2 else "  "
        print(f"{flag} [{a['cross_score']}매체] {a['publisher']:6s} | {a['title']}")


if __name__ == "__main__":
    main()
