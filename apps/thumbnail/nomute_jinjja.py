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

노뮤트 무접촉 보증: 이 파일은 자기 상수만 쓴다. 노뮤트 헤더 축(MARGIN 60 / AVAIL 960 /
자간 시작 0)과 자막 축(fit_tracking limit 920·844 / floor -45·-30)은 어느 것도 참조·변경하지 않는다.
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
TXT_FS, TXT_Y = 56, 469      # fs = 샘플 잉크높이 53 역산 실측 / draw y = 잉크탑 486 − PIL 'la' 앵커 오프셋 17
MARGIN = 100                 # 좌우 마진(운영자 확정 100/100)
AVAIL = W - 2 * MARGIN * SCALE   # 가용폭 = 880×SCALE = 1760
TR_START = -10               # 자간 시작(운영자 확정 · 노뮤트 0/-1과 별개 축)
TR_MIN = -45                 # 자간 하한 = em-상대(스케일 무관 · reels2 TR_MIN 동값)


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
    """가운데 정렬 + 자간 압축. reels2.py:44-60 축자 계승.
    진짜예요는 시작 자간이 -10이라 '자간0 통줄 렌더' 단축 경로가 없다(항상 글자별 렌더).
    적용 tr 반환."""
    tr = _fit_tr(text, font, fs)
    tp = tr / 1000.0 * fs
    advs = [font.getlength(ch) for ch in text]
    total = sum(advs) + tp * (len(text) - 1)
    x = (W - total) / 2.0
    for ch, adv in zip(text, advs):
        d.text((x, y), ch, font=font, fill=color)
        x += adv + tp
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


def render_overlay(fmt, lines, out, opacity=None, tracking=None, lm_offsets=None, base_path=None):
    """진짜예요 오버레이 1장 → 투명 RGBA PNG. nomute_overlay.generate(:138-171) 스택 축자 계승."""
    from nomute_overlay import SPECS, FONT_PATH, mk_grad, mk_shadow, draw_t, parse   # 절대규칙1 = import만

    sp = SPECS[fmt]                      # 노뮤트 값 그대로(운영자 "글자 배선 그대로 적용")
    S = SCALE
    cw, chh = sp['w'] * S, sp['h'] * S
    fs = sp['fs'] * S
    fnt = ImageFont.truetype(FONT_PATH, fs, index=1)
    tr_val = tracking if tracking is not None else sp['tr']
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
    cy = sp['ty'] * S
    for i, ln in enumerate(lines):
        cx = sp['lm'] * S + (lm_offsets[i] * S if lm_offsets and i < len(lm_offsets) else 0)
        for st, stx in parse(ln):
            co = (15, 253, 2) if st == 'h' else (255, 255, 255)   # 콘텐츠 산출물 색(generate:160 동일 축)
            cx = draw_t(dr, cx, cy, stx, fnt, co, tp, sp['stroke'])
        cy += sp['lh'] * S

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
