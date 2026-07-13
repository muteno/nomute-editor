#!/usr/bin/env python3
"""뷰어 '이미지 생성'(검색 카러셀 + 버튼 팝업) — 버튼으로 고른 옵션(화풍·비율·해상도·장수·문구·주문)과
기사 요약·시사점을 Claude(Opus 4.8·effort max·구독 OAuth)가 읽고 Gemini 이미지 프롬프트 *영문 1개*를 작성
→ Gemini(thumb_gen.gemini_image·종량제 GEMINI_API_KEY)가 렌더 → R2 업로드 →
cards/<stem>/thumbs/search.json **앞쪽** prepend(label '생성') → 뷰어 카러셀 자동 반영(articles.json 폴링).

운영 원칙(운영자 260707): 구독+종량제 병행 활용 — 프롬프트 지능=구독 Opus·렌더=종량제 Gemini.
- Claude 호출 = 폴오버 SSOT(shared/claude_py.run_claude · 쿼터 시 4계정 체인 자동 전환 · §📰).
- Claude가 완전 실패해도 결정형 폴백 프롬프트로 렌더 강행(fail-soft — '생성' 버튼은 항상 결과를 내려 노력).
- 카드 제미나이 0 불변과 무관: 이 경로는 뷰어 수동 발사(슛과 동일 정책·자동 파이프라인 아님).
입력: env GENIMG_STEM(기사 file 베이스) · GENIMG_OPTS(JSON: style/sub/aspect[N:N 자유]/size[720p·FHD·2K·4K]/count/fmt[png·jpg90]/
      mood[auto·axes+moodAx 게이지]/kweb/textOn[문구 살리기 토글]/wish · 레거시 text·font·1K도 수용 — 260710 개요 개편).
자유 생성(GENIMG_FREE=1 · 운영자 260707 "이미지 제작 세부메뉴 4번"): 기사 없음 — 운영자 주문(wish)/문구(text)가 장면의 전부.
  산출 = viewer/gen_out/free.json prepend(캡 24) · R2 키 genfree/ · 뷰어 이미지 제작 도구 /6 생성 탭 그리드가 폴링.
"""
import datetime
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
import thumb_gen as tg   # __main__ 가드 있음 = import 안전. gemini_image·r2_upload·parse_md·R2_ON 재사용.  # noqa: E402
from claude_py import run_claude   # 쿼터 한도 시 대체 계정 자동 전환(account failover · SSOT)  # noqa: E402

MODEL = os.environ.get("PIPE_MODEL", "claude-opus-4-8")   # 프롬프트 작성 = Opus 4.8(운영자 "프롬프트 뽑는거는 opus 4.8 --effort max")
KST = datetime.timezone(datetime.timedelta(hours=9))      # §📐 시각 = KST


def die(msg, code=1):
    print("::error::" + msg, flush=True)
    sys.exit(code)


# ── 옵션 화이트리스트(genimg.js와 동일 집합 — 이중 검증) ──────────────────────────
# 260710 개요 개편(운영자): 해상도 = 픽셀 라벨(720p/FHD/2K/4K · 기본 FHD) · 비율 = 자유 N:N(각 1~99) · 품질 = PNG/JPG90.
NATIVE_ASPECTS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")   # Gemini imageConfig.aspectRatio 실지원 집합 — 커스텀 비율은 근접 네이티브로 렌더 → post_process가 정확 크롭
SIZE_RENDER = {"720p": "1K", "FHD": "1K", "2K": "2K", "4K": "4K"}   # 렌더 호출 크기 — FHD도 1K 렌더 후 보간(기본 과금 = 현행 1K 동일 · 문구 살리기 ON이면 main()이 2K 플로어)
SIZE_SHORT = {"720p": 720, "FHD": 1080, "2K": 1440, "4K": 2160}    # 목표 = 짧은 변 px(비율 무관 단일 기준 · 4:5 FHD = 1080×1350 = 카드 표준)
ASPECT_EN = {"4:5": "vertical 4:5 portrait", "1:1": "square 1:1", "3:4": "vertical 3:4 portrait",
             "9:16": "tall vertical 9:16 story format", "16:9": "wide horizontal 16:9"}


def _parse_aspect(a):
    """'W:H'(각 1~99 정수 · 비율 1:4~4:1) → (w, h) | None — genimg.js·뷰어 geniArVal과 동일 계약.
    비율 상한 = 극단값(99:1 등) 크롭·리사이즈 병리(수만 px 캔버스·libjpeg 65500 한계) 차단(평의회3 260710)."""
    m = re.match(r"^(\d{1,2}):(\d{1,2})$", str(a or ""))
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if not (w >= 1 and h >= 1):
        return None
    return (w, h) if 0.25 <= w / h <= 4 else None


def aspect_en(a):
    """화면비 영문 지시 — 표준형은 정본 문구, 커스텀 N:N은 방향 서술 생성."""
    if a in ASPECT_EN:
        return ASPECT_EN[a]
    w, h = _parse_aspect(a) or (4, 5)
    if w == h:
        return "square {} format".format(a)
    return ("wide horizontal {} format" if w > h else "vertical {} portrait format").format(a)


