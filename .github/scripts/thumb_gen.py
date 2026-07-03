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
# 비용: 픽한 기사당 이미지 4장(유료·4화풍 — 운영자 260703). MAX_BATCH로 1런당 상한(최신 우선·이미 생성된 기사 skip).
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
# 🔍 품질 게이트(TH-06 · 분신술⑧ 260703) — 기본 OFF. THUMB_GATE=1이면 생성 직후 단색 밴드(PIL) 판독→미달 시 1회 재생성.
#    §📰 카나리아 절차 준수: 기본 OFF로 머지(라이브 무영향) → workflow_dispatch 단건 실측 → 승격.
#    ⚠️ 승격 시 배선 필수(검증4): Pillow 설치는 news-analyze.yml·moreimg.yml 두 곳뿐 — news-ask.yml thumb_gen 잡·
#    thumb-redo.yml에 pip install Pillow + THUMB_GATE env를 같이 넣어야 함(없으면 _band_fail이 조용히 no-op = 헛 카나리아).
GATE = os.environ.get("THUMB_GATE", "").strip() == "1"
# 🖼 참조 체이닝(운영자 260703 "그 사람 그대로") — 기본 OFF. THUMB_REF=1이면 극화·수채화 생성 시 그 기사 대표
#    실사진(search.json 대표 og:image)을 Gemini 입력으로 첨부해 실제 얼굴 재현(텍스트 이름만으론 모델이 얼굴 모름).
#    §📰 카나리아 절차: OFF 머지→thumb-redo 단건 실측→승격. photo(실사)는 제외(딥페이크 인접). 사인·피해자·미성년은 프롬프트가 익명 유지.
REF_ON = os.environ.get("THUMB_REF", "").strip() == "1"
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
# v2(260703 분신술 10인): look(질감)과 기본 카메라(구도 폴백)를 분리 — 카메라는 dispatch(AG/DF)가 있으면 그쪽이 정본,
#   없을 때만 4번째 필드(폴백). 옛 photo "와이드 롱샷·아이레벨" 하드코딩은 dispatch와 6/6본 모순(아이레벨+top-down 동시 지시)
#   + 세로 4:5 피드 저후킹(46 CTS-08 "타이트가 이긴다")이라 폐지 → 감정 코어 타이트 기본.
# 고정문 = 영어(카드 cards.md 문법과 통일 — 같은 Gemini 모델서 운영 검증) · SCENE(장면)만 한국어 유지(상류 무변경).
# ⚠️ sid 리네임 금지 = 기존 카드 재과금 0(process_one이 sid로 보존). 추가만 허용(웹툰/포토 sid 유지).
# ✅ 4화풍 재편(운영자 260703 — "에디토리얼1·극화1·수채화1·풍자(시사만평)1"): v2 개선 위에 수채화(260621 폐지)·
#    시사만평(260630 폐지)을 **옛 sid 그대로(watercolor·cartoon)** 재추가 = 옛 gen.json 보존분 재과금 0.
#    픽당 2장→4장 = 과금 2배(운영자 승인) · 소급은 THUMB_SINCE(워크플로)가 260703으로 캡(261619~ 백로그 폭탄 차단).
#    photo_close(포토클로즈업)만 폐지 유지. 정의는 옛 한국어 원문(백업 _versions)을 v2 영어 look으로 등가 이식.
STYLES = [
    ("photo", "포토 에디토리얼",
     "reportage press photograph, natural available light, documentary realism, "
     "front-page news immediacy, unposed subjects caught mid-action — not a staged studio portrait or magazine editorial",
     "tight medium shot on the emotional core of the scene, shallow depth of field separating the subject from the background, eye-level"),
    ("webtoon", "웹툰 극화",
     "korean webtoon serious drama illustration, bold clean ink lines, dramatic high-contrast shading, "
     "intense emotional expression",
     "tight upper-body framing, medium close-up, slight low angle for tension, single hard side light"),
    ("watercolor", "수채화",
     # 인물 표정·동작 위주(운영자 260703): 극화는 표정 강조 시 과강렬 ↔ 수채화는 매체가 순화해줘서 표정·동작
     # 정면 승부가 오히려 적정 타격. + 근접 강화(운영자 2차: "표정·핵심 사물 더 크게·카메라 더 근접") =
     # 수채화는 카메라를 dispatch와 무관하게 잠근다(process_one이 cam_lock 전달 · 항상 초근접).
     # 260703 운영자 확정 판("거의 온듯 — 이 느낌 살려서 반영") = 벤치마크 v4 실물의 문법을 굳힘:
     # 측면/3/4 프로필·얼굴의 결(주름·세월)을 다정하게·안료 번짐 입자·손과 사물이 전경에 큼직하게.
     "soft editorial watercolor illustration, bleeding translucent washes, granulated pigment texture, "
     "textured paper grain, muted palette with one quiet warm accent — human figures are the heart of the "
     "scene: their facial expressions and body gestures carry the story, weathered faces rendered tenderly "
     "in profile or three-quarter view, raw emotion softened and made bearable by the gentle medium",
     "intimate close-up from a profile or three-quarter angle — the main figure's face and the key object "
     "in their hands fill most of the frame, hands prominent in the foreground, gentle framing, soft "
     "atmospheric depth"),
    ("cartoon", "시사만평",
     # ⚠️ 'korean'은 만평 전통(화풍)이지 장소 아님 — 명시 없으면 해외 사건도 한국 배경·한글 간판으로 렌더(카나리아 실측 260703).
     # 260703 운영자 "기존 기틀 무시하고 가보자" = 만평만 3대 봉쇄 해제(글자·공인 캐리커처·여백틀) — 세부는 CARTOON_TEXT_RULES·_cartoon_frame.
     "newspaper editorial cartoon in the korean manpyeong tradition (drawing style only — depict the event's "
     "actual people and location), pen-and-ink caricature linework with restrained flat or light watercolor "
     "tinting, witty bitter-smile irony with exaggerated scale contrast — one metaphorical scene of dignified "
     "satire on the issue, not a solemn illustration",
     "single-panel composition with one clear central metaphor, eye-level"),
]

