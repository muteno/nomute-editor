#!/usr/bin/env python3
"""
NO MUTE 카피라이트 오버레이 생성기

Usage:
  기본:    python3 nomute_copyright.py <output_path> <reels|post> <년도> <이름> <플랫폼>
  완성문구: python3 nomute_copyright.py <output_path> <reels|post> --raw "ⓒ 2026. nomute(인스타그램). all rights reserved."

- 캔버스: reels=1080x1920, post=1080x1350 (완전 투명 배경)
- 폰트: NotoSansCJK-Regular 29px, 흰색 (#FFFFFF)
- 위치: Y=100, 수평 중앙 정렬
- 템플릿: ⓒ {년도}. {이름}({플랫폼}). all rights reserved.
"""

import sys
from PIL import Image, ImageFont, ImageDraw

SCALE = 2   # 2K 렌더(1080 기준 ×SCALE)

SPECS = {
    "reels": {"w": 1080, "h": 1920},
    "post":  {"w": 1080, "h": 1350},
}

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_SIZE = 29 * SCALE
TEXT_Y = 100 * SCALE
TEXT_COLOR = (255, 255, 255, 255)


def main():
    # ── 인자 파싱 ─────────────────────────────────────────
    if len(sys.argv) < 4:
        print("Usage:")
        print("  python3 nomute_copyright.py <output> <reels|post> <년도> <이름> <플랫폼>")
        print("  python3 nomute_copyright.py <output> <reels|post> --raw \"완성문구\"")
        sys.exit(1)

    output_path = sys.argv[1]
    fmt = sys.argv[2]

    if fmt not in SPECS:
        print(f"ERROR: 포맷은 reels 또는 post만 가능 (입력: {fmt})")
        sys.exit(1)

    # --raw 모드 vs 분리 인수 모드
    rest = sys.argv[3:]
    if rest[0] == "--raw":
        if len(rest) < 2:
            print("ERROR: --raw 뒤에 완성 문구를 입력해야 함")
            sys.exit(1)
        text = rest[1]
    else:
        if len(rest) < 3:
            print("ERROR: <년도> <이름> <플랫폼> 3개 인수 필요")
            sys.exit(1)
        year = rest[0]
        name = rest[1]
        platform = rest[2]
        text = f"ⓒ {year}. {name}({platform}). all rights reserved."

    spec = SPECS[fmt]
    canvas_w = spec["w"] * SCALE
    canvas_h = spec["h"] * SCALE

    # ── 캔버스 생성 (완전 투명) ───────────────────────────
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # ── 폰트 로드 ─────────────────────────────────────────
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    # ── 텍스트 너비 측정 → 수평 중앙 정렬 ────────────────
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    x_offset = bbox[0]
    y_offset = bbox[1]

    draw_x = (canvas_w - text_w) // 2 - x_offset
    draw_y = TEXT_Y - y_offset

    # ── 렌더링 ────────────────────────────────────────────
    draw.text((draw_x, draw_y), text, fill=TEXT_COLOR, font=font)

    # ── 저장 ──────────────────────────────────────────────
    canvas.save(output_path, format="PNG")

    # ── 검증 ──────────────────────────────────────────────
    import numpy as np
    arr = np.array(canvas)
    white = arr[:, :, 3] > 200
    if white.any():
        rows = np.where(np.any(white, axis=1))[0]
        cols = np.where(np.any(white, axis=0))[0]
        print(f"OK: {output_path} ({canvas.size},{canvas.mode}) "
              f"text_y={rows[0]}~{rows[-1]} text_x={cols[0]}~{cols[-1]}")
    else:
        print(f"WARN: no visible text in {output_path}")

    print(f"TEXT: {text}")


if __name__ == "__main__":
    main()
