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
           "tech": "테크", "it": "테크", "science": "테크", "culture": "문화",
           "sports": "문화", "entertainment": "문화", "ent": "문화", "cartoon": "문화"}   # 스포츠·연예·만화 = 문화(운영자 1안 — 전용 피드 24개가 빈칸→사회 오분류로 새던 것 봉합·260625)


def cat_ko(category):
    # 피드 categories 토큰(쉼표·공백·슬래시·파이프 구분) 중 첫 매핑값. culture|entertainment→문화, politics|international→정치.
    for tok in re.split(r"[,\s/|]+", str(category or "").lower()):
        if tok in CAT_MAP:
            return CAT_MAP[tok]
    return ""


# 종합(_all_)·미매핑 피드 폴백 — 제목 키워드로 대분류 추정(뷰어 articleCat CAT_KW와 동일 취지·운영자 260623).
# 스포츠는 문화에 포함(운영자 1안). 0매칭이면 "" 유지(수집함은 빈칸 허용 — 사회 강제 안 함=보수적).
CAT_KW = {
    "국제": ["트럼프", "바이든", "미국", "중국", "일본", "러시아", "우크라", "이란", "이스라엘", "가자", "전쟁", "외교", "정상", "종전", "협상", "백악관", "관세", "푸틴", "시진핑", "나토", "중동", "북한", "김정은", "파병"],
    "경제": ["경제", "금융", "증시", "주가", "코스피", "코스닥", "환율", "부동산", "집값", "금리", "매출", "영업", "실적", "투자", "수출", "무역", "물가", "부채", "고용", "세금", "상장", "은행", "인수", "합병", "스타트업",
             "채무", "부도", "파산", "임금", "실업", "연봉", "회장", "경영", "독점"],   # py↔js 정합 흡수 (260628 C9 — viewer에만 있던 경제어·check_cat_kw 가드 · 스타트업=경제 통일[테크 아님])
    "문화": ["영화", "드라마", "음악", "가수", "배우", "공연", "전시", "예술", "연예", "아이돌", "스포츠", "축구", "야구", "올림픽", "월드컵", "중계", "게임", "웹툰", "콘서트", "앨범", "예능", "감독", "넷플릭스", "OTT", "시즌", "데뷔", "컴백", "신곡", "개봉", "관객", "흥행", "박스오피스", "빌보드", "그래미", "뮤지컬", "박물관", "미술관", "축제", "만화", "문학", "소설", "작가", "OST", "방탄", "BTS", "블랙핑크", "뉴진스", "아이브", "세븐틴", "에스파", "르세라핌", "MLB", "KBO", "프로야구", "홈런", "손흥민", "이정후", "류현진", "메달", "우승", "결승", "갤러리", "패션", "관람", "뮤직비디오", "뷰티", "상영", "연주", "전시회", "출연",   # 관람~출연 = py↔js 정합 흡수(260628 C9 — viewer에만 있던 문화어·check_cat_kw 가드)
              # 야구/스포츠 전문용어 — 비유적·폭력적으로 들려 사회로 오독되기 쉬운 것 위주(운영자 260625)
              "삼진", "사구", "빈볼", "병살", "끝내기", "도루", "폭투", "강판", "완봉", "완투", "보크", "만루", "볼넷", "출루", "타점", "방어율", "타율", "평균자책", "자책점", "선발투수", "불펜", "마무리투수", "연타석", "벤치클리어링", "이닝", "타석", "투구", "결승타", "세이브", "노히트", "퍼펙트게임", "호수비", "역전승", "한국시리즈", "포스트시즌", "플레이오프", "와일드카드", "골든글러브", "선취점",
              "해트트릭", "페널티킥", "코너킥", "자책골", "선제골", "결승골", "승점", "강등", "승격", "어시스트", "득점왕", "구단", "프로농구", "프로배구", "K리그", "챔스", "챔피언스리그", "포메이션", "원클럽맨", "이적료",   # 부분매칭·비유 오염어(안타[안타까운]·타격·등판·방출·실책·리그·FA) 제외
              # 셀럽 라이프스타일 + 스포츠 종목어 (운영자 260627·평의회 8인 — 셀럽 라이프/골프·UFC·테니스가 빈칸·사회로 새던 것 보강 · 정치인 비중복 연예-전속 어휘만[근황·인스타·명품은 정치인도 써서 제외] · 단어 다중자=부분매칭 안전 · 사회 키워드 동반 시 아래 사회-우선 tie-break이 셀럽 범죄를 사회로 보존)
              "열애", "열애설", "결별", "재혼", "만삭", "득남", "득녀", "웨딩", "청첩장", "화보", "먹방", "브이로그", "인플루언서", "예비신부", "예비신랑", "PGA", "LPGA", "KLPGA", "KPGA", "UFC", "MMA", "테니스", "골프", "복싱", "윔블던",
              # 토너먼트 대진·국대 감독·예능 컬럼태그 (운영자 260627 — '월드컵' 단어 없는 32강 경우의수·국대 감독명 단신·연예 반응기사가 빈칸→사회 catch-all로 새던 것 보강 · 대진수(32강~4강)=대회 전용·홍명보=현 국대 감독명[손흥민·이정후류 인물어 패턴]·순간포착=연예/스포츠 반응 컬럼 · 셀럽 범죄는 CRIME_OVERRIDE 하드가드가 사회 보존)
              "32강", "16강", "8강", "4강", "홍명보", "순간포착",
              # KBO 야구 주요용어 + 10개 구단 마스코트 (운영자 260628 — "다승 1위 KIA" 등 야구 기사가 사회 catch-all로 새던 것 보강 · 구단 줄임말[기아·삼성·LG·롯데·한화·두산·KT·NC·SSG·키움]은 飢餓·기업명과 충돌해 제외, 무충돌 마스코트만)
              "다승", "승률", "연승", "연패", "다승왕", "타격왕", "도루왕", "타점왕", "홈런왕", "선발승", "구원승", "완봉승", "매직넘버", "가을야구", "와이어투와이어", "사이클링히트",
              "타이거즈", "라이온즈", "트윈스", "베어스", "위즈", "랜더스", "다이노스", "자이언츠", "히어로즈", "이글스",
              # 멜론 차트인 가수·그룹명 = 문화 고정 (운영자 260628 — 차트 진입 아티스트는 사건어 없이도 문화 · 운영자 큐레이션 리스트로 점증 · 흔한단어 충돌명[있지·비·god·거미 등] 제외 = 고유·무충돌만 · viewer와 동기)
              "베이비몬스터",
              # 멜론 차트인 가수·그룹명 일괄 등재 (운영자 큐레이션 260628 — 차트 아티스트=문화 고정 · 라이브 충돌스캔 통과한 고유명만[충돌어 지수=주가지수·청하=신청하·리사=변리사·슈화=이슈화·라이즈=엔터프라이즈·태연=태연하게·선미=船尾·레이=플레이 등 + 논외 거미·god·비 제외] · viewer와 동기)
              "엔하이픈", "투모로우바이투게더", "스트레이키즈", "제로베이스원", "보이넥스트도어", "투어스", "플레이브", "에이티즈", "더보이즈", "몬스타엑스", "슈퍼주니어", "샤이니", "엑소", "엔시티", "엔믹스", "아일릿", "키스오브라이프", "스테이씨", "프로미스나인", "레드벨벳", "트와이스", "오마이걸", "마마무", "비비지", "잇지", "ITZY", "(여자)아이들", "여자아이들",
              "아이유", "임영웅", "성시경", "폴킴", "멜로망스", "헤이즈", "이무진", "경서", "김호중", "정승환", "정지훈", "로제", "다이나믹듀오", "에픽하이", "빈지노", "코드쿤스트", "페노메코", "호미들", "릴보이", "데이식스", "잔나비", "실리카겔", "검정치마", "새소년", "너드커넥션", "QWER", "카더가든", "선우정아", "영탁", "이찬원", "정동원", "장민호", "송가인", "박서진",
              "카리나", "윈터", "닝닝", "지젤", "장원영", "안유진", "우기", "제니", "해린", "혜인"],
    "테크": ["AI", "인공지능", "반도체", "플랫폼", "과학", "우주", "로봇", "데이터", "클라우드", "전기차", "배터리", "네이버", "카카오", "구글", "애플", "갤럭시", "아이폰"],
    "정치": ["대통령", "여당", "야당", "국회", "의원", "장관", "특검", "탄핵", "공천", "선거", "여론조사", "내각", "대선", "총선"],
    "사회": ["사건", "사고", "경찰", "검찰", "법원", "재판", "판결", "구속", "파업", "교육", "학교", "복지", "의료", "병원", "범죄", "화재", "시위", "노조", "수사", "고소", "갑질", "마약",
            "음주운전", "기소", "입건", "혐의", "체포", "송치", "압수수색", "구형", "사망", "성범죄", "폭행",
            "성착취", "아동학대", "디지털성범죄"],   # 범죄·사법 절차어 보강(운영자 260627·평의회5) + 중대범죄어(운영자 260628 — 헌재/대법원/합헌은 정치(탄핵)와 겹쳐 lexicon 제외·아래 JUDICIAL 하드가드[문화 한정]만)
}