# 지배 조건(맨 앞·최상위) — 화풍·구도보다 먼저 읽혀 "무엇을·어떻게"의 우선순위를 잡는다(프롬프트 위계 = 나열보다 준수율↑).
GOVERNING = (
    "NEWS EDITORIAL IMAGE — one decisive moment that instantly identifies this news event and makes the reader "
    "stop scrolling. Do not retreat into vague mood shots, generic stock-photo scenes, posed models facing the "
    "camera, or smiling business people."
)

# FRAME = full-bleed 충전 + 단일 초점 + 지역 기본값. (구) '하단 자막 자리'는 260621 폐기(검정 띠만 유발).
# ⚠️ 암시룰(시신·유혈·고통 '직접묘사 말고 암시' 강제)은 260621 제거 — 충돌·분노 순화 방지(운영자 요청·일단은).
#    AVOID의 gore 항목은 '유혈 클로즈업·무기 겨눔'(표지 강등 모티프)만 한정 = 긴장 유지·순화 아님(분신술⑩ RCH-02 대칭).
_FRAME_KO = ("every person in the scene is KOREAN and the setting is Korea — this is a domestic Korean news "
             "story (only if the event is clearly foreign, use the event's actual region and people)")
# ⚠️ 하드 부정문("NOT Korea") 금지 — image_query_en은 '외신 검색 키'라 북한·한국팀 해외경기도 정당하게 채워짐
#    → NOT Korea 강제 시 한반도 인물·한국 선수가 외국인으로 오염(실물 4/45건 · 검증9). 긍정문만.
_FRAME_FOREIGN = "set in the event's actual country, region and people (this is a foreign-location news event)"
def _frame(foreign, likeness=False):
    # likeness(운영자 260703 "인물을 좀 더 닮게 — 극화·수채화") = 일러스트 계열만 공인 닮음 허용.
    # photo(실사)는 계속 익명 — 실사 닮음 = 딥페이크 인접 리스크(일러스트 캐리커처 전통과 결이 다름).
    tail = ("; the named public figure must look like the REAL person — reproduce their actual facial "
            "features, hairstyle and eyewear faithfully as seen in press photos, adapted to the drawing "
            "style (a portrait of that person, not a generic lookalike) — private individuals, victims "
            "and minors stay anonymous generic figures."
            if likeness else "; depict roles, professions and situations with generic faces.")
    return ("FRAME: vertical 4:5, the scene fills the entire frame edge to edge — every corner is part of the "
            "location, no empty margins or bands; one clear protagonist with a single sharp focal point (eyes, "
            "hands, or a key object), background and foreground filled naturally; "
            + (_FRAME_FOREIGN if foreign else _FRAME_KO) + tail)

# 금지 = AVOID 1줄 응집(옛 GOVERNING·화풍·COMPOSITION·NO_TITLE에 흩어졌던 금지 11절 → 이미지 모델 부정문
# 프라이밍 최소화·정보 손실 0). 글자 = 오버레이 전면금지 + 읽히는 한글 금지(깨짐 방지) 그대로 계승.
def _avoid(likeness=False):
    person = ("photorealistic likeness of real individuals (stylized illustration likeness of public figures "
              "is allowed); private individuals, victims and minors as anonymous figures"
              if likeness else "identifiable real individuals")
    return ("AVOID: blank/white/black bands, letterbox or borders; watermark or logo; overlay text, captions, "
            "headlines or legible lettering (tiny blurred incidental signage only — readable Korean text "
            "renders broken); " + person + "; sexualized or gratuitous depiction; any harm involving minors; "
            "graphic gore close-ups or a weapon aimed at the viewer (keep the dramatic tension, not shock).")
AVOID = _avoid(False)   # 하위호환(빌드 상수 참조처 보존)

