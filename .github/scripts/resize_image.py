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
EDGE_SOLID_STD = 6.0   # 가장자리 픽셀 표준편차 임계 — 이하 = 단색/그라데(PIL 공짜 경로)

P_PADFILL = (
    "First, carefully analyze the attached image: identify the subject, their exact pose and "
    "orientation, the scene, the lighting direction, and the textures. Base everything you draw "
    "on what is actually visible in this specific image — not on generic assumptions. "
    "This canvas contains an original photo {place}, with flat neutral gray areas "
    "{where}. Fill ONLY the gray areas by seamlessly extending the existing scene {dirhint} — "
    "never leave any gray visible. Continue the background's lighting, perspective, textures, and "
    "grain across the boundary, and match the exact brightness and tone of the photo at the "
    "boundary so no edge or band is visible. Match the depth of field: if the pixels adjacent to "
    "a gray area are out of focus or blurred, the new content there must be equally out of focus — "
    "do not introduce new sharp objects, buildings, crowds, stands, or scenery that are not "
    "already visible in the photo. Keep every existing pixel of the original photo "
    "exactly unchanged. Do not add any new text, watermarks, logos, or people. The result must "
    "look like one single continuous photograph."
)   # v0 확정본(exp r5+r7) — 룰 삭제 금지: 선분석(r7)·방향 동적(r2)·심도 유지(r4)·톤 일치가 각각 실측 실패를 막는다


def gemini_judge(png_bytes):
    """생성 결과 자가 QA(exp r8 검증 이식 — 운영자 '검증하면서 뽑는 프롬프팅') — 같은 모델 TEXT 판정.
    (passed, reason) · 판정 콜 실패 = None(fail-soft·렌더는 살림)."""
    import base64
    import urllib.request
    prompt = ("You are a strict photo QA judge. Answer in EXACTLY this format:\n"
              "VERDICT: PASS or FAIL\nREASON: <one short sentence>\n"
              "FAIL if any of these are visible: anatomically wrong human body, unnatural body proportions, "
              "duplicated objects or duplicated text, watermarks, leftover flat gray areas, or an obvious "
              "visible seam or brightness band. Otherwise PASS.")
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


def edge_stats(img):
    """가장자리 8px 밴드의 픽셀 표준편차·평균색 — 단색 배경 판정(제안서 §2 라우팅)."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    b = 8
    strips = [a[:b].reshape(-1, 3), a[-b:].reshape(-1, 3), a[:, :b].reshape(-1, 3), a[:, -b:].reshape(-1, 3)]
    e = np.concatenate(strips)
    return float(e.std(axis=0).mean()), tuple(int(v) for v in e.mean(axis=0))


def solid_pad(img, ar, color, box=None):
    if box:
        return place_canvas(img, ar, box, fill=color)[0]
    canvas, _ = pad_canvas(img, ar, fill=color)
    return canvas


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
    std, mean_color = edge_stats(img)
    route = "solid_pad" if std < EDGE_SOLID_STD else "gemini"
    if fill != "auto":
        route = {"solid": "solid_pad", "blur": "blur_pad", "ai": "gemini"}[fill]
    if box:
        print("배치 지정: x={:.4f} y={:.4f} w={:.4f} h={:.4f}".format(*box), flush=True)
    print("라우팅: edge_std={:.1f} fill={} → {} (aspect={} size={} lock={})".format(std, fill, route, aspect, size, lock), flush=True)

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
            base_prompt = P_PADFILL.format(place=place, where=where, dirhint=dirhint)
            print("배치 문구: {} / 여백 {}".format(place, where), flush=True)   # 프롬프트가 캔버스를 정확히 묘사하는지 런 로그로 사후 대조(운영자 260806 "프롬프팅이 어떻게 고정되어있는지")
            png, fb, qa_fail = None, "", False
            for attempt in (1, 2):   # 생성→자가 QA→실패 사유 피드백 재생성 1회(exp r8 검증 · 운영자 '검증하면서 뽑기')
                p = base_prompt + ((" IMPORTANT — the previous attempt FAILED quality review for this "
                                    "reason: \"" + fb + "\". Fix exactly that issue this time.") if fb else "")
                cand = tg.gemini_image(p, image_size=size, tag="resize:t{}".format(attempt),
                                       aspect=aspect, ref_png=jpg_bytes(canvas))
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
