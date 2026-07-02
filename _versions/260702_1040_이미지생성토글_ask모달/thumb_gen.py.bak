#!/usr/bin/env python3
# thumb_gen.py — 픽한 기사(queue/*.md)별 썸네일 후보: 검색이미지(기사 og:image+유사) + AI 2화풍(Gemini).
#
# 기존 카드 이미지 경로(외부 Apps Script + Drive + Cloud Run compose)와 완전 분리된 레포 내 경로:
#   - GitHub Actions가 Gemini(gemini-3.1-flash-image-preview = Nanobanana 2 Pro·4:5)를 직접 호출
#   - 기사 타이틀(헤드라인) 문구는 이미지에 안 박음 = 글자 없는 장면만(현장 간판 등 자연 글자는 무관). 1K(토큰 절감).
#   - 산출 → Cloudflare R2 업로드(공개 URL) + gen.json([{sid,img,label}]) → build-viewer가 뷰어로 투영
#     (R2 미설정 시 git 폴백 = cards/<stem>/thumbs/gen-<style>.png 로컬 커밋·아무것도 안 깨짐)
#
# 안전: GEMINI_API_KEY 없으면 즉시 no-op(스캐폴드). 어떤 기사/화풍 실패도 fail-soft(파이프라인 안 깸).
# 비용: 픽한 기사당 이미지 2장(유료·2화풍). MAX_BATCH로 1런당 상한(최신 우선·이미 생성된 기사 skip).
#
# 정본 = 이 파일(썸네일 프롬프트 SSOT). 참조 = apps/news/03_자동화_레퍼런스.md §썸네일 후보.

import os, sys, re, json, base64, time, glob, subprocess, tempfile, ipaddress, socket, csv
import urllib.request, urllib.error, urllib.parse

MODEL = "gemini-3.1-flash-image-preview"   # 카드와 동일 모델(03 레퍼런스). 4:5 · 썸네일·카드 1K.
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(MODEL)

def _int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default

MAX_BATCH = _int_env("THUMB_MAX_BATCH", 3)   # 1런당 기사 수 상한(비용 바운드)
# 활성화 기준일(YYMMDD) — 파일명이 이 날짜 이후인 기사만 생성 = 신규 픽 한정(기존 큐 백로그 폭탄 차단).
# 빈값이면 전체(백로그 포함). 워크플로가 활성화 날짜를 박는다.
SINCE = os.environ.get("THUMB_SINCE", "").strip()
KEY = os.environ.get("GEMINI_API_KEY", "").strip()
# ⏸ AI 썸네일 생성 OFF 스위치(옵션) — THUMB_AI_OFF=1이면 Gemini 2화풍 생성만 건너뛰고
#    검색이미지(og:image·관련사진 fetch = 망만 필요·키 무관)는 그대로 채운다.
#    ✅ 260630 자동경로(news-analyze·news-ask) 재가동 = 미세팅(AI ON) · 260622 임시 OFF는 운영자 요청으로 해제.
#    수동 '다시 만들기'[thumb-redo.yml]는 항상 AI ON.
AI_OFF = os.environ.get("THUMB_AI_OFF", "").strip().lower() in ("1", "true", "yes", "on")
# ⚠️ 검색이미지는 더 이상 Google CSE JSON API를 안 씀(2025 신규고객 차단 死 → "this project does not have
#    access" 403 PERMISSION_DENIED). 대체 = 기사 본인 og:image 추출(fetch_article_images). CSE 시크릿 미사용.
# ── 저장소 = Cloudflare R2 (설정 시) → 공개 URL 직접 서빙(레포 비대 회피·egress 0). 미설정이면 git 폴백. ──
R2_ACCOUNT = os.environ.get("R2_ACCOUNT_ID", "").strip()
R2_BUCKET = os.environ.get("R2_BUCKET", "").strip()
R2_PUBLIC = os.environ.get("R2_PUBLIC_BASE", "").strip().rstrip("/")   # 예: https://pub-xxxx.r2.dev
R2_KEY = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
R2_ON = all([R2_ACCOUNT, R2_BUCKET, R2_PUBLIC, R2_KEY, R2_SECRET])

# ── 2화풍 (포토에디토리얼·극화 · label = 뷰어 캡션) ─────────────────────────────────────────────
# 구도/카메라 어휘 = apps/k 라이브러리(카메라·거리·앵글·조명) 증류 인라인(빌드주입 X = 재과금 폭탄 회피).
# 글자: NO_TITLE이 타이틀 오버레이 전면금지 + 현장 자연글자도 최소만(아래).
# ⚠️ sid 리네임 금지 = 기존 카드 재과금 0(process_one이 sid로 보존). 추가만 허용(웹툰/포토 sid 유지).
# ⚠️ cartoon(시사만평) 폐지(운영자 260630) = 포토에디토리얼+극화 2장만 생성(과금 1/3 절감).
#    기존에 cartoon이 든 gen.json은 보존(재과금 0) · 재생성('다시 만들기') 시 2화풍만 다시 그림.
STYLES = [
    ("photo", "포토 에디토리얼",
     "보도/르포르타주 사진 스타일. 자연광, 현장 다큐멘터리 사실감, 신문 1면 보도사진의 즉발성. "
     "연출된 스튜디오·잡지 화보·정적 인물 포트레이트가 아니라 실제 사건 현장을 포착한 듯한 보도사진. "
     "와이드 설정샷(롱샷)으로 현장 전체와 맥락을 넓게 담고, 깊은 심도로 배경까지 또렷, 아이레벨."),
    ("webtoon", "웹툰 극화",
     "한국 웹툰 극화체 일러스트레이션. 굵고 선명한 잉크 라인, 극적인 명암 대비, 강한 감정 표현. "
     "인물 상반신 중심의 타이트한 프레이밍, 살짝 로우앵글로 긴장감, 단일 하드 측광."),
]

# 지배 조건(맨 앞·최상위) — 화풍·구도보다 먼저 읽혀 "무엇을·어떻게"의 우선순위를 잡는다(프롬프트 위계 = 나열보다 준수율↑).
GOVERNING = (
    "이 기사의 핵심 사건을 한 장으로 대표하는 결정적 순간을 포착한다. "
    "독자가 스크롤을 멈추고 시선이 머물도록, 그 사건이라고 곧장 알아보는 구체적 장면이어야 한다 — "
    "막연한 분위기·일반 자료사진·스톡사진풍·카메라를 향해 포즈 취한 모델·미소 짓는 비즈니스 인물 등으로 도피하지 말 것."
)