# ── 라이브러리(apps/k/library) 코드 → Gemini 키워드 조회 (P1·운영자 260621) ──
# analyze가 사건 보고 고른 thumb_dispatch 코드(AG 앵글·LGT 조명·SG 연출)를 *실제 라이브러리 TSV*에서 조회해
# 프롬프트에 삽입(인라인 복붙 아님 = SSOT 단일출처·기틀 OK). 미존재 코드·파일부재는 드롭·fail-soft(현 동작 유지).
_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apps", "k", "library")
_LIB_FILES = ["38_cardnews_distance_crop", "39_cardnews_angle_height", "40_cardnews_staging",
              "13_style_news_canon", "12_lighting_emotion",
              "01a_camera_lens_focal_length", "01b_camera_shot_size",
              # 후킹 어휘 배선(분신술④ 260703) — 38/40 TSV가 내부 참조(추천조합)하는 EM/GST/ACT를 런타임 조회망에 연결.
              # analyze 메뉴(news-analysis.md) 확장과 세트(메뉴 없이 파일만 = 히트 0 죽은 로드).
              "22_expression_emotion", "33_gesture_interaction", "47_action_dynamics"]
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

# 코드 접두사 → 프롬프트 버킷(라벨 줄). 옛 한 줄 뭉치(lib_lookup)는 카메라↔조명↔연출이 콤마열에 뒤섞여
# 화풍 카메라와 모순 충돌 + 라이브러리 예시 소품('명패·연단') 리터럴 오염을 유발(분신술③⑨ 실측) → 라벨 분리.
_BUCKET_PREFIX = {"AG": "camera", "S": "camera", "L": "camera",
                  # DF(거리/크롭)는 camera가 아니라 focus 버킷 — DF-09 '빈 의자' 류 장면 모티프가 섞여 있어
                  # CAMERA 줄에 넣으면 소품이 카메라 지시로 오염(v1 리터럴 오염 재발 · 자가 트레이스 실측 260703).
                  "DF": "focus",
                  # NST(뉴스 화풍 캐논)는 화풍 정의라 STYLE 줄에 병기(STAGING 오배치 방지·검증1 — 현 메뉴엔 없어 수동 dispatch 대비).
                  "LGT": "light", "SG": "staging", "NST": "style",
                  "EM": "expression", "GST": "expression", "ACT": "expression"}

# 동일 모티프 SG↔DF 쌍 — analyze가 습관적으로 둘 다 찍음(큐 실측 SG-09+DF-09 동시 지정 ~23건 · 검증3).
# 같은 모티프(부재·군중고립·이중성)를 FOCUS·STAGING 2줄로 반복하면 'adapt' 래핑을 뚫고 리터럴 소품 확률↑ → DF 쪽 드롭.
_MOTIF_DUP = (("SG-09", "DF-09"), ("SG-04", "DF-07"), ("SG-16", "DF-12"))

def lib_buckets(dispatch):
    """thumb_dispatch 코드열 → 버킷별 Gemini 키워드 dict(camera/focus/light/staging/expression).
    미존재 코드 드롭(화이트리스트=실존 코드만·fail-soft 유지) + 동일 모티프 SG↔DF 중복이면 DF 드롭."""
    out = {}
    if not dispatch:
        return out
    codes = [c.strip() for c in dispatch.replace(",", " ").split() if c.strip()]
    for sg, df in _MOTIF_DUP:
        if sg in codes and df in codes:
            codes.remove(df)
    lib = _load_lib()
    for code in codes:
        kw = lib.get(code)
        if not kw:
            continue
        pm = re.match(r"[A-Za-z]+", code)
        bucket = _BUCKET_PREFIX.get(pm.group(0).upper() if pm else "", "staging")
        if kw not in out.setdefault(bucket, []):
            out[bucket].append(kw)
    return {k: ", ".join(v) for k, v in out.items()}

# 거리(샷사이즈) 어휘 검출 — AG 22코드 중 거리 포함은 3개뿐(AG-18·21·22·전부 wide)·최다 사용 AG-01은 각도 전용
# = 거리 미지정이면 르포 프라이어상 와이드 회귀(검증3) → 거리·DF 둘 다 없을 때만 화풍 기본 거리 구절을 병기.
# ⚠️ 부감 계열(top-down·bird's-eye·god's-eye·aerial·high-angle)은 거리 지정으로 간주 = 병기 억제 —
#    부감 뒤에 'tight medium' 병기 시 모순 재생산(실물 24/195건 · 검증9).
_SHOT_RE = re.compile(r"\b(wide|close[- ]?up|medium|long shot|full[- ]?shot|extreme|macro|tight|choker|"
                      r"bird'?s[- ]?eye|top[- ]?down|overhead|god'?s[- ]?eye|aerial|high[- ]?angle|cowboy)\b", re.I)

