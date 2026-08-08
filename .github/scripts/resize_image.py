#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이미지 비율 재구성(리사이즈) v1 — 구성 보존 확장 (운영자 260708 v1 착수 · v0 5라운드 검증 척추)

3층 라우팅(비용·품질 최적 — docs/reports/260707_나노바나나_비율재구성_제안.html §2):
  1층 solid_pad  = 가장자리 단색·저분산 → PIL 가장자리색 패딩(과금 0·즉시)
  2층 gemini     = 복잡 배경 → 패드필 1콜(P_PADFILL: 방향 동적·심도 유지·톤 일치 = v0 r2·r4 실측 룰)
                   + 픽셀락(원본 재부착·기본 ON — 문구·얼굴 100% 보장)
  폴백 blur_pad  = 렌더 실패·검증 미달 → 원본 블러 확대 배경(과금 0·항상 성공)

입력(env): RESIZE_ID · RESIZE_SRC(uploads/<id>/src.ext) · RESIZE_OPTS(JSON {aspect,size,lock,fill})
  fill(운영자 260803 "편집탭까지 하자" — 3층을 사용자 선택지로): auto=종전 edge_std 라우팅(기본·무변) ·
  solid=단색 패드 강제 · blur=블러 확대 강제 · ai=Gemini 아웃페인팅 강제(실패 시 blur 폴백 종전 그대로)
산출: R2 resize/<id>/… (미설정 시 git viewer/gen_out/) → viewer/gen_out/resize.json prepend(캡 24)
      + /tmp/resize_new.json(race-heal · imggen 계승)