# 하트(♥♡❤ 등) — 제목에 들어가면 연예인 열애/결혼·2세 = 100% 문화(운영자 260624). 사회 오분류·미분류 구제.
HEART_RE = re.compile("[♡♥❣❤\U0001F493-\U0001F49F\U0001F9E1\U0001FA77]")
# OSEN(오!쎈) — 조선일보 문화부 스포츠·연예 브랜드 → 100% 문화(운영자 260625). 제목 [오!쎈]/[Oh!쎈]/[OSEN=] 태그로 잡힘(영문 'Oh!쎈' 스펠링 보강·운영자 260628).
OSEN_RE = re.compile(r"오\s*!?\s*쎈|Oh\s*!?\s*쎈|OSEN", re.I)
# 스포츠·연예 전문 매체 — 매체명만으로 100% 문화(운영자 260625). 선수·팀명 아님(선수 사회면 논란 오분류 방지) + 연예도 문화라 마이데일리류 안전.
SPORTS_MEDIA_RE = re.compile(r"스포츠|스포탈|스포티비|SPOTV|OSEN|오\s*!?\s*쎈|마이데일리|엑스포츠|인터풋볼|풋볼리스트|베스트일레븐|점프볼|데일리스포츠", re.I)
# 정치 우선 마커 — 대통령·정부·정책 주체가 주어/화자면 주제(반도체 등 테크)보다 정치다(운영자 260627).
# "李대통령 '호남반도체 물부족' 비판에…" 식 정부발화·정책 기사가 반도체 키워드로 테크에 새던 것 봉합.
# ⚠️ 테크만 정치로 뒤집는다(경제·국제·문화·사회 등 다른 주제는 주제 유지 — 정부정책이 테크로 오분류되는 케이스만 좁게 교정).
POL_OVERRIDE_RE = re.compile(r"대통령|대통령실|청와대|국무총리|총리|장관|차관|내각|국무회의|국회|여당|야당|여야|정부|정책")
# 범죄·사법 절차어 하드가드 — 셀럽이라도 *실제 사건*(체포·기소·구속…)이면 문화 아닌 사회(운영자 260627·평의회5 "사회 하드가드 최우선").
# ⚠️ *절차어*만(영화 제목·플롯엔 안 나옴) — 마약·폭행·사기 등 콘텐츠어는 제외(영화 줄거리 오염 방지·구형[舊型]·소환[게임] 동음 제외).
CRIME_OVERRIDE_RE = re.compile(r"음주운전|뺑소니|구속|불구속|기소|입건|체포|송치|압수수색|집행유예|피의자|검거|구속영장|징역형")
# 사법·헌재 하드가드 — 헌재·대법원 판결·성착취물·아동학대 등 *사법 판단·중대범죄*면 만화·게임·영화 *소재*여도 사회(운영자 260628 · CRIME_OVERRIDE 자매 가드).
# 콘텐츠 위법성을 '판단·판결'한 기사는 소재가 만화여도 본질이 사법 = 사회('헌재 아동 성착취 만화 합헌'이 만화→문화로 새던 근본 봉합). 콘텐츠어 아닌 *기관·판단어*만 = 문화 플롯 오염 0.
JUDICIAL_OVERRIDE_RE = re.compile(r"헌재|헌법재판소|합헌|위헌|대법원|항소심|상고심|성착취|아동학대|디지털성범죄|불법촬영물")
# 모호 가수·그룹명(흔한 단어와 substring 충돌) — *단독이면 무시*, 음악 문맥 동반될 때만 문화 가점(운영자 260628).
# 지수=주가/물가지수·가을=가을총선·리즈=시리즈·레이=플레이·리사=변리사·슈화=이슈화 등은 단독 등재 불가 →
# 그룹명·소속사·앨범·타 가수명 등 음악 신호와 *함께* 나올 때만 문화(운영자 "지수+블핑/앨범/YG/제니… 붙어야 문화·가을·리즈도 동일").
AMBIG_ARTIST_RE = re.compile(r"지수|가을|리즈|레이|리사|슈화|청하|태연|선미|하니|미연|소연|민지|다니엘|이서|라이즈|케플러|빅뱅")
MUSIC_CTX_RE = re.compile(r"앨범|음악|신곡|컴백|데뷔|타이틀곡|뮤직비디오|뮤비|음원|콘서트|공연|팬미팅|월드투어|걸그룹|보이그룹|아이돌|완전체|솔로곡|소속사|엔터테인먼트|블랙핑크|블핑|에스파|아이브|뉴진스|르세라핌|세븐틴|방탄|BTS|트와이스|레드벨벳|여자아이들|YG|JYP|HYBE|제니|로제|카리나|윈터|장원영|안유진", re.I)


