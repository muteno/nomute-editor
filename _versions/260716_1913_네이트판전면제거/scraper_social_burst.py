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
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import re
import math

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
# 게시물수(members) 로그캡 — 네이버 쿼리 대량수집(members 폭증)이 burst를 지배하는 것 차단(1·7 분신술+Fable).
# 커뮤(members 2~4)는 2·log2(x)가 선형과 교차해 사실상 불변, 네이버(71)만 CAP으로 포화.
POSTS_W   = float(os.environ.get("SOCIAL_POSTS_W",   "2.0"))
POSTS_CAP = float(os.environ.get("SOCIAL_POSTS_CAP", "6.0"))
# 수집량 대비 정규화 기준(운영자: "수집량이 그만큼 많으니 다른거 수집량에 대비해서 가점 배분") —
# 소스가 NORM_REF보다 많이 긁으면 게시물 개당 가점↓(개당 weight = min(1, NORM_REF/그 소스 총수집)).
# ⚙️ 20→75 (운영자 260704): 네이버 개당 가점이 과하게 깎여(100수집→0.20=20%) 교차 클러스터서 저평가 → 75로 완화(100수집→0.75=75%).
#   커뮤(대개 <20수집 = 이미 1.0)엔 거의 무영향, 뽐뿌(~60)만 부분 상향. 네이버카페(수백)는 75/N로 여전히 물량 방어(예 400→0.19).
#   platform_count 1차정렬·POSTS_CAP=6은 불변 = 네이버 단독 지배 방지 유지(가점만 상향).
NORM_REF  = float(os.environ.get("SOCIAL_NORM_REF",  "75"))

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
            "청와대", "민주당", "국민의힘", "탄핵", "개헌", "정부", "외교", "북한", "미사일", "검찰총장",
            "독재", "집권", "정권", "계엄", "특검", "지지율"]   # 260704 검토6인: '독재' 등 누수 보강("진짜 독재 가능하다고" 통과 방지)
# 노이즈 컷 — 공론화 아님(홍보·후기·질문·거래). 네이버 블로그 광고·제품추천·하우투 정보글 컷.
# (260704 카나리아: 상거래광고['롤매트 추천'] + 정보성 하우투 블로그['층간소음 대처법'·'해결 방법'·'이런 방법이']가
#  burst 상위 점거 → 상거래어+하우투어 확장. 명백어 위주로 커뮤 정상글·연예 이슈['서예지 가스라이팅'] 오컷 최소화.)
NOISE = ["후기", "추천좀", "추천", "질문", "구매", "할인", "이벤트", "공구", "나눔", "인증", "대란", "특가",
         "최저가", "쿠폰", "협찬", "내돈내산", "체험단", "분양", "시공", "견적", "설치", "상담", "홍보", "리뷰", "세일", "판매"]   # 상거래 광고(전 소스 적용)
# 하우투 블로그 상투어 — ⚠️ 네이버 소스에만 적용(is_noise의 source 인자). 전 소스 적용하면 커뮤글 오컷
# (260704 분신술 실측: "애도엔 완벽한 방법이 없어요"[문화기사]가 '방법이'로 오컷 → 소스 스코핑으로 네이버 하우투만 컷).
NOISE_NAVER = ["대처법", "예방법", "노하우", "총정리", "꿀팁", "해결 방법", "방법이"]
# 논란/공론화 신호어 — 있으면 하우투·상거래 컷 면제(연예이슈 보존·6 분신술: "서예지 가스라이팅 총정리"가
# NOISE_NAVER '총정리'로, "뒷협찬 논란"이 NOISE '협찬'으로 오컷되는 것 방지). ⚠️ is_political veto는 안 함(정치 논란은 컷 유지).
CONTROVERSY = ["가스라이팅", "갑질", "의혹", "폭로", "논란", "해명", "사과", "저격", "학폭", "왕따", "파문",
               "성희롱", "성추행", "고소", "분쟁", "황당", "목격", "충격", "경악", "공론화", "시비", "막말",
               "잠적", "먹튀", "바가지", "진상", "몰카", "불륜", "피해", "신상", "논쟁", "폭행", "갈등",
               "위협", "협박", "사망", "실종", "화재", "붕괴", "참사", "감금", "학대", "따돌림"]