def nearest_native(a):
    """커스텀 비율 → 가장 가까운 Gemini 네이티브 비율(렌더용 — 이후 post_process가 정확 비율로 중앙 크롭)."""
    w, h = _parse_aspect(a) or (4, 5)
    r = w / h
    return min(NATIVE_ASPECTS, key=lambda n: abs(int(n.split(":")[0]) / int(n.split(":")[1]) - r))
# 화풍 프리셋 — photo/webtoon 은 썸네일 정본(tg.STYLES)의 look을 그대로 계승(드리프트 0),
# 나머지는 이 기능 전용 look(뉴스 카드 배경에 실효적인 계열 — 아이데이션 분신술 260707).
# likeness: 일러스트 계열만 공인 닮음 허용(실사=익명 — thumb_gen §닮음 정책 그대로).
_TG = {s[0]: s for s in tg.STYLES}
STYLE_KO = {"photo": "실사 보도", "webtoon": "웹툰 극화", "cartoon": "시사만평", "watercolor": "수채화",
            "cinematic": "시네마틱", "illust": "플랫 일러스트", "iso3d": "3D 아이소메트릭", "pictogram": "픽토그램"}
STYLE_FRAG = {
    "photo": (_TG.get("photo") or ("", "", "reportage press photograph, documentary realism", ""))[2],
    "webtoon": (_TG.get("webtoon") or ("", "", "korean webtoon serious drama illustration", ""))[2],
    "cartoon": ("korean newspaper editorial cartoon satire, bold hand-drawn caricature with exaggerated "
                "features, clean ink outlines and flat colors, one witty visual metaphor that lands the point"),
    "watercolor": ("soft watercolor illustration, translucent layered washes, delicate brush strokes, "
                   "muted emotional palette, subtle paper texture"),
    "cinematic": ("cinematic film still, anamorphic framing, dramatic volumetric key light, moody teal-and-amber "
                  "color grading, shallow depth of field, high production value"),
    "illust": ("modern flat editorial illustration, clean bold vector shapes, confident color blocking, "
               "one strong conceptual visual metaphor, generous negative space"),
    "iso3d": ("isometric 3D rendered scene, soft studio lighting, matte clay-like materials, crisp geometry, "
              "miniature diorama feel, high detail"),
    "pictogram": ("minimal infographic pictogram composition, bold iconographic shapes, strictly limited palette, "
                  "strong negative space, poster-like clarity"),
}
LIKENESS_STYLES = ("webtoon", "cartoon", "watercolor", "illust")   # 일러스트 계열 = 공인 닮음 허용(캐리커처 전통)
# 한국웹툰식 토글(전 화풍 공통 · 운영자 260707 "모든 장르 선택 시 옵션") — 선택 화풍을 한국 웹툰 만화 문법으로 번안.
#   화풍=극화(webtoon)일 땐 NST-B 정본 전문으로 승격(중복 병기 대신 강화 · 13_style_news_canon 계승).
KWEB_MIX = ("rendered in korean webtoon (manhwa) visual grammar — clean confident digital ink outlines, "
            "cel-shaded color with defined edges, subtle screentone shading accents, polished webtoon finish")
KWEB_FULL = ("korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, "
             "precise anatomical rendering, screentone shading, cel-shaded color with defined edges, "
             "high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere")
MOOD_KO = {"auto": "자동", "tense": "긴장", "somber": "침통", "hope": "희망", "calm": "차분", "anger": "분노", "eerie": "스산", "warm": "온기"}   # +3 = 라이브러리 12(감정 조명) 계열 보완(운영자 260707 "분위기 보완")
MOOD_FRAG = {"auto": "", "tense": "tense, high-stakes urgency", "somber": "somber, grave, mournful stillness",
             "hope": "hopeful, a resolving light breaking through", "calm": "calm, composed, analytical stillness",
             "anger": "furious, indignant confrontational energy, protest heat", "eerie": "uneasy, eerie stillness, something quietly wrong",
             "warm": "warm everyday human warmth, gentle intimate closeness"}
# 무드 게이지 4축(운영자 260710 "종류별 분리·게이지로 선택") — 각 -2..+2 · 0=중립(미지시) · 프리셋(MOOD_FRAG)은 레거시 수용.
MOOD_AX = {
    "ct": ("차분", "긴장", ("deeply calm, serene composed stillness", "quietly composed, unhurried",
                          "tense, uneasy urgency in the air", "extreme tension, high-stakes urgency")),
    "sh": ("침통", "희망", ("grave, mournful heaviness", "somber undertone",
                          "a hopeful undertone, light beginning to break", "radiant hope, uplifting resolve")),
    "ew": ("스산", "온기", ("eerie, unsettling stillness, something quietly wrong", "cool, detached air",
                          "gentle human warmth", "warm intimate closeness, everyday humanity")),
    "rr": ("냉정", "격앙", ("icy restraint, clinical control", "held-back, measured emotion",
                          "simmering indignation", "furious confrontational energy, protest heat")),
}


def mood_axes_frag(ax):
    """게이지 값 → (영문 MOOD 조각, 한글 요약). 0축은 침묵 — 전부 0이면 ('', '')."""
    frs, kos = [], []
    for k, (lo, hi, fr) in MOOD_AX.items():
        v = int(ax.get(k, 0) or 0)
        if not v:
            continue
        frs.append(fr[{-2: 0, -1: 1, 1: 2, 2: 3}[v]])
        kos.append("{} {:+d}".format(hi if v > 0 else lo, v))
    return ", ".join(frs), " · ".join(kos)


