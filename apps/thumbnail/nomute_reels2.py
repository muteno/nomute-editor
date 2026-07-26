"""nomute_reels2.py — 릴스 신규형태(상단 헤더 + 흰 영상영역).
강조(*) 없는 릴스 입력용. 기존 nomute_overlay.py와 별개(절대규칙1: 코드 불변).

레이아웃 (1080x1920, 첨부3 실측):
  - 베이스: 1번 빈배경(그라데이션+로고 포함) 에셋
  - 흰 영역: y590~1431 전체폭 (영상 들어갈 자리, 결과물에 포함)
  - 부제(1줄): 흰색, 중앙 / 제목(1줄): 초록(15,253,2), 중앙
  - 폰트: NotoSansCJK-Bold index=1, 가운데 정렬
  - 좌우 마진 MARGIN 유지(가용폭 AVAIL). 폭 초과 시 자간만 0→TR_MIN(-45)로
    줄여 맞춘다(폰트 크기 불변). 안 넘으면 자간0(레거시 단일 렌더로 동일).

템플릿 축(운영자 260726) — HDR_TPL:
  - 'nomute'(기본) = 위 레이아웃 그대로. tpl 미지정 호출 = 기존과 바이트 동일(회귀 0).
  - 'jinjja'(진짜예요) = 파란 밴드 베이스. 밴드 y0~605(색 9,49,136 균일)·하부 투명 유지 →
    산출도 투명 PNG(운영자 확정: 영상·사진 위에 얹는 프레임). 베이스에 구워진 샘플 문구를
    밴드색 사각형으로 덮고(wipe) 그 자리에 제목 1줄만 렌더. 부제 없음(입력칸은 read-only 잠금).
    가용폭 880(1080 기준 좌우 100 대칭) · 자간 시작 -10 → TR_MIN(-45) sweep.
    ※ 자막(nomute_overlay)의 fit_tracking limit 920/844·floor -30은 별개 경로 = 무접촉.
"""
import os

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))   # 베이스 자산 기준점 = 이 모듈 폴더(cwd 무관 · 워크플로/로컬 공통)
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
GREEN = (15, 253, 2)  # 형광그린 — 콘텐츠 상수 원복(운영자 260706 롤백 · 콘텐츠 색 = UI 팔레트와 별개 축, UI 개편에 동행 금지)
WHITE = (255, 255, 255)
JJ_BAND = (9, 49, 136)    # 진짜예요 헤더 밴드색 — 베이스 실측(전 행 균일) · 콘텐츠 상수 = UI 팔레트 별개 축(GREEN 선례)
SCALE = 2                 # 2K 렌더(1080 기준 ×SCALE). reels2_base.png(1080×1920)는 render()에서 ×SCALE 업스케일.
W, H = 1080 * SCALE, 1920 * SCALE
BAND = (590 * SCALE, 1431 * SCALE)   # 흰 영상영역 (top, bottom)
MARGIN = 60 * SCALE       # 좌우 마진 (주황박스 실측 좌44/우60 → 안전 60 대칭, 양쪽 박스 안)
AVAIL = W - 2 * MARGIN    # 가용폭
TR_MIN = -45              # 자간 하한 = em-상대(스케일 무관 · 기존 /th post sweep과 동일)

SUB_FS, SUB_Y = 66 * SCALE, 270 * SCALE       # 부제 폰트크기 / draw y
TITLE_FS, TITLE_Y = 90 * SCALE, 385 * SCALE   # 제목 폰트크기 / draw y

# 템플릿 스펙 — 값은 전부 1080 기준(render가 ×SCALE). 운영자 260726.
HDR_TPL = {
    'nomute': {
        'base': 'assets/reels2_base.png',
        'mode': 'RGB', 'save_fmt': None,   # None = 확장자 자동(기존 JPG 계약 유지)
        'margin': 60, 'tr_start': 0,
        'band': (590, 1431),               # 흰 영상영역 채움
        'wipe': None,
        'sub': True,                       # 부제 렌더(2줄 헤더)
    },
    'jinjja': {
        'base': 'assets/jinjja_header_base.png',
        'mode': 'RGBA', 'save_fmt': 'PNG',  # 하부 투명 유지 = 프레임 산출(운영자 확정)
        'margin': 100, 'tr_start': -10,
        'band': None,                       # 베이스가 밴드+투명 하부 = 흰칸 안 그림
        'wipe': (0, 460, 1080, 100),        # 샘플 문구 덮기 — 실측(문구 잉크 y486~538 · 로고 하단 403 무접촉)
        'sub': False,                       # 제목 1줄만(운영자 "무조건 1줄")
        'title_fs': 56, 'title_y': 469,     # 잉크높이 53 역산 fs56 · draw y = 잉크탑 486 − 'la' 오프셋 17
        'title_color': WHITE,               # 베이스 샘플 문구색 실측 = 순백
    },
}


