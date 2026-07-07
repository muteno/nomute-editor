#!/usr/bin/env python3
"""뷰어 '이미지 생성'(검색 카러셀 + 버튼 팝업) — 버튼으로 고른 옵션(화풍·비율·해상도·장수·문구·주문)과
기사 요약·시사점을 Claude(Opus 4.8·effort max·구독 OAuth)가 읽고 Gemini 이미지 프롬프트 *영문 1개*를 작성
→ Gemini(thumb_gen.gemini_image·종량제 GEMINI_API_KEY)가 렌더 → R2 업로드 →
cards/<stem>/thumbs/search.json **앞쪽** prepend(label '생성') → 뷰어 카러셀 자동 반영(articles.json 폴링).

운영 원칙(운영자 260707): 구독+종량제 병행 활용 — 프롬프트 지능=구독 Opus·렌더=종량제 Gemini.
- Claude 호출 = 폴오버 SSOT(shared/claude_py.run_claude · 쿼터 시 4계정 체인 자동 전환 · §📰).
- Claude가 완전 실패해도 결정형 폴백 프롬프트로 렌더 강행(fail-soft — '생성' 버튼은 항상 결과를 내려 노력).
- 카드 제미나이 0 불변과 무관: 이 경로는 뷰어 수동 발사(슛과 동일 정책·자동 파이프라인 아님).
입력: env GENIMG_STEM(기사 file 베이스) · GENIMG_OPTS(JSON: style/aspect/size/count/text/wish).
자유 생성(GENIMG_FREE=1 · 운영자 260707 "이미지 제작 세부메뉴 4번"): 기사 없음 — 운영자 주문(wish)/문구(text)가 장면의 전부.
  산출 = viewer/gen_out/free.json prepend(캡 24) · R2 키 genfree/ · 뷰어 이미지 제작 도구 /6 생성 탭 그리드가 폴링.
"""
import datetime
import hashlib
import json
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
ASPECTS = ("4:5", "1:1", "3:4", "9:16", "16:9")
SIZES = ("1K", "2K", "4K")
ASPECT_EN = {"4:5": "vertical 4:5 portrait", "1:1": "square 1:1", "3:4": "vertical 3:4 portrait",
             "9:16": "tall vertical 9:16 story format", "16:9": "wide horizontal 16:9"}
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
MOOD_KO = {"auto": "자동", "tense": "긴장", "somber": "침통", "hope": "희망", "calm": "차분"}
MOOD_FRAG = {"auto": "", "tense": "tense, high-stakes urgency", "somber": "somber, grave, mournful stillness",
             "hope": "hopeful, a resolving light breaking through", "calm": "calm, composed, analytical stillness"}
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
# 배치 = 카드뉴스 프롬프팅 정본 계승(apps/news/02 §합성 "main subject anchored in the upper-center" · 라우터 "핵심요소 상단 2/3")
PLACE_FRAG = {"auto": "",
              "top23": ("the main subject anchored in the upper two-thirds of the frame (upper-center), "
                        "the lower zone kept visually calm and uncluttered so a caption can sit over it"),
              "center": "the main subject centered with balanced, symmetrical visual weight",
              "full": "full-figure staging — the protagonist visible head to toe within the scene"}
