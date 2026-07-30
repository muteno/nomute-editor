"""nomute_jinjja.py — 「진짜예요」 템플릿(운영자 260726).

절대규칙1(00_지침 §절대 규칙 1) 준수 — `nomute_overlay.py` / `nomute_compose.py` /
`nomute_copyright.py` / `nomute_reels2.py` 네 파일은 **내용 수정 0, import만**.
이 파일은 `nomute_reels2.py`의 문법을 100% 축자 계승한 5번째 형태 모듈이다
(신규 형태 = 신규 파일 = reels2.py:2 "기존 nomute_overlay.py와 별개" 선례).

헤더형 레이아웃 (1080x1920 · 베이스 실측):
  - 베이스: assets/jinjja_header_base.png — 상단 파란 밴드 y0~605(색 9,49,136 완전 균일) +
    밴드 안에 로고가 이미 구워짐(잉크 x219~862 / y145~403 · 가로 정중앙) + y606 이하 전부 투명
  - 베이스에 구워진 샘플 문구(잉크 x103~975 / y486~538)를 WIPE 사각형으로 덮고
    그 자리에 문구 1줄만 가운데 정렬 렌더(운영자 "저 자리를 전경색으로 덮고 그 자리
    기억해놧다가 그 자리에 문구들어가게하면됨" · "입력할 수 있는 글자는 무조건 1줄")
  - 좌우 마진 100/100 → 가용폭 880(운영자 "1080px일때 좌우 100 100 해서 880안에 들어가야한다")
  - 폭 초과 시 자간만 TR_START(-10)→TR_MIN(-45)로 줄여 맞춘다(폰트 크기 불변 · reels2 _fit_tr 동형)
    운영자 "-10 마진을 기준으로해서 -45까지 땅겨서 더 들어갈 수 있게하는거 기존에 이미 그러고있잖아"
  - 하부 투명 유지 → RGBA PNG 산출(운영자 확정: 영상·사진 위에 얹는 프레임)
    ⚠ reels2.py:65의 `convert('RGB')`는 계승하지 않는다(알파 즉사 = 투명 프레임 불가)

노뮤트 무접촉 보증: 노뮤트 헤더 축(MARGIN 60 / AVAIL 960 / 자간 시작 0)과 자막 축(SPECS lm·tr /
fit_tracking limit 920·844 / floor -45·-30)의 값을 **변경하지 않는다**(파일 무접촉 = 절대규칙1).
⚠ 260728 개정: 오버레이형 가로축은 이제 노뮤트 자막 축을 **참조(계승)** 한다 — 운영자
"진짜예요일 때 좌측정렬이여야 하는데, 노뮤트때 나오는거랑 똑같이 적용". 헤더형은 종전대로 자기 상수만 쓴다.
"""
import os

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))   # 베이스 자산 기준점 = 이 모듈 폴더(cwd 무관 · 워크플로/로컬 공통)
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"   # reels2.py:14 동일 · index=1 고정
WHITE = (255, 255, 255)          # 베이스 샘플 문구색 실측 = 순백
BAND_COL = (9, 49, 136)          # 밴드색 — 베이스 실측(전 행 균일) · 콘텐츠 상수 = UI 팔레트와 별개 축(reels2 GREEN 선례)
SCALE = 2                        # 2K 렌더(1080 기준 ×SCALE) — ⚠ nomute_overlay·nomute_compose SCALE과 동값 필수
W, H = 1080 * SCALE, 1920 * SCALE