# 공론화 포지티브 게이트(검토6인 260704) — 필터가 네거티브 컷(정치·노이즈)만이라 웹툰·아이폰·줄거리 등 순수
# 정보/가십/밈이 통과(라이브 6/6이 떡밥) → 위 CONTROVERSY 신호어를 '진입 요건'으로 승격(하나라도 있어야 통과).
# env로 롤백 가능(SOCIAL_TOPIC_GATE=0이면 옛 네거티브-컷-only 동작). 신호어 없는 순수 정보/밈은 컷.
TOPIC_GATE = os.environ.get("SOCIAL_TOPIC_GATE", "1") == "1"
# 네이버 계열 소스명 — 교차소스 카운트에서 1플랫폼("네이버")으로 접기(2·7·8·9·10 수렴 + Fable 채택).
# blog/cafe/kin이 3 distinct source로 세지면 MIN_SOURCES 게이트·정렬 1차키가 게이밍됨(네이버 단독 가짜 공론화).
NAVER_SRC = {"네이버블로그", "네이버카페", "지식iN"}
def _platform(src):
    return "네이버" if src in NAVER_SRC else src


def is_political(title):
    return any(p in title for p in POLITICS)


def is_controversy(text):   # 공론화 진입 신호어(제목+네이버 스니펫). TOPIC_GATE ON이면 필수요건.
    return any(c in text for c in CONTROVERSY)


NSFW = ["ㅇㅎ", "후방주의"]   # 선정성 태그 — 운영자 확정 2어휘만(가십은 통과). CONTROVERSY 면제 없이 최우선 하드컷. 구 `후방` 단독은 군 후방 실뉴스 오컷이라 `후방주의`로 정밀화(운영자).


def is_noise(title, source=""):
    if any(x in title for x in NSFW):
        return True    # 선정성 태그 = 무조건 컷(공론화 신호어 면제도 안 통함)
    if any(c in title for c in CONTROVERSY):
        return False   # 공론화 신호 = 하우투/상거래 컷 면제(연예이슈 보존)
    if any(n in title for n in NOISE):
        return True
    return _platform(source) == "네이버" and any(n in title for n in NOISE_NAVER)   # 하우투는 네이버 소스만


def _age_h(ts, now):
    if not ts:
        return 999.0
    try:
        return max(0.0, (now - ts).total_seconds() / 3600)
    except Exception:
        return 999.0


def cluster_and_score(posts, now, src_total=None):
    """posts=[{title,source,url,ts}] → 클러스터별 버스트 랭킹 rows. src_total=소스별 수집총량(수집량 대비 정규화용)."""
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
        srcs = sorted({posts[m]["source"] for m in members})          # 표시용 서비스명(뷰어 칩 구분 유지)
        plats = sorted({_platform(s) for s in srcs})                  # 네이버 3서비스→1플랫폼(정렬·색·배점 소스항용)
        tss = [posts[m].get("ts") for m in members if posts[m].get("ts")]
        newest = max(tss) if tss else None
        age = _age_h(newest, now)
        recency = max(0.0, 1.0 - age / FRESH_HOURS)               # 최근일수록 1.0 → 0
        # 게시물수 가점 = 수집량 대비 정규화 — 각 게시물 = min(1, NORM_REF/그 소스 총수집).
        # 네이버(display100·수백건)=개당 소수, 커뮤(수십)=1.0 → 많이 긁어도 물량으로 커뮤 못 누름.
        if src_total:
            wposts = sum(min(1.0, NORM_REF / max(src_total.get(posts[m]["source"], 1), 1)) for m in members)
        else:
            wposts = float(len(members))
        posts_score = min(POSTS_CAP, POSTS_W * math.log2(1.0 + wposts))   # 로그 상한(정규화 후에도 대량 완충)
        burst = len(plats) * 2 + posts_score + recency * 3         # 플랫폼폭(가중2) + 수집량정규화 게시물수 + 최신성(가중3)
        rep = min(members, key=lambda m: posts[m].get("ts") or now)   # 최초 보도 = 대표
        src_posts = dict(Counter(posts[m]["source"] for m in members))   # 소스별 글수 — 뷰어 출처성향 게이지 수집량 가중용(어느 성향 커뮤에 몇 글 = 무게중심)
        rows.append({
            "title": posts[rep]["title"],
            "url": posts[rep].get("url", ""),
            "sources": srcs,                    # 서비스명(칩 표시)
            "source_count": len(srcs),          # 원시 서비스수 — 게이트(MIN_SOURCES)용 → 네이버 단독(블로그+카페)도 생존(운영자: 교차만 생존 금지)
            "platform_count": len(plats),       # 접힌 플랫폼수 — 정렬 1차키·색티어(네이버 단독은 하단·보라 방지)
            "posts": len(members),
            "src_posts": src_posts,             # {소스명:글수} — 게이지 중간값 수집량 가중(보수 커뮤 글 많으면 보수 쏠림 · 뷰어 socMid)
            "age_h": round(age, 1),
            "burst": round(burst, 2),
        })
    rows.sort(key=lambda r: (r["platform_count"], r["burst"]), reverse=True)   # 플랫폼수 1차 → 네이버 단독(1)은 커뮤(2+) 아래·생존은 게이트가 보장
    return rows


