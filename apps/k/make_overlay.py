#!/usr/bin/env python3
"""/k AI 표기 오버레이 PNG 생성기 (재생성·문구 변경용).

AI기본법(26.1 시행) 딥페이크 가시적 표기 대비 — 생성 프롬프트가 아니라
편집 생성기(CapCut 등)에서 레이어로 얹는 투명 PNG를 만든다.
기본 산출: apps/k/assets/ai_overlay_916.png (1080x1920) · ai_overlay_169.png (1920x1080)

문구 정본(260613 — 공직선거관리규칙 별표1의3 영상 표시사항 차용):
  "이 영상은 실제가 아닌 인공지능 기술 등을 이용하여 만든 가상의 정보입니다"
  ※ 선거 소재가 아니면 개인 창작자는 법적 의무 없음(과기정통부 투명성 가이드라인 2026.01
    — 단순 이용자 제외)·자발 표기 = 명예훼손·플랫폼 방어 목적. 예술·창작물은 향유를
    저해하지 않는 완화 표시 허용 → 기본 = 배경 필 없는 맨 글자 + 연한 그림자,
    투명도 0.25(75% 반투명) (260613 사용자 확정).
  ⚠️ 선거 관련 소재(후보·정당·당락 연관)면 이 완화 불가 — 불투명+전체 10% 크기 테두리
    상시 표시(별표1의3) + 선거일 전 90일~선거일은 제작 자체 금지(82조의8).

사용: python3 apps/k/make_overlay.py [--text "줄1|줄2"] [--opacity 0.25] [--outdir apps/k/assets]
  --text    "|"로 줄바꿈. 캔버스 폭에 안 맞으면 폰트 자동 축소.
  --opacity 0~1 (1=불투명). 기본 0.25 = 75% 반투명(260613 사용자 지정).
배치: 9:16 = 상단 중앙(플랫폼 UI 안전지대) / 16:9 = 우상단. CapCut에서 레이어 이동 가능.
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
DEFAULT_TEXT = "이 영상은 실제가 아닌 인공지능 기술 등을|이용하여 만든 가상의 정보입니다"


def text_badge(lines, font_px, opacity, max_w):
    """배경 필 없는 맨 글자 + 아주 연한 드롭 섀도(밝은 배경 가독 보조)."""
    def measure(px):
        font = ImageFont.truetype(FONT, px)
        boxes = [font.getbbox(t) for t in lines]
        widths = [r - l for l, t, r, b in boxes]
        return font, boxes, widths

    font, boxes, widths = measure(font_px)
    while max(widths) > max_w and font_px > 14:  # 캔버스 초과 시 자동 축소
        font_px -= 2
        font, boxes, widths = measure(font_px)

    line_h = max(b - t for l, t, r, b in boxes)
    gap = int(font_px * 0.32)
    blur = max(2, int(font_px * 0.10))
    off = max(1, int(font_px * 0.05))
    margin = blur * 3
    w = max(widths) + margin * 2
    h = line_h * len(lines) + gap * (len(lines) - 1) + margin * 2
    a = lambda base: max(0, min(255, int(base * opacity)))

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ds = ImageDraw.Draw(shadow)
    y = margin
    for (l, t, r, b), lw, text in zip(boxes, widths, lines):
        ds.text(((w - lw) // 2 - l + off, y - t + off), text, font=font, fill=(0, 0, 0, a(120)))
        y += line_h + gap
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))

    d = ImageDraw.Draw(img)
    y = margin
    for (l, t, r, b), lw, text in zip(boxes, widths, lines):
        d.text(((w - lw) // 2 - l, y - t), text, font=font, fill=(255, 255, 255, a(255)))
        y += line_h + gap
    return img


def make(canvas_w, canvas_h, lines, font_px, opacity, pos, out):
    cv = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    b = text_badge(lines, font_px, opacity, canvas_w - 120)
    if pos == "top-center":
        xy = ((canvas_w - b.width) // 2, 110)
    else:  # top-right
        xy = (canvas_w - b.width - 60, 48)
    cv.alpha_composite(b, xy)
    cv.save(out)
    print(f"OK {out} ({canvas_w}x{canvas_h}, badge {b.width}x{b.height}, opacity {opacity})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--opacity", type=float, default=0.25)
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    lines = [s.strip() for s in a.text.split("|") if s.strip()]
    make(1080, 1920, lines, 34, a.opacity, "top-center", os.path.join(a.outdir, "ai_overlay_916.png"))
    make(1920, 1080, lines, 30, a.opacity, "top-right", os.path.join(a.outdir, "ai_overlay_169.png"))


if __name__ == "__main__":
    main()