# 화풍 서브 분기(운영자 260707 "수채도 여러 수채") — STYLE_FRAG에 병기되는 변주 look. 'auto' = 기본 look만.
STYLE_SUB = {
    "photo": {"film": "shot on 35mm film, visible grain, subtle lens vignette, slightly underexposed photojournalism look",
              "bw": "black-and-white press photograph, deep blacks, high-contrast documentary tone",
              "cinedoc": "cinematic documentary still, handheld immediacy, natural imperfect framing"},
    "webtoon": {"noir": "stark noir inking, heavy chiaroscuro shadow shapes, minimal palette",
                "tone": "manga screentone shading, halftone dot texture, crisp line hierarchy",
                "color": "rich full-color webtoon rendering, soft digital gradient shading"},
    "cartoon": {"brush": "loose brush-inked daily newspaper cartoon, quick confident strokes",
                "flat": "flat modern editorial cartoon, clean shapes, minimal shading"},
    "watercolor": {"bleed": "loose wet-on-wet washes, heavy pigment blooms and bleeding edges",
                   "fine": "fine controlled watercolor, delicate detailed brushwork, crisp edges",
                   "sumuk": "korean ink-wash (sumuk) painting with sparse watercolor accents, generous white space"},
    "cinematic": {"noir": "film-noir mood, hard shadows, venetian-blind light patterns",
                  "neon": "neon-lit night palette, wet reflective streets, cyan-magenta glow"},
    "illust": {"riso": "risograph print texture, limited spot-color palette, visible grain",
               "paper": "cut-paper collage layers, tactile edges, flat color planes"},
    "iso3d": {"clay": "soft matte clay materials, rounded edges, pastel palette",
              "lowpoly": "stylized low-poly geometry, faceted surfaces"},
    "pictogram": {"line": "thin-line iconography, outline style, minimal fills"},
}


def load_opts():
    try:
        o = json.loads(os.environ.get("GENIMG_OPTS", "{}") or "{}")
    except Exception:
        o = {}
    if not isinstance(o, dict):
        o = {}
    style = o.get("style") if o.get("style") in STYLE_FRAG else "photo"
    aspect = o.get("aspect") if o.get("aspect") in ASPECTS else "4:5"
    size = o.get("size") if o.get("size") in SIZES else "1K"
    mood = o.get("mood") if o.get("mood") in MOOD_FRAG else "auto"
    font = o.get("font") if o.get("font") in FONT_FRAG else "gothic"
    try:
        count = max(1, min(4, int(o.get("count", 1))))
    except Exception:
        count = 1
    text = re.sub(r"\s+", " ", str(o.get("text", "") or "")).strip()[:60]
    wish = re.sub(r"\s+", " ", str(o.get("wish", "") or "")).strip()[:300]
    if text and size == "1K":
        size = "2K"   # 문구 렌더 = 2K 하한(1K는 한글 자모 뭉개짐 — 공식 팁·아이데이션 분신술 260707 · UI도 1K 딤이지만 서버 이중 플로어)
    sub = o.get("sub") if o.get("sub") in STYLE_SUB.get(style, {}) else "auto"
    angle = o.get("angle") if o.get("angle") in ANGLE_CODES else "auto"
    point = o.get("point") if o.get("point") in POINT_CODES else "auto"
    light = o.get("light") if o.get("light") in LIGHT_CODES else "auto"
    place = o.get("place") if o.get("place") in PLACE_FRAG else "auto"
    return {"style": style, "aspect": aspect, "size": size, "count": count,
            "mood": mood, "font": font, "text": text, "wish": wish,
            "sub": sub, "angle": angle, "point": point, "light": light, "place": place}




def lib_keywords(o):
    """선택된 라이브러리 코드(angle/point/light) → tg.lib_buckets 해석(camera/focus/light 키워드 dict)."""
    codes = [o[k] for k in ("angle", "point", "light") if o.get(k) and o[k] != "auto"]
    try:
        return tg.lib_buckets(" ".join(codes)) if codes else {}
    except Exception as e:  # noqa: BLE001 — 라이브러리 파일 부재 등 = 코드 드롭(fail-soft)
        print("::warning::lib_buckets 실패(코드 드롭): {}".format(e), flush=True)
        return {}


def style_look(o):
    """화풍 look = 기본 STYLE_FRAG + 서브 분기 병기."""
    frag = STYLE_FRAG[o["style"]]
    sub = STYLE_SUB.get(o["style"], {}).get(o.get("sub", ""), "")
    return frag + (", " + sub if sub else "")