# full-bleed 충전 + (구) '하단 자막 자리' 폐기(다운스트림에 썸네일 자막 미존재 = 무용·검정 띠만 유발 — 260621 분신술 실측).
# ⚠️ 암시룰(시신·유혈·고통 '직접묘사 말고 암시' 강제)은 260621 제거 — 충돌·분노 순화 방지(운영자 요청·일단은). 선정·미성년·실존인물 닮기 금지는 유지.
COMPOSITION = (
    "세로 4:5 비율의 한 장면. 장면이 프레임 네 가장자리 끝까지 가득 차게(full-bleed) 구성하고, "
    "좌우·상하 어디에도 빈 여백·흰 띠·검은 띠·단색 밴드·레터박스/필러박스·테두리를 두지 말 것 — 화면 전체를 사건 현장으로 채운다. "
    "핵심 피사체와 주요 요소(인물의 눈·눈빛·표정·손짓, 핵심 사물·증거 등 시선이 머무는 부분)는 화면 안에서 또렷한 단일 초점이 되게 배치하되, "
    "어느 영역도 의도적으로 비우거나 검게 죽이지 말고 배경·환경·전경으로 자연스럽게 채운다. 한 장면 = 하나의 명확한 주인공(과밀 금지). "
    "한국인·한국 배경을 기본값으로(국제 기사 등 명백히 외국이면 해당 지역). "
    "자극적·선정적 묘사 금지, 미성년자 안전, 특정 실존 개인을 식별 가능하게 닮게 그리지 말 것(역할·직군·상황으로). 워터마크·로고 없음."
)

# 글자 = 양방향 정의: 오버레이/타이틀 전면금지 + 현장 자연글자도 "최소·작게·흐릿"까지만(읽히게 그리지 말 것 = 한글 깨짐 방지).
NO_TITLE = (
    "이미지 속 글자는 최소화한다. 기사 제목·헤드라인·자막·설명 문장 등 오버레이/텍스트 밴드는 전면 금지. "
    "현장에 자연스러운 글자(간판·표지판·도로명 등)는 화면 구석에 작게 1~2개까지만 허용하고, 화면 중앙·다수·또렷한 글자판은 금지. "
    "글자를 읽을 수 있게 또렷이 렌더링하지 말 것(읽히는 한글은 깨질 위험이 크다)."
)

# ── 라이브러리(apps/k/library) 코드 → Gemini 키워드 조회 (P1·운영자 260621) ──
# analyze가 사건 보고 고른 thumb_dispatch 코드(AG 앵글·LGT 조명·SG 연출)를 *실제 라이브러리 TSV*에서 조회해
# 프롬프트에 삽입(인라인 복붙 아님 = SSOT 단일출처·기틀 OK). 미존재 코드·파일부재는 드롭·fail-soft(현 동작 유지).
_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apps", "k", "library")
_LIB_FILES = ["38_cardnews_distance_crop", "39_cardnews_angle_height", "40_cardnews_staging",
              "13_style_news_canon", "12_lighting_emotion",
              "01a_camera_lens_focal_length", "01b_camera_shot_size"]
_LIB = None
def _load_lib():
    """코드ID → Gemini 키워드 문자열 dict(1회 캐시). 헤더에 'Gemini' 들어간 칼럼을 키워드로 잡음(파일마다 위치 달라도)."""
    global _LIB
    if _LIB is not None:
        return _LIB
    _LIB = {}
    for name in _LIB_FILES:
        path = os.path.join(_LIB_DIR, name + ".tsv")
        try:
            with open(path, encoding="utf-8") as f:
                rows = list(csv.reader(f, delimiter="\t"))
        except Exception:
            continue
        if not rows:
            continue
        hdr = [h.lstrip("﻿").strip() for h in rows[0]]
        gi = next((i for i, h in enumerate(hdr) if "Gemini" in h), None)
        if gi is None:
            continue
        for r in rows[1:]:
            if len(r) <= gi:
                continue
            code = (r[0] or "").lstrip("﻿").strip()
            kw = (r[gi] or "").strip()
            if code and kw and code not in _LIB:
                _LIB[code] = kw
    return _LIB

def lib_lookup(dispatch):
    """thumb_dispatch 코드열 → 라이브러리 Gemini 키워드 콤마 합성. 미존재 코드 드롭(화이트리스트=실존 코드만)."""
    if not dispatch:
        return ""
    lib = _load_lib()
    out = []
    for code in dispatch.replace(",", " ").split():
        kw = lib.get(code.strip())
        if kw and kw not in out:
            out.append(kw)
    return ", ".join(out)

def build_prompt(art_dir, scene, dispatch=""):
    parts = [GOVERNING, art_dir]   # 지배조건 맨 앞 = 화풍/구도보다 우선(위계 선언)
    if scene:
        parts.append("장면: " + scene)
    cam = lib_lookup(dispatch)     # 사건별 앵글·조명·연출(라이브러리 DB 조회) — 화풍/장면과 구도 사이(앞 토큰 가중)
    if cam:
        parts.append("앵글·조명·연출(이 장면에 적용): " + cam)
    parts.append(COMPOSITION)
    parts.append(NO_TITLE)
    return " ".join(parts)

# ── queue md 파싱: frontmatter title + 본문 h1(에디토리얼 헤드라인) + 한줄요약 ──
def parse_md(path):
    raw = open(path, encoding="utf-8").read()
    fm = {}
    m = re.search(r"^---\s*$(.*?)^---\s*$", raw, re.M | re.S)
    body = raw
    if m:
        for line in m.group(1).splitlines():
            kv = re.match(r'\s*([a-zA-Z_]+)\s*:\s*"?(.*?)"?\s*$', line)
            if kv:
                fm[kv.group(1)] = kv.group(2)
        body = raw[m.end():]
    h1 = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    head = (h1.group(1) if h1 else fm.get("title", "")).strip()
    head = re.sub(r"^[\U0001F000-\U0001FAFF☀-➿️\s]+", "", head)  # 앞 이모지 제거
    lead = ""
    lm = re.search(r"한줄\s*요약\s*\n+(.+?)(?:\n\n|\n#|\Z)", body, re.S)
    if lm:
        lead = re.sub(r"\s+", " ", lm.group(1)).strip()
    # 상단 검색이미지용 키워드(요약이 뽑은 entity 중심) — 없거나 플레이스홀더면 빈 문자열(→ head 폴백).
    iq = fm.get("image_query", "").strip()
    if iq in ("삼성전자 반도체 평택공장",):   # 프롬프트 예시값을 모델이 그대로 베끼면 무시(→ head 폴백)
        iq = ""
    # AI 썸네일이 '무엇을 그릴지' = 분석(시사점까지)을 끝낸 시점에 정한 충돌/분노 장면(명사 아님·장면 묘사).
    # 검색용 image_query와 분리 — 있으면 thumb scene 1순위(없으면 iq→lead 폴백). 미기입 템플릿(<…>)이면 무시.
    ts = fm.get("thumb_scene", "").strip()
    # 미기입 템플릿(<…>) 또는 프롬프트 예시문을 그대로 베낀 것 무시 → iq/lead 폴백(image_query 예시 가드와 대칭).
    if ts.startswith("<") or ts == "화재로 그을린 건물 앞 가족 잃은 주민이 오열하는데 뒤편 관계자들은 서류만 들여다보는 순간":
        ts = ""
    return head, lead, iq, ts, fm.get("url", "").strip(), fm.get("alt_urls", "").split(), fm.get("image_sources", "").split(), fm.get("thumb_dispatch", "").strip()