def _parse_reltime(s, now):
    """'2 시간, 48 분전' / '37 분전' / '1 일전' → 대략 ts(now - age). 못 읽으면 now."""
    import re
    d = re.search(r"(\d+)\s*일", s)
    h = re.search(r"(\d+)\s*시간", s)
    m = re.search(r"(\d+)\s*분", s)
    age = (int(d.group(1)) * 24 if d else 0) + (int(h.group(1)) if h else 0) + (int(m.group(1)) / 60 if m else 0)
    return now - timedelta(hours=age)


# ── cupid.js(SlowAES JS 쿠키) 챌린지 우회 (260625) ──
# 이슈링크가 06-22부터 cupid.js 봇월로 전환 → 평문 GET은 767B 챌린지 페이지만 받아 0건.
# 챌린지는 결정론적 SlowAES: a=키·b=IV·c=암호문(1블록) → 쿠키 CUPID=hex(AES-128-CBC-decrypt(c, a, b)) → ?ckattempt=1 재요청.
# 무료·무키. pycryptodome 미설치면 graceful 0건(옛 동작과 동일).
_CUPID_RE = re.compile(
    r'a\s*=\s*toNumbers\("([0-9a-fA-F]+)"\)\s*,\s*'
    r'b\s*=\s*toNumbers\("([0-9a-fA-F]+)"\)\s*,\s*'
    r'c\s*=\s*toNumbers\("([0-9a-fA-F]+)"\)')


def _get_cupid(session, url, _depth=0):
    """이슈링크 GET — cupid 챌린지면 AES-CBC 복호로 CUPID 쿠키 발급 후 재요청(통과 페이지 반환)."""
    r = session.get(url, timeout=20)
    if _depth < 2 and "toNumbers(" in r.text and "ckattempt" not in url:
        m = _CUPID_RE.search(r.text)
        if not m:
            print("::warning::cupid 챌린지 파싱 실패 — 포맷 변경 가능(이슈링크 0건)")
            return r
        try:
            from Crypto.Cipher import AES
        except Exception:
            print("::warning::pycryptodome 미설치 — cupid 우회 불가(이슈링크 0건)")
            return r
        try:
            from urllib.parse import urlparse
            a, b, c = (bytes.fromhex(x) for x in m.groups())
            cookie = AES.new(a, AES.MODE_CBC, b).decrypt(c).hex()   # 1블록 CBC = AES-ECB-dec(c,a) XOR b
            session.cookies.set("CUPID", cookie, domain=urlparse(url).netloc)
        except Exception as ex:  # noqa: BLE001
            print(f"::warning::cupid 복호 실패: {ex} (이슈링크 0건)")
            return r
        sep = "&" if "?" in url else "?"
        return _get_cupid(session, url + sep + "ckattempt=1", _depth + 1)
    return r