BASE = 'assets/jinjja_header_base.png'   # 모듈 폴더 기준 상대(_HERE로 결합)
WIPE = (0, 460, 1080, 100)   # 샘플 문구 덮기 (x, y, w, h · 1080 기준) — 로고 잉크 하단 403 무접촉·밴드 하단 605 안
TXT_FS, TXT_Y = 70, 457      # fs 70 = 구 56의 125%(운영자 260726 "사이즈 125%로 변경하자 너무 작네") · draw y 457 = 잉크 중심 512.0 유지(구 fs56/y469의 중심 512.5 · Δ-0.5px 실측) — 밴드 하단 605 여유 60.5px · 로고 잉크 하단 403 여유 76.5px
MARGIN = 100                 # 좌우 마진(운영자 확정 100/100)
AVAIL = W - 2 * MARGIN * SCALE   # 가용폭 = 880×SCALE = 1760
TR_START = -10               # 자간 시작(운영자 확정 · 노뮤트 0/-1과 별개 축)
TR_MIN = -45                 # 자간 하한 = em-상대(스케일 무관 · reels2 TR_MIN 동값)
HDR_EMPH = (255, 225, 61)    # 헤더 문구 **강조** = 골드레몬(운영자 260730 "**로 하면 강조 … 노란색 가까운 색") — index :root --accent-2/--accent-4/--amber #FFE13D 동값(발행 콘텐츠 색 축 · UI 재유입 아님 · 자막 강조 OV_EMPH와 별개 축)


def _line_width(text, font, tr, fs):
    """tracking tr(1/1000 em) 적용 시 advance 합 폭. reels2.py:28-33 축자 계승."""
    if not text:
        return 0.0
    tp = tr / 1000.0 * fs
    return sum(font.getlength(ch) for ch in text) + tp * (len(text) - 1)


def _fit_tr(text, font, fs):
    """자간 TR_START→-1…로 줄여 AVAIL 안에 드는 첫 tr. 끝까지 넘으면 TR_MIN.
    reels2.py:36-41 축자 계승 — 시작값만 0 → TR_START(-10)."""
    for tr in range(TR_START, TR_MIN - 1, -1):
        if _line_width(text, font, tr, fs) <= AVAIL:
            return tr
    return TR_MIN


def _draw_line(d, text, y, font, color, fs):
    """가운데 정렬 + 자간 압축 + **강조**(골드레몬). reels2.py:44-60 축자 계승.
    진짜예요는 시작 자간이 -10이라 '자간0 통줄 렌더' 단축 경로가 없다(항상 글자별 렌더).

    강조(운영자 260730) = 자막과 같은 별표 문법(1~2개 = 델리미터 토글 · 3+ = 리터럴) →
    파서는 `nomute_overlay.parse` 그대로 재사용(절대규칙1 = import만 · 파서 4면 일치 유지).
    ⚠ 별표는 **폭 0** = 자간 sweep·가운데 정렬 계산에 안 들어간다(마커 제거분 plain으로만 측정).
    적용 tr 반환."""
    from nomute_overlay import parse   # 절대규칙1 = import만(수정 0)

    segs = parse(text or '')
    plain = ''.join(t for _, t in segs)   # 별표 제거분 = 폭·자간·중앙정렬의 유일한 기준
    tr = _fit_tr(plain, font, fs)
    if not plain:
        return tr
    tp = tr / 1000.0 * fs
    advs = [font.getlength(ch) for ch in plain]
    total = sum(advs) + tp * (len(plain) - 1)
    x = (W - total) / 2.0
    i = 0
    for st, stx in segs:
        co = HDR_EMPH if st == 'h' else color   # 강조 = 골드레몬 · 일반 = 순백(호출자 color)
        for ch in stx:
            d.text((x, y), ch, font=font, fill=co)
            x += advs[i] + tp
            i += 1
    return tr


def render_header(line, out, base_path=None, fs=TXT_FS, ty=TXT_Y):
    """진짜예요 헤더형 1줄 렌더 → 투명 PNG. reels2.render() 문법 계승."""
    img = Image.open(base_path or os.path.join(_HERE, BASE)).convert('RGBA')   # ⚠ RGBA(투명 유지)
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)   # 베이스(1080×1920) → 2K 업스케일
    d = ImageDraw.Draw(img)
    wx, wy, ww, wh = [v * SCALE for v in WIPE]
    d.rectangle([wx, wy, wx + ww - 1, wy + wh - 1], fill=BAND_COL + (255,))   # 샘플 문구 덮기(불투명)
    tr = _draw_line(d, line or '', ty * SCALE,
                    ImageFont.truetype(FONT, fs * SCALE, index=1), WHITE, fs * SCALE)
    img.save(out, format='PNG')
    assert Image.open(out).mode == 'RGBA', 'MODE ERROR: 투명 PNG 아님'   # overlay.py:170-171 검증 관례 계승
    return {'out': out, 'tr': tr, 'tpl': 'jinjja'}