def _md_url(path):
    """프런트매터 url만 가볍게 추출(main의 백필 판정용 · 파일 앞부분만 읽음)."""
    try:
        m = re.search(r'^\s*url\s*:\s*"?([^"\n]*)', open(path, encoding="utf-8").read(2000), re.M)
        return (m.group(1).strip() if m else "")
    except Exception:
        return ""

def _md_has_imgsrc(path):
    """프런트매터 image_sources(AI WebSearch 관련소스)가 비어있지 않은지 가볍게 판정(백필 게이트용).
    paste(전문 붙여넣기)는 url이 없어도 image_sources로 검색이미지를 채우므로 이 경로도 백필 대상에 포함해야 한다(앵글3·J ISSUE-1)."""
    try:
        m = re.search(r'^\s*image_sources\s*:\s*(.+)', open(path, encoding="utf-8").read(2000), re.M)
        return bool(m and m.group(1).strip())
    except Exception:
        return False

# ── 제미나이 토큰 사용량 기록 (운영자 260620) — 모든 Gemini 호출의 usageMetadata를 한곳에 누적.
# 기사별은 process_one이 슬라이스해 cards/<stem>/thumbs/usage.json + Actions 로그로 남긴다.
# (이미지 생성이 현재 유일한 Gemini 호출 · 카드 슛도 같은 gemini_image라 자동 포함.
#  비전훅 _vision_keep은 현재 OFF=호출 0 · 점화 시 그 Gemini 호출을 _rec_usage(tag="vision")로 기록하면 합산됨.)
_USAGE = []
def _rec_usage(um, tag):
    if not isinstance(um, dict):
        return
    _USAGE.append({"tag": tag, "prompt": int(um.get("promptTokenCount") or 0),
                   "output": int(um.get("candidatesTokenCount") or 0), "total": int(um.get("totalTokenCount") or 0)})
def _usage_total(calls):
    s = lambda k: sum(int(c.get(k) or 0) for c in calls)
    return {"calls": len(calls), "prompt_tokens": s("prompt"), "output_tokens": s("output"), "total_tokens": s("total")}