def cat_of(category, title, media=""):
    c = cat_ko(category)
    t = title or ""
    pol = bool(POL_OVERRIDE_RE.search(t))   # 정치 주체 마커 — 테크 오버라이드용
    if c and c != "사회":
        if c == "테크" and pol:   # 테크 피드라도 대통령·정부정책이면 정치(운영자 260627)
            return "정치"
        if c == "문화" and (CRIME_OVERRIDE_RE.search(t) or JUDICIAL_OVERRIDE_RE.search(t)):   # 문화 피드여도 사법·범죄 본질이면 사회(운영자 260628 — 만화 소재 사법 기사 구제)
            return "사회"
        return c
    if OSEN_RE.search(t) or SPORTS_MEDIA_RE.search(media or ""):   # OSEN 태그·스포츠 전문매체 = 100% 문화(사회·빈칸 위로)
        return "문화"
    if HEART_RE.search(t):   # 하트 = 100% 문화(사회·빈칸 위로)
        return "문화"
    if c:   # 사회(하트 없음)
        return c
    best, bn = "", 0
    music_combo = bool(AMBIG_ARTIST_RE.search(t) and MUSIC_CTX_RE.search(t))   # 모호 가수명 + 음악문맥 동반(운영자 260628)
    for k, ws in CAT_KW.items():
        n = sum(1 for w in ws if w in t)
        if k == "문화" and music_combo:   # 모호 가수명(지수·가을·리즈 등)은 단독이면 0가점, 음악문맥과 함께면 문화 강가점
            n += 2
        if n > bn or (n == bn and n > 0 and k == "사회"):   # 사회-우선 tie-break(운영자 260627·평의회5) — 셀럽 범죄("열애설 OOO 폭행 고소")는 문화·사회 동점이면 사회 보존
            bn, best = n, k
    if best == "문화" and (CRIME_OVERRIDE_RE.search(t) or JUDICIAL_OVERRIDE_RE.search(t)):   # 셀럽 범죄·사법(헌재·대법원·성착취 등)이면 문화어 다수여도 사회(운영자 260627·260628)
        return "사회"
    if best == "테크" and pol:   # 키워드 매칭서 테크 1등이어도 정부·대통령 마커 있으면 정치(반도체+대통령 동시 = 정치)
        return "정치"
    return best   # 0매칭이면 "" (빈칸 허용)


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
            "cat": cat_of(a.get("category"), bp.get("title") or a.get("title") or "", bp.get("media") or a.get("publisher") or ""),
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