def _line_width(text, font, tr, fs):
    """tracking tr(1/1000 em) 적용 시 advance 합 폭."""
    if not text:
        return 0.0
    tp = tr / 1000.0 * fs
    return sum(font.getlength(ch) for ch in text) + tp * (len(text) - 1)


def _fit_tr(text, font, fs, avail=None, tr_start=0):
    """자간 tr_start→-1…로 줄여 avail 안에 드는 첫 tr. 끝까지 넘으면 TR_MIN.
    tr_start = 시작 자간(노뮤트 0 · 진짜예요 -10) · avail 생략 = 모듈 AVAIL(노뮤트)."""
    av = AVAIL if avail is None else avail
    for tr in range(tr_start, TR_MIN - 1, -1):
        if _line_width(text, font, tr, fs) <= av:
            return tr
    return TR_MIN


def _draw_line(d, text, y, font, color, fs, avail=None, tr_start=0):
    """가운데 정렬. avail 이내면 단일 렌더(레거시 동일·자간 tr_start=0),
    초과 시 글자별 tracking으로 자간만 좁힘(폰트 크기 불변). 적용 tr 반환."""
    av = AVAIL if avail is None else avail
    if tr_start == 0 and _line_width(text, font, 0, fs) <= av:
        bbox = d.textbbox((0, 0), text, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2 - bbox[0]
        d.text((x, y), text, font=font, fill=color)
        return 0
    tr = _fit_tr(text, font, fs, av, tr_start)
    tp = tr / 1000.0 * fs
    advs = [font.getlength(ch) for ch in text]
    total = sum(advs) + tp * (len(text) - 1)
    x = (W - total) / 2.0
    for ch, adv in zip(text, advs):
        d.text((x, y), ch, font=font, fill=color)
        x += adv + tp
    return tr


def render(sub, title, base_path, out,
           sub_fs=SUB_FS, sub_y=SUB_Y, title_fs=TITLE_FS, title_y=TITLE_Y,
           tpl='nomute'):
    """헤더형 렌더. tpl 미지정·미등록 = 'nomute' = 기존 동작 그대로(회귀 0).
    base_path 생략(None) 시 템플릿 기본 베이스 사용."""
    spec = HDR_TPL.get(tpl) or HDR_TPL['nomute']
    avail = W - 2 * spec['margin'] * SCALE      # 노뮤트 1920(=AVAIL) · 진짜예요 1760(=880×SCALE)
    tr0 = spec['tr_start']
    img = Image.open(base_path or os.path.join(_HERE, spec['base'])).convert(spec['mode'])
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)   # 베이스(1080×1920) → 2K 업스케일
    d = ImageDraw.Draw(img)
    if spec['band']:
        d.rectangle([0, spec['band'][0] * SCALE, W, spec['band'][1] * SCALE], fill=WHITE)
    if spec['wipe']:                              # 베이스에 구워진 샘플 문구 덮기(운영자 "저 자리를 전경색으로 덮고")
        wx, wy, ww, wh = [v * SCALE for v in spec['wipe']]
        d.rectangle([wx, wy, wx + ww - 1, wy + wh - 1], fill=JJ_BAND)
    sub_tr = None
    if spec['sub']:
        sub_tr = _draw_line(d, sub, sub_y,
                            ImageFont.truetype(FONT, sub_fs, index=1), WHITE, sub_fs,
                            avail, tr0)
    t_fs = spec.get('title_fs', title_fs // SCALE) * SCALE
    t_y = spec.get('title_y', title_y // SCALE) * SCALE
    t_col = spec.get('title_color', GREEN)
    title_tr = _draw_line(d, title, t_y,
                          ImageFont.truetype(FONT, t_fs, index=1), t_col, t_fs,
                          avail, tr0)
    img.save(out, spec['save_fmt']) if spec['save_fmt'] else img.save(out)
    return {'out': out, 'sub_tr': sub_tr, 'title_tr': title_tr, 'tpl': tpl}