def gemini_image(prompt, image_size="1K", tag="img", aspect="4:5"):
    """Gemini 이미지 1장 생성 → PNG bytes(실패 시 None, fail-soft). usageMetadata는 _USAGE에 기록.

    image_size: "1K"(기본·gen_cards 재사용 시 유지)·"2K"·"4K"(대문자 K 필수). 썸네일·카드 모두 1K 호출(토큰 절감).
    aspect: 화면비("4:5" 기본=카드/썸네일 · "16:9"/"9:16"=영상 레퍼런스 등).
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"],
                             "imageConfig": {"aspectRatio": aspect, "imageSize": image_size}},
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API + "?key=" + KEY, data=data,
                                headers={"Content-Type": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.loads(r.read().decode())
            _rec_usage(j.get("usageMetadata") or {}, tag)   # 토큰 사용량 기록(이미지 파트 유무 무관 = 실제 호출 과금 반영)
            for cand in j.get("candidates", []):
                for p in cand.get("content", {}).get("parts", []):
                    inl = p.get("inlineData") or p.get("inline_data")
                    if inl and inl.get("data"):
                        return base64.b64decode(inl["data"])
            print("  ⚠️ 이미지 파트 없음(응답에 inlineData 부재)", flush=True)
            return None
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:300]
            print("  ⚠️ HTTP {} — {}".format(e.code, msg), flush=True)
            if e.code in (429, 500, 503) and attempt == 0:
                time.sleep(4); continue
            return None
        except Exception as e:
            print("  ⚠️ 호출 실패: {}".format(e), flush=True)
            if attempt == 0:
                time.sleep(4); continue
            return None
    return None

# ── 검색이미지 = 기사 본인 대표사진(og:image) + 관련기사 유사사진 추출 — Google CSE JSON API 대체(2025 신규차단 死) ──
# 구글 검색 대신 "원기사 URL의 og:image(대표) + 관련기사 og:image(유사·대표와 다른 사진)"를 끌어와 검색이미지 칸을 채운다.
# 대표=라벨'' / 유사=라벨'유사'. R2 설정 시 재호스팅(핫링크·리퍼러 차단 0)·미설정이면 외부 핫링크. 차단매체(403)·paste(url無)면 [].
# 🔑 신뢰원: og:image/twitter/JSON-LD = 발행사 선언만 사용(대표 보존·크기/크롭 면제). 본문 <img>는
#    '속보' 배너 등 그래픽 오염으로 폐지(260620) — body=True 분기·필터는 보존(미호출). 분신술 10인 감사 반영.
# 🔗 유사 보강(260620): 대표 1장 + 자리 남으면 '유사' 채움 — ① 클러스터 멤버(픽이 심은 같은 사건 타매체
#    url = frontmatter `alt_urls`, analyze.sh가 보존) og:image **우선**(신뢰·다른 앵글) ② 마커 매체(SBS oaid·
#    이투데이 trc=view_joinnews) 관련기사 og 폴백. 대표와 중복/소형/잡것 컷. 비전 게이트 OFF 훅(THUMB_VISION).
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
# 대표·본문 공통 컷 = 명백한 비콘텐츠(플레이스홀더·스페이서·파비콘)
_PLACEHOLDER = re.compile(r"(og[-_]?default|no[-_]?image|noimage|placeholder|blank|spacer|"
                          r"1x1|/pixel|favicon|sprite)", re.I)
# 본문 <img> 전용 잡것(로고·아이콘·광고·동영상썸네일) — 경계화로 본문단어(shareholder·iconic…) 오탐 방지
_BODY_SKIP = re.compile(
    r"((?:^|[/_.-])(?:logo|icons?|btn|button|banner|share|sharebtn|avatar|emoji|"
    r"thumb|sthumb|mini|small|resize|argon)(?:[/_.-]|$)|"
    r"[/_-]ads?(?=[/_.-])|adfit|doubleclick|googlesyndication|googleads|"          # 광고
    r"ytimg|youtube|youtu\.be|[mhs]qdefault|maxresdefault|/vi/)",                  # 동영상 썸네일
    re.I)
# 속보(breaking) 플래시 기사 = 대표사진 대신 '[속보]' 그래픽 배너를 og:image로 선언 → 유사로 쓰면 배너 오염.
# 기사 제목(og:title/twitter:title/<title>)에 속보 마커가 있으면 그 기사 og는 유사서 컷한다. 클러스터 멤버(신뢰경로)로
# 들어와도 배너면 차단 = 기사단위 일반화(특정 이미지 URL 차단은 다른 커버에 또 뚫림 — 운영자 260620 이투데이 속보 재유입).
_BREAKING_MARK = re.compile(r"[\[【(<]\s*속\s*보\s*[\]】)>]")   # [속보]·【속보】·(속보)·<속보> (양 괄호 필수 = 고정밀·오탐 최소)
def _is_breaking_article(html):
    """기사 HTML의 제목에 '[속보]' 류 마커가 있으면 True(=속보 플래시 → og는 배너일 위험, 유사서 컷)."""
    if not html:
        return False
    for tag in re.findall(r"<meta\b[^>]*>", html, re.I):
        if re.search(r'(?:property|name)\s*=\s*["\'](?:og:title|twitter:title)["\']', tag, re.I):
            cm = re.search(r'content\s*=\s*["\']([^"\']+)', tag, re.I)
            if cm and _BREAKING_MARK.search(cm.group(1)):
                return True
    tm = re.search(r"<title[^>]*>([^<]*)</title>", html, re.I)
    return bool(tm and _BREAKING_MARK.search(tm.group(1)))

def _dom_core(host):
    """호스트 → 핵심 도메인 라벨(img.etoday.co.kr·www.etoday.co.kr → 'etoday'). 같은 매체 판정용."""
    SUF = {"co", "com", "net", "org", "kr", "jp", "go", "or", "ne", "gov", "edu", "io"}  # 'news'=라벨 오붕괴 → 제외
    parts = [p for p in (host or "").lower().split(".") if p]
    while len(parts) > 1 and parts[-1] in SUF:
        parts.pop()
    return parts[-1] if parts else (host or "")

def _norm_key(u):
    """리사이즈 변형(같은 사진·다른 크기·다른 size디렉터리) 중복제거 키.

    뉴스 CDN 파일명은 날짜/시퀀스 고유ID(예: 20260419144431_2323414…) → 같은 파일명 = 같은 사진(다른 크기/디렉터리).
    파일명 기준 dedup하되, generic 파일명(photo01·image·1)은 오수집(서로 다른 사진 손실) 방지 위해 전체 URL로 폴백.
    """
    base = urllib.parse.urlparse(u).path.lower().rsplit("/", 1)[-1].split("?")[0]
    base = re.sub(r"[_-]\d{2,4}x\d{2,4}(?=\.)", "", base)    # _800x600 접미사
    base = re.sub(r"[_-](?:th|sm|lg|xl|s|m|l)(?=\.)", "", base)  # _th _s 접미사
    return base if sum(c.isdigit() for c in base) >= 7 else u   # 고유ID성 파일명만 basename dedup

def _small_dim(u):
    """URL에 박힌 치수가 작은 썸네일(둘 다 <400 or 쿼리 치수 max<400)인지 — 큰 값 있으면 통과(OG카드 1200×630 보존)."""
    nums = [int(x) for x in re.findall(r"[?&](?:w|width|h|height|size)=(\d{1,5})", u, re.I)]
    if nums and max(nums) < 400:
        return True
    m = re.search(r"[_/-](\d{2,4})x(\d{2,4})(?=[._/]|$)", u)
    if m and int(m.group(1)) < 400 and int(m.group(2)) < 400:
        return True
    mh = re.search(r"[_-](\d{2,4})[_-](\d{2,4})\.(?:jpe?g|png|webp|gif)(?:[?#]|$)", u, re.I)   # etoday류 _W_H.jpg 트레일링 치수
    if mh and int(mh.group(1)) < 400 and int(mh.group(2)) < 400:
        return True
    m2 = re.search(r"[?&]type=w(\d{1,4})", u, re.I)          # 네이버 mblogthumb type=w80
    return bool(m2 and int(m2.group(1)) < 400)

def _img_candidates(html, base):
    """기사 HTML → 이미지 후보(대표 먼저·중복제거). 대표(og/twitter/JSON-LD)=신뢰·최소필터 / 본문 img=엄격필터."""
    import html as _html
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)      # 주석 제거(주석 og 오대표·주석 img 차단)
    out, seen, seen_key = [], set(), set()
    def core_of(u):
        return _dom_core(urllib.parse.urlparse(u).hostname or "")
    def seg0(u):
        return ([s for s in urllib.parse.urlparse(u).path.split("/") if s] or [""])[0].lower()
    def add(u, body=False, junk=False):
        if not u:
            return
        u = _html.unescape(u.strip())
        if u.startswith("//"):
            u = "https:" + u
        u = urllib.parse.urljoin(base, u)
        if not re.match(r"https?://", u, re.I):
            return
        if not re.search(r"\.(jpe?g|png|webp|gif)(?:[/?#]|$)", u, re.I):
            return
        if _PLACEHOLDER.search(u):
            return
        if (body or junk) and _BODY_SKIP.search(u):         # 본문·JSON-LD = 로고/아바타/광고/동영상 컷
            return
        if body:   # 본문 <img> = 비신뢰 → 추가 엄격: 같은매체(대표 호스트)·같은 디렉터리·작은썸네일 컷
            ref = out[0] if out else base                   # 대표(og) 호스트 기준 = 네이버/다음(기사≠CDN) 구제
            if core_of(u) != core_of(ref):
                return
            # 같은 사진 디렉터리 컷(프로모·배너) — 대표와 정확히 같은 호스트일 때만(리사이저=다른 host면 면제: nate·daum)
            if (out and urllib.parse.urlparse(u).hostname == urllib.parse.urlparse(out[0]).hostname
                    and seg0(u) != seg0(out[0])):
                return
            if _small_dim(u):
                return
        k = _norm_key(u)                                    # 리사이즈 변형 중복 제거(정규화 키)
        if u in seen or k in seen_key:
            return
        seen.add(u); seen_key.add(k); out.append(u)
    # 1) 대표 = og:image / twitter:image (속성 순서 무관 · 발행사 선언=신뢰, 호스트·크기 무관 허용)
    for tag in re.findall(r"<meta\b[^>]*>", html, re.I):
        if re.search(r'(?:property|name)\s*=\s*["\'](?:og:image(?::url)?|twitter:image(?::src)?)["\']', tag, re.I):
            cm = re.search(r'content\s*=\s*["\']([^"\']+)', tag, re.I)
            if cm:
                add(cm.group(1))
    # 2) JSON-LD "image" — og/twitter 못 찾았을 때만(fallback) · 윈도 400자·앞 2개·로고/아바타/동영상 컷(bleed 방지)
    if not out:
        for m in re.finditer(r'"image"\s*:', html):
            for u in re.findall(r'"(https?:[^"]+?\.(?:jpe?g|png|webp|gif)[^"#?]*)', html[m.end():m.end() + 400])[:2]:
                add(u, junk=True)
    # 3) 본문 <img> 긁기 = 비활성(운영자 260622 재폐지). 같은-호스트라도 사이드바·'많이 본 뉴스'·추천기사
    #    썸네일(골프·축구 등 무관)이 '유사'로 새는 문제(부산 교통사고 기사에 스포츠 사진 실측). 본문 사진과
    #    사이드바 썸네일은 HTML상 구별이 안 됨 → 한 기사당 og/twitter/JSON-LD(발행사 선언) 1장만 = 대표.
    #    다장 '유사'는 관련기사(image_sources = 분석단계 AI가 *이 사건* 키워드로 찾은 소스 · alt_urls)의 og 로
    #    채운다(fetch_article_images 2단계) = 우측 검색버튼(AI 키워드) 로직과 정합 = 관련성 보장.
    return out

def _url_ok(u):
    """fetch 허용 = http(s) + 호스트가 (DNS resolve 후) 전역 공인 IP만. SSRF 게이트.

    ⚠️ 문자열만 보면 8진수/정수(2130706433)/16진수/단축(127.1)/nip.io 난독화에 우회됨
    (ipaddress는 거부하지만 OS 리졸버는 사설로 풂) → 실제 resolve해 모든 A/AAAA가 is_global인지 검사
    (사설·루프백·링크로컬169.254·CGNAT100.64·예약·멀티캐스트 전부 차단). 동적 리바인딩은 잔여(수용).
    """
    try:
        p = urllib.parse.urlparse(u)
    except Exception:
        return False
    if p.scheme.lower() not in ("http", "https"):
        return False                                        # file://·ftp://·data:· gopher:// 차단
    host = (p.hostname or "").lower()
    if not host or host == "localhost" or host.endswith(".localhost"):
        return False
    ips = set()
    try:
        ips.add(str(ipaddress.ip_address(host)))            # 정규형 IP literal
    except ValueError:
        pass
    try:                                                    # 도메인·난독화 literal을 OS 리졸버로 실제 해석
        ips |= {ai[4][0] for ai in socket.getaddrinfo(host, None)}
    except Exception:
        pass
    if not ips:
        return False                                        # resolve 실패 = fail-closed
    for s in ips:
        try:
            ip = ipaddress.ip_address(s.split("%")[0])      # IPv6 zone id 제거
        except ValueError:
            return False
        if not ip.is_global or ip.is_reserved:              # 비전역(사설/루프백/링크로컬/CGNAT)·예약 = 거부
            return False
    return True

class _NoPrivateRedirect(urllib.request.HTTPRedirectHandler):
    """리다이렉트 매 hop 재검증 — 공개 URL → 302 내부IP/file 우회(SSRF) 차단."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _url_ok(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)

