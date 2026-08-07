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
    "This image has already been mechanically extended {where} — those margins were filled by "
    "stretching the last row/column of pixels outward, so the colours and layout there are already "
    "correct but the texture is smeared into obvious streaks. Your ONLY job is to replace those "
    "streaks with the proper texture so the whole frame reads as one single continuous photograph. "
    "Do NOT reimagine or replace the scene. Do NOT add any object, person, body part, star, light "
    "effect, furniture, wall, panel, text or watermark that is not already present. Keep the "
    "composition and every colour region exactly where it is. "
    "Work only on the extended margins {where}: keep each streak's colour and position, but rebuild "
    "its detail by continuing the neighbouring texture — if the adjacent area is a city skyline at "
    "night, the streaks become more of that same skyline at the same scale and density; if it is "
    "fabric, more of that same fabric. Never leave a smooth flat area where the neighbouring "
    "pixels have texture. Straighten lines and horizons so they run continuously across the joins, "
    "and even out brightness so no seam or band remains. "
    "Preserve the existing lighting direction, perspective, grain and depth of field — if the "
    "neighbouring pixels are out of focus, the repaired margins must be equally out of focus. "
    "Keep every pixel of the central original area exactly unchanged. "
    "The result must look like the camera simply captured a wider view of the exact same scene."
)   # 씨앗 다듬기 프롬프트(260806 · 운영자 "firefly로 만들때 명령어 아예 입력안해도 자연스럽게 채우기는 잘하던데")
#   ⚠ P_PADFILL(회색 빈칸 → 채워라)과 **과업이 다르다**: 여기선 seed_pad가 이미 메꿔 놓았고 모델은 **결함 제거만** 한다.
#   실호출 근거(260806 앵커 3비율) = 회색 빈칸 방식의 실패 사유가 「seam + severe ghosting/duplication」(4:5 QA 2회 FAIL)이라
#   그 결함 이름을 그대로 과업으로 준다 = 모델이 「무엇을 그릴까」를 결정할 여지 자체를 없앤다.
#   ⚠ 260806 2차 개정 = 씨앗을 거울반사 → **clamp(가장자리 연장)** 로 바꾼 데 맞춰 문구 동기화(구 "mirroring"·"mirror-symmetry"는
#     거짓 서술 = 모델에게 없는 결함을 찾게 시킨다) + **「매끈한 면 금지」 절 추가**: 1차 실측에서 확장부가 「밋밋한 파란 면」으로
#     남는 실패가 났다(모델이 흐린 씨앗을 「원래 흐린 배경」으로 읽음) → 이웃에 텍스처가 있으면 확장부에도 같은 밀도의 텍스처를
#     요구하고, 「가구·벽·패널」을 발명 금지 목록에 명시(16:9 실측 = 없던 스튜디오 기둥·조명 발명).


