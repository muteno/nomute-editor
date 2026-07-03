# LOVE 마퀴 펫 에셋 재작화기(260703 v3 · 운영자 목표 디자인) — 간판부를 전구 테두리 마퀴로 재작화.
# 입력 = v2 에셋(정본 백업: _versions/260703_2234_마퀴간판전구_120중앙_탭분리/love_marquee.webp)
# 출력 = viewer/love_marquee.webp(v3). 검은 테두리+전구 점(NOW SHOWING 라벨 겹침 점만 제외·운영자 지시)
# + 크림 패널 + LOVE♥ 5×7 픽셀폰트 재작화(셀4px = 원본의 ~120%·세로 중앙). 사다리·펫·글로우 = 원본 유지.
# 펫 복원 = 정적 기준프레임(f70) 차분 + 공간 게이트(x≥188 ∨ 플레이트 위) — 옛 텍스트 고스트 차단.
import math, sys
import numpy as np
from PIL import Image, ImageDraw

SRC = 'viewer/love_marquee.webp'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'viewer/love_marquee_v3.webp'

# ── 실측 기하(f70 기준) ──
PX0, PY0, PX1, PY1 = 58, 19, 208, 80        # 크림 패널 bbox(inclusive)
OM = 7                                       # 테두리 밴드 폭 → 외곽 = 패널 +7px
OX0, OY0, OX1, OY1 = PX0-OM, PY0-OM, PX1+OM, PY1+OM
PLX0, PLY0, PLX1, PLY1 = 87, 9, 178, 18      # NOW SHOWING 플레이트 bbox
TX0, TY0, TX1, TY1 = 80, 42, 186, 64         # LOVE♥ 텍스트 bbox
LIT = set(range(48, 84))                     # 점등 프레임
DIM = {48: 187/211, 49: 199/211, 50: 206/211, 51: 206/211, 52: 206/211, 53: 208/211}
CREAM = (248, 238, 200)
FRAME_C = (33, 26, 21)                       # 이미지1 느낌의 웜 블랙
BULB = (250, 242, 212)
S = 4                                        # 슈퍼샘플

def perimeter_points(x0, y0, x1, y1, rad, step):
    """둥근사각 둘레를 step 간격으로 순회(전구 자리)."""
    segs = []
    # 직선 4변(모서리 arc 제외)
    segs.append((('h', y0), x0+rad, x1-rad))           # top
    segs.append((('v', x1), y0+rad, y1-rad))           # right
    segs.append((('h', y1), x1-rad, x0+rad))           # bottom(역방향)
    segs.append((('v', x0), y1-rad, y0+rad))           # left(역방향)
    arcs = [((x1-rad, y0+rad), -90, 0), ((x1-rad, y1-rad), 0, 90),
            ((x0+rad, y1-rad), 90, 180), ((x0+rad, y0+rad), 180, 270)]
    pts, acc = [], 0.0
    def emit(x, y):
        pts.append((x, y))
    # top → arc(우상) → right → arc(우하) → bottom → arc(좌하) → left → arc(좌상)
    order = [segs[0], arcs[0], segs[1], arcs[1], segs[2], arcs[2], segs[3], arcs[3]]
    for seg in order:
        if isinstance(seg[0], tuple) and seg[0][0] in ('h', 'v'):
            kind, c = seg[0]
            a, b = seg[1], seg[2]
            L = abs(b - a); n = max(1, int(L / step)); direc = 1 if b > a else -1
            for i in range(n):
                t = a + direc * (i * L / n)
                emit(*((t, c) if kind == 'h' else (c, t)))
        else:
            (cx, cy), a0, a1 = seg
            L = math.pi * rad / 2; n = max(1, int(L / step))
            for i in range(n):
                ang = math.radians(a0 + (a1 - a0) * i / n)
                emit(cx + rad * math.cos(ang), cy + rad * math.sin(ang))
    return pts