_OPENER = urllib.request.build_opener(_NoPrivateRedirect)   # urlopen 대신 사용(리다이렉트 게이트 적용)

_MAGIC = ((b"\xff\xd8\xff", "image/jpeg", "jpg"), (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
          (b"GIF87a", "image/gif", "gif"), (b"GIF89a", "image/gif", "gif"))
def _img_type(b):
    """매직바이트 → (안전 content-type, ext) 또는 (None, None). SVG·HTML·스크립트 등 비이미지 차단(R2 저장형 XSS 방지)."""
    if len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp", "webp"
    for sig, ct, ext in _MAGIC:
        if b.startswith(sig):
            return ct, ext
    return None, None

def _fetch_html(u):
    """기사 URL → 디코드 HTML 또는 None(실패·비허용 url). 대표·관련기사 fetch 공용(SSRF·리다이렉트 게이트)."""
    if not (u and _url_ok(u)):
        return None
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        with _OPENER.open(req, timeout=20) as r:
            raw = r.read(1500000)
            charset = r.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, "replace")
        except LookupError:                                 # 알 수 없는 charset 라벨 → utf-8 폴백(fail-soft)
            return raw.decode("utf-8", "replace")
    except Exception as e:
        print("  ⚠️ fetch 실패({}…): {}".format(u[:45], e), flush=True)
        return None

# phase2 = 관련기사 og:image를 '유사'로(대표와 다른 사진). '이 기사의 관련'임을 보증하는 마커 있는 매체만
# (오염·무관 차단 — 운영자 "무관 금지" 우선). 도메인코어 → 관련링크 정규식. 마커 없는 매체·차단매체·paste면 [].
_RELATED_RULES = {
    "sbs":    re.compile(r'href\s*=\s*["\']([^"\']*?endPage\.do\?[^"\']*?oaid=[^"\']+)', re.I),                 # oaid=원기사id 백레프
    "etoday": re.compile(r'href\s*=\s*["\']([^"\']*?/news/view/\d{5,}[^"\']*?trc=view_joinnews[^"\']*)', re.I),  # trc=조인뉴스(관련)
}
def _related_urls(html, base):
    """기사 HTML → 관련기사 URL(마커 신뢰 매체만·중복제거·최대 6). 화이트리스트 규칙만(범용 추출=오염 위험이라 금지)."""
    import html as _h
    pat = _RELATED_RULES.get(_dom_core(urllib.parse.urlparse(base).hostname or ""))
    if not pat:
        return []
    out, seen = [], set()
    for m in pat.findall(html):
        u = urllib.parse.urljoin(base, _h.unescape(m).replace("&amp;", "&"))
        if u != base and u not in seen and _url_ok(u):
            seen.add(u); out.append(u)
    return out[:6]

