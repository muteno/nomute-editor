"""nomute_reels2.py — 릴스 신규형태(상단 헤더 + 흰 영상영역).
강조(*) 없는 릴스 입력용. 기존 nomute_overlay.py와 별개(절대규칙1: 기존 3파일 불변).

레이아웃 (1080x1920, 첨부3 실측):
  - 베이스: 1번 빈배경(그라데이션+로고 포함) 에셋
  - 흰 영역: y590~1431 전체폭 (영상 들어갈 자리, 결과물에 포함)
  - 부제(1줄): 흰색, 중앙
  - 제목(1줄): 초록(15,253,2), 중앙
  - 폰트: NotoSansCJK-Bold index=1, 자간0, 가운데 정렬
"""
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
GREEN = (15, 253, 2)
WHITE = (255, 255, 255)
W, H = 1080, 1920
BAND = (590, 1431)   # 흰 영상영역 (top, bottom)

# 기본 스펙 (실측 기반 — 렌더 대조로 튜닝)
SUB_FS, SUB_Y = 66, 270      # 부제 폰트크기 / draw y
TITLE_FS, TITLE_Y = 90, 385  # 제목 폰트크기 / draw y


def _center(d, text, y, font, color):
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2 - bbox[0]
    d.text((x, y), text, font=font, fill=color)


def render(sub, title, base_path, out,
           sub_fs=SUB_FS, sub_y=SUB_Y, title_fs=TITLE_FS, title_y=TITLE_Y):
    img = Image.open(base_path).convert('RGB')
    d = ImageDraw.Draw(img)
    d.rectangle([0, BAND[0], W, BAND[1]], fill=WHITE)
    _center(d, sub, sub_y, ImageFont.truetype(FONT, sub_fs, index=1), WHITE)
    _center(d, title, title_y, ImageFont.truetype(FONT, title_fs, index=1), GREEN)
    img.save(out)
    return out
