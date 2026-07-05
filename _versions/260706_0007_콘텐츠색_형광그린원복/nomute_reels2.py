"""nomute_reels2.py — 릴스 신규형태(상단 헤더 + 흰 영상영역).
강조(*) 없는 릴스 입력용. 기존 nomute_overlay.py와 별개(절대규칙1: 코드 불변).

레이아웃 (1080x1920, 첨부3 실측):
  - 베이스: 1번 빈배경(그라데이션+로고 포함) 에셋
  - 흰 영역: y590~1431 전체폭 (영상 들어갈 자리, 결과물에 포함)
  - 부제(1줄): 흰색, 중앙 / 제목(1줄): 터쿼이즈(0,238,210), 중앙
  - 폰트: NotoSansCJK-Bold index=1, 가운데 정렬
  - 좌우 마진 MARGIN 유지(가용폭 AVAIL). 폭 초과 시 자간만 0→TR_MIN(-45)로
    줄여 맞춘다(폰트 크기 불변). 안 넘으면 자간0(레거시 단일 렌더로 동일).
"""
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
GREEN = (0, 238, 210)  # 터쿼이즈(구 네온그린 · 브랜드 개편 동행 260705 — 상수명은 호환 유지)
WHITE = (255, 255, 255)
SCALE = 2                 # 2K 렌더(1080 기준 ×SCALE). reels2_base.png(1080×1920)는 render()에서 ×SCALE 업스케일.
W, H = 1080 * SCALE, 1920 * SCALE
BAND = (590 * SCALE, 1431 * SCALE)   # 흰 영상영역 (top, bottom)
MARGIN = 60 * SCALE       # 좌우 마진 (주황박스 실측 좌44/우60 → 안전 60 대칭, 양쪽 박스 안)
AVAIL = W - 2 * MARGIN    # 가용폭
TR_MIN = -45              # 자간 하한 = em-상대(스케일 무관 · 기존 /th post sweep과 동일)

SUB_FS, SUB_Y = 66 * SCALE, 270 * SCALE       # 부제 폰트크기 / draw y
TITLE_FS, TITLE_Y = 90 * SCALE, 385 * SCALE   # 제목 폰트크기 / draw y


def _line_width(text, font, tr, fs):
    """tracking tr(1/1000 em) 적용 시 advance 합 폭."""
    if not text:
        return 0.0
    tp = tr / 1000.0 * fs
    return sum(font.getlength(ch) for ch in text) + tp * (len(text) - 1)


def _fit_tr(text, font, fs):
    """자간 0→-1…로 줄여 AVAIL 안에 드는 첫 tr. 끝까지 넘으면 TR_MIN."""
    for tr in range(0, TR_MIN - 1, -1):
        if _line_width(text, font, tr, fs) <= AVAIL:
            return tr
    return TR_MIN


def _draw_line(d, text, y, font, color, fs):
    """가운데 정렬. AVAIL 이내면 단일 렌더(레거시 동일·자간0),
    초과 시 글자별 tracking으로 자간만 좁힘(폰트 크기 불변). 적용 tr 반환."""
    if _line_width(text, font, 0, fs) <= AVAIL:
        bbox = d.textbbox((0, 0), text, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2 - bbox[0]
        d.text((x, y), text, font=font, fill=color)
        return 0
    tr = _fit_tr(text, font, fs)
    tp = tr / 1000.0 * fs
    advs = [font.getlength(ch) for ch in text]
    total = sum(advs) + tp * (len(text) - 1)
    x = (W - total) / 2.0
    for ch, adv in zip(text, advs):
        d.text((x, y), ch, font=font, fill=color)
        x += adv + tp
    return tr


def render(sub, title, base_path, out,
           sub_fs=SUB_FS, sub_y=SUB_Y, title_fs=TITLE_FS, title_y=TITLE_Y):
    img = Image.open(base_path).convert('RGB')
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)   # 베이스(1080×1920) → 2K 업스케일
    d = ImageDraw.Draw(img)
    d.rectangle([0, BAND[0], W, BAND[1]], fill=WHITE)
    sub_tr = _draw_line(d, sub, sub_y,
                        ImageFont.truetype(FONT, sub_fs, index=1), WHITE, sub_fs)
    title_tr = _draw_line(d, title, title_y,
                          ImageFont.truetype(FONT, title_fs, index=1), GREEN, title_fs)
    img.save(out)
    return {'out': out, 'sub_tr': sub_tr, 'title_tr': title_tr}