def fetch_issuelink(now):
    """어그리게이터(이슈링크) — 여러 커뮤니티 인기글을 모아줌 = 교차소스 확보의 핵심.
       ISSUELINK_URLS의 페이지(홈+/community) 전부 긁어 합침. 각 행 <a rel='<community>-<id>' href=...>제목</a>
       + second_date '(N 시간, M 분전)'. source=원 커뮤니티. cupid.js 봇월은 _get_cupid가 통과(260625)."""
    import re
    import html as _html
    try:
        import requests
    except Exception:
        print("::warning::requests 미설치 — 이슈링크 생략")
        return []
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Referer": "https://www.google.com/"})
    posts = []
    for page in ISSUELINK_URLS:
        try:
            r = _get_cupid(sess, page)
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


# ── 네이버 검색 OpenAPI 어댑터 (기본 OFF · "붙여만" 260704) ─────────────────────────
# 네이버 블로그·카페·지식iN에서 비정치 이슈 키워드 최신글을 소셜 소스로 편입 = 교차소스 폭↑.
#   게이트 2중 = 플래그 SOCIAL_NAVER=1 AND 키(NAVER_CLIENT_ID/SECRET). 하나라도 없으면 즉시 skip(현 동작 100% 불변 = dead path).
#   켜기(라이브) = social-scan.yml env SOCIAL_NAVER '1' + GitHub Secret 2개. 무료 한도 내(검색 API 일 25,000콜).
#   설계·프로세스·플랫폼별 엔드포인트 = docs/social-burst.md.
NAVER_ON     = os.environ.get("SOCIAL_NAVER", "") == "1"
NAVER_ID     = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
NAVER_DISPLAY = int(os.environ.get("NAVER_DISPLAY", "100"))   # 수집은 많이(운영자) — 물량은 cluster_and_score 수집량정규화가 흡수(개당 가점↓)
NAVER_SORT    = os.environ.get("NAVER_SORT", "date")
# (표시이름, 서비스, 쿼리) — cafe 주력(커뮤니티성)·blog 최소·지식iN 드롭(개인 Q&A·공론화 신호 약·7 분신술).
# 연예 논란 쿼리 포함 — 운영자: "서예지 같은 연예 이슈가 오히려 SNS에서 얻어야 되는 내용"(6 분신술).
NAVER_QUERIES = [
    ("네이버카페",   "cafearticle", "층간소음 고소"),
    ("네이버카페",   "cafearticle", "갑질 폭로"),
    ("네이버카페",   "cafearticle", "학교폭력 공론화"),
    ("네이버카페",   "cafearticle", "연예인 논란"),
    ("네이버블로그", "blog",        "가스라이팅 폭로"),
]


def fetch_naver(now):
    """네이버 검색 OpenAPI(블로그·카페·지식iN) — 이슈 키워드 최신글을 소셜 소스로.
       기본 OFF: SOCIAL_NAVER=1 + 키(NAVER_CLIENT_ID/SECRET) 셋 다 있어야 작동, 아니면 빈 리스트(현 동작 불변)."""
    if not (NAVER_ON and NAVER_ID and NAVER_SECRET):
        return []
    try:
        import requests
    except Exception:
        print("::warning::requests 미설치 — 네이버 생략")
        return []
    import html as _html
    hdr = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    posts = []
    for name, svc, q in NAVER_QUERIES:
        try:
            r = requests.get(f"https://openapi.naver.com/v1/search/{svc}.json",
                             params={"query": q, "display": NAVER_DISPLAY, "sort": NAVER_SORT},
                             headers=hdr, timeout=20)
            if r.status_code != 200:
                print(f"::warning::네이버 {svc}/{q} status {r.status_code}")
                continue
            for it in r.json().get("items", []):
                title = _html.unescape(re.sub(r"<[^>]+>", "", it.get("title", ""))).strip()   # <b> 강조·HTML 엔티티 제거
                if len(title) < 4:
                    continue
                ts = None   # 날짜 없으면 None → recency 가점 0(카페 ts=now 만점 인플레·클러스터 age 오염 차단·rss와 정합·7·9 분신술)
                pd = it.get("postdate")   # 블로그만 YYYYMMDD 제공(카페는 없음 → None)
                if pd and len(pd) == 8:
                    try:
                        ts = datetime(int(pd[:4]), int(pd[4:6]), int(pd[6:8]), tzinfo=KST)
                    except Exception:
                        ts = None
                desc = _html.unescape(re.sub(r"<[^>]+>", "", it.get("description", ""))).strip()   # 본문 스니펫(무료·추가콜0·검토6인 260704) — 공론화 신호어/정치 매칭 표면적↑. ⚠️ 클러스터 토큰엔 미편입(제목만=과병합 방지)
                posts.append({"title": title, "source": name, "url": it.get("link", ""), "ts": ts, "desc": desc[:200]})
        except Exception as ex:  # noqa: BLE001
            print(f"::warning::네이버 {svc}/{q} 실패: {ex}")
    print(f"네이버: {len(posts)}건 ({len(NAVER_QUERIES)}쿼리·display={NAVER_DISPLAY})")
    return posts


