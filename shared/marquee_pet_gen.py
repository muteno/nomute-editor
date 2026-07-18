# LOVE 마퀴 펫 에셋 재작화기(260704 v4 · 운영자 "LOVE 크기 원본 유지") — v3 전구 테두리 전광판은 유지하되,
# LOVE♥ 텍스트의 120% 확대·세로중앙정렬을 롤백해 원본 크기·원본 코럴색으로 복원.
# 입력 = v2 원본(전구·120% 이전): _versions/260703_2119_배너_LOVE마퀴펫/love_marquee.webp
# 출력 = viewer/love_marquee.webp. 전구 테두리+크림 패널+플레이트+펫 = 유지 · LOVE♥ = v2 원본 크롭(원본 크기)을 원위치 합성.
# 펫 복원 = 정적 기준프레임(f70) 차분 + 공간 게이트(x≥188 ∨ 플레이트 위) — 옛 텍스트 고스트 차단.
# ⚠ 수동 실행 전용(워크플로·훅 미배선 — 평의회 o9 260718) · 기본 산출 viewer/love_marquee.webp = Q169에서 레포 제거(소비 0·마퀴 폐지 260705) — 재생성 = 로컬 확인용, 커밋 재개는 운영자 지시로만.
import math, sys
import numpy as np
from PIL import Image, ImageDraw

SRC = '_versions/260703_2119_배너_LOVE마퀴펫/love_marquee.webp'   # v2 원본(전구·120% 이전 = 원본 크기 텍스트 보유)
PLATE_SRC = '_versions/260704_0720_마퀴펫_LOVE원본크기복원/love_marquee.webp'  # 직전 v3(반듯한 NOW SHOWING 플레이트 — v2 원본은 라벨이 기울어져 크롭 어긋남)
OUT = sys.argv[1] if len(sys.argv) > 1 else 'viewer/love_marquee.webp'

# ── 실측 기하(f70 기준) ──
PX0, PY0, PX1, PY1 = 58, 19, 208, 80        # 크림 패널 bbox(inclusive)
OM = 7                                       # 테두리 밴드 폭 → 외곽 = 패널 +7px
OX0, OY0, OX1, OY1 = PX0-OM, PY0-OM, PX1+OM, PY1+OM
PLX0, PLY0, PLX1, PLY1 = 87, 9, 178, 18      # NOW SHOWING 플레이트 bbox
LTX0, LTY0, LTX1, LTY1 = 72, 49, 182, 72     # v2 원본 LOVE♥ 크롭 영역(원본 크기·코럴색 — f70 실측)
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
    W, H = 264, 240
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
    sign.alpha_composite(love_bmp, (LTX0, LTY0))             # LOVE♥ = v2 원본 크롭을 원위치에(원본 크기·확대·중앙정렬 없음)
    return sign

def extract_love(im):
    """v2 원본 f70에서 LOVE♥ 텍스트만 소프트 알파로 추출 — 원본 크기·원본 코럴색 보존(재작화·확대 없음)."""
    im.seek(70)
    a = np.array(im.convert('RGBA')).astype(float)
    crop = a[LTY0:LTY1+1, LTX0:LTX1+1]
    r, g, b = crop[..., 0], crop[..., 1], crop[..., 2]
    redness = r - (g + b) / 2                      # 코럴=높음 · 크림/앰버 배경=낮음
    alpha = np.clip((redness - 30) / 50, 0, 1) * 255
    out = np.dstack([crop[..., 0], crop[..., 1], crop[..., 2], alpha]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')

def main():
    im = Image.open(SRC)
    n = im.n_frames
    im.seek(70); ref = np.array(im.convert('RGBA')).astype(int)
    love_bmp = extract_love(im)   # v2 원본 텍스트 크롭(원본 크기·코럴색)
    plate_im = Image.open(PLATE_SRC); plate_im.seek(70)
    plate_crop = plate_im.convert('RGBA').crop((PLX0, PLY0, PLX1+1, PLY1+1))   # NOW SHOWING = v3(반듯·깔끔)
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