FONT_KO = {"gothic": "고딕", "serif": "명조", "brush": "붓글씨", "neon": "네온"}
FONT_FRAG = {"gothic": "heavy bold Hangul sans-serif poster lettering, thick even strokes",
             "serif": "elegant Hangul serif (Myeongjo-style) lettering, refined thin-to-thick stroke contrast",
             "brush": "energetic Korean brush-calligraphy Hangul lettering, hand-inked strokes",
             "neon": "glowing neon-tube Hangul sign lettering"}
# ── 구도·조명·표현 포인트 = /k 메인 라이브러리(archive_media_master SSOT) 실코드 — 해석은 tg.lib_buckets 재사용
#    (thumb_dispatch와 동일 조회망 = 어휘 드리프트 0 · 운영자 260707 "레포 라이브러리 뒤져서 배선"). 'auto' = 코드 없음(Opus 재량).
ANGLE_CODES = ("AG-01", "AG-02", "AG-03", "AG-04", "AG-06", "AG-09")       # 39_cardnews_angle_height: 눈높이/로우위압/하이왜소/부감/더치/측면
POINT_CODES = ("DF-01", "DF-02", "DF-04", "DF-05", "DF-07")                # 38_cardnews_distance_crop: 눈물클로즈/주먹인서트/서류매크로/대치투샷/군중속1인
LIGHT_CODES = ("LGT05", "LGT06", "LGT08", "LGT09", "LGT10", "LGT12")       # 12_lighting_emotion: 촛불/골든아워/흐린확산/하드측광/역광실루엣/형광임상
SHOT_CODES = ("S03", "S04", "S06", "S08", "S10")                           # 01b_camera_shot_size: 와이드/전신/상반신/클로즈업/표정 익스트림 클로즈업(운영자 260707 "카메라 얼마나 가까이")
EXPR_CODES = ("EM-03", "EM-05", "EM-09", "EM-12", "EM-16", "EM-17")        # 22_expression_emotion(FACS): 슬픔/분노/억눌린 표정/직시/눈물 글썽/턱 악물기(운영자 260707 "표정 묘사")
# 배치 = 카드뉴스 프롬프팅 정본 계승(apps/news/02 §합성 "main subject anchored in the upper-center" · 라우터 "핵심요소 상단 2/3")
#   top23 = 뷰어 라벨 '썸네일'(운영자 260707 — 썸네일 조건 명칭 · 조각/값 불변 = 지침 정본 그대로)
PLACE_FRAG = {"auto": "",
              "top23": ("the main subject anchored in the upper two-thirds of the frame (upper-center), "
                        "the lower zone kept visually calm and uncluttered so a caption can sit over it"),
              "center": "the main subject centered with balanced, symmetrical visual weight",
              "full": "full-figure staging — the protagonist visible head to toe within the scene"}
# 화풍 서브 분기(운영자 260707 "수채도 여러 수채") — STYLE_FRAG에 병기되는 변주 look. 'auto' = 기본 look만.
# 세부 확장 260707 2차+3차(운영자 "게키카도 여러 화풍·한국웹툰식 상시") — 어휘 = /k 라이브러리 실코드 + 게키가 유파 웹실증(위키 Gekiga·TCJ·MUSE 260707 검색):
#   극화 세부 = 대표만(운영자 260707 3차 "기본+분열 4~5"): 게키가 정통·하드보일드·시대극·순정·명랑 — 서정·극사실·톤 변주는 컷.
#   한국웹툰식 = 전 화풍 공통 토글(opts.kweb · 운영자 "모든 장르 선택 시 옵션") — 아래 KWEB_* 참조.
#   STYLE27 뉴스릴·NST-B 극화(13)·STYLE25 데포르메·STYLE29 과슈·STYLE18 유화·STYLE02 35mm·FM-01 표현주의(24)·STYLE10/11 애니·STYLE26 디오라마.
STYLE_SUB = {
    "photo": {"film": "shot on 35mm film, visible grain, subtle lens vignette, slightly underexposed photojournalism look",
              "bw": "black-and-white press photograph, deep blacks, high-contrast documentary tone",
              "cinedoc": "cinematic documentary still, handheld immediacy, natural imperfect framing",
              "newsreel": "vintage newsreel archive footage look, desaturated tones, slight gate flicker, official documentary feel"},
    "webtoon": {"gekiga": "japanese gekiga-style dramatic manga, heavy expressive ink, dense cross-hatching and hatched shadows, weathered realistic faces, cinematic panel staging, grave heavy atmosphere",
                "hardboiled": "hardboiled assassin-thriller gekiga, cold cinematic framing, chiseled stoic faces, precise mechanical detail, ruthless noir tension",
                "jidai": "samurai-era period gekiga, dynamic sumi-brush strokes, weathered costumes and textures, kinetic swordplay staging",
                "sunjung": "korean sunjung-manhwa delicate style, fine graceful pen lines, luminous emotive eyes, soft floral tones and airy screentone accents",
                "chibi": "cheerful deformed cartoon, chibi proportions with oversized heads and expressive hands, exaggerated comic expressions, clean bright colors"},
    "cartoon": {"brush": "loose brush-inked daily newspaper cartoon, quick confident strokes",
                "flat": "flat modern editorial cartoon, clean shapes, minimal shading",
                "woodcut": "bold woodcut print satire, carved black linework, coarse paper grain, two-tone ink feel"},
    "watercolor": {"bleed": "loose wet-on-wet washes, heavy pigment blooms and bleeding edges",
                   "fine": "fine controlled watercolor, delicate detailed brushwork, crisp edges",
                   "sumuk": "korean ink-wash (sumuk) painting with sparse watercolor accents, generous white space",
                   "gouache": "opaque gouache illustration, flat matte color fields, visible chalky brushwork, soft layered edges",
                   "oil": "classical oil painting, thick impasto brushwork, layered glazing, museum-canvas texture"},
    "cinematic": {"noir": "film-noir mood, hard shadows, venetian-blind light patterns",
                  "neon": "neon-lit night palette, wet reflective streets, cyan-magenta glow",
                  "film35": "shot on cinematic 35mm film stock, organic grain, halation on highlights, anamorphic bokeh",
                  "expressionism": "german expressionist staging, distorted angular set geometry, painted elongated shadows, high-contrast chiaroscuro"},
    "illust": {"riso": "risograph print texture, limited spot-color palette, visible grain",
               "paper": "cut-paper collage layers, tactile edges, flat color planes",
               "anime": "anime key visual artwork, clean lineart, vibrant colors, detailed painted background",
               "retro80": "retro 1980s cel anime look, airbrushed gradients, halation glow, vintage color palette"},
    "iso3d": {"clay": "soft matte clay materials, rounded edges, pastel palette",
              "lowpoly": "stylized low-poly geometry, faceted surfaces",
              "diorama": "miniature diorama tilt-shift look, shallow toy-like depth, handcrafted model textures"},
    "pictogram": {"line": "thin-line iconography, outline style, minimal fills",
                  "blueprint": "technical blueprint diagram style, precise white line iconography on deep drafting-blue field"},
}


