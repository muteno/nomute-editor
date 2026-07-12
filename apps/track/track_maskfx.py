#!/usr/bin/env python3
# 세그 트래킹 채움(M4) — SAM2 픽셀 마스크가 피사체를 따라가고, 그 영역만 {모자이크 | 가면 이미지}로 채워 번인.
#   운영자 260712: "트래킹되면서 모자이크가 따라가는 게 중요 · 얼굴만/전신 분리 · 픽셀 단위로 바뀌는 부위를 모자이크 · 가면도"
#   — M2 박스 모자이크와 별개 축(여긴 픽셀 실루엣 추종) · 대상 선택 = 키잉과 동일{keep=전신/사물(sid) · keepP=얼굴(pid) · extra=탭 포인트}
#   = 분석(M1) 1회 후 렌더 시점에 부위 지정("트래킹 이후에 설정") · 전파 코어 = track_keying 미러(plan_passes·상수 import = 단일 출처).
# UI 무의존 엔진(MODULES.md M4): run(src, tracks, req, out_path) + CLI — R2·git·뷰어 배선 = 콜러 몫(도먼트 · 배선 시 10인 평의회).
# 실측 기반 캡 = 키잉과 동일(90s·4객체·1920·발사 전 예산 가드 — 전파 비용이 지배라 동일 산식).
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 키잉 심볼(전파 계획·캡 상수)은 run() 진입 시 lazy import — track_keying 로드가 thumb_gen(.github/scripts)을
#   전이로 끌어와 모듈 로드만으로 결합되는 것 차단(track_render lazy 선례 · M4평의회1 ③)

FEATHER_DFLT = 8   # 모자이크 가장자리 페더 기본(키잉 3보다 크게 — 번인은 경계 티 안 나는 게 우선)


def die(msg, log=""):
    print(f"::error::{log or msg}", flush=True)
    raise SystemExit(json.dumps({"error": msg}, ensure_ascii=False))


def _num(v, lo, hi, dflt):   # 키잉 _num과 동일 구현(모듈 레벨 사용이라 lazy 불가 — 4줄 중복 = 이거 결합 회피 트레이드오프)
    try:
        x = float(v)
        if math.isnan(x):
            return dflt
        return max(lo, min(hi, x))
    except (TypeError, ValueError):
        return dflt


