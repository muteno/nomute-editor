#!/usr/bin/env python3
"""/k AI 표기 오버레이 PNG 생성기 (재생성·문구 변경용).

AI기본법(26.1 시행) 딥페이크 가시적 표기 대비 — 생성 프롬프트가 아니라
편집 생성기(CapCut 등)에서 레이어로 얹는 투명 PNG를 만든다.
기본 산출: apps/k/assets/ai_overlay_916.png (1080x1920) · ai_overlay_169.png (1920x1080)

사용: python3 apps/k/make_overlay.py [--text "AI 생성 콘텐츠"] [--outdir apps/k/assets]
배치: 9:16 = 상단 중앙(플랫폼 UI 안전지대) / 16:9 = 우상단. CapCut에서 레이어 이동 가능.
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def badge(text, font_px):
    font = ImageFont.truetype(FONT, font_px)
    l, t, r, b = font.getbbox(text)
    tw, th = r - l, b - t
    pad_x, pad_y = int(font_px * 0.62), int(font_px * 0.34)
    w, h = tw + pad_x * 2, th + pad_y * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2,
                        fill=(0, 0, 0, 150), outline=(255, 255, 255, 70), width=2)
    d.text((pad_x - l, pad_y - t), text, font=font, fill=(255, 255, 255, 255))
    return img


def make(canvas_w, canvas_h, text, font_px, pos, out):
    cv = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    b = badge(text, font_px)
    if pos == "top-center":
        xy = ((canvas_w - b.width) // 2, 110)
    else:  # top-right
        xy = (canvas_w - b.width - 60, 48)
    cv.alpha_composite(b, xy)
    cv.save(out)
    print(f"OK {out} ({canvas_w}x{canvas_h}, badge {b.width}x{b.height})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="AI 생성 콘텐츠")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    make(1080, 1920, a.text, 48, "top-center", os.path.join(a.outdir, "ai_overlay_916.png"))
    make(1920, 1080, a.text, 44, "top-right", os.path.join(a.outdir, "ai_overlay_169.png"))


if __name__ == "__main__":
    main()