# 만평 전용 지배조건(운영자 260703 — "만평은 사건이 아니라 시사점 위주"): 사건 재현 금지·시사점을 한 컷 은유로.
GOVERNING_SATIRE = (
    "EDITORIAL CARTOON — one single-panel metaphorical scene that makes the INSIGHT below land in a single "
    "glance, with the bitter-smile irony of a daily newspaper cartoon. Do NOT illustrate the literal news "
    "event; invent a visual metaphor for the point — symbolic objects, exaggerated scale contrast, ironic "
    "juxtaposition."
)

# 만평 3대 봉쇄 해제(운영자 260703 "기존 기틀을 무시하고 한번 가보자" — 실제 신문 만평 문법 복원 · 만평 화풍 한정):
# ① 한글 말풍선·손글씨 라벨 허용(짧고 크게 = 깨짐 최소화 — 리스크는 카나리아 실측) ② 공인 캐리커처 허용
# ③ full-bleed 예외(흰 여백+얇은 테두리 = 만평 정체성). ⚠️ 안전 하한은 유지: 사인·피해자·미성년 익명·모욕/혐오 금지.
CARTOON_TEXT_RULES = (
    "TEXT & FIGURES: short Korean speech bubbles and hand-written labels ARE allowed and are part of the "
    "genre — but use AT MOST 3 text elements in total (e.g. one speech bubble + one or two labels, plus "
    "optionally one bottom caption strip); do NOT label every object — the drawing speaks, text only lands "
    "the punch. Keep each to a few large, clearly legible Korean words (fewer, bigger words render cleaner); "
    "draw the wording from the HOOK/INSIGHT above. Caricatures of public figures (politicians, senior "
    "officials) in the editorial-cartoon tradition are allowed. "
    "AVOID: watermark or logo; sexualized or gratuitous depiction; any harm involving minors; private "
    "individuals and victims stay anonymous role figures; no slurs, nothing hateful or demeaning beyond "
    "dignified satire."
)

def _cartoon_frame(foreign):
    return ("FRAME: vertical 4:5 canvas — one editorial-cartoon panel with a thin rounded border, sitting on "
            "a clean white background with generous margins (the panel does NOT fill the canvas edge to "
            "edge — white space is part of the genre); "
            + (_FRAME_FOREIGN if foreign else _FRAME_KO) + ".")

def build_cartoon_prompt(look, cam_default, insight, hook="", lead="", wish="", foreign=False):
    """시사만평 전용 v3(운영자 260703) — 원료 = 사건 장면(thumb_scene)이 아니라 **시사점(💡 산문)+hook**.
    사건은 EVENT CONTEXT로만 깔아 은유의 소재를 제공(문자 그대로 그리지 말 것 명시). dispatch(사건용
    앵글·조명)는 의도적으로 미사용 — 은유가 구도를 결정한다. insight·hook 둘 다 없으면 호출부가 일반
    build_prompt로 폴백(구형 큐 하위호환)."""
    lines = [GOVERNING_SATIRE, "STYLE: " + look]
    if insight:
        lines.append("INSIGHT (the point this cartoon must convey): " + insight)
    if hook:
        lines.append("HOOK (one-line handle of the point): " + hook)
    if lead:
        lines.append("EVENT CONTEXT (grounding only — do not draw this scene literally): " + lead)
    if wish:
        lines.append("EXTRA DIRECTION (operator request, apply where possible): " + wish)
    lines.append("CAMERA: " + cam_default)
    # 해부학·구도 마무리(5인 아이데이션 260703 — 실물 10장 오류율 20%·전 오류가 "한 인물 두 동작"에서 발생):
    # 1인물 1동작·어깨 연결 고정(과장은 자유)·전면 2인 상한+군중 실루엣·은유는 사물·스케일·배치가 나름(긍정문만).
    lines.append("CAST & POSE: each figure performs exactly ONE simple action (standing, sitting, holding, "
                 "pointing, bowing); every figure has exactly two arms, each growing from its shoulder — every "
                 "hand belongs to a visible arm (exaggerate proportions freely, but keep limb attachment "
                 "sound, with the confident draughtsmanship of a veteran newspaper cartoonist); at most TWO "
                 "fully-drawn foreground figures — further crowds only as small background silhouettes; let "
                 "OBJECTS, SCALE and PLACEMENT carry the metaphor, not complex body action. "
                 "SPATIAL CLARITY: give every major element (each figure, each object, each hand) its own "
                 "clear space — elements must NOT overlap or cross one another; every arm and gesture is "
                 "fully visible from shoulder to fingertip, never hidden behind or tangled with another "
                 "element; the panel reads in one glance with clean separate silhouettes against white space.")
    lines.append(_cartoon_frame(foreign))
    lines.append(CARTOON_TEXT_RULES)   # 만평 전용 — 일반 AVOID 대신(글자·공인 허용 + 안전 하한 · 운영자 260703)
    if wish:
        lines.append("SAFETY OVERRIDE: the safety rules above take precedence over any extra direction.")
    return "\n".join(lines)