def build_sign(love_bmp, plate_crop):
    W, H = 263, 240
    hi = Image.new('RGBA', (W*S, H*S), (0, 0, 0, 0))
    d = ImageDraw.Draw(hi)
    d.rounded_rectangle((OX0*S, OY0*S, (OX1+1)*S-1, (OY1+1)*S-1), radius=11*S, fill=FRAME_C+(255,))
    d.rounded_rectangle((PX0*S, PY0*S, (PX1+1)*S-1, (PY1+1)*S-1), radius=7*S, fill=CREAM+(255,))
    # 전구: 밴드 중심선 궤도 · 라벨(x 83~182) 위 top 구간은 스킵 = "겹치는 점 제거"
    ins = OM/2.0
    pts = perimeter_points(OX0+ins, OY0+ins, OX1+1-ins, OY1+1-ins, 11-ins, step=8.4)
    for (x, y) in pts:
        if y < PY0 and (PLX0-4) <= x <= (PLX1+4):
            continue
        r = 1.6
        d.ellipse(((x-r)*S, (y-r)*S, (x+r)*S, (y+r)*S), fill=BULB+(255,))
    sign = hi.resize((W, H), Image.LANCZOS)
    sign.alpha_composite(plate_crop, (PLX0, PLY0))            # 플레이트 원본 재사용
    nw, nh = love_bmp.size                                    # 이미 120% 크기로 작화됨
    cx, cy = (PX0+PX1+1)//2, (PY0+PY1+1)//2                   # 패널 중심 = 세로 중앙정렬
    sign.alpha_composite(love_bmp, (cx-nw//2, cy-nh//2))
    return sign

# 5×7 픽셀 폰트 재작화 — 셀 4px → 글자높이 28px = 원본 23px의 ~120%(운영자 지시)
GLYPHS = {
    'L': ["X....", "X....", "X....", "X....", "X....", "X....", "XXXXX"],
    'O': [".XXX.", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."],
    'V': ["X...X", "X...X", "X...X", "X...X", "X...X", ".X.X.", "..X.."],
    'E': ["XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "XXXXX"],
    '♥': [".XX.XX.", "XXXXXXX", "XXXXXXX", "XXXXXXX", ".XXXXX.", "..XXX..", "...X..."],
}
RED, RED_D = (172, 62, 58), (138, 46, 44)

def draw_love(cell=4, gap=6):
    seq = ['L', 'O', 'V', 'E', '♥']
    wcells = [len(GLYPHS[c][0]) for c in seq]
    W = sum(w*cell for w in wcells) + gap*(len(seq)-1)
    H = 7*cell
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 0
    for c, wc in zip(seq, wcells):
        rows = GLYPHS[c]
        for cy_ in range(7):
            for cx_ in range(wc):
                if rows[cy_][cx_] == 'X':
                    below = cy_ == 6 or rows[cy_+1][cx_] != 'X'
                    col = RED_D if below else RED   # 하단 에지 셀 = 어두운 베벨(원본 질감 계승)
                    d.rectangle((x+cx_*cell, cy_*cell, x+(cx_+1)*cell-1, (cy_+1)*cell-1), fill=col+(255,))
        x += wc*cell + gap
    return img

def main():
    im = Image.open(SRC)
    n = im.n_frames
    im.seek(70); ref = np.array(im.convert('RGBA')).astype(int)
    # LOVE♥ 비트맵(빨강만 소프트 알파 추출 — AA 가장자리 보존)
    love_bmp = draw_love()   # 노이즈 소스 구제 대신 그리드 재작화(목표 이미지의 균일 픽셀 폰트)
    im.seek(70)
    plate_crop = im.convert('RGBA').crop((PLX0, PLY0, PLX1+1, PLY1+1))
    sign = build_sign(love_bmp, plate_crop)

    frames, durs = [], []
    for fi in range(n):
        im.seek(fi)
        durs.append(im.info.get('duration', 100))
        fr = im.convert('RGBA')
        if fi in LIT:
            out = fr.copy()
            layer = sign
            if fi in DIM:
                f = DIM[fi]
                arr = np.array(sign).astype(float)
                arr[..., :3] *= f
                layer = Image.fromarray(arr.astype(np.uint8), 'RGBA')
            out.alpha_composite(layer)
            # 펫이 간판 앞을 지나는 프레임 = 원본 펫 픽셀 복원.
            # 분리 축 = 정적 기준(f70)과의 차분: 움직이는 건 펫뿐(텍스트·패널·플레이트 = 정적이라 자동 제외).
            a = np.array(fr).astype(int)
            rr_, gg, al = a[..., 0], a[..., 1], a[..., 3]
            diff = np.abs(a[..., :3] - ref[..., :3]).sum(-1)
            pig = (al > 150) & (diff > 90) & ((rr_ - gg) > 25)
            pig[:OY0, :] = False; pig[OY1+1:, :] = False
            pig[:, :OX0] = False; pig[:, OX1+1:] = False
            # 공간 게이트: 펫 동선 = 우측(x≥188) 또는 플레이트 상단(y≤패널 top)뿐 —
            # 점등 팝인 순간 옛 텍스트(x80~186·y42~64)가 '움직임'으로 오인되는 고스트 원천 차단
            allow = np.zeros_like(pig)
            allow[:, 188:] = True
            allow[:PY0+1, :] = True
            pig &= allow
            if pig.any():
                oa = np.array(out)
                oa[pig] = np.array(fr)[pig]
                out = Image.fromarray(oa, 'RGBA')
            frames.append(out)
        else:
            frames.append(fr)
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=durs,
                   loop=0, quality=85, method=6)
    chk = Image.open(OUT)
    print('저장:', OUT, '프레임', chk.n_frames, '크기', chk.size)
    import os; print('용량 %.0fKB (원본 %.0fKB)' % (os.path.getsize(OUT)/1024, os.path.getsize(SRC)/1024))

if __name__ == '__main__':
    main()
