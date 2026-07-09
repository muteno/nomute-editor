#!/usr/bin/env python3
# 인물 트래킹 렌더 — tracks.json 타임라인 + 선택 페이로드 → 모자이크(픽셀레이트) 또는 핀셋(이름표) 번인
#   → R2 업로드 → viewer/track_out/<id>/video.json (뷰어 폴링 · ly_burn video.json 패턴 계승).
#   사용: track_render.py <id>   (track-make.yml render 스텝 전용 · 소스는 tracks.json meta.src에서 자체 회수)
# env: RENDER = {"mode":"mosaic"|"pinset","targets":[pid],"invert":bool,"names":{pid:이름},"colors":{pid:"#hex"},
#                "opts":{pxw,pxh,size,feather,shape}}   (opts = 모자이크 조절 · 핀셋은 무시)
#      mode="keying" = track_keying.py 위임(선택 피사체만 남기는 알파 렌더 · {"keep":[sid],"extra":[{t,x,y}],"opts":{feather}})
#      R2 5종(thumb_gen 재사용 · 미설정 = 30MB 이하 git 폴백)
# 고퀄 5원칙(00_지침 정본): ① 검출 갭 보간(깜빡임 0) ② 3탭 이동평균 스무딩(덜덜 떨림 0·EMA 지연 없음)
#   ③ 시간 안전마진 ±0.3s(모자이크는 한 프레임 노출도 실패 → 과잉 커버 편향) ④ 같은 인물 트랙 간 갭 ≤1.2s 브리지(가림 통과)
#   ⑤ 넉넉한 공간 마진(가로 1.45× 세로 1.6× 위로 10% 시프트 = 이마·머리카락 커버).
# 실패 = fail-soft: video.json에 사유 기록 후 rc 0 (분석 산출은 이미 정상 — 렌더가 잡을 죽이면 안 됨 · ly_burn 동일).
import json
import math
import os
import re
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".github", "scripts"))
import thumb_gen as tg   # r2_upload · R2_ON 재사용

PAD_SEC = 0.30           # 트랙 앞뒤 시간 안전마진
EDGE_PAD_SEC = 0.5       # 화면 가장자리 접촉 트랙 추가 패딩 — 이탈/진입 슬리버(검출 불가 부분 얼굴)는 속도 외삽으로 추적 커버(평의회I 노출 적발 봉합)
EDGE_TOUCH_PX = 4        # 가장자리 접촉 판정 여유
BRIDGE_SEC = 1.2         # 같은 인물 트랙 간 이 이하 갭 = 보간 브리지(짧은 가림·검출 미스 통과)
MARGIN_W, MARGIN_H, SHIFT_UP = 1.45, 1.60, 0.10   # 모자이크 공간 마진(이마·머리카락)
BLOCK_DIV = 9            # 픽셀 블록 기본 분할 수(가로=폭/9 · 세로=높이/9 · 하한 8px — 구 렌더는 세로도 폭 기준이라 기본값도 픽셀 비동일·커버는 동일)
GIT_FALLBACK_MAX = 30 * 1024 * 1024
PALETTE = ["#00EED2", "#e23b2a", "#d8ff3d", "#0FFD02", "#38C6FF", "#FF5EC8", "#FFE13D", "#AC5CFF",
           "#2CF5A5", "#ff7a6b", "#3a6ddb", "#eef7f0"]   # 뷰어 STEP2 카드와 동일 순서(브랜드 팔레트 값 복사 — 자기완결 산출물 = §핵심명령 3-c 계승)