def load_opts():
    try:
        o = json.loads(os.environ.get("GENIMG_OPTS", "{}") or "{}")
    except Exception:
        o = {}
    if not isinstance(o, dict):
        o = {}
    style = o.get("style") if o.get("style") in STYLE_FRAG else "photo"
    aspect = o.get("aspect") if _parse_aspect(o.get("aspect")) else "4:5"   # 자유 N:N(운영자 260710) — genimg.js와 동일 정규식 계약
    _aw, _ah = _parse_aspect(aspect)
    _ag = math.gcd(_aw, _ah)
    aspect = "{}:{}".format(_aw // _ag, _ah // _ag)   # gcd 축약 정규화(2:4→1:2 · 4:6→2:3) — 프롬프트 표기 정돈 + 네이티브 적중률↑(6인 검증 P3)
    size = {"1K": "FHD"}.get(o.get("size"), o.get("size"))                  # 레거시 '1K'(구 클라이언트) = FHD로 수렴
    if size not in SIZE_RENDER:
        size = "FHD"                                                        # 기본 = FHD(운영자 260710)
    fmt = "jpg" if o.get("fmt") == "jpg" else "png"                         # 품질 = PNG(기본) / JPG q90
    mood = o.get("mood")
    mood_ax = {k: 0 for k in MOOD_AX}
    if mood == "axes":                                                      # 무드 게이지(운영자 260710) — 레거시 프리셋 문자열도 계속 수용
        src = o.get("moodAx") if isinstance(o.get("moodAx"), dict) else {}
        for k in mood_ax:
            try:
                mood_ax[k] = max(-2, min(2, int(src.get(k, 0))))
            except Exception:
                mood_ax[k] = 0
        if not any(mood_ax.values()):
            mood = "auto"                                                   # 전축 0 = 자동과 동치
    elif mood not in MOOD_FRAG:
        mood = "auto"
    font = o.get("font") if o.get("font") in FONT_FRAG else "gothic"
    try:
        count = max(1, min(4, int(o.get("count", 1))))
    except Exception:
        count = 1
    text = re.sub(r"\s+", " ", str(o.get("text", "") or "")).strip()[:60]   # 레거시 명시 문구(구 클라이언트) — 신 UI = textOn 토글(문구는 Opus가 주문에서 정함)
    wish = re.sub(r"\s+", " ", str(o.get("wish", "") or "")).strip()[:300]
    sub = o.get("sub") if o.get("sub") in STYLE_SUB.get(style, {}) else "auto"
    shot = o.get("shot") if o.get("shot") in SHOT_CODES else "auto"
    expr = o.get("expr") if o.get("expr") in EXPR_CODES else "auto"
    angle = o.get("angle") if o.get("angle") in ANGLE_CODES else "auto"
    point = o.get("point") if o.get("point") in POINT_CODES else "auto"
    light = o.get("light") if o.get("light") in LIGHT_CODES else "auto"
    place = o.get("place") if o.get("place") in PLACE_FRAG else "auto"
    return {"style": style, "aspect": aspect, "size": size, "count": count, "fmt": fmt,
            "mood": mood, "mood_ax": mood_ax, "font": font, "text": text,
            "texton": o.get("textOn") is True, "wish": wish,
            "sub": sub, "angle": angle, "point": point, "light": light, "place": place,
            "shot": shot, "expr": expr, "kweb": bool(o.get("kweb"))}




def lib_keywords(o):
    """선택된 라이브러리 코드(shot/angle/point/light/expr) → tg.lib_buckets 해석(camera/focus/light/expression 버킷).
    shot(S)·angle(AG)은 같은 camera 버킷에 ", " 병합(260707 실측)."""
    codes = [o[k] for k in ("shot", "angle", "point", "light", "expr") if o.get(k) and o[k] != "auto"]
    try:
        return tg.lib_buckets(" ".join(codes)) if codes else {}
    except Exception as e:  # noqa: BLE001 — 라이브러리 파일 부재 등 = 코드 드롭(fail-soft)
        print("::warning::lib_buckets 실패(코드 드롭): {}".format(e), flush=True)
        return {}


def style_look(o):
    """화풍 look = 기본 STYLE_FRAG + 서브 분기 병기 + 한국웹툰식 토글(전 화풍 · 극화는 NST-B 전문 승격)."""
    frag = STYLE_FRAG[o["style"]]
    sub = STYLE_SUB.get(o["style"], {}).get(o.get("sub", ""), "")
    look = frag + (", " + sub if sub else "")
    if o.get("kweb"):
        look = (KWEB_FULL + (", " + sub if sub else "")) if o["style"] == "webtoon" else (look + ", " + KWEB_MIX)
    return look



def post_process(png, o):
    """렌더 후처리(운영자 260710 개요 개편) — 커스텀 비율 정확 크롭(중앙) + 목표 짧은변 스냅(SIZE_SHORT) + 포맷 인코딩(PNG/JPG q90).
    PIL 부재·오류 = 원본 PNG 그대로(fail-soft — 기능이 절대 안 죽게 · imggen.yml pillow 스텝도 continue-on-error)."""
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(png))
        im.load()
        w, h = _parse_aspect(o["aspect"]) or (4, 5)
        tr = w / h
        W, H = im.size
        if W and H and abs(W / H - tr) > 0.005:   # 렌더비(근접 네이티브) ≠ 요청비 = 중앙 크롭으로 정확 비율
            if W / H > tr:
                nw = max(1, round(H * tr)); x = (W - nw) // 2; im = im.crop((x, 0, x + nw, H))
            else:
                nh = max(1, round(W / tr)); y = (H - nh) // 2; im = im.crop((0, y, W, y + nh))
        tgt = SIZE_SHORT[o["size"]]
        short = min(im.size)
        if short and short != tgt:   # FHD = 1K 렌더 → 1080 보간(≈1.2× LANCZOS · 과금 현행 동일) · 720p = 다운스케일
            sc = tgt / short
            im = im.resize((max(1, round(im.size[0] * sc)), max(1, round(im.size[1] * sc))), Image.LANCZOS)
        buf = io.BytesIO()
        if o["fmt"] == "jpg":
            im.convert("RGB").save(buf, "JPEG", quality=90, optimize=True, subsampling=0)   # 4:4:4 — 문구 번인(textOn) 크로마 번짐 방지(전 JPEG 저장 경로 통일 · 260710)
            return buf.getvalue(), "jpg"
        im.save(buf, "PNG", optimize=True)
        return buf.getvalue(), "png"
    except Exception as e:  # noqa: BLE001
        print("::warning::후처리 실패(원본 PNG 유지): {}: {}".format(type(e).__name__, e), flush=True)
        return png, "png"