def fetch_live(now):
    """라이브 수집 = 어그리게이터(이슈링크·다중 커뮤니티) + 직접 RSS(뽐뿌 등) + 네이버(기본 OFF). (source, 제목) 중복 제거."""
    import re
    posts = fetch_issuelink(now) + fetch_rss(now) + fetch_naver(now)
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
        # 네이버 하우투(네이버 소스 → NOISE_NAVER 컷 검증)
        {"title": "층간소음 대처법 총정리 이런 방법이",              "source": "네이버블로그", "url": "n1", "ts": t(1)},
        {"title": "층간소음 해결 방법 노하우 꿀팁 모음",            "source": "네이버카페",   "url": "n2", "ts": t(1)},
        # 커뮤글 '방법이'(커뮤라 통과 = 오컷 방지 검증)
        {"title": "애도에는 완벽한 방법이 없어요 신간 소설 화제",      "source": "클리앙",     "url": "n3", "ts": t(2)},
        # 연예 이슈 — 네이버 '총정리'지만 CONTROVERSY '가스라이팅' veto로 보존 + 커뮤(더쿠)×네이버 = 2플랫폼 통과(교차 공론화)
        {"title": "서예지 가스라이팅 논란 총정리 재조명",            "source": "네이버블로그", "url": "n4", "ts": t(1)},
        {"title": "서예지 가스라이팅 그 사건 재점화 공론화",         "source": "더쿠",       "url": "n5", "ts": t(1)},
        # 네이버 단독(블로그+카페·커뮤 교차 0) 진짜 이슈 — 원시 source_count 2로 생존·platform 1로 하단(운영자: 교차만 생존 금지)
        {"title": "빅히트 소속사 갑질 폭로 파문 확산",              "source": "네이버블로그", "url": "n6", "ts": t(1)},
        {"title": "빅히트 갑질 폭로 추가 증언 공론화",             "source": "네이버카페",   "url": "n7", "ts": t(1)},
    ]


def main():
    ap = argparse.ArgumentParser(description="소셜 버스트 PoC — 비정치 공론화 이슈 교차소스 검출")
    ap.add_argument("--sample", action="store_true", help="네트워크 없이 표본으로 코어 검증")
    ap.add_argument("--min-sources", type=int, default=MIN_SOURCES, help="교차소스 최소 수(기본 2)")
    args = ap.parse_args()
    now = datetime.now(KST)

    posts = sample_posts(now) if args.sample else fetch_live(now)
    def _txt(p): return p.get("title", "") + " " + p.get("desc", "")   # 제목+네이버 스니펫(정치·공론화 매칭용·is_noise는 제목만=광고)
    kept = [p for p in posts
            if not is_political(_txt(p))
            and not is_noise(p["title"], p.get("source", ""))
            and (not TOPIC_GATE or is_controversy(_txt(p)))]   # 포지티브 공론화 게이트(검토6인 260704·env로 롤백)
    src_total = Counter(p["source"] for p in kept)   # 소스별 수집총량 — 수집량 대비 배점 정규화(운영자)
    rows = cluster_and_score(kept, now, src_total)
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