def kst_now():
    from datetime import datetime, timedelta, timezone
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    except Exception:
        return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def out_json(outdir, doc):
    doc["ts"] = kst_now()
    with open(os.path.join(outdir, "video.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print("video.json:", json.dumps(doc, ensure_ascii=False)[:200], flush=True)


def hex_bgr(hx):
    hx = (hx or "").lstrip("#")
    try:
        if len(hx) != 6:
            raise ValueError(hx)
        return (int(hx[4:6], 16), int(hx[2:4], 16), int(hx[0:2], 16))
    except ValueError:   # 비-hex 색 하나가 렌더 전체를 죽이면 안 됨(평의회4) — 기본 = --accent #00EED2의 BGR
        return (210, 238, 0)


def smooth3(kf):
    """키프레임 [f,x,y,w,h,score] → 중심 3탭 이동평균(cx·cy·w·h) — EMA와 달리 지연 0."""
    if len(kf) < 3:
        return [[k[0], k[1], k[2], k[3], k[4]] for k in kf]
    out = []
    for i, k in enumerate(kf):
        a = kf[max(0, i - 1)]
        b = k
        c = kf[min(len(kf) - 1, i + 1)]
        cx = (a[1] + a[3] / 2 + b[1] + b[3] / 2 + c[1] + c[3] / 2) / 3
        cy = (a[2] + a[4] / 2 + b[2] + b[4] / 2 + c[2] + c[4] / 2) / 3
        w = (a[3] + b[3] + c[3]) / 3
        h = (a[4] + b[4] + c[4]) / 3
        out.append([k[0], cx - w / 2, cy - h / 2, w, h])
    return out


def _near_edge(k, W, H):
    """박스가 화면 가장자리 접촉 = 이탈/진입 중일 개연(검출 불가 슬리버가 이어질 자리)."""
    if not W or not H:
        return False
    return k[1] <= EDGE_TOUCH_PX or k[2] <= EDGE_TOUCH_PX or k[1] + k[3] >= W - EDGE_TOUCH_PX or k[2] + k[4] >= H - EDGE_TOUCH_PX


def _extrap(k1, k2, df):
    """k2에서 df프레임 외삽(속도 = k1→k2) — 가장자리 이탈/진입 슬리버를 이동 방향 그대로 추적 커버.
    크기는 축소 금지(마지막 크기 유지 하한) = 커버 감소 방향 차단."""
    dt = max(1, k2[0] - k1[0])
    vx, vy = (k2[1] - k1[1]) / dt, (k2[2] - k1[2]) / dt
    return [k2[0] + df, k2[1] + vx * df, k2[2] + vy * df, max(k2[3], k1[3]), max(k2[4], k1[4])]


def build_spans(person, fps, total_frames, W=0, H=0):
    """사람 1명의 segs → 연속 스팬 목록. 스팬 = 단조증가 키프레임 [[f,x,y,w,h],...] (± 패딩·갭 브리지 포함).
    가장자리 접촉 끝단 = 속도 외삽 + 연장 패딩(0.3s→0.8s) — 정적 패딩은 움직이는 이탈 슬리버(f당 수 px씩
    화면 밖으로 나가는 부분 얼굴)를 못 덮는다(평의회I 실측: 이탈 4~15프레임 노출 → 봉합)."""
    pad = int(round(PAD_SEC * fps))
    epad = int(round(EDGE_PAD_SEC * fps))
    bridge = int(round(BRIDGE_SEC * fps))
    segs = sorted(person.get("segs") or [], key=lambda s: s["f0"])
    groups = []   # 브리지(≤1.2s 갭)로 이어붙인 kf 묶음 — 갭 구간은 sample()의 선형보간이 커버
    cur, cur_end = None, -1
    for s in segs:
        kf = smooth3(s.get("kf") or [])
        if not kf:
            continue
        # 브리지 기준 = 그룹의 *최대* 끝프레임(cur_end) — cur[-1]은 포함(contained) 트랙 extend 후
        #   방금 붙인 짧은 세그의 끝을 가리켜 실제 갭을 과대평가 → 브리지 실패 → 모자이크 노출(평의회4 실버그)
        if cur is not None and kf[0][0] - cur_end <= bridge:
            cur.extend(kf)
            cur_end = max(cur_end, kf[-1][0])
        else:
            if cur is not None:
                groups.append(cur)
            cur = list(kf)
            cur_end = kf[-1][0]
    if cur is not None:
        groups.append(cur)
    spans = []
    for g in groups:
        g.sort(key=lambda k: k[0])   # 포함 트랙 extend = f 역행 가능 → 정렬로 단조 복원(끝 패딩·이분탐색 안전 · 평의회4 후속)
        edge_h, edge_t = _near_edge(g[0], W, H), _near_edge(g[-1], W, H)
        pad_h = pad + (epad if edge_h else 0)
        pad_t = pad + (epad if edge_t else 0)
        if edge_h and len(g) >= 2:
            head = _extrap(g[1], g[0], -min(pad_h, g[0][0]))   # 역방향 외삽(진입 슬리버 추적)
            head[0] = max(0, g[0][0] - pad_h)
        else:
            head = [max(0, g[0][0] - pad_h)] + list(g[0][1:])   # 시간 안전마진(첫 박스 고정)
        if edge_t and len(g) >= 2:
            tail = _extrap(g[-2], g[-1], pad_t)                 # 순방향 외삽(이탈 슬리버 추적)
            tail[0] = min(total_frames, g[-1][0] + pad_t)
        else:
            tail = [min(total_frames, g[-1][0] + pad_t)] + list(g[-1][1:])
        sp = [head] + g + [tail]
        dd = []   # f 단조·중복 제거(패딩이 기존 kf와 같은 f일 때)
        for k in sp:
            if dd and k[0] <= dd[-1][0]:
                continue
            dd.append(k)
        if len(dd) == 1:
            dd.append([dd[0][0] + 1] + list(dd[0][1:]))
        spans.append(dd)
    return spans


def sample(span, f):
    """스팬 안에서 프레임 f의 박스 선형보간. 밖이면 None."""
    if f < span[0][0] or f > span[-1][0]:
        return None
    lo, hi = 0, len(span) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if span[mid][0] <= f:
            lo = mid
        else:
            hi = mid
    a, b = span[lo], span[hi]
    t = 0.0 if b[0] == a[0] else (f - a[0]) / float(b[0] - a[0])
    return [a[i] + (b[i] - a[i]) * t for i in range(1, 5)]


def mosaic_region(frame, x, y, w, h, W, H, pxw=BLOCK_DIV, pxh=BLOCK_DIV, size=1.0, feather=0, shape="rect"):
    """모자이크 1박스 — 옵션(운영자 260708): pxw/pxh = 블록 가로/세로 분할 수(프리미어 수평/수직 블록 동일 개념 ·
    적을수록 굵음) · size = 커버 배율 · feather = 가장자리 페더 px · shape = rect/ellipse.
    커버 보증 = 코어-강제 방식(평의회 A F1·G③④ 봉합): 코어(마진박스·참 중심 기준) 마스크를 블러 후
    `maximum(core)`로 내부 1.0 복원 → 페더는 코어 *바깥 링 전용*(소형 얼굴 중심 반투명·가장자리 후퇴 원천 차단).
    타원 = 코어 내접(검출박스 모서리 = 대부분 배경 · size 하한 0.75가 얼굴 타원 커버 보증 — 완전 박스 커버는 네모)."""
    cx, cy = x + w / 2, y + h / 2 - h * SHIFT_UP
    cw, ch = w * MARGIN_W * size, h * MARGIN_H * size   # 코어(보증 커버) 크기
    w2, h2 = cw + feather * 2, ch + feather * 2         # 렌더 영역 = 코어 + 페더 링
    x0, y0 = int(max(0, cx - w2 / 2)), int(max(0, cy - h2 / 2))
    x1, y1 = int(min(W, cx + w2 / 2)), int(min(H, cy + h2 / 2))
    rw, rh = x1 - x0, y1 - y0
    if rw < 4 or rh < 4:
        return
    bw = max(8, int(round(w2 / max(1, pxw))))   # 블록 절대 하한 8px = 구 렌더 익명성 바닥 유지(평의회F·A F3)
    bh = max(8, int(round(h2 / max(1, pxh))))
    sw, sh = max(1, rw // bw), max(1, rh // bh)
    reg = frame[y0:y1, x0:x1]
    mos = cv2.resize(cv2.resize(reg, (sw, sh), interpolation=cv2.INTER_LINEAR), (rw, rh), interpolation=cv2.INTER_NEAREST)
    if feather <= 0 and shape != "ellipse":
        frame[y0:y1, x0:x1] = mos
        return
    f = max(0, int(feather))
    # 코어 마스크 = 참 중심(cx,cy) 기준 미클램프 기하 — 화면 가장자리 클램프에도 후퇴 없이 경계까지 솔리드(cv2가 자동 클립 · 평의회A F2·G④)
    mcx, mcy = cx - x0, cy - y0
    ax, ay = cw / 2, ch / 2
    core = np.zeros((rh, rw), np.float32)
    if shape == "ellipse":
        cv2.ellipse(core, (int(round(mcx)), int(round(mcy))), (max(1, int(round(ax))), max(1, int(round(ay)))), 0, 0, 360, 1.0, -1)
    else:
        cv2.rectangle(core, (int(round(mcx - ax)), int(round(mcy - ay))), (int(round(mcx + ax)), int(round(mcy + ay))), 1.0, -1)
    mask = core
    if f > 0:
        ds = 4 if f >= 8 else 1   # 다운스케일 블러 ≈47% 절감(평의회H) — 그라디언트라 업스케일 후 시각 동일
        if ds > 1:
            sm = cv2.resize(core, (max(1, rw // ds), max(1, rh // ds)), interpolation=cv2.INTER_AREA)
            kk = 2 * max(1, f // ds) + 1
            sm = cv2.GaussianBlur(sm, (kk, kk), (f / ds) * 0.6)
            mask = cv2.resize(sm, (rw, rh), interpolation=cv2.INTER_LINEAR)
        else:
            k = 2 * f + 1
            mask = cv2.GaussianBlur(core, (k, k), f * 0.6)
        mask = np.maximum(mask, core)   # 코어 강제 1.0 — 중심·구 커버 완전 보증(블러의 코어 침식 복원)
    m3 = mask[:, :, None]
    frame[y0:y1, x0:x1] = np.rint(reg.astype(np.float32) * (1 - m3) + mos.astype(np.float32) * m3).astype(np.uint8)


def find_font():
    try:
        r = subprocess.run(["fc-match", "--format", "%{file}", "Noto Sans CJK KR:weight=bold"],
                           capture_output=True, text=True, timeout=15)
        p = (r.stdout or "").strip()
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    import glob
    for pat in ("/usr/share/fonts/**/NotoSansCJK*Bold*.ttc", "/usr/share/fonts/**/NotoSansCJK*.ttc",
                "/usr/share/fonts/**/*.ttf"):
        g = glob.glob(pat, recursive=True)
        if g:
            return g[0]
    return None


def assert_cjk_font():
    """핀셋 하드게이트 — CJK 폰트 없으면 이름표가 에러 없이 두부(□)로 조용히 렌더 → 깨진 영상이 '성공'
    video.json으로 표시(ly-make.yml:95 두부 게이트와 동일 원리 · 평의회1 H-2). 사일런트 폴백 금지."""
    try:
        r = subprocess.run(["fc-list"], capture_output=True, text=True, timeout=20)
        if "noto sans cjk" in (r.stdout or "").lower():
            return
    except Exception:
        pass
    raise RuntimeError("한글 폰트 준비 실패 — 잠시 후 다시 렌더해줘.")


class PinsetPainter:
    """핀셋 이름표 — 코너 브래킷 + 리더선 + 필(이름). 스타일 = viewer/track.html 목업 캔버스 계승."""

    def __init__(self, W, H):
        from PIL import ImageFont
        self.W, self.H = W, H
        fs = int(max(18, min(44, H * 0.033)))
        self.fs = fs
        fp = find_font()
        try:
            self.font = ImageFont.truetype(fp, fs) if fp else ImageFont.load_default()
            if not fp:
                print("::warning::폰트 경로 탐색 실패 — 기본 비트맵 폴백(assert_cjk_font 통과 후라 비정상)", flush=True)
        except Exception:
            self.font = ImageFont.load_default()
            print("::warning::truetype 로드 실패 — 기본 비트맵 폴백", flush=True)
        self.lw = max(2, int(round(H * 0.0035)))

    def draw(self, frame, tags):
        """tags = [(box[x,y,w,h], name, (r,g,b))] — PIL RGBA 오버레이 1회 합성."""
        from PIL import Image, ImageDraw
        im = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        placed = []
        for box, name, rgb in tags:
            x, y, w, h = box
            cx = x + w / 2
            ex_w, ex_h = w * 1.5, h * 1.7
            bx0, by0 = cx - ex_w / 2, y + h / 2 - h * 0.15 - ex_h / 2
            bx1, by1 = bx0 + ex_w, by0 + ex_h
            L = max(10, ex_w * 0.24)
            lw = self.lw
            col = rgb + (235,)
            for (px, py, dx, dy) in ((bx0, by0, 1, 1), (bx1, by0, -1, 1), (bx0, by1, 1, -1), (bx1, by1, -1, -1)):
                d.line([(px + dx * L, py), (px, py)], fill=col, width=lw)
                d.line([(px, py), (px, py + dy * L)], fill=col, width=lw)
            # 필(이름) — 박스 위
            pad_x, pad_y = int(self.fs * 0.62), int(self.fs * 0.38)
            tb = d.textbbox((0, 0), name, font=self.font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            dot = int(self.fs * 0.42)
            bw = pad_x * 2 + dot + int(self.fs * 0.35) + tw
            bh = th + pad_y * 2
            px0 = min(max(4, cx - bw / 2), self.W - bw - 4)
            py0 = by0 - bh - max(12, self.fs * 0.8)
            # 겹침 회피(위로 밀기 · 목업 layoutTags 계승)
            guard = 0
            while guard < 40:
                guard += 1
                c = next((p for p in placed if px0 < p[0] + p[2] + 8 and p[0] < px0 + bw + 8 and py0 < p[1] + p[3] + 8 and p[1] < py0 + bh + 8), None)
                if c is None:
                    break
                py0 = c[1] - bh - 8
            py0 = max(4, py0)
            placed.append((px0, py0, bw, bh))
            # 리더선(필 하단 중앙 → 브래킷 상단 중앙)
            d.line([(px0 + bw / 2, py0 + bh), (cx, by0 - 4)], fill=rgb + (150,), width=max(1, lw - 1))
            d.ellipse([cx - 4, by0 - 8, cx + 4, by0], fill=rgb + (255,))
            r = int(bh / 2)
            d.rounded_rectangle([px0, py0, px0 + bw, py0 + bh], radius=r, fill=(17, 18, 20, 222), outline=rgb + (255,), width=max(1, lw - 1))
            dy_c = py0 + bh / 2
            d.ellipse([px0 + pad_x, dy_c - dot / 2, px0 + pad_x + dot, dy_c + dot / 2], fill=rgb + (255,))
            d.text((px0 + pad_x + dot + int(self.fs * 0.35), py0 + pad_y - tb[1]), name, font=self.font, fill=(238, 247, 240, 255))
        im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
        return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


def resolve_src(meta, vid_id, outdir):
    src = meta.get("src") or ""
    if src.lstrip("/").startswith("track_out/"):   # git 폴백(상대 정본 · 구 절대경로 하위호환)
        p = os.path.join("viewer", src.lstrip("/"))
        return p if os.path.isfile(p) else None
    if src.startswith("https://"):
        ext = (os.path.splitext(src.split("?")[0])[1].lstrip(".") or "mp4")   # 쿼리스트링 방어(평의회4)
        dst = f"/tmp/track_src.{ext}"
        try:
            subprocess.run(["curl", "-fsSL", "--max-time", "300", src, "-o", dst], check=True, timeout=330)
            return dst if os.path.isfile(dst) and os.path.getsize(dst) > 0 else None
        except Exception:
            return None
    return None


def main():
    vid_id = sys.argv[1] if len(sys.argv) > 1 else ""
    if not re.match(r"^[0-9]{12}-[0-9a-f]{6}$", vid_id):   # 인-스크립트 자체 방어(워크플로 가드와 이중 · ly_burn 문법 · 평의회4)
        raise RuntimeError("잘못된 작업 ID — 먼저 분석부터 해줘.")
    outdir = os.path.join("viewer", "track_out", vid_id)
    if not os.path.isdir(outdir):
        raise RuntimeError("작업 폴더 없음 — 먼저 분석부터 해줘.")
    try:
        doc = json.load(open(os.path.join(outdir, "tracks.json"), encoding="utf-8"))
    except Exception:
        raise RuntimeError("분석 결과(tracks.json)가 없어 — 먼저 분석부터 해줘.")
    try:
        req = json.loads(os.environ.get("RENDER") or "{}")
    except Exception:
        req = {}
    if not isinstance(req, dict):   # 유효 JSON이지만 객체가 아님(리스트·수) — AttributeError 방지(평의회4)
        req = {}
    mode = req.get("mode") if req.get("mode") in ("mosaic", "pinset", "keying") else "mosaic"
    if mode == "keying":   # 키잉 = 별도 모듈 위임(lazy import — torch 스택은 키잉 러너에서만 · 모자이크/핀셋 경로 무영향)
        import track_keying
        track_keying.run(vid_id, req, doc, outdir)   # 예외 = 아래 fail-soft 래퍼가 video.json{error}로 기록
        return
    names = {str(k): str(v)[:24] for k, v in (req.get("names") or {}).items() if str(v).strip()}
    colors = {str(k): str(v) for k, v in (req.get("colors") or {}).items()}
    invert = bool(req.get("invert"))
    targets = {int(t) for t in (req.get("targets") or []) if isinstance(t, (int, float)) and not isinstance(t, bool)}

    def _num(v, lo, hi, dflt):   # 옵션 수치 방어(서버 검증과 이중 — 직접 dispatch도 안전)
        try:
            x = float(v)
            if math.isnan(x):
                return dflt
            return max(lo, min(hi, x))
        except (TypeError, ValueError):
            return dflt
    raw_opts = req.get("opts") if isinstance(req.get("opts"), dict) else {}
    mo = {"pxw": int(round(_num(raw_opts.get("pxw"), 3, 20, BLOCK_DIV))),   # round = api Math.round와 정렬(평의회B N1) · 상한 20 = 얼굴당 ~14블록(재식별 방지 바닥 · 평의회G⑤)
          "pxh": int(round(_num(raw_opts.get("pxh"), 3, 20, BLOCK_DIV))),
          "size": _num(raw_opts.get("size"), 0.75, 2.5, 1.0),   # 하한 0.75 = 하단 시프트 구속(0.4+0.8×0.75≥1) — 커버 ≥ 검출박스 전 변(초상권 바닥 · 평의회G①)
          "feather": int(round(_num(raw_opts.get("feather"), 0, 40, 0))),   # 상한 40 = UI와 정렬(60은 성능·커버 여유 밖 · 평의회H)
          "shape": "ellipse" if raw_opts.get("shape") == "ellipse" else "rect"}

    people = doc.get("people") or []
    all_pids = {p["pid"] for p in people}
    if mode == "mosaic":
        sel = (all_pids - targets) if invert else (targets & all_pids)
    else:
        sel = {int(k) for k in names.keys() if k.isdigit() and int(k) in all_pids}
    if not sel:
        raise RuntimeError("선택된 인물이 없어 — 카드를 고르고 다시 렌더해줘.")

    meta = doc.get("meta") or {}
    src = resolve_src(meta, vid_id, outdir)
    if not src:
        raise RuntimeError("원본 보관본을 못 가져왔어 — 처음(영상 분석)부터 다시 해줘.")

    cap = cv2.VideoCapture(src)
    try:
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)   # 분석과 동일 설정 = 좌표 공간 일치(불변)
    except Exception:
        pass
    if not cap.isOpened():
        raise RuntimeError("원본을 못 열었어 — 처음부터 다시 해줘.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    if not fps or fps <= 1 or fps > 240 or math.isnan(fps):
        fps = float(meta.get("fps") or 30.0)
    ok, first = cap.read()
    if not ok:
        raise RuntimeError("원본 프레임을 못 읽었어 — 처음부터 다시 해줘.")
    H, W = first.shape[:2]
    W2, H2 = W - (W % 2), H - (H % 2)   # yuv420p 짝수 강제
    total = int(meta.get("frames") or 0) or 10 ** 9

    plans = []   # (spans, name, bgr, rgb)
    for p in people:
        if p["pid"] not in sel:
            continue
        spans = build_spans(p, fps, total, W=int(meta.get("w") or 0), H=int(meta.get("h") or 0))
        cidx = (p["pid"] - 1) % len(PALETTE)
        hexc = colors.get(str(p["pid"])) or PALETTE[cidx]
        bgr = hex_bgr(hexc)
        plans.append((spans, names.get(str(p["pid"]), f"#{p['pid']}"), bgr, (bgr[2], bgr[1], bgr[0])))

    painter = None
    if mode == "pinset":
        assert_cjk_font()   # 두부 번인 하드게이트(평의회1 H-2) — 렌더 시작 전 차단
        painter = PinsetPainter(W2, H2)
    out_mp4 = "/tmp/track_result.mp4"
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W2}x{H2}", "-r", f"{fps:.4f}", "-i", "-",
         "-i", src, "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", "-c:a", "aac", "-b:a", "160k", "-shortest", out_mp4],
        stdin=subprocess.PIPE)

    f = 0
    frame = first
    t0 = time.time()
    try:   # 예외·타임아웃에도 ffmpeg·cap 명시 정리(좀비·미상 상태 차단 · 평의회4)
        while True:
            frame = frame[:H2, :W2]
            if mode == "mosaic":
                for spans, _n, _bgr, _rgb in plans:
                    for sp in spans:
                        b = sample(sp, f)
                        if b:
                            mosaic_region(frame, b[0], b[1], b[2], b[3], W2, H2,
                                          pxw=mo["pxw"], pxh=mo["pxh"], size=mo["size"],
                                          feather=mo["feather"], shape=mo["shape"])
            else:
                tags = []
                for spans, name, _bgr, rgb in plans:
                    for sp in spans:
                        b = sample(sp, f)
                        if b:
                            tags.append((b, name, rgb))
                            break   # 같은 사람이 동시 스팬 2개(드묾) = 첫 것만 라벨(중복 이름표 방지)
                if tags:
                    frame = painter.draw(frame, tags)
            try:
                enc.stdin.write(frame.tobytes())
            except BrokenPipeError:
                break
            f += 1
            ok, frame = cap.read()
            if not ok or frame is None:
                break
        try:
            enc.stdin.close()
        except Exception:
            pass   # BrokenPipe flush 재예외 — wait로 진행(구체 실패는 rc가 말함)
        rc = enc.wait(timeout=900)
    finally:
        cap.release()
        if enc.poll() is None:
            enc.kill()
    if rc != 0 or not os.path.isfile(out_mp4) or os.path.getsize(out_mp4) < 1024:
        raise RuntimeError("영상 인코딩 실패 — 다시 시도해줘.")
    print(f"렌더 완료 {f}프레임 · {time.time()-t0:.0f}s · {os.path.getsize(out_mp4)//1048576}MB", flush=True)

    # 출력 키 = stable(id·모드당 1개 덮어쓰기) + ?v= 캐시버스트 — epoch 접미 파일명은 재렌더(주 루프)마다
    #   R2 고아·git 폴백 mp4가 무한 누적(ly_burn stable+?v= 불변 위반 · 평의회8 상①)
    bust = int(time.time())
    url = ""
    if tg.R2_ON:
        with open(out_mp4, "rb") as fv:
            url = tg.r2_upload(fv.read(), f"track_res/{vid_id}/{mode}.mp4", "video/mp4") or ""
    if not url:
        if os.path.getsize(out_mp4) <= GIT_FALLBACK_MAX:
            import shutil
            res_rel = f"result-{mode}.mp4"
            shutil.copyfile(out_mp4, os.path.join(outdir, res_rel))
            url = f"track_out/{vid_id}/{res_rel}"
        else:
            raise RuntimeError("결과 업로드 실패(R2) — 잠시 후 다시 렌더해줘.")
    out_json(outdir, {"url": f"{url}?v={bust}", "mode": mode, "n": len(sel), "frames": f,
                      "opts": (mo if mode == "mosaic" else None)})   # 옵션 에코 = 결과가 어떤 설정인지 추적(디버그·재현)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # fail-soft: 사유를 video.json에 — 뷰어 헛폴 차단(ly_burn 전면 동일). rc 0 = Commit output이 반드시 푸시.
        vid_id = sys.argv[1] if len(sys.argv) > 1 else ""
        outdir = os.path.join("viewer", "track_out", vid_id)
        msg = str(e) if isinstance(e, RuntimeError) else f"렌더 중 오류 — 다시 시도해줘. ({type(e).__name__})"
        print("::warning::렌더 실패: " + repr(e), flush=True)
        try:   # 최후 방어 — 기록 실패가 rc≠0로 새면 failure() 경로로 오염(ly_burn 611 미러 · 평의회4)
            if vid_id and os.path.isdir(outdir):
                out_json(outdir, {"error": msg})
        except Exception as e2:
            print("::warning::video.json 기록 실패: " + repr(e2), flush=True)