불변: workflow_dispatch 전용 = 유료 Gemini 수동 발사만(§📰) · 자동 파이프라인 무접촉 · KST(§📐).
"""
import datetime
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # gemini_image·r2_upload·R2_ON 재사용(단일 렌더 진입점)

from PIL import Image, ImageFilter, ImageOps
import numpy as np

KST = datetime.timezone(datetime.timedelta(hours=9))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

ASPECTS = ("16:9", "9:16", "4:5", "1:1", "21:9")   # 프리셋(21:9 = 260713 · 구 이력 재발사 호환) · api/resize ASPECTS와 한 쌍 · Gemini 실패 시 3층 라우팅 폴백(blur_pad)이 결정론 커버


def custom_aspect_ok(a):   # 직접 비율 N:N(운영자 260718 "AI 생성 비율 따라가기" — genidlg 직접 계약 미러): 각 1~99 정수 + 비율 1:4~4:1 · pad_canvas는 W:H 일반 파싱이라 검증만 완화
    m = re.fullmatch(r"([1-9][0-9]?):([1-9][0-9]?)", str(a or ""))
    if not m:
        return False
    r = int(m.group(1)) / int(m.group(2))
    return 0.25 <= r <= 4
SIZES = ("1K", "2K")
FILLS = ("auto", "solid", "blur", "ai")   # 채움 오버라이드(운영자 260803) — api/resize FILLS와 한 쌍 · auto = 종전 자동 라우팅
SEED_ON = os.environ.get("RESIZE_SEED", "1") != "0"   # 씨앗 다듬기 모드(260806 기본 ON · RESIZE_SEED=0 = 구 회색 빈칸 방식으로 즉시 원복)
EDGE_SOLID_STD = 6.0   # 가장자리 픽셀 표준편차 임계 — 이하 = 단색/그라데(PIL 공짜 경로)
IMG_MODEL = os.environ.get("RESIZE_IMG_MODEL", "").strip()   # 이미지 모델 오버라이드(260808 · 빈값 = thumb_gen MODEL 정본 = 종전 동작 바이트 동일)
#   ⚠ 신설 사유 = 260808 실사고까지 이 파이프는 **Flash Image 한 종만** 써봤다(원장 24건 전건). 운영자
#     260808 «3.1 pro를 쓰든 3.1 flash를 쓰든 다 테스트해서 최대한 자연스럽게» — 비교하려면 씨앗·프롬프트·
#     판정을 고정한 채 모델만 갈아끼우는 축이 있어야 하는데, API가 모듈 상수라 실험 축 자체가 없었다.
JUDGE_MODEL = os.environ.get("RESIZE_JUDGE_MODEL", "").strip()   # 판정 모델(빈값 = 생성과 같은 모델 = 종전)
_CALLS = {"gen": 0, "judge": 0}   # 회차 과금 실측(생성·판정 발사 수 · 성패 무관 = 실제 청구 단위)
STREAK_MAX = 0.50   # 여백 clamp 줄무늬 잔류 상한 — 초과 = 「모델 무동작」(260807 실측: 무동작 0.983 vs 정상 재작성 0.000 · JPEG 왕복 후에도 성립)

P_PADFILL = (
    "This is a mechanical uncrop / continuation task, NOT a creative one — you are revealing more "
    "of the SAME picture, not imagining a new one. Behave like a clone-and-heal tool. "
    "First, carefully analyze the attached image: identify the subject, their exact pose and "
    "orientation, the scene, the lighting direction, and the textures. Base everything you draw "
    "on what is actually visible in this specific image — not on generic assumptions. "
    "This canvas contains an original photo {place}, with flat neutral gray areas "
    "{where}. Fill ONLY the gray areas by seamlessly extending the existing scene {dirhint} — "
    "never leave any gray visible. Source everything ONLY from what already touches the gray "
    "boundary: continue each line, edge, surface and texture outward at its existing angle, "
    "scale and rhythm, so every stroke in the fill is the continuation of a stroke that already "
    "exists. If the pixels adjacent to a gray area are plain or empty background (a solid color, "
    "a soft gradient, plain darkness), fill that gap with that same plain background and NOTHING "
    "else — do not invent stars, sparkles, light effects, body parts, limbs, reflections, or any "
    "object that does not already cross the boundary. "
    "Continue the background's lighting, perspective, textures, and "
    "grain across the boundary, and match the exact brightness and tone of the photo at the "
    "boundary so no edge or band is visible. Match the depth of field: if the pixels adjacent to "
    "a gray area are out of focus or blurred, the new content there must be equally out of focus — "
    "do not introduce new sharp objects, buildings, crowds, stands, or scenery that are not "
    "already visible in the photo. Keep every existing pixel of the original photo "
    "exactly unchanged. Do not add any new text, watermarks, logos, or people. The result must "
    "look like one single continuous photograph — as if the camera had simply captured a wider "
    "view of the exact same scene."
)   # v0 확정본(exp r5+r7 · 룰 삭제 금지: 선분석 r7·방향 동적 r2·심도 유지 r4·톤 일치) + 260806 「선 잇기」 절 증축(운영자
#   "뭘 만드는게 아니라 최대한 기존에 있던 선을 이어서 자연스러운 이미지 처럼만드는거" — 실측 대조: 폐허 일러스트 확장은
#   경계의 잔해·건물 선을 그대로 이어 성공[운영자 제출 성공례] · 마네킹 확장은 경계가 빈 배경인데 별·성운·팔을 **발명**해 실패
#   → ⓐ 과업 재정의 = uncrop(창작 아님·클론힐) ⓑ 소스 제한 = 경계에 닿은 것만 ⓒ 빈 배경 = 그 배경 그대로 + 발명 금지
#   목록{별·빛효과·신체}을 실패 모드 그대로 명문화 · 구 룰은 전문 보존 = 성공례 경로 회귀 0)


P_SEEDFILL = (
    # ⓞ 두 장을 준다 = 「진짜 사진」이 그림 증거로 들어간다(개수·정체를 말로 주장하지 않고 보여준다)
    "You are given two pictures. Picture 1 is the REAL PHOTOGRAPH and is the only source of truth for "
    "what exists in this scene: every subject in your output must come from Picture 1, and nothing "
    "absent from Picture 1 may appear. Picture 2 is that same photograph placed on a larger canvas, "
    "and it is the canvas you must repair. "
    # ① 캔버스 실측 서술 — 대명사 없이 %로 지목(구판 "extended above and below **it**" = 선행사 없는 순환문)
    "In Picture 2 the real photograph occupies only {keep}. {where} — those bands are not photographed "
    "content at all: each was produced by taking the single last row or column of the real photograph "
    "and repeating it outward, so their colours and layout are already correct but the texture is "
    "smeared into one-pixel streaks. Your ONLY job is to rebuild real texture inside those bands so "
    "the whole frame reads as one single continuous photograph. "
    # ② 줄무늬 해석 고정 — 「줄무늬는 물체가 아니다」
    "Read every streak as EMPTY space still waiting to be filled, never as an object. A streak depicts "
    "nothing: it is one pixel repeated hundreds of times. A tall streak that happens to be skin-, hair- "
    "or suit-coloured is NOT a person, NOT a body and NOT a garment. "
    # ③ 개수 = 원본 대비 상대(절대수 금지 = 2명·0명 사진에서 거짓 지시가 된다)
    "Your output must contain exactly the same subjects as Picture 1 — the same people, the same number "
    "of people, the same faces, the same objects. Creating a second copy of anything that already exists "
    "is the single worst failure of this task: no second person, no second face, no second head, no "
    "second torso, no second pair of shoulders, no second collar or tie, nowhere in the frame. "
    # ④ 잘린 피사체의 정당한 연장 = 「한 몸」으로만(이 절이 없으면 몸이 허공에서 끊기는 새 실패가 난다)
    "If a person or object is cut off by the edge of the real photograph and its streak runs into a "
    "band, you may continue that ONE body outward so it stays a single, anatomically attached, "
    "correctly proportioned body that simply leaves the frame, with the background continuing around "
    "it. Continuing one body is correct; starting a second body is not. "
    # ⑤ 텍스처 재건 — ⚠ 구판의 "if it is fabric, more of that same fabric" 삭제(진범)
    "Work only inside the bands: keep each streak's colour and position, but rebuild its detail by "
    "continuing the neighbouring texture at the same scale, density, grain and focus. Background "
    "continues as background — a night skyline becomes more of that same skyline, a wall more of that "
    "same wall, out-of-focus bokeh more of that same bokeh. Never leave a smooth flat area where the "
    "neighbouring pixels have texture; but everything you add must be either background texture or the "
    "single continuation described above — never a new subject. {edgerule} "
    # ⑥ 종전 유지 절(회귀 0) — 「that is not already present」 꼬리절은 제거(유령을 면책하던 구멍)
    "Do NOT reimagine or replace the scene. Apart from background texture and that single continuation, "
    "do NOT add anything at all — no extra object, person, body part, star, light effect, furniture, "
    "wall, panel, text or watermark. Keep the composition and every colour region exactly where it is. "
    "Straighten lines and horizons so they run continuously across the joins, and even out brightness "
    "so no seam or band remains. Preserve the existing lighting direction, perspective, grain and depth "
    "of field — if the neighbouring pixels are out of focus, the repaired bands must be equally out of "
    "focus. Keep every pixel of the real photograph exactly unchanged. "
    "The result must look like the camera simply captured a wider view of the exact same scene."
)   # 씨앗 다듬기 프롬프트(260806 · 운영자 "firefly로 만들때 명령어 아예 입력안해도 자연스럽게 채우기는 잘하던데")
#   ⚠ 260807 평의회 개정 = **구판이 유령을 「금지 못한」 게 아니라 「주문했다」**. 진범 3문장:
#     ⓐ `if it is fabric, more of that same fabric.` — 하단 204px 밴드의 이웃 텍스처가 **정장**이라
#        「그 자리에 정장 천을 더 만들어라」가 된다. 204px에 정장 천을 이행하는 물리적 방법은 **또 한 사람**뿐.
#        (이 레포가 `check_thumb_prompt_sanity`로 이미 이름 붙인 병 = 한 프롬프트 안의 자기모순)
#     ⓑ `... that is not already present` 꼬리절 — 유령 몸통은 「이미 있는 것」(사람·정장)이라 금지 목록을
#        문자 그대로 **빠져나간다**. 실패 모드 이름이 `ghosting/duplication`인데 금지어에 second·copy가 0개였다.
#     ⓒ `Keep ... every colour region exactly where it is` — 204px 정장색 영역을 「올바른 것」으로 승인해
#        모델에게 남은 자유도가 「그 영역에 디테일 주기」뿐이 된다 = 몸통.
#     + `extended {where} ... it` = 선행사 없는 순환문이라 모델이 원본/밴드 경계를 문장으로 알 수 없었다.
#   슬롯 3개({keep}·{where}·{edgerule})는 `seed_dirs()`가 **실측 %**로 채운다(구 box_dirs는 P_PADFILL 전용 문법).
#   ⚠ P_PADFILL(회색 빈칸 → 채워라)과 **과업이 다르다**: 여기선 seed_pad가 이미 메꿔 놓았고 모델은 **결함 제거만** 한다.
#   실호출 근거(260806 앵커 3비율) = 회색 빈칸 방식의 실패 사유가 「seam + severe ghosting/duplication」(4:5 QA 2회 FAIL)이라
#   그 결함 이름을 그대로 과업으로 준다 = 모델이 「무엇을 그릴까」를 결정할 여지 자체를 없앤다.
#   ⚠ 260806 2차 개정 = 씨앗을 거울반사 → **clamp(가장자리 연장)** 로 바꾼 데 맞춰 문구 동기화(구 "mirroring"·"mirror-symmetry"는
#     거짓 서술 = 모델에게 없는 결함을 찾게 시킨다) + **「매끈한 면 금지」 절 추가**: 1차 실측에서 확장부가 「밋밋한 파란 면」으로
#     남는 실패가 났다(모델이 흐린 씨앗을 「원래 흐린 배경」으로 읽음) → 이웃에 텍스처가 있으면 확장부에도 같은 밀도의 텍스처를
#     요구하고, 「가구·벽·패널」을 발명 금지 목록에 명시(16:9 실측 = 없던 스튜디오 기둥·조명 발명).


def gemini_judge(png_bytes, ref_bytes=None, model=None):
    """생성 결과 자가 QA(exp r8 검증 이식 — 운영자 '검증하면서 뽑는 프롬프팅') — 같은 모델 TEXT 판정.
    (passed, reason) · 판정 콜 실패 = None(fail-soft·렌더는 살림).

    ⚠ 260807 평의회 4개 렌즈가 **독립적으로 같은 결론**에 도달한 봉합 — 구판은 **결과 1장만** 보냈다.
      그래서 「duplicated objects」는 **원리적으로 판정 불가능한 술어**였다: 원본에 사람이 몇이었는지
      모르는 심판에게 「복제됐나」를 물은 셈이다. 260806 9:16 유령이 QA를 **통과해서 출고된** 직접 원인이고,
      잡혔더라면 파이프는 설계대로 씨앗 폴백으로 내려가 **유령 대신 줄무늬**가 나갔다(안전망이 안 돈 게 아니라
      안전망에 눈이 없었다). 이식원 = `exp_resize_v0.gemini_judge`의 2이미지 분기(**신설 아님 · 사본**).
      추가 과금 = 입력 이미지 1장 ≈ $0.0006(생성 콜의 1/100).
    ⚠ 위양성 3겹이 실효 조건 = 언크롭은 **원래 더 보이는 게 정상**이라 그걸 결함으로 읽으면 게이트가
      성공본을 죽인다: ⓐ 프레이밍 면책을 FAIL 목록 **앞**에 선언 ⓑ 「이어진 한 몸」은 복제가 아님을 명문화
      ⓒ 개수는 **절대수가 아니라 원본 대비 상대**(원본이 2명이면 2명이 정답 · 0명·N명에서도 자동으로 옳다)."""
    import base64
    import urllib.request
    if ref_bytes:
        prompt = (
            "You are a strict photo QA judge. Image 1 is the ORIGINAL photograph. Image 2 is that same "
            "photograph after its frame was extended (uncropped) to a different aspect ratio.\n"
            "Answer in EXACTLY this format:\nVERDICT: PASS or FAIL\nREASON: <one short sentence>\n"
            "Image 2 legitimately shows MORE of the scene than Image 1 — a larger frame, more background, "
            "and more of a body or object that was cut off by the edge of Image 1. A different crop, a "
            "different framing and more visible background are all EXPECTED and are never failures.\n"
            "FAIL only if one of these is visible in Image 2:\n"
            "(a) DUPLICATED SUBJECT — a person, face, head, torso, pair of shoulders, limb, building or "
            "object that has NO counterpart in Image 1 and is spatially separate from the subjects of "
            "Image 1; that is, the number of distinct people, or of distinct main objects, is higher in "
            "Image 2 than in Image 1. A body that is simply continued from a body in Image 1 and stays "
            "attached to it is NOT a duplicate and must PASS. If Image 1 shows a crowd of more than six "
            "people, do not count them — in that case FAIL only if a clearly separate new figure appears "
            "in an area that was plain empty background in Image 1.\n"
            "(b) anatomically wrong human body, or unnatural body proportions (for example a torso "
            "stretched far longer than a real human torso).\n"
            "(c) duplicated text, watermarks, leftover flat gray areas, smeared one-pixel streaks left "
            "unrepaired, or an obvious visible seam or brightness band.\n"
            "(d) brand-new elements in the extended margins (stars, light effects, body parts, objects) "
            "that do not continue anything present in Image 1.\n"
            "Otherwise PASS. If you FAIL, REASON must say WHERE the defect is — for example "
            "\"a second torso appears in the lower left\".")
        parts = [{"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(ref_bytes).decode()}},
                 {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(png_bytes).decode()}},
                 {"text": prompt}]
    else:
        prompt = ("You are a strict photo QA judge. Answer in EXACTLY this format:\n"
                  "VERDICT: PASS or FAIL\nREASON: <one short sentence>\n"
                  "FAIL if any of these are visible: anatomically wrong human body, unnatural body proportions, "
                  "duplicated objects or duplicated text, watermarks, leftover flat gray areas, an obvious "
                  "visible seam or brightness band, or brand-new elements in the filled margins (stars, "
                  "light effects, body parts, objects) that do not continue anything present in the "
                  "original photo. Otherwise PASS.")
        parts = [{"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(png_bytes).decode()}},
                 {"text": prompt}]
    payload = {"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["TEXT"]}}
    _api = tg.API if not model else tg.API.replace("/models/" + tg.MODEL + ":", "/models/" + model + ":")
    req = urllib.request.Request(_api + "?key=" + tg.KEY, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.loads(r.read().decode())
        txt = "".join(p.get("text", "") for c in j.get("candidates", [])
                      for p in c.get("content", {}).get("parts", []))
        up = txt.upper()
        if "VERDICT" not in up:
            return None
        passed = "PASS" in up.split("REASON")[0]
        reason = (txt.split(":", 2)[-1].strip().splitlines()[0] if "REASON" in up else txt.strip())[:200]
        return passed, reason
    except Exception as e:  # noqa: BLE001
        print("  ⚠️ QA 판정 콜 실패(스킵): {}".format(e), flush=True)
        return None


MAX_CANVAS = 4096   # 캔버스 장변 상한 — 축소 배치(box.w가 작다)는 캔버스를 원본보다 크게 만든다(cw = W/box.w) → 메모리·Gemini 첨부 폭주 차단


def parse_box(opts):
    """운영자 지정 배치(운영자 260805 "축소하면 빈 공간이 생길 수 있는데 … 빈 공간을 채우는 기능") — 캔버스 대비 원본 자리 {x,y,w,h} 0~1.
    미지정·불량 = None = 종전 중앙 배치(pad_canvas) 그대로 = 편집 탭·구 이력 재발사 무접촉. api/resize.js 검증과 한 쌍(이중 검증)."""
    b = opts.get("box")
    if not isinstance(b, dict):
        return None
    try:
        x, y, w, h = (float(b[k]) for k in ("x", "y", "w", "h"))
    except Exception:  # noqa: BLE001
        return None
    if not (0.05 <= w <= 1.0 and 0.05 <= h <= 1.0):
        return None
    if x < -0.001 or y < -0.001 or x + w > 1.001 or y + h > 1.001:
        return None   # 캔버스 밖으로 새는 배치 = 원본이 잘린다 = 픽셀락(원본 100% 보존) 계약 위반
    return (max(0.0, x), max(0.0, y), w, h)


def place_canvas(img, ar, box, fill=(127, 127, 127)):
    """지정 배치로 캔버스에 앉힌다 — pad_canvas('중앙·한 변 꽉')의 일반형. (canvas, box_px, placed_src)
    캔버스 크기 = 원본이 box.w를 차지하도록 역산(원본 해상도 보존) · 치수 8배수 · 장변 MAX_CANVAS 캡."""
    W, H = img.size
    x, y, w, h = box
    aw, ah = (int(v) for v in ar.split(":"))
    cw = int(round(W / w / 8) * 8)
    ch = int(round(cw * ah / aw / 8) * 8)
    if max(cw, ch) > MAX_CANVAS:   # 캡 = 비율 유지 축소(배치 비율은 정규화값이라 불변)
        k = MAX_CANVAS / max(cw, ch)
        cw = max(8, int(round(cw * k / 8) * 8))
        ch = max(8, int(round(ch * k / 8) * 8))
    pw, ph = max(8, int(round(w * cw))), max(8, int(round(h * ch)))
    px, py = int(round(x * cw)), int(round(y * ch))
    px, py = max(0, min(px, cw - pw)), max(0, min(py, ch - ph))
    src = img if (pw, ph) == (W, H) else img.resize((pw, ph), Image.LANCZOS)
    canvas = Image.new("RGB", (cw, ch), fill)
    canvas.paste(src, (px, py))
    return canvas, (px, py, px + pw, py + ph), src


P_CENTER = "placed in the center"   # v0 확정 문구(대칭 배치 전용 · 아래 대칭 분기에서만 쓴다)
_EDGE_WHERE = {"top": "above it", "bottom": "below it", "left": "to its left", "right": "to its right"}
_EDGE_HINT = {"top": "upward (for example, extend a ceiling or sky upward)",
              "bottom": "downward (for example, extend a floor or ground downward)",
              "left": "to the left", "right": "to the right"}


def _join_en(parts):
    """영어 열거 — 'A' / 'A and B' / 'A, B and C'."""
    if len(parts) <= 1:
        return parts[0] if parts else ""
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def box_dirs(box_px, canvas_size):
    """여백이 실제로 생긴 **변**을 그대로 문구화 → (place, where, dirhint) = P_PADFILL 3슬롯.

    ⚠ 260806 봉합(운영자 "막 왜곡하거나 그러지않고 그냥 원래 변경된 크기였떤것 처럼 자연스럽게") — 구판은 프롬프트에
      「placed in the center」가 **고정 문자열**이고 방향도 상하만/좌우만/사방 **대칭 3형**뿐이었다. 그런데
      `place_canvas`는 운영자가 미리보기에서 끌어놓은 자리(box)에 사진을 앉히므로 **중앙이 아닐 수 있다** →
      사진을 위로 붙인 배치는 여백이 아래에만 있는데도 모델에게 「사진은 중앙에 있다 · 위와 아래로 확장하라」고
      말하게 된다(실측: box y=0 → `vert=True` 분기 = "above and below it"). 없는 여백을 채우라는 지시가
      곧 「원본을 밀어내고 새 장면을 그리는」 왜곡의 입구다 = 운영자가 물은 바로 그 축.
      → 4변을 각각 재서 **실제로 빈 변만** 말한다. 대칭(= 중앙 배치·pad_canvas 경로)일 때는 v0 확정 문구를
        **바이트 그대로** 반환하므로 검증된 경로의 프롬프트는 1글자도 안 바뀐다(회귀 0).
    """
    x0, y0, x1, y1 = box_px
    cw, ch = canvas_size
    top, bot = y0 > 1, ch - y1 > 1
    lft, rgt = x0 > 1, cw - x1 > 1
    sym_v, sym_h = (top and bot), (lft and rgt)
    if (sym_v and sym_h) or not (top or bot or lft or rgt):   # 사방 대칭 · 여백 0(도달 불가 방어) = 구판 문구 그대로
        return (P_CENTER, "on all sides around it",
                "outward in every direction (for example, extend a ceiling or sky "
                "upward, a floor or ground downward, and the scene sideways)")
    if sym_v and not (lft or rgt):
        return (P_CENTER, "above and below it",
                "upward and downward (for example, extend a ceiling or sky upward "
                "and a floor or ground downward)")
    if sym_h and not (top or bot):
        return (P_CENTER, "to its left and right", "to the left and to the right")
    # ── 비대칭 = 운영자가 사진을 한쪽으로 붙여 놓은 배치 ──
    gap = [e for e, on in (("top", top), ("bottom", bot), ("left", lft), ("right", rgt)) if on]
    flush = [e for e, on in (("top", top), ("bottom", bot), ("left", lft), ("right", rgt)) if not on]
    place = ("placed off-center, flush against the {} edge{} of the canvas"
             .format(_join_en(flush), "" if len(flush) == 1 else "s")) if flush else P_CENTER
    return (place, "only " + _join_en([_EDGE_WHERE[e] for e in gap]),
            _join_en([_EDGE_HINT[e] for e in gap]) + " ONLY — the other edges already reach the canvas border, "
            "so nothing there may be redrawn, shifted, or cropped")


RENDER_MP = {"1K": 1.0, "2K": 4.0}   # 렌더 티어 화소수(백만) — 「1K」·「2K」 이름의 정의값(창작 아님)


def pad_canvas(img, ar, fill=(127, 127, 127), size=None):
    """타겟 비율 캔버스에 원본 중앙 배치. (canvas, box) · 치수 8배수. (v0 검증 함수)

    ⚠ 260807 봉합(운영자 "기준거를 키우지말고 폭이 맞는 가로 세로가 있으면 축소시켜서") —
      구판은 캔버스에 **상한이 없었다**(`MAX_CANVAS` 캡은 `place_canvas`에만 있다). 세로 원본을 가로
      비율로 늘리면 캔버스가 원본보다 훨씬 커지는데(실측 1200×1800 → 16:9 = **3200×1800 = 5.76MP**),
      모델은 `size` 티어만큼만 그려 돌려준다(1K ≈ 1MP) → `pixel_lock`이 그 렌더를 캔버스로
      **LANCZOS 업스케일**한다 = **AI가 채운 여백만 2.4배 확대 = 흐릿함**. 원본 자리는 무손실로
      다시 붙으니 가운데만 선명하고 가장자리가 무른 그림이 나온다.
    수리 = 캔버스가 렌더 티어를 넘으면 **원본을 줄여서** 맞춘다(캔버스를 키우지 않는다 · 확대는 절대 안 한다).
      `k = min(1, sqrt(티어화소 / 캔버스화소))` — k≥1이면 무동작이라 **작은 원본은 종전과 바이트 동일**
      (실측: 앵커 365×241의 3비율 전건 무변 = 5세대 검증 회귀 0).
    """
    W, H = img.size
    aw, ah = (int(x) for x in ar.split(":"))

    def _canvas_wh(w, h):
        if aw / ah >= w / h:
            return int(round(h * aw / ah / 8) * 8), h
        return w, int(round(w * ah / aw / 8) * 8)

    cw, ch = _canvas_wh(W, H)
    cap = RENDER_MP.get(size or "", 0) * 1e6
    if cap and cw * ch > cap:
        k = (cap / (cw * ch)) ** 0.5          # 항상 <1 (확대 분기 없음)
        W, H = max(8, int(round(W * k))), max(8, int(round(H * k)))
        img = img.resize((W, H), Image.LANCZOS)
        cw, ch = _canvas_wh(W, H)
        print("캔버스 캡: {} 티어({:.0f}MP) 초과 → 원본 {}×{}로 축소 · 캔버스 {}×{}".format(
            size, cap / 1e6, W, H, cw, ch), flush=True)
    canvas = Image.new("RGB", (cw, ch), fill)
    x, y = (cw - W) // 2, (ch - H) // 2
    canvas.paste(img, (x, y))
    return canvas, (x, y, x + W, y + H), img


def pixel_lock(gen_png, canvas_size, src_img, box, seed_img=None, feather=16):
    """생성 결과 위 원본 재부착 — **원본 박스는 무손실**, 페더는 여백이 있는 변의 **바깥**으로만.

    ⚠ 260807 평의회 실측 봉합(확정 결함 · 유령과 무관하게 상시 발동하던 라이브 사고) —
      구판은 `mask`를 박스 **안쪽**으로 4변 무조건 램프했다. 그래서
        ⓐ `ramp[0]=0` = 박스 최외곽 1px이 **모델 출력 100%** → 원본 화소의 **38.3%가 alpha<1**
           (실측 = 순빨강 가짜 생성본 주입 후 원본 대조 · 변조 33,728/87,965 · **최대오차 254**)
        ⓑ **여백이 0인 밀착 변에도** 램프를 걸었다 — 섞을 여백이 없는데 원본만 양보한다.
      실물 피해 = 260806 16:9 「성공」본의 **원본 하단 12행이 크림색 가로 막대로 덮였다**
      (모델이 그린 데스크·자막바가 페더를 타고 원본 안으로 들어왔고 QA는 그걸 통과시켰다).
      파일 머리말 「픽셀락 = 문구·얼굴 100% 보장」은 그 상태에서 **거짓 서술**이었다.
    수리 = ① 박스 안 = 항상 원본 그대로(마지막에 무조건 덮는다 = 무손실 계약 복원 · 실측 변조 **0.0%**)
           ② 페더는 `gap_sides` 논리와 같은 술어로 **여백이 실재하는 변의 바깥**으로만 편다
              (붙이는 그림 = 씨앗 = 박스 안 원본 + 밖 연장이라 색이 이어진다 · 씨앗 없으면 하드 부착)
           ③ 감쇠 = smoothstep(C¹ 연속) — 선형 램프는 양 끝 기울기가 꺾여 마하 밴드가 보인다
           ④ feather 32→16 — 32는 **회색 빈칸 시대**의 톤 단차를 지우려 24→32로 키운 값이고,
              씨앗 시대엔 모델이 경계 색을 이어받으므로 근거가 사라졌다(밖으로만 펴므로 원본 손실은 어차피 0).
    """
    gen = (gen_png if isinstance(gen_png, Image.Image)
           else Image.open(io.BytesIO(gen_png)).convert("RGB"))
    if gen.size != canvas_size:   # 이미 같은 크기면 LANCZOS 공회전 금지(래더·재판정 경로에서 세대 손실 0)
        gen = gen.resize(canvas_size, Image.LANCZOS)
    x0, y0, x1, y1 = box
    cw, ch = canvas_size
    gap = {"left": x0 > 0, "right": x1 < cw, "top": y0 > 0, "bottom": y1 < ch}
    out = gen.copy()
    if seed_img is not None and any(gap.values()):
        fx = min(feather, x0 if gap["left"] else feather, cw - x1 if gap["right"] else feather)
        fy = min(feather, y0 if gap["top"] else feather, ch - y1 if gap["bottom"] else feather)
        fx, fy = max(0, int(fx)), max(0, int(fy))
        ex0, ey0 = x0 - (fx if gap["left"] else 0), y0 - (fy if gap["top"] else 0)
        ex1, ey1 = x1 + (fx if gap["right"] else 0), y1 + (fy if gap["bottom"] else 0)
        m = np.ones((ey1 - ey0, ex1 - ex0), dtype=np.float32)

        def _smooth(n):
            t = np.linspace(0.0, 1.0, n, dtype=np.float32)
            return t * t * (3 - 2 * t)

        if gap["left"] and fx:
            m[:, :fx] = np.minimum(m[:, :fx], _smooth(fx)[None, :])
        if gap["right"] and fx:
            m[:, -fx:] = np.minimum(m[:, -fx:], _smooth(fx)[::-1][None, :])
        if gap["top"] and fy:
            m[:fy, :] = np.minimum(m[:fy, :], _smooth(fy)[:, None])
        if gap["bottom"] and fy:
            m[-fy:, :] = np.minimum(m[-fy:, :], _smooth(fy)[::-1][:, None])
        out.paste(seed_img.crop((ex0, ey0, ex1, ey1)), (ex0, ey0),
                  Image.fromarray((m * 255).astype("uint8"), "L"))
    out.paste(src_img, (x0, y0))   # ⚠ 순서 불변 — 박스는 **마지막에** 원본으로 덮는다(무손실 계약)
    return out


def edge_stats(img, sides=None):
    """가장자리 8px 밴드의 픽셀 표준편차·평균색 — 단색 배경 판정(제안서 §2 라우팅).

    sides = 잴 변만 지정({top,bottom,left,right} 부분집합) · None = 4변 전부(구 동작).
    ⚠ 260806 실사고 봉합(운영자 "원래 하나의 이미지인것처럼 · 새로 어떤 특이점을 창조하면안됨") —
      구판은 **항상 4변 평균**이라, 확장과 무관한 변에 피사체가 닿기만 해도 표준편차가 올라
      「복잡한 배경」으로 오판하고 유료 창조 모델로 갔다. 실측(운영자 제출 케이스 재현):
        4변 평균 std 30.68 → gemini(유료·창조) / **좌우 변만 std 0.00 → solid_pad(0원)**
        범인 = 하단 변 std 41.02(파란 어깨가 거기 닿는다) — 좌우 확장에는 아무 상관이 없는 값이다.
      → 「채울 자리에 맞닿은 변」만 재면 순흑 확장은 애초에 생성 문제가 아니게 된다(= 창조 여지 0)."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    b = 8
    pick = {"top": a[:b], "bottom": a[-b:], "left": a[:, :b], "right": a[:, -b:]}
    use = [v for k, v in pick.items() if not sides or k in sides] or list(pick.values())
    e = np.concatenate([v.reshape(-1, 3) for v in use])
    return float(e.std(axis=0).mean()), tuple(int(v) for v in e.mean(axis=0))