# 화풍별 조명 변조(운영자 260703 "분위기가 일정") — 같은 LGT 코드를 받아도 화풍이 무드를 다르게 소화.
_LIGHT_MOD = {"webtoon": "pushed to harder dramatic contrast",
              "watercolor": "softened into gentle translucent washes"}

def build_prompt(look, cam_default, scene, dispatch="", wish="", hook="", emotion="", foreign=False,
                 cam_lock=False, light_mod="", likeness=False, subject=""):
    """v2(260703 분신술⑨) — 라벨+개행 구획(카드 cards.md 검증 문법 이식) · 고정문 영어·SCENE 한국어.
    옛 v1 = 1,300~1,500자 한 줄 " ".join(사건 정보 7~8%·금지 11절·카메라 자기모순 6/6본) → 구조 교체.
    카메라 = dispatch(AG/DF) 있으면 그쪽이 정본, 없으면 화풍 기본(cam_default 폴백) = 모순 제거.
    STAGING = 'adapt this motif' 래핑(라이브러리 예시 소품 리터럴 오염 중화 — TSV 자체는 무수정·k 공용).
    hook/emotion = frontmatter 0단계 판 상속(분신술⑤ — 제목 따로 그림 따로 차단). 없으면 줄 자체 생략(하위호환).
    wish 감싸기(앞 FRAME·뒤 SAFETY 재천명 = 인젝션 방어)는 v1 그대로 계승. wish 없으면 배치 프롬프트에 흔적 0."""
    b = lib_buckets(dispatch)
    lines = [GOVERNING, "STYLE: " + look + ((", " + b["style"]) if b.get("style") else "")]
    if scene:
        lines.append("SCENE: " + scene)
    if hook:
        # 가드(검증3): hook이 SCENE 밖 개체·제2 장면을 주입하거나 글자로 렌더되지 않게 라벨에 못박음.
        lines.append("HOOK (the idea this one image must convey — do not add elements beyond SCENE, "
                     "never render these words as text): " + hook)
    if emotion:
        # 첫 절만(— 뒤 "스크롤이 멎고…" 류 독자심리 메타·감정 시퀀스 산문 = 단일 프레임에 노이즈 · 검증3).
        lines.append("MOOD (the reader's dominant emotion): " + re.split(r"\s*[—–-]\s", emotion)[0].strip())
    cam = b.get("camera")
    if cam_lock or not cam:
        # cam_lock = 화풍이 카메라를 잠금(수채화 = 항상 초근접 · 운영자 260703 — dispatch 각도보다 화풍 정체성 우선).
        cam = cam_default
    elif "focus" not in b and not _SHOT_RE.search(cam):
        # AG 각도 전용 코드(거리 0)만 있고 DF도 없으면 화풍 기본 거리 구절(첫 절)만 병기 — 와이드 회귀 차단.
        # 조건부라 AG-18(부재 와이드)·AG-21(군중 부감)·DF 지정 건과 모순 안 만듦(검증3 "무조건 병기 금물").
        cam = cam + ", " + cam_default.split(",")[0].strip()
    # 평면 탈피(운영자 260703 "전부 카메라가 평면") — 눈높이(윤리)는 존엄이지 정면 평면이 아님을 명시:
    # 감정에 맞는 시점(3/4·측면·어깨너머·살짝 높낮이)을 고르게 해 밋밋한 정면 구도 고착을 푼다.
    lines.append("CAMERA: " + cam + ", a frozen split-second; choose an expressive viewpoint — three-quarter, "
                 "profile, over-the-shoulder or a subtle height shift as the emotion demands, not a flat "
                 "head-on composition (eye-level dignity does not mean flatness)")
    if b.get("focus") and not cam_lock:
        lines.append("FOCUS (distance & crop of the key subject, adapt this to the scene above, "
                     "do not copy its literal props): " + b["focus"])
    if b.get("light"):
        lines.append("LIGHT: " + b["light"] + ((", " + light_mod) if light_mod else ""))
    if b.get("staging"):
        lines.append("STAGING (adapt this motif to the scene above, do not copy its literal props): " + b["staging"])
    if b.get("expression"):
        lines.append("EXPRESSION & ACTION: " + b["expression"])
    if wish:
        lines.append("EXTRA DIRECTION (operator request, apply where possible): " + wish)
    if likeness and subject:
        # 닮음은 이름이 있어야 성립(장면 텍스트는 "40대 남성 정치인" 식 익명 — 한줄요약으로 주체 명시 · 운영자 260703).
        lines.append("SUBJECT (who this scene is about — draw this public figure's REAL face, "
                     "a faithful portrait of the actual person): " + subject)
    lines.append(_frame(foreign, likeness))
    lines.append(_avoid(likeness))
    if wish:
        lines.append("SAFETY OVERRIDE: the AVOID line above takes precedence over any extra direction.")
    return "\n".join(lines)

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
    if ts.startswith("<") or ts in (
            "화재로 그을린 건물 앞 가족 잃은 주민이 오열하는데 뒤편 관계자들은 서류만 들여다보는 순간",
            "충혈된 눈으로 오열하는 50대 주민의 일그러진 얼굴, 그 뒤 그을린 건물 앞에서 서류만 들여다보는 정장 차림 관계자들, 잿빛 오후"):
        ts = ""
    # 0단계 판 상속(분신술⑤ 260703) — SYS-06 frontmatter 3키 중 hook·emotion을 썸네일 프롬프트로 계승
    # (제목·카드·썸네일이 같은 감정 좌표에서 출발 = '제목 따로 그림 따로' 차단). 예시 placeholder 베낌은 가드.
    hook = fm.get("hook", "").strip()
    if hook.startswith("<") or hook == "독자가 다음 사람에게 옮길 화두 한 마디":
        hook = ""
    emo = fm.get("emotion", "").strip()
    if emo.startswith("<") or emo == "1순위 감정 + 왜 거기서 멈추는지 반 줄":
        emo = ""
    # 시사점(💡 산문) = 만평의 원료(운영자 260703 — "만평은 사건이 아니라 시사점 위주"). 앞 400자 응축.
    im_ = re.search(r"^###?\s*💡[^\n]*\n+(.+?)(?:\n#|\Z)", body, re.S | re.M)
    insight = re.sub(r"\s+", " ", im_.group(1)).strip()[:400] if im_ else ""
    # 해외 사건 판정(분신술③ T8 — '한국 기본값'이 태국 사건을 한옥으로 오염) = image_query_en 채움 여부(해외 전용 키).
    extras = {"hook": hook, "emotion": emo, "insight": insight,
              "foreign": bool(fm.get("image_query_en", "").strip())}
    return head, lead, iq, ts, fm.get("url", "").strip(), fm.get("alt_urls", "").split(), fm.get("image_sources", "").split(), fm.get("thumb_dispatch", "").strip(), extras

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