def _vision_keep(rep_src, cand_src):
    """비전 훅(기본 OFF=pass-through). THUMB_VISION=1일 때만 Gemini로 '대표와 같은 인물/장면이면 컷' 판정.
    기본(미설정)은 cand 그대로 반환 = 과금 0. 점화는 후속(운영자 승인 시 여기에 Gemini 1콜 배선)."""
    if os.environ.get("THUMB_VISION", "") != "1":
        return cand_src
    return cand_src   # (점화 시: 대표와 동일 인물/장면이면 None 반환해 컷)


def _is_logo_card(img_bytes):
    """솔리드 배경 + 텍스트 = 매체 로고/브랜딩 카드(예: '아시아경제' 빨강 og:image) 추정 → True(컷).
    이미지를 픽셀로 *직접 본다*(운영자 '일일이 안 봤다' 지적). PIL 없거나 판독 실패면 False(통과=무회귀).
    보수적 임계(실사진 오컷 최소): 지배색 70%↑ AND 색 단순(≤80 양자화색) — 실사진은 노이즈/그라데로 dom<0.7·색多."""
    try:
        import io
        from PIL import Image
        from collections import Counter
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        im.thumbnail((48, 48))
        px = [(r >> 5, g >> 5, b >> 5) for (r, g, b) in im.getdata()]   # 3비트/채널 양자화(512색)
    except Exception:
        return False
    n = len(px)
    if n < 64:
        return False
    c = Counter(px)
    dom = c.most_common(1)[0][1] / n   # 지배색 픽셀 비율
    return dom >= 0.70 and len(c) <= 80

def fetch_article_images(art_url, alt_urls=None, image_sources=None, want=7):
    """기사 관련 대표·유사 이미지 [{src,link,label}] 최대 want장.
    소스 우선순위: 원기사 og(대표) → AI 관련소스(image_sources, 분석단계 WebSearch 유추) → 클러스터(alt_urls) → 마커매체 관련.
    ⚠️ 원기사 URL이 없거나(전문 붙여넣기) 막혀도(403) image_sources로 채운다 = 소스 무관(운영자 260620).
    품질 필터: 속보 배너(_is_breaking_article)·로고/광고/동영상(_BODY_SKIP)·소형(_small_dim)·플레이스홀더(_PLACEHOLDER) + 호출부 매직바이트."""
    out, seen = [], set()
    have_art = bool(art_url and _url_ok(art_url))
    text = _fetch_html(art_url) if have_art else None
    # 1) 원기사 자체 대표(속보 배너면 컷) — URL 있고 fetch 되면(기존 동작 보존: og 대표 + 본문유사).
    if text is not None and not _is_breaking_article(text):
        for u in _img_candidates(text, art_url)[:want]:
            k = _norm_key(u)
            if k in seen:
                continue
            seen.add(k)
            out.append({"src": u, "link": art_url, "label": "" if not out else "유사"})
    # 2) 관련 소스 보강(자리 남으면): AI image_sources 우선 → 클러스터 alt_urls → 마커매체 관련.
    #    paste·차단매체(art_url 無/막힘)는 여기서 대표부터 채운다(label = 첫 장 ''=대표 / 이후 '유사').
    if len(out) < want:
        rep = out[0]["src"] if out else ""
        related, seen_u = [], set()
        for u in (list(image_sources or []) + list(alt_urls or []) + (_related_urls(text, art_url) if text is not None else [])):
            if u and _url_ok(u) and u != art_url and u not in seen_u:
                seen_u.add(u); related.append(u)
        for ru in related[:15]:                             # 관련소스 상한 10→15(운영자 260622 — 더 많이)
            if len(out) >= want:
                break
            rhtml = _fetch_html(ru) or ""
            if _is_breaking_article(rhtml):                 # 속보 플래시 og = '[속보]' 배너 위험 → 컷(기사단위 일반화)
                print("  ⏭ 관련 컷: 속보기사 og=배너 위험 ({}…)".format(ru[:42]))
                continue
            for rog in _img_candidates(rhtml, ru):          # 페이지당 og 1장 → og+본문 다장 채움(운영자 260622)
                if len(out) >= want:
                    break
                if not rog or _norm_key(rog) in seen or _small_dim(rog) or _BODY_SKIP.search(rog):
                    continue
                if rep and not _vision_keep(rep, rog):
                    continue
                seen.add(_norm_key(rog))
                out.append({"src": rog, "link": ru, "label": "" if not out else "유사"})
                print("  🔗 관련이미지 +1 ({}…)".format(ru[:42]))
    return out

def http_image(url):
    """이미지 URL → (bytes, 안전 content-type, ext) 또는 (None,None,None). 매직바이트로 실제 이미지만 통과."""
    if not _url_ok(url):
        return None, None, None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with _OPENER.open(req, timeout=20) as r:
            b = r.read(8000000)
    except Exception as e:
        print("  ⚠️ 이미지 다운로드 실패({}…): {}".format(url[:45], e), flush=True)
        return None, None, None
    ct, ext = _img_type(b or b"")
    if not ct:                                              # SVG/HTML/비이미지 → 거부(R2 오염·저장형 XSS 차단)
        print("  ⚠️ 비이미지 응답 거부({}…)".format(url[:45]), flush=True)
        return None, None, None
    return b, ct, ext

def r2_upload(png_bytes, key, content_type="image/png"):
    """바이트 → R2 업로드(aws cli S3호환·러너 기본설치) → 공개 URL. 실패 시 None(fail-soft → 로컬 폴백)."""
    endpoint = "https://{}.r2.cloudflarestorage.com".format(R2_ACCOUNT)
    env = dict(os.environ, AWS_ACCESS_KEY_ID=R2_KEY, AWS_SECRET_ACCESS_KEY=R2_SECRET,
               AWS_DEFAULT_REGION="auto")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(png_bytes); tmp = f.name
        subprocess.run(["aws", "s3", "cp", tmp, "s3://{}/{}".format(R2_BUCKET, key),
                        "--endpoint-url", endpoint, "--content-type", content_type,
                        "--only-show-errors"], check=True, env=env, timeout=90)
        return "{}/{}".format(R2_PUBLIC, key)
    except Exception as e:
        print("  ⚠️ R2 업로드 실패: {}".format(e), flush=True)
        return None
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)