def gap_sides(img, ar, box):
    """채울 여백이 실제로 생기는 변 집합 — 라우팅·채움색을 **그 변만** 보고 정하기 위한 축(위 주석)."""
    if box:
        x, y, w, h = box
        eps = 0.002
        return {s for s, on in (("left", x > eps), ("right", x + w < 1 - eps),
                                ("top", y > eps), ("bottom", y + h < 1 - eps)) if on} or {"top", "bottom", "left", "right"}
    W, H = img.size            # 중앙 배치(pad_canvas) = 한 축만 늘어난다
    aw, ah = (int(v) for v in ar.split(":"))
    return {"left", "right"} if aw / ah >= W / H else {"top", "bottom"}


def streak_frac(out_img, box_px, tol=1.0):
    """여백에 **clamp 줄무늬가 그대로 남은** 비율 — 「모델 무동작」 결정론 검출(과금 0).

    ⚠ 260807 평의회 5 실측 = 실제로 `route="gemini"`로 출고된 산출 하나가 **여백의 90.6%를 입력 그대로**
      내보냈다(`9x16-fb4f9112`). 같은 모델 QA는 자기 판정 목록에 「leftover flat gray areas」를 글자
      그대로 갖고도 그걸 통과시켰다 = **씨앗 방식의 가장 흔한 실패(모델이 아무것도 안 함)를 LLM 판정이
      원리적으로 못 잡는다**. 그래서 결정론 축이 필요하다.
    ⚠ 축 선택 = 「입력과 같은 색인가」가 아니라 **「줄무늬인가」**. 평의회 5의 원안(입력 캔버스 대비
      동일 화소 비율)을 이 세션의 드라이런에 걸었더니 **정상 재작성본에서 12~34%가 나왔다** — 밴드가
      넓은 단색 하늘이면 모델이 옳게 그려도 색이 우연히 일치하기 때문이다(그 상태로 하드 거부하면
      좋은 산출을 버리고 줄무늬 폴백으로 내려간다 = 개악). clamp는 **이웃 행/열과의 차가 수학적으로
      정확히 0**이라 이 축은 그 혼동이 구조적으로 없다.
      실측(같은 앵커·JPEG 왕복 후) = 무동작 **0.983** vs 정상 재작성 **0.000** → 임계 0.5(양쪽 여유 ≈2배·∞).
    ⚠ 축별로 방향이 다르다 — 상/하 밴드는 clamp가 **행** 복제, 좌/우 밴드는 **열** 복제다.
    """
    a = np.asarray(out_img.convert("RGB"), dtype=np.float32)
    x0, y0, x1, y1 = box_px
    ch, cw = a.shape[:2]
    tot = flat = 0
    for seg in (a[:y0], a[y1:]):                       # 세로 밴드 = 행 방향 복제
        if seg.shape[0] > 1:
            dv = np.abs(np.diff(seg, axis=0)).max(axis=(1, 2))
            tot += dv.size
            flat += int((dv <= tol).sum())
    for seg in (a[:, :x0], a[:, x1:]):                 # 가로 밴드 = 열 방향 복제
        if seg.shape[1] > 1:
            dh = np.abs(np.diff(seg, axis=1)).max(axis=(0, 2))
            tot += dh.size
            flat += int((dh <= tol).sum())
    return float(flat) / tot if tot else 0.0