def build_fallback(head, lead, scene, o):
    """Claude 실패 시 결정형 프롬프트(썸네일 정본 골격 계승) — 기능이 절대 안 죽게.
    문구(TEXT)는 프롬프트 앞쪽 + 큰따옴표 리터럴(모델이 '해석'이 아닌 '렌더 대상'으로 취급 — 아이데이션 분신술 260707)."""
    likeness = o["style"] in LIKENESS_STYLES or o.get("kweb")   # 웹툰화 = 일러스트 계열 닮음 정책 승계
    parts = [tg.GOVERNING]
    if o["text"]:
        parts.append('TEXT (render these Korean characters EXACTLY, letter-for-letter; do not translate or restyle '
                     'the wording): "' + o["text"] + '" — the ONLY legible text in the image, one large line, '
                     + FONT_FRAG[o["font"]] + ", every hangul syllable block complete and correctly formed, "
                     "high contrast, kept clear of faces; no other text anywhere.")
    parts.append("STYLE: " + style_look(o))
    parts.append("SCENE: " + (scene or (head + (" — " + lead if lead else ""))))
    kw = lib_keywords(o)
    if kw.get("camera"):
        parts.append("CAMERA: " + kw["camera"])
    if kw.get("focus"):
        parts.append("FOCUS (distance & crop of the key subject, adapt to the scene, "
                     "do not copy literal props): " + kw["focus"])
    if kw.get("light"):
        parts.append("LIGHT: " + kw["light"])
    if kw.get("expression"):
        parts.append("EXPRESSION (of the protagonist, adapt to the scene): " + kw["expression"])
    if PLACE_FRAG[o["place"]]:
        parts.append("COMPOSITION: " + PLACE_FRAG[o["place"]])
    parts.append(tg._frame(False, likeness).replace("vertical 4:5", aspect_en(o["aspect"])))
    if o["mood"] == "axes":
        _mfr, _ = mood_axes_frag(o["mood_ax"])
        if _mfr:
            parts.append("MOOD: " + _mfr)
    elif MOOD_FRAG[o["mood"]]:
        parts.append("MOOD: " + MOOD_FRAG[o["mood"]])
    if o["text"]:
        parts.append(tg._avoid(likeness).replace("overlay text, captions, "
                     "headlines or legible lettering (tiny blurred incidental signage only — readable Korean text "
                     "renders broken); ", "any text other than the specified Korean phrase; "))
    else:
        parts.append(tg._avoid(likeness))
    if o["wish"]:
        parts.append("OPERATOR NOTE (highest priority): " + o["wish"])
    return " ".join(parts)