def _md_no_thumb(path):
    """프런트매터 no_thumb: "1" 판정(뷰어 '이미지' 토글 OFF → 제미나이 썸네일 생성 skip · 검색 og:image는 무관·항상 · 운영자 260702).
    ask.sh가 asks/*.json의 nothumb 플래그를 queue frontmatter로 주입. 파일 앞부분만 읽음(main 배치 게이트·process_one 게이트 공용)."""
    try:
        m = re.search(r'^\s*no_thumb\s*:\s*"?([^"\n]*)', open(path, encoding="utf-8").read(2000), re.M)
        return bool(m and m.group(1).strip().lower() in ("1", "true", "yes", "on"))
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

def gemini_image(prompt, image_size="1K", tag="img", aspect="4:5", ref_png=None):
    """Gemini 이미지 1장 생성 → PNG bytes(실패 시 None, fail-soft). usageMetadata는 _USAGE에 기록.

    image_size: "1K"(기본·gen_cards 재사용 시 유지)·"2K"·"4K"(대문자 K 필수). 썸네일·카드 모두 1K 호출(토큰 절감).
    aspect: 화면비("4:5" 기본=카드/썸네일 · "16:9"/"9:16"=영상 레퍼런스 등).
    ref_png: 참조 얼굴 사진 bytes(운영자 260703 참조 체이닝) — 있으면 parts 앞에 inline_data로 첨부해
             "이 실제 얼굴로 그려라". 실사진→일러스트 = 공인 캐리커처 전통(안전 하한은 프롬프트가 유지). 없으면 텍스트 전용.
    """
    parts = []
    if ref_png:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(ref_png).decode()}})
    parts.append({"text": prompt})
    payload = {
        "contents": [{"parts": parts}],
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

def _band_fail(png_bytes):
    """상·하 8% 가장자리 띠가 '검정/흰 단색 밴드·레터박스'(FRAME 위반)인지 PIL로 직접 판독(THUMB_GATE 전용).
    _is_logo_card와 같은 '픽셀 직접 보기' 계열. PIL 없음·판독 실패 = False(통과 = 무회귀·fail-soft).
    ⚠️ 판정 = 분산 극소 AND 극단 명도(거의 순검정/순백) 둘 다 — 분산만 보면 thumbnail() 평균화로
    하늘·밤·벽 등 평범한 저분산 밴드가 전부 오탐(검증1 실측: 노이즈 전체 이미지 var~35<40)이라
    레터박스의 본질인 '순검정/순백 띠'로 조인다(흐린 하늘 mean~180대·밤하늘 mean>10은 통과)."""
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(png_bytes)).convert("L")
        im.thumbnail((64, 80))
        w, h = im.size
        px = list(im.getdata())
        band = max(2, int(h * 0.08))
        for rows in (range(band), range(h - band, h)):
            vals = [px[y * w + x] for y in rows for x in range(w)]
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            if var < 15 and (mean < 10 or mean > 245):       # 사실상 균일 + 순검정/순백 = 진짜 밴드만
                return True
        return False
    except Exception:
        return False

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