def build_fallback(head, lead, scene, o):
    """Claude 실패 시 결정형 프롬프트(썸네일 정본 골격 계승) — 기능이 절대 안 죽게.
    문구(TEXT)는 프롬프트 앞쪽 + 큰따옴표 리터럴(모델이 '해석'이 아닌 '렌더 대상'으로 취급 — 아이데이션 분신술 260707)."""
    likeness = o["style"] in LIKENESS_STYLES
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
    if PLACE_FRAG[o["place"]]:
        parts.append("COMPOSITION: " + PLACE_FRAG[o["place"]])
    parts.append(tg._frame(False, likeness).replace("vertical 4:5", ASPECT_EN[o["aspect"]]))
    if MOOD_FRAG[o["mood"]]:
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
    likeness = o["style"] in LIKENESS_STYLES
    person = ("일러스트 계열이므로 공인(정치인·유명인)은 실제 인상(이목구비·헤어·안경)을 닮게 지시하되, "
              "사인·피해자·미성년은 익명 일반 인물로." if likeness
              else "실사 계열이므로 모든 인물은 익명의 일반 얼굴(실존 인물 닮기 금지 — 딥페이크 인접).")
    text_rule = (('- 이미지 속 문구: 한글 "' + o["text"] + '" 를 이미지에 크고 정확하게 렌더하도록 지시하라. '
                  "이 한글 원문을 큰따옴표로 감싸 프롬프트 *앞쪽*에 리터럴로 인용하고(번역·리스타일 금지·letter-for-letter), "
                  "서체 무드 = " + FONT_KO[o["font"]] + '("' + FONT_FRAG[o["font"]] + '"), 한 줄 크게, 모든 한글 자모 완전한 형태, '
                  "고대비, 얼굴 안 가리게. 이 문구 외 다른 글자는 전부 금지.") if o["text"]
                 else "- 이미지에 읽히는 글자·자막·헤드라인 절대 금지(한글은 깨져 렌더됨 — 흐릿한 배경 간판만 허용).")
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
        aspect=o["aspect"], aspect_en=ASPECT_EN[o["aspect"]],
        mood_rule=mood_rule, lib_rule=lib_rule, text_rule=text_rule, wish_rule=wish_rule, person=person)

    args = ["claude", "-p", "--model", MODEL, "--effort", "max",
            "--disallowedTools", "Bash,Edit,Write,MultiEdit,NotebookEdit,WebFetch,WebSearch,Task",
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

    print("🎨 이미지 생성 — '{}' · 화풍={} 비율={} 해상도={} 장수={}{}{}".format(
        ("자유: " + (o["wish"] or o["text"]))[:40] if free else head[:40], STYLE_KO[o["style"]], o["aspect"], o["size"], o["count"],
        " · 문구=" + o["text"] if o["text"] else "", " · 주문=" + o["wish"][:40] if o["wish"] else ""), flush=True)

    if not tg.KEY:
        die("GEMINI_API_KEY 없음 — 렌더 불가(워크플로 시크릿 확인)")

    try:
        prompt = ask_opus(head, lead, insight, scene or iq, o, free=free)
    except Exception as e:  # noqa: BLE001 — Opus 경로의 *코드 예외*까지 폴백이 받는다(카나리아1 KeyError 실측 = 기능 무중단 보증)
        print("::warning::ask_opus 예외 — 결정형 폴백으로 진행: {}: {}".format(type(e).__name__, e), flush=True)
        prompt = None
    fb_scene = (o["wish"] or o["text"]) if free else (scene or iq)   # 자유 모드 폴백 SCENE = 주문/문구(기사 없음 = head 폴백 불가)
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
    new_items = []
    for i in range(o["count"]):
        png = tg.gemini_image(prompt, image_size=o["size"], tag="genimg", aspect=o["aspect"])
        if not png:
            print("::warning::{}번째 렌더 실패(fail-soft — 나머지 계속)".format(i + 1), flush=True)
            continue
        url = None
        if tg.R2_ON:
            url = tg.r2_upload(png, ("genfree/{}-{}.png" if free else "thumbs/" + stem + "/genimg-{}-{}.png").format(h8, i + 1))
        if not url:   # R2 미설정/실패 = git 폴백(로컬 커밋 → 뷰어 상대경로 서빙·gen.json 폴백과 동일 방식)
            fname = "genimg-{}-{}.png".format(h8, i + 1)
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
    print("✅ +{}장(생성) → {} 총 {}장".format(len(new_items), sjson, len(new_items) + len(existing)), flush=True)


if __name__ == "__main__":
    main()
