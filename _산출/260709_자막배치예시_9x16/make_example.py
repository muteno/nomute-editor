# 릴스 9:16 자막 배치 예시 이미지 생성 — 원본 스틸을 정확히 9:16으로 크롭·업스케일 후
# /ly 분리 모드 조각(EN+KR 1:1 쌍)을 하단 안전영역 위에 오버레이.
# 스타일 계승: apps/thumbnail/nomute_reels2.py — NotoSansCJK-Bold index=1 · 콘텐츠 형광그린 (15,253,2)
# 실행: python3 make_example.py  (이 폴더에서)
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
SRC = HERE / "원본.webp"
OUT = HERE / "자막예시_9x16.png"
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
GREEN = (15, 253, 2)   # 콘텐츠 브랜드 텍스트색 — UI 팔레트와 별개 축(CLAUDE.md §핵심명령 3-b-1)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
W, H = 1080, 1920      # 릴스 표준 캔버스 = 정확히 9:16

im = Image.open(SRC).convert("RGB")
w, h = im.size
target = 9 / 16
if w / h > target:      # 가로가 남으면 좌우 중앙 크롭
    nw = round(h * target)
    x0 = (w - nw) // 2
    im = im.crop((x0, 0, x0 + nw, h))
else:                   # 세로가 남으면 상하 중앙 크롭
    nh = round(w / target)
    y0 = (h - nh) // 2
    im = im.crop((0, y0, w, y0 + nh))
im = im.resize((W, H), Image.LANCZOS)

# 자막 조각 — ly 지침 v2.8의 실측 예(분리 모드 조각 1:1 쌍)
EN = "I know everything is meant to be"
KR = "모든 건 다 의미가 있어"

d = ImageDraw.Draw(im)

def draw_center(text, y, fs, color, stroke):
    f = ImageFont.truetype(FONT, fs, index=1)
    bbox = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
    x = (W - (bbox[2] - bbox[0])) // 2 - bbox[0]
    d.text((x, y), text, font=f, fill=color,
           stroke_width=stroke, stroke_fill=BLACK)

# 배치 = 세로 약 73% 지점(하단 릴스 캡션·UI 존 회피) · 중앙 정렬 · EN 위 + KR 아래
en_fs, kr_fs, gap = 48, 82, 30
y = 1355
draw_center(EN, y, en_fs, GREEN, 5)
draw_center(KR, y + en_fs + gap, kr_fs, WHITE, 7)

im.save(OUT)
print("saved:", OUT, im.size)
