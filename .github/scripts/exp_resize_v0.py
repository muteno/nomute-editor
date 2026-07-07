#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""나노바나나 비율 재구성 v0 실험 (카나리아 · 라이브 무영향 · 운영자 260707 "무한정 테스트 OK")

목적: 완성 이미지(문구 有/無)를 다른 비율로 확장할 때 3가지 변형의 구성·문구 보존 품질 실측.
  A(reframe)  = 원본 + aspect 1콜 (전처리 없음 — 모델이 알아서 리프레임)
  B(padfill)  = PIL 패딩(타겟 캔버스·빈칸 중립그레이) + "회색 영역만 이어 그려라" 1콜
  C(pixellock)= B 결과 위에 원본 픽셀 재부착 + 경계 페더 (API 콜 0 — B에서 파생)
케이스: plain(문구 없는 장면) · poster(PIL로 한글 헤드라인 합성한 포스터 모사)

입력(env): EXP_SRC(레포 내 이미지 경로) · EXP_ASPECT("16:9") · EXP_CASES("plain,poster")
산출: _산출/exp_resize_v0/<KST ts>/ 에 입력·결과 JPG + meta.json (git 커밋은 워크플로가)
불변: workflow_dispatch 전용 = 유료 Gemini 수동 발사만(§📰) · 자동 파이프라인 무접촉.
"""
import io
import json
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # gemini_image·_USAGE·_usage_total 재사용 (§📰 단일 렌더 진입점)

from PIL import Image, ImageDraw, ImageFont
import numpy as np

KST = datetime.timezone(datetime.timedelta(hours=9))          # §📐 시각 = KST
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

SRC = os.environ.get("EXP_SRC", "cards/260622-1736-2595974/scenes/장면01.jpg")
ASPECT = os.environ.get("EXP_ASPECT", "16:9")
CASES = [c.strip() for c in os.environ.get("EXP_CASES", "plain,poster").split(",") if c.strip()]
SIZE = os.environ.get("EXP_SIZE", "1K")   # "1K"/"2K" — 2K = 문구·디테일 선명도 실험(장당 $0.101)

# 한글 폰트 = card_news와 동일 계열(fonts-noto-cjk · 워크플로가 설치)
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

P_REFRAME = (
    "Reframe this exact image to a {ar} aspect ratio. Preserve every existing element exactly — "
    "subject, composition, colors, and any text or logos must remain unchanged and legible. "
    "Extend the scene naturally to fill the new frame. Do not crop, shrink, or restyle existing "
    "content. Match the original lighting, color grading, and grain. "
    "Do not add any new text, watermark, or people."
)
P_PADFILL = (
    "First, carefully analyze the attached image: identify the subject, their exact pose and "
    "orientation, the scene, the lighting direction, and the textures. Base everything you draw "
    "on what is actually visible in this specific image — not on generic assumptions. "
    "This canvas contains an original photo placed in the center, with flat neutral gray areas "
    "{where}. Fill ONLY the gray areas by seamlessly extending the existing scene {dirhint} — "
    "never leave any gray visible. Continue the background's lighting, perspective, textures, and "
    "grain across the boundary, and match the exact brightness and tone of the photo at the "
    "boundary so no edge or band is visible. Match the depth of field: if the pixels adjacent to "
    "a gray area are out of focus or blurred, the new content there must be equally out of focus — "
    "do not introduce new sharp objects, buildings, crowds, stands, or scenery that are not "
    "already visible in the photo. Keep every existing pixel of the original photo "
    "exactly unchanged. Do not add any new text, watermarks, logos, or people. The result must "
    "look like one single continuous photograph."
)   # 라운드2: 'beside'가 상하 확장 회색 방치 → 방향 동적 주입. 라운드4: 망원 클로즈업 좌우에 관중석 등 의미적 확장 → 심도 유지·신규 사물 금지 명시


def _font(size):
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size, index=1)
            except Exception:
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make_poster(img):
    """장면 위에 뉴스 포스터풍 한글 문구 합성(통제된 '문구 포스터' 케이스). 원본 불변 복사본 반환."""
    im = img.copy().convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im)
    head = _font(int(H * 0.062))
    sub = _font(int(H * 0.030))
    lines = ["한미 관세 협상 타결", "자동차 25% 관세 철회"]
    y = int(H * 0.06)
    for ln in lines:
        # 얇은 그림자 + 흰 본문(카드뉴스 문구 스타일 근사)
        d.text((int(W * 0.07) + 3, y + 3), ln, font=head, fill=(0, 0, 0))
        d.text((int(W * 0.07), y), ln, font=head, fill=(255, 255, 255))
        y += int(H * 0.075)
    cap = "no_mute | 뉴스 큐레이션"
    d.text((int(W * 0.07) + 2, int(H * 0.90) + 2), cap, font=sub, fill=(0, 0, 0))
    d.text((int(W * 0.07), int(H * 0.90)), cap, font=sub, fill=(0, 238, 210))
    return im


def pad_canvas(img, ar):
    """타겟 비율 캔버스(중립그레이)에 원본 중앙 배치. (canvas, box) 반환 · 치수 8배수."""
    W, H = img.size
    aw, ah = (int(x) for x in ar.split(":"))
    if aw / ah >= W / H:                     # 폭 확장(세로→가로)
        ch = H
        cw = int(round(H * aw / ah / 8) * 8)
    else:                                    # 높이 확장(가로→세로)
        cw = W
        ch = int(round(W * ah / aw / 8) * 8)
    canvas = Image.new("RGB", (cw, ch), (127, 127, 127))
    x, y = (cw - W) // 2, (ch - H) // 2
    canvas.paste(img, (x, y))
    return canvas, (x, y, x + W, y + H)


def pixel_lock(gen_png, canvas_size, src_img, box, feather=24):
    """생성 결과 위에 원본 재부착 + 경계 페더(선형 alpha ramp)."""
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


def jpg_bytes(img, q=92):
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=q)
    return b.getvalue()


def main():
    if not tg.KEY:
        print("::error::GEMINI_API_KEY 없음 — 실험 불가(과금 게이트)")
        sys.exit(1)
    src_path = os.path.join(ROOT, SRC)
    if not os.path.isfile(src_path):
        print("::error::소스 없음: {}".format(SRC))
        sys.exit(1)
    base = Image.open(src_path).convert("RGB")
    ts = datetime.datetime.now(KST).strftime("%y%m%d_%H%M")
    out_dir = os.path.join(ROOT, "_산출", "exp_resize_v0", ts)
    os.makedirs(out_dir, exist_ok=True)
    meta = {"src": SRC, "aspect": ASPECT, "ts": ts, "results": []}

    for case in CASES:
        # crop = 피사체를 일부러 잘라(상반신만) 잘린 신체·사물을 확장부에서 '완성'해야 하는 케이스(운영자 260708 질문 — amodal completion)
        if case == "crop":
            img = base.crop((0, 0, base.size[0], int(base.size[1] * 0.55)))
        elif case == "poster":
            img = make_poster(base)
        else:
            img = base
        open(os.path.join(out_dir, case + "_src.jpg"), "wb").write(jpg_bytes(img))
        src_bytes = jpg_bytes(img)

        # A — reframe 1콜 (crop 케이스 = 전체 재생성 기반 전신 완성 비교군 — 원본 픽셀 보존 포기 대신 해부학 자유도)
        pa = P_REFRAME.format(ar=ASPECT)
        if case == "crop":
            pa = ("Expand this cropped photo to a {ar} aspect ratio, completing the partially visible person "
                  "naturally: they are STANDING UPRIGHT walking on grass — anatomically correct full body with "
                  "natural human proportions, same uniform, same face, same lighting and grain. "
                  "Do not add any new separate people, text, or logos.").format(ar=ASPECT)
        a = tg.gemini_image(pa, image_size=SIZE,
                            tag="exp:{}:A".format(case), aspect=ASPECT, ref_png=src_bytes)
        if a:
            open(os.path.join(out_dir, case + "_A_reframe.jpg"), "wb").write(a)
        meta["results"].append({"case": case, "var": "A", "ok": bool(a)})

        # B — pad-fill 1콜 (패딩 방향을 프롬프트에 동적 주입 — 라운드2 상하 회색 방치 수리)
        canvas, box = pad_canvas(img, ASPECT)
        if box[1] > 0:   # 상하 확장(세로화)
            where = "above and below it"
            dirhint = ("upward and downward (for example, extend a ceiling or sky upward and a "
                       "floor or ground downward)")
        else:            # 좌우 확장(가로화)
            where = "to its left and right"
            dirhint = "to the left and to the right"
        pb = P_PADFILL.format(where=where, dirhint=dirhint)
        if case == "crop":   # 잘린 피사체 완성 허용(같은 대상 연장 OK · 별도 신규 인물만 금지) — 기본 'no people'이 완성을 막는 것 방지
            pb = pb.replace("Do not add any new text, watermarks, logos, or people.",
                            "Do not add any new text, watermarks, or logos.")
            pb += (" A person is partially cut off at the bottom edge of the original photo: naturally "
                   "complete the missing lower body of that SAME person. The person is STANDING UPRIGHT and "
                   "walking on the grass — draw anatomically correct hips, legs, knees, and football boots in "
                   "a natural standing/walking pose with correct human proportions (legs roughly as long as "
                   "the visible torso), matching the uniform, lighting, and grain. "
                   "Never add a new, separate person or object.")   # r6 실측: 포즈 미지정 = 앉은 자세·해부학 붕괴 → 포즈·비례 명시(운영자 "불구수준" 지적)
        b = tg.gemini_image(pb, image_size=SIZE,
                            tag="exp:{}:B".format(case), aspect=ASPECT, ref_png=jpg_bytes(canvas))
        if b:
            open(os.path.join(out_dir, case + "_B_padfill.jpg"), "wb").write(b)
            # C — pixel-lock (콜 0)
            c = pixel_lock(b, canvas.size, img, box)
            open(os.path.join(out_dir, case + "_C_pixellock.jpg"), "wb").write(jpg_bytes(c))
        meta["results"].append({"case": case, "var": "B(+C)", "ok": bool(b)})

    meta["usage"] = tg._usage_total(tg._USAGE)
    meta["prompts"] = {"A": P_REFRAME, "B": P_PADFILL}
    json.dump(meta, open(os.path.join(out_dir, "meta.json"), "w"), ensure_ascii=False, indent=1)
    print("✅ 실험 산출 → {}".format(out_dir))
    print(json.dumps(meta["usage"], ensure_ascii=False))


if __name__ == "__main__":
    main()