# ── 오버레이형(릴스 9:16 · 포스트 4:5) ───────────────────────────────────────
# 운영자 260726 "릴스랑 포스트 오버레이형은 opa가 들어가야겠지. 이미지 맨 아래 그 위에
# opa 오버레이 그다음에 ci … 그냥 로고랑 로고 위치랑 글자 들어가는 형태, 조건만 다른거야"
# = 노뮤트 오버레이(nomute_overlay.generate) 스택·값 100% 계승, 로고 레이어만 교체.
#   레이어(아래→위): 투명 → OPA 스크림(mk_grad) → (CI+글자) 그림자 → CI → 글자
#   글자 배선(fs·lh·tr·lm·ty)·그라데 곡선·OPA 스케일 = SPECS 값 그대로 계승(신규 창작 0)
#   로고 = mk_logo(임베드 base64) 대신 워터마크가 이미 구워진 진짜예요 베이스 PNG 합성
#          (베이스 실측: 릴스 잉크 x362~721/y1010~1154 중앙 · 포스트 x108~500/y654~796)
JJ_BASE = {'reels': 'assets/jinjja_reels_base.png', 'post': 'assets/jinjja_post_base.png'}

# 진짜예요 오버레이 축(운영자 260728 개정 "진짜예요일 때 좌측정렬이여야 하는데, 노뮤트때 나오는거랑
# 똑같이 적용") — 가로축(정렬·좌마진 lm·가용폭·자간 sweep·따옴표 들여쓰기)은 **노뮤트 자막 축 그대로**
# = SPECS[fmt]['lm'] 계승 + 워크플로 fit_tracking(limit 920/844 · floor -45/-30)과 동일 한도.
#   구 260726 축(가운데 정렬 · 좌우 150 · 폭 780)은 폐기 — 서버 자간은 이미 노뮤트 fit_tracking을
#   받고 있었으므로(thumb-make.yml:166) 이 개정으로 정렬·폭·자간 3축이 한 번에 정합된다.
# 진짜예요 고유로 남는 것 = CI 베이스(로고 구움) · 강조색 네온 파랑 · 첫 줄 y/글자크기/줄간(OV_SPEC).
# ⚠ 260730 개정: **릴스만 가운데 정렬**(운영자 "릴스 진짜예요는 릴스 오버레이 가운데 정렬로") — 폭·자간 한도(844/-30)는
#   그대로 노뮤트 계승이고 시작 x 계산만 좌/우 마지노선(lm 101 / rm 135) 박스 중심으로 바뀐다. 포스트 = 좌측정렬 유지.
OV_LIMIT = {'post': 920, 'reels': 844}   # 워크플로 fit_tracking limit 1:1 미러(post lm85/rm75 · reels lm101/rm135)
OV_FLOOR = {'post': -45, 'reels': -30}   # 워크플로 fit_tracking floor 1:1 미러(sweep 하한)
OV_RM = {'post': 75, 'reels': 135}       # 우 마지노선 = 워크플로 fit_tracking 주석 "post lm85/rm75 · reels lm101/rm135" 1:1 미러(좌 마지노선 = SPECS lm)
OV_CENTER = {'post': False, 'reels': True}   # 릴스만 가운데 정렬(운영자 260730 "릴스 진짜예요는 릴스 오버레이 가운데 정렬") — 중심 = 좌/우 마지노선 사이 박스 중심(101 … 1080-135) = 523이라 최대폭(844)에서도 양 마진 각각 보존 · 포스트는 260728 좌측정렬 유지
OV_EMPH = (56, 198, 255)               # 네온 파랑 = --bias-l1 #38C6FF 동값(발행 콘텐츠 색 축 · UI 팔레트 재유입 아님)
OV_PLAIN = (255, 255, 255)
# 첫 줄 y·글자크기·줄간 = 운영자가 플레이그라운드에서 고른 선택값 그대로(260726 · 정렬만 260728 개정)
#   릴스 = {"align":"center","ty":1214,"fs":76,"lh":96,"rule":false} ← 복사본 원문(align은 260728 좌측으로 개정)
#   포스트 = 운영자 "릴스형 오버레이도 그대로 가야돼. 얘는 오히려 쉬워 로고만 교체하면 되니까"
#     → fs·lh는 릴스 선택값 그대로(76·96) · ty는 **워터마크 아래 여백을 릴스와 동일(60px)** 로 환산:
#       릴스 워터마크 잉크 하단 1154 + 60 = 1214(운영자 선택값과 일치) →
#       포스트 워터마크 잉크 하단 796 + 60 = 856
OV_SPEC = {'reels': {'ty': 1214, 'fs': 76, 'lh': 96},
           'post':  {'ty': 856,  'fs': 76, 'lh': 96}}