def ask_opus(head, lead, insight, scene, o, free=False):
    """Opus 4.8(effort max)에게 옵션 반영 Gemini 프롬프트 작성 요청 — 실패·빈출력이면 None(→ 폴백).
    free = 자유 생성(기사 없음): [기사] 블록 대신 운영자 주문이 장면의 전부(260707)."""
    likeness = o["style"] in LIKENESS_STYLES or o.get("kweb")   # 웹툰화 토글 = 닮음 정책 승계
    person = ("일러스트 계열이므로 공인(정치인·유명인)은 실제 인상(이목구비·헤어·안경)을 닮게 지시하되, "
              "사인·피해자·미성년은 익명 일반 인물로." if likeness
              else "실사 계열이므로 모든 인물은 익명의 일반 얼굴(실존 인물 닮기 금지 — 딥페이크 인접).")
    text_rule = (('- 이미지 속 문구: 한글 "' + o["text"] + '" 를 이미지에 크고 정확하게 렌더하도록 지시하라. '
                  "이 한글 원문을 큰따옴표로 감싸 프롬프트 *앞쪽*에 리터럴로 인용하고(번역·리스타일 금지·letter-for-letter), "
                  "서체 무드 = " + FONT_KO[o["font"]] + '("' + FONT_FRAG[o["font"]] + '"), 한 줄 크게, 모든 한글 자모 완전한 형태, '
                  "고대비, 얼굴 안 가리게. 이 문구 외 다른 글자는 전부 금지.") if o["text"]
                 else ("- 이미지 속 문구 = 살리기 ON(운영자 토글): 주문(장면 설명)에서 이미지에 살릴 핵심 한글 문구를 네가 정해 TEXT 지시를 넣어라 — "
                       "장면 속 자연 요소(현수막·간판·피켓·화면 자막)로 녹여내되, 렌더가 흔들릴 것 같으면 그 정확한 한글 문구를 큰따옴표 리터럴로 "
                       "프롬프트 앞쪽에 명기하라(letter-for-letter·모든 자모 완전한 형태·고대비·얼굴 회피·2~8자 짧게). "
                       "그 문구 외 다른 글자는 전부 금지.") if o.get("texton")
                 else "- 이미지에 읽히는 글자·자막·헤드라인 절대 금지(한글은 깨져 렌더됨 — 흐릿한 배경 간판만 허용).")
    if o["mood"] == "axes":
        _mfr, _mko = mood_axes_frag(o["mood_ax"])
        mood_rule = '- 무드(운영자 게이지) = {} — 이 결을 MOOD 지시에 반드시 반영: "{}"'.format(_mko, _mfr)
    else:
        mood_rule = ("- 무드: 기사 감정에 맞게 스스로 정해 MOOD 지시를 넣어라." if o["mood"] == "auto"
                     else '- 무드 = {} — MOOD 지시 포함: "{}"'.format(MOOD_KO[o["mood"]], MOOD_FRAG[o["mood"]]))
    kw = lib_keywords(o)   # 운영자 선택 라이브러리 코드(앵글·포인트·조명) → 실키워드
    lib_lines = []
    if kw.get("camera"):
        lib_lines.append('- 카메라 앵글(라이브러리 정본) — CAMERA 지시에 반드시 포함: "{}"'.format(kw["camera"]))
    if kw.get("focus"):
        lib_lines.append('- 표현 포인트(거리·크롭 · 라이브러리 정본) — 장면에 맞게 번안해 포함(예시 소품 리터럴 복사 금지): "{}"'.format(kw["focus"]))
    if kw.get("light"):
        lib_lines.append('- 조명(라이브러리 정본) — LIGHT 지시에 포함: "{}"'.format(kw["light"]))
    if kw.get("expression"):
        lib_lines.append('- 주인공 표정(FACS 라이브러리 정본) — EXPRESSION 지시에 포함(장면에 맞게 번안): "{}"'.format(kw["expression"]))
    if PLACE_FRAG[o["place"]]:
        lib_lines.append('- 피사체 배치 — COMPOSITION 지시에 포함: "{}"'.format(PLACE_FRAG[o["place"]]))
    lib_rule = "\n".join(lib_lines)
    wish_rule = ("- 운영자 추가 주문(최우선 반영): " + o["wish"]) if o["wish"] else ""
    ctx = ("[주제 — 운영자 자유 주문(기사 없음 · 이 주문이 장면의 전부다 · 소재를 스스로 결정적 장면으로 구성)]\n"
           + (o["wish"] or "(주문 없음 — 아래 문구를 장면 소재로 삼아라)")
           + (('\n(이미지 속 렌더할 문구: "' + o["text"] + '")') if o["text"] else "")) if free else """[기사]
제목: {head}
한줄 요약: {lead}
시사점: {insight}
장면 제안(분석 시점 초안 — 더 좋은 결정적 장면이 있으면 재구성 가능): {scene}""".format(
        head=head, lead=lead or "(없음)", insight=insight or "(없음)", scene=scene or "(없음)")
    prompt = """너는 Gemini 이미지 생성 모델을 위한 프롬프트 엔지니어다. 아래 {src}와 운영자 옵션을 읽고,
뉴스 카드 배경용 이미지 생성 프롬프트 *영문 1개*를 작성하라.

{ctx}

[운영자 옵션 — 전부 프롬프트에 반영]
- 화풍 = {style_ko}. 이 스타일 지시를 반드시 포함: "{frag}"
- 화면비 = {aspect}({aspect_en}). 장면이 프레임 가장자리까지 가득 차게(full-bleed·빈 띠/레터박스 금지·단일 초점).
{mood_rule}
{lib_rule}
{text_rule}
{wish_rule}

[작성 규칙]
- {decisive} — 막연한 무드샷·스톡사진 포즈·카메라 보고 웃는 인물 금지.
- {person}
- 선정성·시신·유혈 클로즈업·미성년 위해 금지. 워터마크·로고 금지.
- {locale}
- 한글 무결성 지시는 긍정형 1회만(부정어 반복 강조 금지 — 부정 프라이밍 역효과).
- 출력 = 영문 프롬프트 본문만, 이 레포 검증 골격의 라벨 블록 구조로: GOVERNING → (문구 있으면 TEXT) → STYLE → SCENE → CAMERA → (포인트 있으면 FOCUS) → LIGHT → MOOD → (배치 있으면 COMPOSITION) → FRAME → AVOID. 각 라벨 한 줄씩. 설명·번호·마크다운·코드블록 금지.""".format(
        src=("운영자 자유 주문" if free else "한국 뉴스 기사"), ctx=ctx,
        decisive=("주문의 소재를 즉시 알아보게 하는 결정적 순간 하나" if free else "이 사건을 즉시 알아보게 하는 결정적 순간 하나"),
        locale=("주문에 지역·인물 맥락이 있으면 그대로, 없으면 한국 기준." if free else "국내 사건이면 인물·배경은 한국(명백한 해외 사건이면 실제 지역·인물)."),
        style_ko=STYLE_KO[o["style"]], frag=style_look(o),
        aspect=o["aspect"], aspect_en=aspect_en(o["aspect"]),
        mood_rule=mood_rule, lib_rule=lib_rule, text_rule=text_rule, wish_rule=wish_rule, person=person)

    args = ["claude", "-p", "--model", MODEL, "--effort", "max",
            "--disallowedTools", "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Task",
            "--max-turns", "3"]
    # 렌더 키는 Claude 서브프로세스에 노출할 이유 0 — 호출 동안만 env서 제거(moreimg unset과 동일 정신·복원)
    saved = {k: os.environ.pop(k, None) for k in ("GEMINI_API_KEY", "GDRIVE_SA_JSON")}
    try:
        p, rc, err = run_claude(args, prompt, timeout=600, source="genimg")
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
    if not p or rc != 0 or not (p.stdout or "").strip():
        print("::warning::Opus 프롬프트 작성 실패(rc={}) — 결정형 폴백 프롬프트로 진행: {}".format(
            rc, (err or "")[:200]), flush=True)
        return None
    out = p.stdout.strip()
    out = re.sub(r"^```[a-z]*\s*|\s*```$", "", out).strip()          # 코드펜스 방어
    out = re.sub(r"[ \t]+", " ", out.replace("\r", "")).strip().strip('"').strip()   # 라벨 블록 개행 보존(레포 검증 골격) · 공백만 정규화
    if len(out) < 60:   # 사실상 빈 응답/거절문 방어
        print("::warning::Opus 출력이 너무 짧음({}자) — 폴백 프롬프트로 진행".format(len(out)), flush=True)
        return None
    return out[:2400]