def _load_mask_img(path):
    """가면 PNG(RGBA 권장) 로드 — 알파 없으면 불투명 취급."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        die("가면 이미지를 못 읽었어 — PNG로 다시 줘.")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return img


def _pixelate(frame, block):
    """프레임 전체 픽셀레이트 판(마스크로 블렌드해 씀) — block px 격자."""
    h, w = frame.shape[:2]
    sw, sh = max(1, w // block), max(1, h // block)
    small = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def _overlay_bbox(frame, mask, mimg, scale, clip):
    """가면 이미지를 마스크 bbox에 등비 fit(중심 정렬·scale 배율) 알파 합성 — clip=True면 실루엣로도 클리핑."""
    ys, xs = np.nonzero(mask > 127)
    if not len(xs):
        return
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    bw, bh = max(2, x1 - x0), max(2, y1 - y0)
    mh, mw = mimg.shape[:2]
    k = min(bw / mw, bh / mh) * scale
    tw, th = max(2, int(mw * k)), max(2, int(mh * k))
    top = int((y0 + y1) / 2 - th / 2)
    left = int((x0 + x1) / 2 - tw / 2)
    r = cv2.resize(mimg, (tw, th), interpolation=cv2.INTER_AREA)
    H, W = frame.shape[:2]
    fx0, fy0 = max(0, left), max(0, top)
    fx1, fy1 = min(W, left + tw), min(H, top + th)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    sub = r[fy0 - top:fy1 - top, fx0 - left:fx1 - left]
    a = sub[:, :, 3:4].astype(np.float32) / 255.0
    if clip:
        a = a * (mask[fy0:fy1, fx0:fx1, None].astype(np.float32) / 255.0)
    roi = frame[fy0:fy1, fx0:fx1].astype(np.float32)
    frame[fy0:fy1, fx0:fx1] = (roi * (1 - a) + sub[:, :, :3].astype(np.float32) * a).astype(np.uint8)


def run(src, tracks, req, out_path):
    """세그 채움 실행 — src 원본 + tracks(M1 dict·extra만 쓰면 None 가능) + req 선택/채움 → out_path(mp4 번인).
    실패 = SystemExit 전파(chroma 관례 · 콜러 except SystemExit). 반환 = {"out","w","h","fps","frames","fill"}."""
    try:
        from ultralytics.models.sam import SAM2VideoPredictor
        import torch
    except Exception:
        die("세그 환경(torch·ultralytics)이 없어 — setup(TRACK_HEAVY=1) 후 다시.")
    from track_keying import (KEY_BUDGET_SEC, KEY_MAX_LONG, KEY_MAX_OBJ, KEY_MAX_SEC, IMGSZ,
                              PASS_HARD_SEC, SEG_FPS, SEG_S_1, SEG_S_OBJ, TAIL_S_PF,
                              SAM_CKPT, plan_passes)   # 전파 계획·캡 = 키잉 단일 출처(드리프트 0 · lazy = 이거 결합 차단)
    if not (os.path.isfile(SAM_CKPT) and os.path.getsize(SAM_CKPT) > 100_000_000):
        die("SAM 모델이 없어 — setup(TRACK_HEAVY=1) 후 다시.")
    torch.set_num_threads(max(1, os.cpu_count() or 4))

    doc = tracks or {}
    subjects = doc.get("subjects") or []
    people = [p for p in (doc.get("people") or []) if isinstance(p, dict) and p.get("pid")]
    keep = {int(t) for t in (req.get("keep") or []) if isinstance(t, (int, float)) and not isinstance(t, bool)} \
        & {s.get("sid") for s in subjects}
    keepP = {int(t) for t in (req.get("keepP") or []) if isinstance(t, (int, float)) and not isinstance(t, bool)} \
        & {p["pid"] for p in people}
    if any(not (isinstance(p.get("pb"), list) and len(p["pb"]) == 4) for p in people if p["pid"] in keepP):
        die("이 분석엔 얼굴 프롬프트가 없어(구 버전 분석) — 다시 분석해줘.")
    extras = []
    for e in (req.get("extra") or [])[:KEY_MAX_OBJ]:
        if isinstance(e, dict):
            t = _num(e.get("t"), 0, KEY_MAX_SEC, None)
            x, y = _num(e.get("x"), 0, 1, None), _num(e.get("y"), 0, 1, None)
            if t is not None and x is not None and y is not None:
                extras.append({"t": t, "x": x, "y": y})
    n_obj = len(keep) + len(keepP) + len(extras)
    if n_obj < 1:
        die("채울 대상을 골라줘 — keep(전신)/keepP(얼굴)/extra(탭) 중 하나는 필요해.")
    if n_obj > KEY_MAX_OBJ:
        die(f"대상은 최대 {KEY_MAX_OBJ}개까지야.")

    fill = req.get("fill") if req.get("fill") in ("mosaic", "image") else "mosaic"
    mo = req.get("mosaic") or {}
    im = req.get("image") or {}
    fe = int(round(_num(req.get("feather"), 0, 40, FEATHER_DFLT)))
    mimg = _load_mask_img(str(im.get("path") or "")) if fill == "image" else None
    im_scale = _num(im.get("scale"), 0.3, 3.0, 1.0)
    im_clip = bool(im.get("clip"))

    cap = cv2.VideoCapture(src)
    try:
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)   # 분석과 좌표 공간 일치(불변)
    except Exception:
        pass
    if not cap.isOpened():
        die("원본을 못 열었어 — 다시 해줘.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    if not fps or fps <= 1 or fps > 240 or math.isnan(fps):
        fps = float((doc.get("meta") or {}).get("fps") or 30.0)
    ok, first = cap.read()
    if not ok:
        die("원본 프레임을 못 읽었어.")
    H, W = first.shape[:2]
    if max(W, H) > KEY_MAX_LONG:
        die(f"세그 채움은 긴 변 {KEY_MAX_LONG}px까지야(지금 {max(W, H)}px).")
    W2, H2 = W - (W % 2), H - (H % 2)
    total_f = float((doc.get("meta") or {}).get("frames") or 0) or float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    real_dur = (total_f / fps) if total_f > 0 else float((doc.get("meta") or {}).get("dur") or 0)
    if total_f <= 0 or real_dur <= 0:   # tracks=None + 디코더 프레임수 0 = 예산·길이 가드가 0으로 통과(우회) → 정직 거절(M4평의회1 ④)
        die("영상 길이를 못 읽었어 — mp4로 변환해 다시 해줘.")
    if real_dur > KEY_MAX_SEC + 1:
        die(f"세그 채움은 {KEY_MAX_SEC}초까지야 — 잘라서 해줘.")
    for e in extras:   # 방어심층: 탭 시각을 실측 길이로 재클램프(키잉 M2 미러 — 직접 CLI 초과 탭)
        e["t"] = min(e["t"], real_dur)

    passes = plan_passes(subjects, keep, people, keepP, extras, fps, W, H, total_f=total_f)
    if not passes:
        die("채울 대상을 골라줘.")
    est_seg = sum((min(float(p["f0"]), total_f) if p.get("rev") else max(0.0, total_f - p["f0"])) / fps
                  * SEG_FPS * (SEG_S_1 + SEG_S_OBJ * max(0, len(p.get("pt_norm") or p["prompts"]) - 1))
                  for p in passes)
    est = est_seg + total_f * TAIL_S_PF * (W * H / 2_073_600.0)
    if est > KEY_BUDGET_SEC:
        die(f"이 조합은 렌더가 너무 오래 걸려(예상 {int(est // 60)}분) — 대상·길이를 줄여줘.")

    # ── 전파(track_keying ② 미러 — 패스 격리 리셋·순/역 트림·마스크 PNG) ──
    mask_root = "/tmp/maskfx"
    shutil.rmtree(mask_root, ignore_errors=True)
    predictor = None
    t_all = time.time()
    for k, p in enumerate(passes):
        t0_sec = p["f0"] / fps
        trim = f"/tmp/mfxpass{k}.mp4"
        if p.get("rev"):
            vf = f"fps={SEG_FPS:g},scale='if(gt(iw,ih),{IMGSZ},-2)':'if(gt(iw,ih),-2,{IMGSZ})',reverse"
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-t", f"{t0_sec:.3f}", "-i", src,
                   "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", trim]   # -t = 입력 옵션(역트림 정본)
        else:
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ss", f"{t0_sec:.3f}",
                   "-vf", f"fps={SEG_FPS:g}", "-an", "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "18", trim]
        r = subprocess.run(cmd, timeout=600)
        if r.returncode != 0 or not os.path.isfile(trim) or os.path.getsize(trim) < 1024:
            die("전처리(트림) 실패 — 다시 시도해줘.")
        if p.get("rev"):
            tc = cv2.VideoCapture(trim)
            tw, th = int(tc.get(cv2.CAP_PROP_FRAME_WIDTH)), int(tc.get(cv2.CAP_PROP_FRAME_HEIGHT))
            tc.release()
            if tw < 2 or th < 2:
                die("전처리(트림) 실패 — 다시 시도해줘.")
            p["prompts"] = [[nx * tw, ny * th] for nx, ny in p["pt_norm"]]
        mdir = os.path.join(mask_root, f"p{k}")
        os.makedirs(mdir, exist_ok=True)
        if predictor is None:
            predictor = SAM2VideoPredictor(overrides=dict(conf=0.25, task="segment", mode="predict",
                                                          imgsz=IMGSZ, model=SAM_CKPT, save=False, verbose=False))
        else:
            predictor.inference_state = {}   # 패스 격리(키잉 평의회 치명 봉합 미러 — init_state len>0 스킵 가드 재무장)
        kwargs = {"bboxes": p["prompts"]} if p["kind"] == "box" else {"points": p["prompts"], "labels": [1] * len(p["prompts"])}
        n_masks, live_masks = 0, 0
        t_p = time.time()
        for j, res in enumerate(predictor(source=trim, stream=True, **kwargs)):
            if j % 150 == 0:
                print(f"패스{k + 1}/{len(passes)} 전파 {j}f · {time.time() - t_p:.0f}s", flush=True)   # CI no-output 워치독·운영자 가시성(키잉 미러 · M4평의회1 ②)
            m = None
            if res.masks is not None and len(res.masks.data):
                m = (res.masks.data.any(0).cpu().numpy().astype(np.uint8)) * 255
                mh, mw = m.shape[:2]
                if p.get("rev"):
                    if abs(mw / max(1, mh) - W / max(1, H)) > 0.05 * (W / max(1, H)):
                        die("전처리 회전 불일치 — mp4로 변환해 다시 해줘.")
                elif (mh, mw) != (H, W):
                    die("전처리 회전 불일치 — mp4로 변환해 다시 해줘.")
                if m.any():
                    live_masks += 1
            if m is None:
                m = np.zeros(res.orig_shape[:2], np.uint8)
            cv2.imwrite(os.path.join(mdir, f"{j:06d}.png"), m)
            n_masks = j + 1
            if time.time() - t_all > PASS_HARD_SEC:
                die("렌더 시간 초과 — 대상·길이를 줄여줘.")
        p["mdir"], p["n_masks"], p["t0"] = mdir, n_masks, t0_sec
        os.remove(trim)
        if n_masks == 0 or live_masks == 0:
            die("대상 마스크 생성 실패 — 다른 프레임에서 지정해줘.")
        print(f"패스{k + 1}/{len(passes)}: {n_masks}마스크(실 {live_masks})", flush=True)

    # ── 합성(마스크 hold + 채움 번인) → h264 mp4(원본 오디오) ──
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W2}x{H2}", "-r", f"{fps:.4f}", "-i", "-",
         "-i", src, "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", out_path], stdin=subprocess.PIPE)
    cap.release()
    cap = cv2.VideoCapture(src)
    try:
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
    except Exception:
        pass
    for p in passes:
        p["last_j"], p["cur"] = -1, None
    kblur = 2 * fe + 1
    block_auto = 0   # 첫 유효 마스크 bbox로 고정(프레임별 블록 변동 = 지터 방지)
    f = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            frame = frame[:H2, :W2]
            mask = None
            for p in passes:
                if p.get("rev"):
                    if f >= p["f0"]:
                        continue
                    j = min(p["n_masks"] - 1, max(0, p["n_masks"] - 1 - int((f / fps) * SEG_FPS + 1e-6)))
                else:
                    if f < p["f0"]:
                        continue
                    j = min(p["n_masks"] - 1, int((f / fps - p["t0"]) * SEG_FPS + 1e-6))
                    if j < 0:
                        continue
                if j != p["last_j"]:
                    m = cv2.imread(os.path.join(p["mdir"], f"{j:06d}.png"), cv2.IMREAD_GRAYSCALE)
                    if m is not None and m.shape[:2] != (H, W):
                        m = cv2.resize(m, (W2, H2), interpolation=cv2.INTER_LINEAR)
                    p["cur"] = m if m is not None else None
                    p["last_j"] = j
                if p["cur"] is not None:
                    c = p["cur"][:H2, :W2]
                    mask = c if mask is None else np.maximum(mask, c)
            if mask is not None and mask.any():
                if fill == "mosaic":
                    if not block_auto:
                        blk = int(_num(mo.get("block"), 0, 64, 0))
                        if not blk:   # 자동 = 첫 bbox 짧은 변 / 9블록(프리미어 감) · 하한 8px(익명성 바닥)
                            ys, xs = np.nonzero(mask > 127)
                            blk = max(8, int(min(xs.max() - xs.min(), ys.max() - ys.min()) / 9)) if len(xs) else 12
                        block_auto = max(4, blk)
                    pix = _pixelate(frame, block_auto)
                    a = mask.astype(np.float32) / 255.0
                    if fe > 0:
                        a = cv2.GaussianBlur(a, (kblur, kblur), fe * 0.6)
                        core = (mask > 127)
                        a[core] = np.maximum(a[core], 1.0)   # 코어-강제(내부 반투명 노출 차단 — M2 커버 보증 계승)
                    a = a[:, :, None]
                    frame = (frame.astype(np.float32) * (1 - a) + pix.astype(np.float32) * a).astype(np.uint8)
                else:
                    _overlay_bbox(frame, mask, mimg, im_scale, im_clip)
            try:
                enc.stdin.write(frame.tobytes())
            except BrokenPipeError:
                break
            f += 1
            if f % 300 == 0:
                print(f"합성 {f}f", flush=True)
        try:
            enc.stdin.close()
        except Exception:
            pass
        rc = enc.wait(timeout=1200)
    finally:
        cap.release()
        if enc.poll() is None:
            enc.kill()
        shutil.rmtree(mask_root, ignore_errors=True)
    if rc != 0 or not os.path.isfile(out_path) or os.path.getsize(out_path) < 1024:
        die("영상 인코딩 실패 — 다시 시도해줘.")
    print(f"세그 채움 완료 {f}프레임 · fill={fill} · 총 {time.time() - t_all:.0f}s", flush=True)
    return {"out": out_path, "w": W2, "h": H2, "fps": round(fps, 2), "frames": f, "fill": fill}


def main():
    ap = argparse.ArgumentParser(description="세그 트래킹 채움(M4) — MODULES.md 계약")
    ap.add_argument("--src", required=True)
    ap.add_argument("--tracks", default="", help="M1 tracks.json 경로(keep/keepP 쓸 때 · extra만이면 생략)")
    ap.add_argument("--req", default="{}", help='JSON {"keep":[sid],"keepP":[pid],"extra":[{t,x,y}],"fill":"mosaic|image","mosaic":{"block":0},"image":{"path","scale","clip"},"feather":8}')
    ap.add_argument("--out", required=True, help="산출 mp4 경로")
    a = ap.parse_args()
    tracks = None
    if a.tracks:
        try:
            tracks = json.load(open(a.tracks, encoding="utf-8"))
        except Exception:
            die("tracks.json을 못 읽었어.")
    try:
        req = json.loads(a.req or "{}")
        if not isinstance(req, dict):
            req = {}
    except ValueError:
        req = {}
    res = run(a.src, tracks, req, a.out)
    print(json.dumps(res, ensure_ascii=False))   # 마지막 줄 = 기계가독 결과(chroma 관례)


if __name__ == "__main__":
    main()