def _ov_fit_tr(segs_lines, font, fs, fmt, start, lm_offsets=None):
    """전 줄이 노뮤트 가용폭(OV_LIMIT[fmt]) 안에 드는 전역 자간(start → OV_FLOOR[fmt]).

    워크플로 fit_tracking(thumb-make.yml:106-127) 미러 — 폭 측정만 알파 bbox 대신 draw_t 진행폭
    (잉크폭 bb + 자간) 합산 근사(폴백 전용 경로 · 정본 tracking은 러너가 계산해 넘긴다).
    따옴표 들여쓰기(lm_offsets)도 우측 한도를 침범하므로 노뮤트 widest와 동일하게 합산한다."""
    avail = OV_LIMIT[fmt] * SCALE
    floor = OV_FLOOR[fmt]
    def widest(tr):
        tp = tr / 1000.0 * fs
        w = 0
        for i, segs in enumerate(segs_lines):
            txt = ''.join(t for _, t in segs)
            if not txt:
                continue
            ink = sum(font.getbbox(ch)[2] - font.getbbox(ch)[0] for ch in txt)   # draw_t 진행폭 = 잉크폭
            off = (lm_offsets[i] * SCALE) if lm_offsets and i < len(lm_offsets) else 0
            w = max(w, ink + tp * (len(txt) - 1) + 5 + off)
        return w
    for tr in range(start, floor - 1, -1):
        if widest(tr) <= avail:
            return tr
    return floor


def _ov_line_w(segs, font, tp, stroke):
    """draw_t 진행폭 실측(스크래치 렌더 = 실제 배치와 동일 산식) — 가운데 정렬 시작 x 계산용.
    draw_t는 마지막 글자 뒤에도 tp를 더하므로 한 칸(tp) 뺀 값이 줄 폭이다."""
    from nomute_overlay import draw_t   # 절대규칙1 = import만

    txt = ''.join(t for _, t in segs)
    if not txt:
        return 0.0
    probe = Image.new('RGBA', (8, 8), (0, 0, 0, 0))   # 8×8 = 버리는 캔버스(글자는 화면 밖 y로 흘림 = 클리핑)
    return draw_t(ImageDraw.Draw(probe), 0, -10000, txt, font, OV_PLAIN, tp, stroke) - tp