def _load_gen(tdir):
    try:
        g = json.load(open(os.path.join(tdir, "gen.json"), encoding="utf-8"))
        return g if isinstance(g, list) else []
    except Exception:
        return []

def process_one(md, stem):
    """기사 1건 = 검색이미지(기사 og:image + 유사) + AI 2화풍. 저장 = R2(공개 URL) 또는 git 폴백."""
    head, lead, iq, thumb_scene, art_url, alt_urls, image_sources, dispatch = parse_md(md)
    if not head:
        print("· {} — 헤드라인 파싱 실패, skip".format(stem)); return False
    print("· {} — “{}”".format(stem, head[:40]), flush=True)
    tdir = os.path.join("cards", stem, "thumbs")
    os.makedirs(tdir, exist_ok=True)
    search_written = False
    # 검색(관련)이미지 = 원기사 og:image + AI 관련소스(image_sources, 분석단계 WebSearch 유추) + 클러스터 — Google CSE 死 대체.
    # ⚠️ 소스 무관(운영자 260620): art_url 또는 image_sources 있고 아직 없을 때 채움 → paste·차단매체도 관련이미지 확보.
    # 대표=라벨'' / 유사='유사'. R2 재호스팅(핫링크 0)·매직바이트 검증, 실패 시 외부 핫링크 폴백.
    if (art_url or image_sources) and not os.path.exists(os.path.join(tdir, "search.json")):
        cand = fetch_article_images(art_url, alt_urls=alt_urls, image_sources=image_sources, want=7)   # 3→7장(og:image fetch는 과금0 · dedup·필터 그대로 = 유사 컷 동일 · 한·외신 공통 · 운영자 260622)
        items = []
        for i, c in enumerate(cand):
            final = None
            if R2_ON:
                b, ctype, ext = http_image(c["src"])        # 매직바이트 검증된 안전 ctype·ext
                if b and _is_logo_card(b):                  # 매체 로고/브랜딩 카드(솔리드+텍스트) = 픽셀 직접 검사 컷(운영자 260622)
                    print("  ⏭ 매체 로고/브랜딩 컷 ({}…)".format((c.get("link") or c["src"])[:42])); continue
                if b:
                    final = r2_upload(b, "thumbs/{}/search-{}.{}".format(stem, i, ext), ctype)
            items.append({"url": final or c["src"], "link": c["link"], "label": c["label"]})
        # 빈 결과(차단매체·사진無)도 search.json=[] 1회 기록 → 매 런 재fetch(좀비 슬롯잠식) 차단(앵글7·10)
        json.dump(items, open(os.path.join(tdir, "search.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        search_written = True
        if items:
            print("  🖼 검색이미지 {}장 (대표 1 + 유사 {})".format(len(items), len(items) - 1))
        else:
            print("  · 검색이미지 0장 기록(차단·사진無 → AI썸네일 커버·재fetch 차단)")
    # AI 생성 2화풍 — THUMB_AI_OFF면 통째 생략(검색이미지만 채움 · 임시 비용차단 260622).
    # 평소엔 기존 gen.json의 완료 화풍(sid)은 보존·재호출(재과금) 안 함 = 부분성공 자동 보완(폐지된 watercolor·photo_close sid는 STYLES에 없어 자동 드롭).
    changed = False
    if AI_OFF:
        print("  ⏸ AI 썸네일 생성 OFF(THUMB_AI_OFF) — 검색이미지만 처리(기존 썸네일·gen.json·토큰 영향 0)")
    else:
        _u0 = len(_USAGE)                         # 이 기사 제미나이 호출 사용량 슬라이스 시작점
        existing = {g.get("sid"): g for g in _load_gen(tdir) if g.get("sid")}
        gen = []
        for sid, label, art_dir in STYLES:
            if sid in existing:                      # 이미 완료(R2 URL or 로컬) → 보존
                gen.append(existing[sid]); continue
            png = gemini_image(build_prompt(art_dir, thumb_scene or iq or lead, dispatch), "1K")   # 1K(토큰 절감 · 운영자 260621 · 폰 피드용 충분). 장면(WHAT)=충돌장면(thumb_scene) 1순위→entity(iq)→한줄요약 + 연출(HOW)=라이브러리 앵글/조명/연출(dispatch). '밥 먹는 그림'화 방지=충돌순간을 라이브러리 연출로 촬영.
            if not png:
                print("  ✗ {} 실패".format(label)); continue
            if R2_ON:                                # R2 = 공개 URL(레포 미저장)
                url = r2_upload(png, "thumbs/{}/gen-{}.png".format(stem, sid))
                if url:
                    gen.append({"sid": sid, "img": url + "?v=" + str(int(time.time())), "label": label}); changed = True   # ?v=캐시버스트(재생성 시 같은 R2 키 덮어써도 새 이미지 반영)
                    print("  ✓ {} → R2".format(label)); continue
                # R2 업로드 실패 → 로컬 폴백(아래로 떨어짐)
            fp = os.path.join(tdir, "gen-{}.png".format(sid))   # git 폴백 = 로컬 PNG
            open(fp, "wb").write(png)
            gen.append({"sid": sid, "file": "gen-{}.png".format(sid), "label": label}); changed = True
            print("  ✓ {} ({:.0f}KB, 로컬)".format(label, len(png) / 1024))
        if changed:
            json.dump(gen, open(os.path.join(tdir, "gen.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        # 제미나이 토큰 사용량 — 이 기사 호출분을 usage.json에 기록 + 로그(누적 합산 포함).
        # 태그별 분리: gen=이미지 생성(tag"img") / search=검색·비전(tag"vision") — 뷰어가 각 라벨(🍌 AI 생성·🔎 검색) 옆에 따로 표기.
        # (현재 검색=og:image 스크래핑이라 vision 호출 0 → search 버킷 0; THUMB_VISION 점화 시 _rec_usage(tag="vision")로 자동 채워짐.)
        calls = _USAGE[_u0:]
        if calls:
            up = os.path.join(tdir, "usage.json")
            try:
                prevj = json.load(open(up, encoding="utf-8"))
            except Exception:
                prevj = {}
            def _prev_cum(bucket):
                try: return int((prevj.get(bucket) or {}).get("cumulative") or 0)
                except Exception: return 0
            tot = _usage_total(calls)
            tot["cumulative_total_tokens"] = int((prevj or {}).get("cumulative_total_tokens") or 0) + tot["total_tokens"]
            # 버킷별(누적 포함) — 미래 비전 점화 대비 분리 집계
            gen_calls    = [c for c in calls if c.get("tag") == "img"]
            search_calls = [c for c in calls if c.get("tag") in ("vision", "search")]
            gt, st = _usage_total(gen_calls), _usage_total(search_calls)
            tot["gen"]    = {"calls": gt["calls"], "total": gt["total_tokens"], "cumulative": _prev_cum("gen")    + gt["total_tokens"]}
            tot["search"] = {"calls": st["calls"], "total": st["total_tokens"], "cumulative": _prev_cum("search") + st["total_tokens"]}
            json.dump(tot, open(up, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print("  📊 제미나이 토큰: {}콜·합계 {:,} (생성 {:,}·검색 {:,})·누적 {:,}".format(
                tot["calls"], tot["total_tokens"], tot["gen"]["total"], tot["search"]["total"], tot["cumulative_total_tokens"]), flush=True)
    return changed or search_written

def main():
    if not KEY and not AI_OFF:                # AI_OFF면 키 없어도 검색이미지는 채운다(검색=망 fetch·키 무관)
        print("GEMINI_API_KEY 없음 — 썸네일 생성 생략(스캐폴드 no-op)")
        return 0
    if AI_OFF:
        print("⏸ THUMB_AI_OFF — AI 썸네일 생성 OFF(검색이미지만 처리 · 임시 · 복구=env 제거)")
    print("저장소: {}".format("Cloudflare R2" if R2_ON else "git 폴백(R2 미설정)"))
    # ── 단일 기사 강제 재생성 (뷰어 '다시 만들기' → thumb-redo.yml · THUMB_ONLY=stem) ──
    # gen.json(2화풍) + search.json(검색이미지) 둘 다 비워 전부 재생성 = '다시 만들기' = 전체 새로고침.
    # (검색은 md frontmatter alt_urls 있으면 유사까지 채움·없으면 대표 og 재fetch). SINCE/MAX_BATCH 무관.
    only = os.environ.get("THUMB_ONLY", "").strip()
    redo_sid = os.environ.get("THUMB_REDO_SID", "").strip()   # 지정 시 = 그 화풍 1개만 재생성(per-image · 검색·타화풍 보존)
    if only:
        md = os.path.join("queue", only + ".md")
        if not os.path.exists(md):
            print("THUMB_ONLY 대상 없음:", md); return 0
        tdir = os.path.join("cards", only, "thumbs")
        if redo_sid:
            # 단일 화풍만 — gen.json에서 그 sid만 제거(나머지·search 보존) → process_one이 그 sid만 재생성
            gp = os.path.join(tdir, "gen.json")
            try:
                g = json.load(open(gp, encoding="utf-8"))
                g2 = [x for x in g if x.get("sid") != redo_sid]
                if len(g2) != len(g):
                    json.dump(g2, open(gp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                    print("  ↻ gen.json '{}' 화풍만 제거 → 재생성: {}".format(redo_sid, only))
                else:
                    print("  ℹ️ '{}' 화풍이 gen.json에 없음 — 미존재분 보완으로 진행".format(redo_sid))
                fp = os.path.join(tdir, "gen-{}.png".format(redo_sid))   # 로컬 폴백 PNG도 제거(있으면)
                if os.path.exists(fp):
                    os.remove(fp)
            except Exception as e:
                print("  ⚠️ 단일 화풍 제거 실패: {}".format(e))
        else:
            for jf, lbl in (("gen.json", "2화풍"), ("search.json", "검색이미지")):
                p = os.path.join(tdir, jf)
                try:
                    if os.path.exists(p):
                        os.remove(p); print("  ↻ {} 비움 → {} 재생성: {}".format(jf, lbl, only))
                except Exception as e:
                    print("  ⚠️ {} 제거 실패: {}".format(jf, e))
        process_one(md, only)
        print("THUMB_ONLY 재생성 완료:", only, ("(화풍 " + redo_sid + ")") if redo_sid else "")
        return 0
    # 미완성 기사만(최신 우선) = gen.json에 2화풍(sid) 다 있으면 완성으로 보고 skip(부분이면 보완).
    target_sids = {s[0] for s in STYLES}
    todo = []
    for md in sorted(glob.glob("queue/*.md"), reverse=True):
        stem = os.path.basename(md)[:-3]
        if SINCE and stem[:6] < SINCE:
            continue   # 활성화 기준일 이전(백로그) 제외 = 신규 픽 한정
        tdir = os.path.join("cards", stem, "thumbs")
        # AI_OFF면 AI는 '완료'로 간주(생성 안 함) → 검색만 끝나면 skip(매 런 불필요 재순회·신규픽 슬롯잠식 방지).
        ai_done = AI_OFF or ({g.get("sid") for g in _load_gen(tdir)} >= target_sids)
        # url 또는 image_sources(AI 관련소스) 있는데 search.json 없으면 검색이미지 백필 대상에 포함.
        # ⚠️ process_one 게이트가 `(art_url or image_sources)`이므로 여기 백필 판정도 동일해야 paste 기사(url無·image_sources有)가 누락 안 됨(앵글3·J ISSUE-1).
        # AI 완료분은 process_one이 기존 sid 보존 → Gemini 0회, 검색이미지만 채움(추가 과금 없음).
        search_pending = (bool(_md_url(md)) or _md_has_imgsrc(md)) and not os.path.exists(os.path.join(tdir, "search.json"))
        if ai_done and not search_pending:
            continue
        todo.append((md, stem))
    if not todo:
        print("새 썸네일 대상 없음")
        return 0
    print("썸네일 대상 {}건 중 {}건 처리(SINCE={})".format(len(todo), min(len(todo), MAX_BATCH), SINCE or "전체"))
    made = 0
    for md, stem in todo[:MAX_BATCH]:
        try:
            if process_one(md, stem):
                made += 1
        except Exception as e:   # 기사 1건 실패가 배치 전체를 안 끊게(기사 단위 fail-soft)
            print("  ⚠️ {} 처리 실패(건너뜀): {}".format(stem, e), flush=True)
            continue
    print("완료 — {}건 처리".format(made))
    return 0

if __name__ == "__main__":
    sys.exit(main())