def _load_ref_face(tdir):
    """search.json 대표(label=='') og:image를 bytes로 fetch — 참조 체이닝용(THUMB_REF · 운영자 260703).
    대표 = 그 기사 인물 실사진. http_image(SSRF·매직바이트 가드) 재사용. 실패·부재=None(fail-soft = 텍스트 전용 회귀)."""
    try:
        items = json.load(open(os.path.join(tdir, "search.json"), encoding="utf-8"))
    except Exception:
        return None
    rep = next((x for x in items if not x.get("label")), None) or (items[0] if items else None)
    if not rep or not rep.get("url"):
        return None
    b, _ct, _ext = http_image(rep["url"])
    if b:
        print("  🖼 참조 얼굴 확보(대표 og:image {}…)".format(rep["url"][-32:]))
    return b

def process_one(md, stem):
    """기사 1건 = 검색이미지(기사 og:image + 유사) + AI 2화풍. 저장 = R2(공개 URL) 또는 git 폴백."""
    head, lead, iq, thumb_scene, art_url, alt_urls, image_sources, dispatch, extras = parse_md(md)
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
    # AI 생성 4화풍(260703 재편) — THUMB_AI_OFF(전역) 또는 no_thumb(이 기사·뷰어 '이미지' 토글 OFF)면 통째 생략(검색이미지만 채움).
    # 평소엔 기존 gen.json의 완료 화풍(sid)은 보존·재호출(재과금) 안 함 = 부분성공 자동 보완(폐지된 photo_close sid는 STYLES에 없어 자동 드롭 · watercolor·cartoon은 260703 복귀).
    changed = False
    no_thumb = _md_no_thumb(md)   # 이 기사만 제미나이 썸네일 생성 skip(뷰어 '이미지' 토글 OFF·검색 og:image는 위서 이미 채움·운영자 260702)
    if AI_OFF or no_thumb:
        print("  ⏸ AI 썸네일 생성 OFF({}) — 검색이미지만 처리(기존 썸네일·gen.json·토큰 영향 0)".format("THUMB_AI_OFF" if AI_OFF else "no_thumb"))
    else:
        _u0 = len(_USAGE)                         # 이 기사 제미나이 호출 사용량 슬라이스 시작점
        redo_wish = re.sub(r"[\x00-\x1f\x7f]", " ", os.environ.get("THUMB_REDO_WISH", "")).strip()[:500]   # 뷰어 '다시 만들기' 팝업 코멘트(선택) — 재생성 화풍에만 반영(배치 경로는 미설정 → 빈값 = 영향 0). 제어문자 제거+[:500] = 수동 dispatch(프론트 우회) 대비 대칭 심층방어(로그 워크플로커맨드 차단·평의회 보안)
        if redo_wish:
            print("  📝 재생성 지시 반영: {}".format(redo_wish[:80]))
        existing = {g.get("sid"): g for g in _load_gen(tdir) if g.get("sid")}
        gen = []
        prompts_rec = {}   # sid → 실제 발사 프롬프트(역추적용 · 운영자 260703 "합격점 되면 역추적해서 프롬프트를 뽑아낼 수 있게")
        ref_face = _load_ref_face(tdir) if REF_ON else None   # 참조 얼굴(극화·수채 = 실제 얼굴 재현 · THUMB_REF)
        for sid, label, look, cam_default in STYLES:
            if sid in existing:                      # 이미 완료(R2 URL or 로컬) → 보존
                gen.append(existing[sid]); continue
            # v2 프롬프트(라벨+개행·영어 고정문·hook/emotion 상속·해외 지역 스위치). 1K(토큰 절감 · 운영자 260621).
            # 장면(WHAT)=충돌장면(thumb_scene) 1순위→entity(iq)→한줄요약 + 연출(HOW)=dispatch 버킷 + wish=재생성 지시.
            # 화풍별 특칙(운영자 260703): cartoon=시사점 은유(사건 장면 미사용·insight/hook 없으면 일반 폴백) /
            # watercolor=카메라 잠금(항상 초근접) / webtoon·watercolor=조명 변조(_LIGHT_MOD).
            if sid == "cartoon" and (extras.get("insight") or extras.get("hook")):
                prompt = build_cartoon_prompt(look, cam_default, extras.get("insight", ""),
                                              hook=extras.get("hook", ""), lead=lead, wish=redo_wish,
                                              foreign=extras.get("foreign", False))
            else:
                like = sid in ("webtoon", "watercolor")   # 일러스트 계열 = 공인 닮음 허용(운영자 260703 · photo=익명 유지)
                prompt = build_prompt(look, cam_default, thumb_scene or iq or lead, dispatch, redo_wish,
                                      hook=extras.get("hook", ""), emotion=extras.get("emotion", ""),
                                      foreign=extras.get("foreign", False),
                                      cam_lock=(sid == "watercolor"), light_mod=_LIGHT_MOD.get(sid, ""),
                                      likeness=like, subject=(lead if like else ""))
            # 참조 체이닝(THUMB_REF · 극화·수채만) — 대표 실사진을 첨부하고 "이 얼굴로 그려라" 프리픽스(앞=최우선).
            #   ⚠️ 안전 하한: 사인·피해자·미성년이면 익명 유지(모델 판단 지시) — photo는 애초 REF 대상 아님·cartoon은 이번 제외.
            use_ref = ref_face if (REF_ON and sid in ("webtoon", "watercolor")) else None
            if use_ref:
                prompt = ("REFERENCE FACE: the attached photo is the REAL face of the public figure this "
                          "story is about. Redraw THAT exact person — same face, hairstyle and build, "
                          "clearly recognizable as the same individual — in the illustration style described "
                          "below. (If the attached photo shows no single clear human face — a building, chart, "
                          "crowd or object — ignore it entirely and just follow the scene below. If the person "
                          "is a private individual, a victim, or a minor, ignore this and keep them an "
                          "anonymous generic figure.)\n" + prompt)
            prompts_rec[sid] = prompt
            png = gemini_image(prompt, "1K", ref_png=use_ref)
            # 품질 게이트(TH-06 · 기본 OFF = THUMB_GATE=1 점화 시만 · §📰 카나리아 절차: OFF 머지→단건 실측→승격) —
            # 단색 밴드(빈/검정 띠 = FRAME 위반)만 결정론 판독, 미달이면 1회 재생성. ⚠️ 상한 = 화풍당 재시도 1회
            # (기사당 최대 4콜)·재시도본도 밴드면 '항상 기록'(미기록형 게이트 = main 백필 루프와 결합해 무한 재과금 — 분신술⑧).
            if png and GATE and _band_fail(png):
                print("  🔍 게이트: 단색 밴드 검출 → 1회 재생성 ({})".format(sid), flush=True)
                # RETRY NOTE는 프롬프트 *앞*에 — 후미는 AVOID·SAFETY 재천명이 '마지막 말'로 남아야(위계 보존·검증4).
                png2 = gemini_image("RETRY NOTE: the previous attempt left a solid blank band — fill the "
                                    "entire frame with the scene, edge to edge.\n" + prompt, "1K", ref_png=use_ref)
                if png2:
                    png = png2
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
            # 프롬프트 원장(역추적 · 운영자 260703) — 이번에 실제 발사된 sid의 프롬프트만 병합 기록(보존 sid는 기존 유지).
            # "이 그림 합격" → prompts.json에서 그 sid 프롬프트를 꺼내 레시피로 굳힌다. 텍스트 ~2KB/기사 = git 부담 미미.
            try:
                pp = os.path.join(tdir, "prompts.json")
                try:
                    prev_p = json.load(open(pp, encoding="utf-8"))
                except Exception:
                    prev_p = {}
                fired = {g.get("sid") for g in gen if g.get("sid")} - set(existing)
                prev_p.update({k: v for k, v in prompts_rec.items() if k in fired})
                json.dump(prev_p, open(pp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            except Exception as e:
                print("  ⚠️ prompts.json 기록 실패(무시): {}".format(e))
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
        # wish 원장 적립(TH-07 · 분신술⑦ 260703) — 재생성 지시(운영자 불만의 유일한 자연어 1차 사료)가 Actions
        # 로그 90일 소멸로 증발하지 않게 jsonl append(rate_record 패턴). 실패해도 무시(fail-soft·재생성 자체는 무영향).
        try:
            from datetime import datetime, timezone, timedelta
            ts_kst = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")   # KST 강제(§📐)
            # 제어문자 + U+2028/2029(유니코드 라인분리) 제거 = jsonl 1레코드 1물리줄 보장(미래 splitlines() 리더 방어·검증7).
            wish_raw = re.sub(r"[\x00-\x1f\x7f  ]", " ", os.environ.get("THUMB_REDO_WISH", "")).strip()[:500]
            if wish_raw:   # 빈 wish(무코멘트 재추첨)는 스킵 — 원장 = 자연어 불만 사료(검증2·4·7·8 수렴 지적)
                os.makedirs("scraper", exist_ok=True)
                with open("scraper/thumb_wishes.jsonl", "a", encoding="utf-8") as wf:
                    wf.write(json.dumps({"ts": ts_kst, "article": only, "sid": redo_sid or "all",
                                         "wish": wish_raw}, ensure_ascii=False) + "\n")
                print("  📒 wish 원장 적립: scraper/thumb_wishes.jsonl")
        except Exception as e:
            print("  ⚠️ wish 원장 기록 실패(무시): {}".format(e))
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
        # AI_OFF(전역) 또는 no_thumb(이 기사·뷰어 '이미지' 토글 OFF)면 AI는 '완료'로 간주(생성 안 함) → 검색만 끝나면 skip(매 런 불필요 재순회·신규픽 슬롯잠식 방지·운영자 260702).
        ai_done = AI_OFF or _md_no_thumb(md) or ({g.get("sid") for g in _load_gen(tdir)} >= target_sids)
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