def _join_en(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def seed_dirs(box_px, canvas_size, src_img, plain_std=EDGE_SOLID_STD):
    """P_SEEDFILL 3슬롯(keep·where·edgerule) — 실측 기하를 **%로** 문장화.

    ⚠ `box_dirs`를 그대로 쓰면 안 된다 — 그건 P_PADFILL 문법 전용이라 선행사("an original photo")가
      그 프롬프트 안에 있다. 씨앗 프롬프트엔 없어서 "extended above and below **it**" = 순환문이 됐다.
      게다가 P_SEEDFILL은 {place}·{dirhint}를 안 쓰므로 배치 지정(box) 발사에서 고정 문구 "central"이
      **거짓말**을 했고(원본이 중앙이 아닌데 중앙이라 단언), dirhint의 가장 강한 잠금 절이 통째로 버려졌다.
    변별(`edgerule`)은 기존 `edge_stats`를 그 변에만 재사용 = 새 값·새 의존성·과금 0.
      · 변이 단색 → 「그 밴드는 같은 민무늬 배경 그대로, 아무것도 넣지 마라」(P_PADFILL의 검증된 룰 이식)
      · 변이 복잡 → 「배경으로 이어라 · 피사체가 닿았으면 **한 몸으로만** 연장」
    """
    x0, y0, x1, y1 = box_px
    cw, ch = canvas_size

    def pct(n, d):
        return "{:.0f}%".format(100.0 * n / d)

    bands = []
    if y0 > 1:
        bands.append(("top", "the top " + pct(y0, ch) + " of the frame"))
    if ch - y1 > 1:
        bands.append(("bottom", "the bottom " + pct(ch - y1, ch) + " of the frame"))
    if x0 > 1:
        bands.append(("left", "the left " + pct(x0, cw) + " of the frame"))
    if cw - x1 > 1:
        bands.append(("right", "the right " + pct(cw - x1, cw) + " of the frame"))
    if not bands:   # 여백 0 = 이 경로에 안 온다(방어)
        return "the whole frame", "There are no stretched bands", ""

    txt = _join_en([t for _, t in bands])
    where = (txt[0].upper() + txt[1:]) + (" is a stretched band" if len(bands) == 1 else " are stretched bands")

    vert, horz = (y0 > 1 or ch - y1 > 1), (x0 > 1 or cw - x1 > 1)
    hp, wp = pct(y1 - y0, ch), pct(x1 - x0, cw)
    # ⚠ 260808 봉합 = 구판은 세 갈래 전부 **"the middle"** 하드코딩이라, 원본이 한쪽 변에 붙어 있어도
    #   「가운데 사각형」이라고 단언했다(실사고 로그 = box x0=0.226·x1=1.0[우변 밀착]인데 "a rectangle in
    #   the middle"). 모델은 그 말대로 사방 대칭 여백을 상정하고 좌측 23% 밴드를 「원본에 없던 새 영역」으로
    #   다뤄 **건물을 복제**했다(QA t1 실패 사유 그대로). 이 파일 seed_dirs 독스트링이 box_dirs의 고정 문구
    #   "central"을 두고 이미 「거짓말」이라 지목했는데, 봉합본이 같은 병을 그대로 안고 있었다.
    #   → 위치를 **실측 구간 %**로 서술하고 맞닿은 변을 명시한다(가운데면 25%~75%로 저절로 드러난다 = 창작 0).
    if vert and not horz:
        keep = ("the horizontal strip from " + pct(y0, ch) + " to " + pct(y1, ch)
                + " of the frame height, spanning the full width")
    elif horz and not vert:
        keep = ("the vertical strip from " + pct(x0, cw) + " to " + pct(x1, cw)
                + " of the frame width, spanning the full height")
    else:
        keep = ("the rectangle spanning " + pct(x0, cw) + " to " + pct(x1, cw) + " of the width and "
                + pct(y0, ch) + " to " + pct(y1, ch) + " of the height")
    keep += " (" + wp + " of the width by " + hp + " of the height)"
    flush = [sd for sd, on in (("left", x0 <= 1), ("right", cw - x1 <= 1),
                               ("top", y0 <= 1), ("bottom", ch - y1 <= 1)) if on]
    if flush:   # 밀착 변 = 「그쪽엔 채울 것이 없다」 = 모델이 그 변을 건드릴 이유를 없앤다
        keep += (", already flush against the " + _join_en(flush)
                 + (" edge" if len(flush) == 1 else " edges") + " of the frame")

    rules = []
    for side, _ in bands:
        std, _mean = edge_stats(src_img, {side})
        if std < plain_std:
            rules.append("Along the {} edge of the real photograph the pixels are plain, even background, "
                         "so the {} band must stay that same plain background and contain nothing at all."
                         .format(side, side))
        else:
            rules.append("Along the {} edge of the real photograph the pixels are busy, so the {} band must "
                         "be rebuilt as more of that same background — and if part of a subject touches that "
                         "edge, extend that one subject as a single continuous body, never as a second one."
                         .format(side, side))
    return keep, where, " ".join(rules)


def solid_pad(img, ar, color, box=None):
    if box:
        return place_canvas(img, ar, box, fill=color)[0]
    canvas, _b, _s = pad_canvas(img, ar, fill=color)
    return canvas


def seed_pad(canvas, box_px):
    """빈칸을 **주변 픽셀로 미리 메꾼다**(가장자리 연장 = clamp) — 모델에 「빈칸」을 주지 않기 위한 씨앗.

    ⚠ 260806 실호출이 드러낸 축(운영자 "firefly로 만들때 명령어 아예 입력안해도 자연스럽게 채우기는 잘하던데"):
      구판은 여백을 **평평한 회색**으로 주고 「채워라」고 했다 → 모델에겐 그게 **빈 캔버스**라 매번 「여기 뭘 넣지」를
      새로 결정한다. 그 결정이 갈리는 게 실패의 정체였다:
        · 경계가 빈 배경 → **발명**(마네킹 케이스: 별·성운·팔 · 260806 1차)
        · 경계에 무늬 → **복제/이음선**(앵커 4:5: QA 2회 FAIL "seam + severe ghosting" · 260806 실호출)
      Firefly 생성형 채우기가 무프롬프트로 자연스러운 이유가 이것 — 빈칸을 상상시키지 않고 **주변에서 끌어와** 메꾼 뒤
      다듬는다. 같은 구조를 우리도 쓴다: 여기서 씨앗을 깔고(과금 0), 모델에겐 「다듬어라」만 시킨다(P_SEEDFILL).
    방식 = **가장자리 연장(edge clamp) 단독**(블러 비채택 = 아래 260806 2차 실측). 있는 픽셀만 늘리므로 없던 것을 만들 수 없다(창조 여지 구조적 0).
    ⚠ 거울반사(symmetric)는 **비채택** — 260806 실측에서 앵커 얼굴이 위쪽에 **거꾸로 복제**됐다(인물이 경계에 걸치면
      「두 번째 얼굴」이 생긴다). 그건 바로 이 파이프가 이미 실패한 사유(QA "severe ghosting/duplication")를 씨앗이
      **더 키우는** 짓이다. clamp는 같은 상황에서 세로 줄무늬로만 늘어나 복제 형상이 안 생긴다.
    블러 = 줄무늬를 눌러 모델이 「여기는 흐린 배경」으로 읽게 하는 힌트(원본 영역은 무접촉 = 픽셀락과 무충돌)."""
    x0, y0, x1, y1 = box_px
    cw, ch = canvas.size
    reg = np.asarray(canvas.convert("RGB"))[y0:y1, x0:x1]
    if reg.size == 0:
        return canvas
    pad = ((y0, max(0, ch - y1)), (x0, max(0, cw - x1)), (0, 0))
    return Image.fromarray(np.pad(reg, pad, mode="edge"))
    # ⚠ 블러 **비채택**(260806 2차 실측) — 1차에 여백에 GaussianBlur를 걸었더니 **씨앗이 정보를 지웠다**:
    #   야경 도시 텍스처가 뭉개져 「밋밋한 파란 면」이 되고, 모델은 그 흐린 면을 「원래 흐린 배경」으로 읽어 **그대로 뒀다**
    #   (실측: 4:5 상 확장 = 텍스처 소실 · 4:5 하 확장 = 정체불명 얼룩 · 9:16 상 확장도 동일 증상).
    #   씨앗의 목적은 「고칠 자국을 명확히 보여주는 것」이지 「미리 예쁘게 하는 것」이 아니다 — clamp 줄무늬는
    #   선명할수록 모델에게 「여기가 늘어난 자리」라는 신호가 강해진다.


def blur_pad(img, ar, box=None):
    """원본 블러 확대 배경 + 원본(유튜브 세로영상식) — 항상 성공하는 결정론 폴백. box 지정 시 그 자리에 앉힌다."""
    if box:   # 배치형 = 캔버스·원본 자리를 place_canvas가 정하고, 배경만 블러 확대본으로 갈아끼운다(값·필터 동일)
        canvas, bpx, src = place_canvas(img, ar, box)
        cw, ch = canvas.size
        W, H = img.size
        scale = max(cw / W, ch / H)
        bg = img.resize((int(W * scale) + 2, int(H * scale) + 2), Image.LANCZOS).filter(ImageFilter.GaussianBlur(24))
        canvas.paste(bg, ((cw - bg.size[0]) // 2, (ch - bg.size[1]) // 2))
        canvas.paste(src, (bpx[0], bpx[1]))
        return canvas
    W, H = img.size
    aw, ah = (int(x) for x in ar.split(":"))
    if aw / ah >= W / H:
        ch = H
        cw = int(round(H * aw / ah / 8) * 8)
    else:
        cw = W
        ch = int(round(W * ah / aw / 8) * 8)
    scale = max(cw / W, ch / H)
    bg = img.resize((int(W * scale) + 2, int(H * scale) + 2), Image.LANCZOS).filter(ImageFilter.GaussianBlur(24))
    canvas = Image.new("RGB", (cw, ch))
    canvas.paste(bg, ((cw - bg.size[0]) // 2, (ch - bg.size[1]) // 2))
    canvas.paste(img, ((cw - W) // 2, (ch - H) // 2))
    return canvas


def jpg_bytes(img, q=90):   # q90 = 전 산출 통일값(운영자 260805 · 구 92) — 정본 = gen_image.post_process(quality=90, subsampling=0, optimize=True)
    b = io.BytesIO()
    # subsampling=0(4:4:4) — 기본 4:2:0 크로마 번짐 방지(솔리드/블러 무과금 경로 재압축 열화 최소화 · 분신11 260709)
    img.convert("RGB").save(b, "JPEG", quality=q, subsampling=0, optimize=True)
    return b.getvalue()


def ratio_ok(size, ar, tol=0.02):
    aw, ah = (int(x) for x in ar.split(":"))
    return abs(size[0] / size[1] - aw / ah) <= (aw / ah) * tol


def main():
    rid = os.environ.get("RESIZE_ID", "")
    src = os.environ.get("RESIZE_SRC", "")
    try:
        opts = json.loads(os.environ.get("RESIZE_OPTS") or "{}")
    except Exception:
        opts = {}
    aspect = opts.get("aspect") if opts.get("aspect") in ASPECTS else (opts.get("aspect") if custom_aspect_ok(opts.get("aspect")) else "16:9")   # 직접 N:N(운영자 260718 · api/resize customAspectOk와 한 쌍) 허용 · 그 외 16:9 폴백(종전)
    size = opts.get("size") if opts.get("size") in SIZES else "1K"
    lock = bool(opts.get("lock", True))
    fill = opts.get("fill") if opts.get("fill") in FILLS else "auto"   # 채움 오버라이드(운영자 260803) — 미지정·구 이력 재발사 = auto(종전)
    _m = opts.get("model")
    if isinstance(_m, str) and re.match(r"^gemini-[0-9][0-9a-z.\-]*$", _m.strip()):
        globals()["IMG_MODEL"] = _m.strip()   # dispatch opts 우선(실험 축 = repo variable 없이 1콜로 모델 교체)
        # ⚠ family 정규식으로 제한 = 임의 문자열 주입으로 엉뚱한 모델에 과금되는 길 차단(models.json vendors
        #   gemini_image.family와 같은 술어 · 승인 안 된 벤더로는 못 넘어간다).
    box = parse_box(opts)   # 운영자 지정 배치(운영자 260805 · 카드 생성 미리보기의 이동·축소 그대로) — None = 종전 중앙 배치

    src_path = os.path.join(ROOT, src)
    if not rid or not os.path.isfile(src_path):
        print("::error::입력 없음 — id={} src={}".format(rid, src))
        sys.exit(1)
    img = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")   # 폰 세로사진 EXIF 회전 적용(눕은 채 패딩 방지)
    if box is None and ratio_ok(img.size, aspect):
        print("이미 목표 비율({}) — no-op".format(aspect))
        return   # ⚠ 배치 지정본은 no-op 금지 — 비율이 이미 맞아도 축소 배치면 채울 여백이 실재한다(운영자 260805)

    # ── 라우팅 ── (auto = 종전 edge_std 자동 · solid/blur/ai = 운영자 지정 강제 — 260803 채움 선택지)
    gs = gap_sides(img, aspect, box)
    std, mean_color = edge_stats(img, gs)   # ⚠ 채울 변만 잰다(위 edge_stats 주석 = 260806 실사고)
    route = "solid_pad" if std < EDGE_SOLID_STD else "gemini"
    if fill != "auto":
        route = {"solid": "solid_pad", "blur": "blur_pad", "ai": "gemini"}[fill]
        # ⚠ 「AI」 강제여도 **맞닿은 변이 단색이면** 유료 창조 콜을 쓰지 않는다(운영자 260806
        #   "이거는 창조가 아니라서 저비용일 수록 더 좋음") — 단색 확장은 PIL 패딩이 화질·자연스러움에서
        #   모델을 못 이길 수가 없는 축이고(값이 그냥 같다), 모델을 부르면 오히려 없던 것을 그린다(별·성운·팔 실사고).
        if route == "gemini" and std < EDGE_SOLID_STD:
            print("::notice::맞닿은 변 단색(std={:.1f}) — AI 지정이지만 무과금 단색 패딩으로 처리(창조 여지 0)".format(std), flush=True)
            route = "solid_pad"
    if box:
        print("배치 지정: x={:.4f} y={:.4f} w={:.4f} h={:.4f}".format(*box), flush=True)
    print("라우팅: edge_std={:.1f}(변 {}) fill={} → {} (aspect={} size={} lock={})".format(std, ",".join(sorted(gs)), fill, route, aspect, size, lock), flush=True)

    out_img = None
    qa_note = "N/A"   # 원장 기록용 — 결정론 경로는 판정 대상이 아니다(gemini 경로만 PASS/FAIL/SKIP/DET-FAIL)
    if route == "solid_pad":
        out_img = solid_pad(img, aspect, mean_color, box)
    elif route == "blur_pad":   # 명시 블러(fill=blur) — 종전엔 폴백 전용 경로였다(결정론·과금 0)
        out_img = blur_pad(img, aspect, box)
    else:
        if not tg.KEY:
            print("::warning::GEMINI_API_KEY 없음 — blur-pad 폴백")
            route = "blur_pad"
            out_img = blur_pad(img, aspect, box)
        else:
            if box:
                canvas, bpx, src_img = place_canvas(img, aspect, box)
            else:
                canvas, bpx, src_img = pad_canvas(img, aspect, size=size)   # 캡 걸리면 src_img = 축소본(픽셀락도 이걸 되붙인다)
            place, where, dirhint = box_dirs(bpx, canvas.size)
            seed = seed_pad(canvas, bpx)   # 빈칸을 먼저 메꾼다(과금 0) → 모델은 「채우기」가 아니라 「다듬기」만 한다
            if SEED_ON:
                s_keep, s_where, s_edge = seed_dirs(bpx, canvas.size, src_img)
                base_prompt = P_SEEDFILL.format(keep=s_keep, where=s_where, edgerule=s_edge)
                print("씨앗 문구: 원본={} / {} / {}".format(s_keep, s_where, s_edge), flush=True)
            else:
                base_prompt = P_PADFILL.format(place=place, where=where, dirhint=dirhint)
                print("배치 문구: {} / 여백 {}".format(place, where), flush=True)   # 프롬프트가 캔버스를 정확히 묘사하는지 런 로그로 사후 대조(운영자 260806 "프롬프팅이 어떻게 고정되어있는지")
            feed = seed if SEED_ON else canvas
            ref_jpg = jpg_bytes(src_img)   # 원본 = 「피사체가 몇인가」의 정답지(생성·판정 양쪽에 같은 장을 준다)
            # ⚠ 씨앗 경로는 [원본, 씨앗] 2장 — 씨앗만 주면 모델이 보는 유일한 증거가 「정장색 세로 밴드」라
            #   텍스트로 "두 번째 몸통 금지"라고 말해도 시각 증거가 이긴다(260806 실사고).
            feed_parts = [ref_jpg, jpg_bytes(feed)] if SEED_ON else jpg_bytes(feed)
            out_cand, fb, qa_fail, qa_note = None, "", False, "NONE"   # NONE = 렌더 자체가 0회 성공
            for attempt in (1, 2):   # 생성→자가 QA→실패 사유 피드백 재생성 1회(exp r8 검증 · 운영자 '검증하면서 뽑기')
                p = base_prompt + ((" IMPORTANT — the previous attempt FAILED quality review for this "
                                    "reason: \"" + fb + "\". Fix exactly that issue this time.") if fb else "")
                cand = tg.gemini_image(p, image_size=size, tag="resize:t{}".format(attempt),
                                       aspect=aspect, ref_png=feed_parts, model=IMG_MODEL or None)
                _CALLS["gen"] += 1   # 과금 실측(운영자 260808 "실패해도 과금이 나갈텐데") — 성공·실패 무관 발사 수
                if not cand:
                    continue
                try:
                    Image.open(io.BytesIO(cand)).verify()   # 손상본 차단(gen_cards.edit_one 계승)
                except Exception:
                    print("::warning::렌더 디코드 실패(t{})".format(attempt))
                    continue
                # ⚠ 판정 대상 = **출고물**(pixel_lock 이후). 구판은 락 이전 원시 렌더를 심사해서
                #   페더가 만드는 단차·원본 침범이 영영 미심사였다(260807 평의회 = 16:9 크림 막대 실사고).
                shipped = pixel_lock(cand, canvas.size, src_img, bpx, seed_img=seed) if lock else \
                    Image.open(io.BytesIO(cand)).convert("RGB").resize(canvas.size, Image.LANCZOS)
                # ── ⓐ 결정론 검문 먼저(과금 0) — 「모델 무동작」은 LLM 판정이 원리적으로 못 잡는다 ──
                sk = streak_frac(shipped, bpx)
                if sk > STREAK_MAX:
                    out_cand, fb, qa_fail = shipped, "the stretched bands were left as raw streaks, not repaired", True
                    qa_note = "DET-FAIL"
                    print("  QA t{}: DET-FAIL — 줄무늬 잔류 {:.1%} > {:.0%}(모델 무동작)".format(attempt, sk, STREAK_MAX), flush=True)
                    continue   # 같은 사유 2연속이면 아래 폴백 — 모델 거부 서명이라 더 조를 이유가 없다
                # ── ⓑ 의미 판정(원본 동봉 2장 비교) ──
                v = gemini_judge(jpg_bytes(shipped), ref_bytes=ref_jpg, model=JUDGE_MODEL or None); _CALLS["judge"] += 1
                if v is None:
                    # ⚠ 260807 봉합 = 구판은 PASS와 **판정 불가**를 같은 가지로 합치고 **둘 다 무출력**이라,
                    #   유령이 「통과했는지 조용히 스킵됐는지」가 로그·원장 어디에도 안 남았다(평의회 5 실측).
                    #   이 레포가 스레드 `[1차 실측]`·틱톡 `_e1`에서 두 번 진단한 「관측이 지워진다」와 같은 병.
                    out_cand, qa_fail, qa_note = shipped, False, "SKIP"
                    print("  QA t{}: SKIP(판정 불가 — 형식 불량·콜 실패) → fail-soft 통과".format(attempt), flush=True)
                    break
                if v[0]:
                    out_cand, qa_fail, qa_note = shipped, False, "PASS"
                    print("  QA t{}: PASS — {}".format(attempt, v[1][:80]), flush=True)
                    break
                out_cand, fb, qa_fail = shipped, v[1], True   # FAIL — 사유 피드백 재시도(최종 FAIL이면 아래서 폴백)
                qa_note = "FAIL"
                print("  QA t{}: FAIL — {}".format(attempt, fb), flush=True)
            if out_cand is not None and qa_fail:   # 재시도까지 전부 FAIL = 불합격본 출력 금지 → 결정론 폴백(분신11 260709)
                print("::warning::QA 최종 FAIL({}) — 씨앗 폴백".format(fb[:80]))
                out_cand, qa_note = None, (qa_note if qa_note == "DET-FAIL" else "FAIL")
            if out_cand is not None:
                out_img = out_cand
            else:
                if SEED_ON:   # 씨앗은 「있는 픽셀만 재배치」라 블러 유령보다 언제나 선이 살아 있다(과금 0 · 260806 실호출 4:5 폴백 품질 봉합)
                    print("::warning::Gemini 렌더/QA 실패 — seed-pad 폴백(가장자리 연장 씨앗 그대로)")
                    route = "seed_pad"
                    out_img = seed
                else:
                    print("::warning::Gemini 렌더/QA 실패 — blur-pad 폴백(항상 결과)")
                    route = "blur_pad"
                    out_img = blur_pad(img, aspect, box)

    if not ratio_ok(out_img.size, aspect):   # 결정론 최종 검증(비율 ±2%)
        print("::warning::비율 불일치 {} — blur-pad 재폴백".format(out_img.size))
        route = "blur_pad"
        out_img = blur_pad(img, aspect, box)

    # ── 저장(R2 → git 폴백 · gen_image 패턴) + resize.json prepend ──
    out_bytes = jpg_bytes(out_img)
    akey = aspect.replace(":", "x")
    h8 = hashlib.sha1(out_bytes).hexdigest()[:8]
    url = tg.r2_upload(out_bytes, "resize/{}/{}-{}.jpg".format(rid, akey, h8), "image/jpeg") if tg.R2_ON else None
    tdir = os.path.join(ROOT, "viewer", "gen_out")
    os.makedirs(tdir, exist_ok=True)
    if not url:
        fname = "resize-{}-{}-{}.jpg".format(rid, akey, h8)
        with open(os.path.join(tdir, fname), "wb") as f:
            f.write(out_bytes)
        url = "gen_out/" + fname
        print("  ⚠️ R2 불가 — git 폴백 저장: " + url, flush=True)

    # ⚠ qa = 판정 결과를 **원장에 남긴다**(260807 평의회 5) — 구판은 PASS와 「판정 불가」가 같은 가지로
    #   합쳐진 채 둘 다 무출력이라, 유령이 통과였는지 조용한 스킵이었는지 사후에 알 방법이 0이었다.
    #   이 레포가 스레드 `[1차 실측]`·틱톡 `_e1`에서 두 번 겪은 「관측이 지워진다」와 같은 병이다.
    item = {"url": url, "srcUrl": src, "aspect": aspect, "size": size, "lock": lock, "route": route, "fill": fill,
            "qa": qa_note, "calls": {"gen": _CALLS["gen"], "judge": _CALLS["judge"]}, "model": IMG_MODEL or tg.MODEL,
            "box": list(box) if box else None,
            "id": rid, "ts": datetime.datetime.now(KST).isoformat(timespec="seconds")}
    sjson = os.path.join(tdir, "resize.json")
    cur = []
    if os.path.exists(sjson):
        try:
            cur = json.load(open(sjson, encoding="utf-8")) or []
        except Exception:
            cur = []
    json.dump(([item] + cur)[:24], open(sjson, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump([item], open("/tmp/resize_new.json", "w", encoding="utf-8"), ensure_ascii=False)   # race-heal(imggen 계승)
    # ⚠ 과금은 **성패와 무관**하게 나간다 — seed_pad 폴백(=무과금 결과물과 똑같은 그림)이 나가도
    #   그 앞의 생성·판정 콜은 이미 청구된다. 구판은 그 사실이 로그·원장 어디에도 안 남아 「실패했는데
    #   얼마 썼나」를 아무도 몰랐다(운영자 260808 지적). 이제 회차마다 남는다.
    print("✅ 완료 route={} qa={} model={} 콜(생성 {} · 판정 {}) → {}".format(
        route, qa_note, IMG_MODEL or tg.MODEL, _CALLS["gen"], _CALLS["judge"], url), flush=True)


if __name__ == "__main__":
    main()