def gemini_judge(png_bytes):
    """생성 결과 자가 QA(exp r8 검증 이식 — 운영자 '검증하면서 뽑는 프롬프팅') — 같은 모델 TEXT 판정.
    (passed, reason) · 판정 콜 실패 = None(fail-soft·렌더는 살림)."""
    import base64
    import urllib.request
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
    req = urllib.request.Request(tg.API + "?key=" + tg.KEY, data=json.dumps(payload).encode(),
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


def pad_canvas(img, ar, fill=(127, 127, 127)):
    """타겟 비율 캔버스에 원본 중앙 배치. (canvas, box) · 치수 8배수. (v0 검증 함수)"""
    W, H = img.size
    aw, ah = (int(x) for x in ar.split(":"))
    if aw / ah >= W / H:
        ch = H
        cw = int(round(H * aw / ah / 8) * 8)
    else:
        cw = W
        ch = int(round(W * ah / aw / 8) * 8)
    canvas = Image.new("RGB", (cw, ch), fill)
    x, y = (cw - W) // 2, (ch - H) // 2
    canvas.paste(img, (x, y))
    return canvas, (x, y, x + W, y + H)


def pixel_lock(gen_png, canvas_size, src_img, box, feather=32):
    """생성 결과 위 원본 재부착 + 경계 페더(v0 검증 · 실사 톤 단차 완화로 24→32px)."""
    gen = Image.open(io.BytesIO(gen_png)).convert("RGB").resize(canvas_size, Image.LANCZOS)
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    mask = np.ones((h, w), dtype=np.float32)
    f = max(1, min(feather, w // 4, h // 4))
    ramp = np.linspace(0.0, 1.0, f, dtype=np.float32)
    mask[:, :f] = np.minimum(mask[:, :f], ramp[None, :])
    mask[:, -f:] = np.minimum(mask[:, -f:], ramp[::-1][None, :])
    mask[:f, :] = np.minimum(mask[:f, :], ramp[:, None])
    mask[-f:, :] = np.minimum(mask[-f:, :], ramp[::-1][:, None])
    m = Image.fromarray((mask * 255).astype("uint8"), "L")
    out = gen.copy()
    out.paste(src_img, (x0, y0), m)
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


def solid_pad(img, ar, color, box=None):
    if box:
        return place_canvas(img, ar, box, fill=color)[0]
    canvas, _ = pad_canvas(img, ar, fill=color)
    return canvas


def seed_pad(canvas, box_px):
    """빈칸을 **주변 픽셀로 미리 메꾼다**(거울반사) — 모델에 「빈칸」을 주지 않기 위한 씨앗.

    ⚠ 260806 실호출이 드러낸 축(운영자 "firefly로 만들때 명령어 아예 입력안해도 자연스럽게 채우기는 잘하던데"):
      구판은 여백을 **평평한 회색**으로 주고 「채워라」고 했다 → 모델에겐 그게 **빈 캔버스**라 매번 「여기 뭘 넣지」를
      새로 결정한다. 그 결정이 갈리는 게 실패의 정체였다:
        · 경계가 빈 배경 → **발명**(마네킹 케이스: 별·성운·팔 · 260806 1차)
        · 경계에 무늬 → **복제/이음선**(앵커 4:5: QA 2회 FAIL "seam + severe ghosting" · 260806 실호출)
      Firefly 생성형 채우기가 무프롬프트로 자연스러운 이유가 이것 — 빈칸을 상상시키지 않고 **주변에서 끌어와** 메꾼 뒤
      다듬는다. 같은 구조를 우리도 쓴다: 여기서 씨앗을 깔고(과금 0), 모델에겐 「다듬어라」만 시킨다(P_SEEDFILL).
    방식 = **가장자리 연장(edge clamp) + 여백만 약한 블러**. 있는 픽셀만 늘리므로 없던 것을 만들 수 없다(창조 여지 구조적 0).
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
                canvas, bpx = pad_canvas(img, aspect)
                src_img = img
            place, where, dirhint = box_dirs(bpx, canvas.size)
            seed = seed_pad(canvas, bpx)   # 빈칸을 먼저 메꾼다(과금 0) → 모델은 「채우기」가 아니라 「다듬기」만 한다
            base_prompt = P_SEEDFILL.format(where=where) if SEED_ON else P_PADFILL.format(place=place, where=where, dirhint=dirhint)
            feed = seed if SEED_ON else canvas
            print("배치 문구: {} / 여백 {}".format(place, where), flush=True)   # 프롬프트가 캔버스를 정확히 묘사하는지 런 로그로 사후 대조(운영자 260806 "프롬프팅이 어떻게 고정되어있는지")
            png, fb, qa_fail = None, "", False
            for attempt in (1, 2):   # 생성→자가 QA→실패 사유 피드백 재생성 1회(exp r8 검증 · 운영자 '검증하면서 뽑기')
                p = base_prompt + ((" IMPORTANT — the previous attempt FAILED quality review for this "
                                    "reason: \"" + fb + "\". Fix exactly that issue this time.") if fb else "")
                cand = tg.gemini_image(p, image_size=size, tag="resize:t{}".format(attempt),
                                       aspect=aspect, ref_png=jpg_bytes(feed))
                if not cand:
                    continue
                try:
                    Image.open(io.BytesIO(cand)).verify()   # 손상본 차단(gen_cards.edit_one 계승)
                except Exception:
                    print("::warning::렌더 디코드 실패(t{})".format(attempt))
                    continue
                v = gemini_judge(cand)
                if v is None or v[0]:   # 판정 스킵(fail-soft) 또는 PASS
                    png, qa_fail = cand, False
                    break
                png, fb, qa_fail = cand, v[1], True   # FAIL — 사유 피드백 재시도(최종 FAIL이면 아래서 폴백)
                print("  QA t{}: FAIL — {}".format(attempt, fb), flush=True)
            if png and qa_fail:   # 재시도까지 전부 FAIL = 불합격본 출력 금지 → 결정론 폴백(분신11 260709)
                print("::warning::QA 최종 FAIL({}) — blur-pad 폴백".format(fb[:80]))
                png = None
            if png:
                out_img = pixel_lock(png, canvas.size, src_img, bpx) if lock else \
                    Image.open(io.BytesIO(png)).convert("RGB").resize(canvas.size, Image.LANCZOS)
            else:
                if SEED_ON:   # 씨앗은 「있는 픽셀만 재배치」라 블러 유령보다 언제나 선이 살아 있다(과금 0 · 260806 실호출 4:5 폴백 품질 봉합)
                    print("::warning::Gemini 렌더/QA 실패 — seed-pad 폴백(거울반사 이어붙임)")
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

    item = {"url": url, "srcUrl": src, "aspect": aspect, "size": size, "lock": lock, "route": route, "fill": fill,
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
    print("✅ 완료 route={} → {}".format(route, url), flush=True)


if __name__ == "__main__":
    main()