def render_overlay(fmt, lines, out, opacity=None, tracking=None, lm_offsets=None, base_path=None):
    """진짜예요 오버레이 1장 → 투명 RGBA PNG. nomute_overlay.generate(:138-171) 스택 축자 계승."""
    from nomute_overlay import SPECS, FONT_PATH, mk_grad, mk_shadow, draw_t, parse   # 절대규칙1 = import만

    sp = SPECS[fmt]                      # 캔버스·그라데 곡선만 노뮤트 계승(글자 축은 OV_SPEC = 진짜예요 전용)
    ov = OV_SPEC[fmt]
    S = SCALE
    cw, chh = sp['w'] * S, sp['h'] * S
    fs = ov['fs'] * S
    fnt = ImageFont.truetype(FONT_PATH, fs, index=1)
    segs_lines = [parse(ln) for ln in lines]   # 강조 세그먼트(1~2별표=토글 · 3+=리터럴) — 폭 측정은 별표 제거분
    tr_val = tracking if tracking is not None else _ov_fit_tr(segs_lines, fnt, fs, fmt, sp['tr'], lm_offsets)
    tp = tr_val / 1000 * fs
    c = Image.new('RGBA', (cw, chh), (0, 0, 0, 0))

    gd = dict(sp['grad'])                # OPA 스케일 = generate:147-152 축자 계승
    if opacity is not None:
        op = max(0, min(100, opacity))
        max_a = 255 - min(gd.values())
        if max_a > 0:
            k = (op / 100 * 255) / max_a
            gd = {kk: max(0, min(255, 255 - int((255 - v) * k))) for kk, v in gd.items()}
    c = Image.alpha_composite(c, mk_grad(cw, chh, gd))

    ll = Image.open(base_path or os.path.join(_HERE, JJ_BASE[fmt])).convert('RGBA')   # CI 레이어 = 베이스(워터마크 구움)
    if ll.size != (cw, chh):
        ll = ll.resize((cw, chh), Image.LANCZOS)

    tx = Image.new('RGBA', (cw, chh), (0, 0, 0, 0))
    dr = ImageDraw.Draw(tx)
    cy = ov['ty'] * S
    for i, segs in enumerate(segs_lines):
        # 좌측정렬(운영자 260728 "노뮤트때 나오는거랑 똑같이") — generate:156-161 축자 계승:
        # 시작 x = lm×SCALE + 따옴표 들여쓰기 · 진행 = draw_t(잉크폭+자간) · 색만 진짜예요 축(네온 파랑).
        if OV_CENTER.get(fmt):
            # 릴스 = 가운데 정렬(운영자 260730) — 좌/우 마지노선 사이 박스 중심 기준(양 마진 각각 보존).
            # 따옴표 들여쓰기(lm_offsets)는 중앙 기준을 깨므로 미적용(연속줄 hanging indent = 좌측정렬 전용 장치).
            bl, br = sp['lm'] * S, cw - OV_RM[fmt] * S
            plain = ''.join(t for _, t in segs)
            cx = bl + (br - bl - _ov_line_w(segs, fnt, tp, sp['stroke'])) / 2.0
            # 중심 정의 = **글자 박스 중심**(draw_t 진행폭 기준 = 노뮤트 lm 의미축과 동일) → 최대폭 844에서 좌101/우135 정확.
            # 좌측 베어링 보정(라틴·숫자는 bb[0]>0 · 한글은 0 = 무동작) · 잔여 Δ = 글리프 내부 여백(실측 ≤2.3px = 광학 노이즈).
            # ⚠ 자간 하한(-30)으로도 844를 넘는 줄은 양쪽으로 흘러넘친다(구 좌측정렬은 우측만) — 프론트 자간 게이트가 그 발사를 이미 차단한다.
            if plain:
                cx -= (fnt.getbbox(plain[0])[0] + fnt.getbbox(plain[-1])[0]) / 2.0
        else:
            cx = sp['lm'] * S + (lm_offsets[i] * S if lm_offsets and i < len(lm_offsets) else 0)
        for st, stx in segs:
            co = OV_EMPH if st == 'h' else OV_PLAIN   # 강조 = 네온 파랑(운영자 260726 · 구 형광그린 폐기)
            cx = draw_t(dr, cx, cy, stx, fnt, co, tp, sp['stroke'])
        cy += ov['lh'] * S

    cb = Image.alpha_composite(ll, tx)
    c = Image.alpha_composite(c, mk_shadow(cb, S))
    c = Image.alpha_composite(c, ll)
    c = Image.alpha_composite(c, tx)
    assert c.mode == 'RGBA', f'MODE ERROR: {c.mode}'
    c.save(out, format='PNG')
    assert Image.open(out).mode == 'RGBA'
    return {'out': out, 'tr': tr_val, 'tpl': 'jinjja', 'fmt': fmt}


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 nomute_jinjja.py output.png '문구 1줄'                 # 헤더형")
        print("       python3 nomute_jinjja.py output.png --ov reels|post '줄1' ['줄2' …]  # 오버레이형")
        raise SystemExit(1)
    if sys.argv[2] == '--ov':
        print(render_overlay(sys.argv[3], sys.argv[4:], sys.argv[1]))
    else:
        print(render_header(sys.argv[2], sys.argv[1]))