def main():
    free = os.environ.get("GENIMG_FREE", "").strip() == "1"   # 자유 생성(도구 /6 생성 탭 · 운영자 260707)
    stem = os.environ.get("GENIMG_STEM", "").strip()
    o = load_opts()
    if free:
        stem = "free"
        if not (o["wish"] or o["text"]):
            die("자유 생성 = 주문(wish) 또는 문구(text) 필수 — 장면 소재 0")
        head = lead = iq = scene = insight = ""
    else:
        if not stem or not re.match(r"^[A-Za-z0-9._-]+$", stem) or ".." in stem:
            die("GENIMG_STEM 누락/부적격: {!r}".format(stem))
        mdpath = os.path.join("queue", stem + ".md")
        if not os.path.exists(mdpath):
            die("기사 md 없음: " + mdpath)
        head, lead, iq, scene, _url, _alts, _srcs, _dispatch, extras = tg.parse_md(mdpath)
        if not head:
            die("헤드라인 파싱 실패: " + stem)
        insight = (extras or {}).get("insight", "")

    print("🎨 이미지 생성 — '{}' · 화풍={} 비율={} 해상도={} 장수={} 포맷={}{}{}".format(
        ("자유: " + (o["wish"] or o["text"]))[:40] if free else head[:40], STYLE_KO[o["style"]], o["aspect"], o["size"], o["count"],
        o["fmt"].upper(), " · 문구=" + (o["text"] or ("살리기 ON" if o["texton"] else "")) if (o["text"] or o["texton"]) else "",
        " · 주문=" + o["wish"][:40] if o["wish"] else ""), flush=True)

    if not tg.KEY:
        die("GEMINI_API_KEY 없음 — 렌더 불가(워크플로 시크릿 확인)")

    try:
        prompt = ask_opus(head, lead, insight, scene or iq, o, free=free)
    except Exception as e:  # noqa: BLE001 — Opus 경로의 *코드 예외*까지 폴백이 받는다(카나리아1 KeyError 실측 = 기능 무중단 보증)
        print("::warning::ask_opus 예외 — 결정형 폴백으로 진행: {}: {}".format(type(e).__name__, e), flush=True)
        prompt = None
    fb_scene = (o["wish"] or o["text"]) if free else (scene or iq)   # 자유 모드 폴백 SCENE = 주문/문구(기사 없음 = head 폴백 불가)
    if not prompt and o["texton"] and not o["text"]:
        print("::warning::문구 살리기 ON이었으나 Opus 실패 → 결정형 폴백은 문구를 못 정해 무문구 렌더(재시도 시 문구 복원 · 평의회3)", flush=True)
    prompt = prompt or build_fallback(head, lead, fb_scene, o)
    print("── 최종 프롬프트({}자) ──\n{}\n──".format(len(prompt), prompt), flush=True)

    tdir = os.path.join("viewer", "gen_out") if free else os.path.join("cards", stem, "thumbs")
    os.makedirs(tdir, exist_ok=True)
    sjson = os.path.join(tdir, "free.json") if free else os.path.join(tdir, "search.json")
    existing = []
    if os.path.exists(sjson):
        try:
            existing = json.load(open(sjson, encoding="utf-8")) or []
        except Exception:
            existing = []

    h8 = hashlib.sha1((prompt + datetime.datetime.now(KST).isoformat()).encode("utf-8")).hexdigest()[:8]
    render_size = SIZE_RENDER[o["size"]]
    if (o["text"] or o["texton"]) and render_size == "1K":
        render_size = "2K"   # 문구 렌더 = 2K 플로어(1K는 한글 자모 뭉개짐 · 목표 px는 불변 = 다운스케일이 글자를 오히려 조여줌)
    render_aspect = o["aspect"] if o["aspect"] in NATIVE_ASPECTS else nearest_native(o["aspect"])   # 커스텀 N:N = 근접 네이티브 렌더 → post_process 정확 크롭
    new_items = []
    for i in range(o["count"]):
        png = tg.gemini_image(prompt, image_size=render_size, tag="genimg", aspect=render_aspect)
        if not png:
            print("::warning::{}번째 렌더 실패(fail-soft — 나머지 계속)".format(i + 1), flush=True)
            continue
        png, ext = post_process(png, o)   # 정확 비율·목표 px·포맷(운영자 260710)
        url = None
        if tg.R2_ON:
            url = tg.r2_upload(png, ("genfree/{}-{}.{}" if free else "thumbs/" + stem + "/genimg-{}-{}.{}").format(h8, i + 1, ext),
                               content_type="image/jpeg" if ext == "jpg" else "image/png")   # ext↔메타 정합(6인 검증 P2 — 미전달 = jpg인데 image/png · gen_cards/k_refgen 선례 계승)
        if not url:   # R2 미설정/실패 = git 폴백(로컬 커밋 → 뷰어 상대경로 서빙·gen.json 폴백과 동일 방식)
            fname = "genimg-{}-{}.{}".format(h8, i + 1, ext)
            with open(os.path.join(tdir, fname), "wb") as f:
                f.write(png)
            url = ("gen_out/" + fname) if free else "cards/{}/thumbs/{}".format(stem, fname)
            print("  ⚠️ R2 불가 — git 폴백 저장: " + url, flush=True)
        it = {"url": url, "link": "", "label": "생성", "style": o["style"], "prompt": prompt[:1500]}
        if free:
            it["ts"] = datetime.datetime.now(KST).isoformat(timespec="seconds")   # /6 그리드 표시·정렬용(§📐 KST)
        new_items.append(it)
        print("  ✅ {}/{} → {}".format(i + 1, o["count"], url), flush=True)

    if not new_items:
        die("렌더 전건 실패 — 생성 이미지 0")
    merged = (new_items + existing)[:24] if free else (new_items + existing)   # 자유 목록 = 캡 24(최근만 · 비대 방지)
    json.dump(merged, open(sjson, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if free:   # 유실 봉합(260707 실측 사고): push 경합 재시도의 pull --rebase -X ours = 리베이스에선 원격 승 →
        #   단일 파일 free.json의 내 항목이 조용히 드랍(렌더·R2는 무사·목록만 증발). 신규 항목을 임시본에 남겨
        #   커밋 스텝이 매 재시도마다 재병합(prepend·URL 중복 제거·캡 24)하게 한다 — 워크플로 재병합 블록과 한 쌍.
        json.dump(new_items, open("/tmp/genimg_new.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("✅ +{}장(생성) → {} 총 {}장".format(len(new_items), sjson, len(new_items) + len(existing)), flush=True)


if __name__ == "__main__":
    main()
