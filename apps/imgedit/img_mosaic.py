#!/usr/bin/env python3
"""편집 탭 — 단일 이미지 피사체 모자이크 렌더(2티어).

기본 = track_render.mosaic_region 재사용(박스/타원 픽셀레이트) · 정밀 = ultralytics SAM2 image predictor로
피사체 실루엣 마스크를 뽑아 그 윤곽에만 픽셀레이트(헤비 스택 · 실패 = 박스로 fail-soft 폴백).

입력 = viewer/imgedit_out/<id>/boxes.json + 렌더 페이로드(env RENDER JSON) · 원본 = boxes.meta.src_url(R2) 또는
outdir/src.<ext>(git 폴백). 출력 = R2 imgedit/<id>/out.jpg → result.json{url,ts}. 실패 = result.json{error}(fail-soft).

사용: RENDER='{"targets":[1,2],"opts":{...},"precise":false}' python3 img_mosaic.py <id>
"""
import json
import os
import sys
import urllib.request

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "track"))
sys.path.insert(0, os.path.join(HERE, "..", "..", ".github", "scripts"))
import track_render as tr    # mosaic_region 재사용(박스/타원 픽셀레이트 · 코어-강제 커버) · kst_now
import thumb_gen as tg       # r2_upload(bytes, key, ctype) · R2_ON
from img_detect import load_image_bgr, OUT_ROOT   # 검출↔렌더 동일 EXIF 로더(좌표 일치)


def fail(iid, user_msg, log_msg=""):
    """렌더 실패 = result.json{error} 기록 후 exit 0(fail-soft — 뷰어 헛폴 차단 · ly_burn/track_render 동일)."""
    outdir = os.path.join(OUT_ROOT, iid)
    try:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "result.json"), "w", encoding="utf-8") as f:
            json.dump({"error": user_msg}, f, ensure_ascii=False)
    except Exception:
        pass
    print(f"::warning::{log_msg or user_msg}", flush=True)
    sys.exit(0)


def sam_masks(img, boxes_xyxy):
    """ultralytics SAM2 image predictor — 박스 프롬프트별 실루엣 마스크(bool HxW) 리스트. 실패 = None(→박스 폴백).
    단일 이미지 1콜(영상 전파·멀티패스 없음 = track_keying 대비 대폭 축약). 모델 = setup.sh 헤비 스택 sam2.1_t.pt."""
    try:
        from ultralytics import SAM
        mp = os.path.join(os.environ.get("NOMUTE_TRACK_MODELS", os.path.expanduser("~/.cache/nomute-track")), "sam2.1_t.pt")
        if not os.path.isfile(mp):
            print("::warning::SAM2 모델 없음 — 박스/타원 폴백", flush=True)
            return None
        model = SAM(mp)
        res = model(img, bboxes=boxes_xyxy, verbose=False)
        if not res or res[0].masks is None:
            return None
        md = res[0].masks.data.cpu().numpy()   # (N,h,w) — 프롬프트 순서 대응(ultralytics 보장)
        out = []
        for i in range(len(boxes_xyxy)):
            m = md[i] if i < len(md) else None
            if m is None:
                out.append(None)
                continue
            if m.shape[:2] != img.shape[:2]:   # 안전 — 입력 해상도로 리사이즈
                m = cv2.resize(m.astype(np.float32), (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
            out.append(m > 0.5)
        return out
    except Exception as e:
        print(f"::warning::SAM2 실패({type(e).__name__}) — 박스/타원 폴백", flush=True)
        return None


def mosaic_by_mask(img, mask, pxw, pxh, feather):
    """SAM2 실루엣 마스크 영역만 픽셀레이트 후 마스크로 합성(정밀 티어 · '윤곽에 딱 묻는' 모자이크)."""
    ys, xs = np.where(mask)
    if xs.size == 0:
        return False
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    rw, rh = x1 - x0, y1 - y0
    if rw < 4 or rh < 4:
        return False
    bw = max(8, int(round(rw / max(1, pxw))))   # 블록 절대 하한 8px = mosaic_region 익명성 바닥 계승
    bh = max(8, int(round(rh / max(1, pxh))))
    sw, sh = max(1, rw // bw), max(1, rh // bh)
    reg = img[y0:y1, x0:x1]
    mos = cv2.resize(cv2.resize(reg, (sw, sh), interpolation=cv2.INTER_LINEAR), (rw, rh), interpolation=cv2.INTER_NEAREST)
    m = mask[y0:y1, x0:x1].astype(np.float32)
    if feather > 0:
        k = 2 * int(feather) + 1
        m = cv2.GaussianBlur(m, (k, k), feather * 0.6)
    m3 = m[:, :, None]
    img[y0:y1, x0:x1] = np.rint(reg.astype(np.float32) * (1 - m3) + mos.astype(np.float32) * m3).astype(np.uint8)
    return True


def main():
    iid = sys.argv[1]
    outdir = os.path.join(OUT_ROOT, iid)
    bpath = os.path.join(outdir, "boxes.json")
    if not os.path.isfile(bpath):
        fail(iid, "분석 정보가 없어 — 이미지를 다시 올려줘.", "no boxes.json")
    boxes = json.load(open(bpath, encoding="utf-8"))
    items = {it["id"]: it for it in boxes.get("items", [])}
    meta = boxes.get("meta", {})

    # 원본 로드 — git 폴백 src 우선(로컬), 없으면 R2 url fetch
    ext = meta.get("src_ext", ".jpg")
    local_src = os.path.join(outdir, f"src{ext}")
    img = None
    if os.path.isfile(local_src):
        img = load_image_bgr(local_src)
    elif meta.get("src_url"):
        try:
            data = urllib.request.urlopen(meta["src_url"], timeout=30).read()
            tmp = f"/tmp/imgedit_src_{iid}{ext}"
            with open(tmp, "wb") as f:
                f.write(data)
            img = load_image_bgr(tmp)
        except Exception as e:
            fail(iid, "원본 이미지를 못 불러왔어 — 다시 올려줘.", f"src fetch: {type(e).__name__}: {e}")
    if img is None or img.size == 0:
        fail(iid, "원본 이미지가 유실됐어 — 다시 올려줘.", "no src")
    H, W = img.shape[:2]

    try:
        payload = json.loads(os.environ.get("RENDER", "{}"))
    except Exception:
        payload = {}
    targets = [t for t in payload.get("targets", []) if t in items]
    if not targets:
        fail(iid, "가릴 피사체를 골라줘.", "no valid targets")
    o = payload.get("opts", {}) or {}
    pxw = max(3, min(20, int(o.get("pxw", 9))))
    pxh = max(3, min(20, int(o.get("pxh", 9))))
    size = max(0.75, min(2.5, float(o.get("size", 1.15))))
    feather = max(0, min(40, int(o.get("feather", 5))))
    shape = o.get("shape") if o.get("shape") in ("rect", "ellipse") else "ellipse"
    precise = bool(payload.get("precise"))

    masks = None
    if precise:
        bxyxy = []
        for t in targets:
            x, y, w, h = items[t]["box"]
            bxyxy.append([x, y, x + w, y + h])
        masks = sam_masks(img, bxyxy)

    for idx, t in enumerate(targets):
        x, y, w, h = items[t]["box"]
        done = False
        if precise and masks and idx < len(masks) and masks[idx] is not None:
            done = mosaic_by_mask(img, masks[idx], pxw, pxh, feather)
        if not done:   # 기본 티어 또는 SAM2 폴백 — 박스/타원 픽셀레이트(코어-강제 커버)
            tr.mosaic_region(img, x, y, w, h, W, H, pxw=pxw, pxh=pxh, size=size, feather=feather, shape=shape)

    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        fail(iid, "이미지 저장 실패 — 다시 시도해줘.", "imencode fail")
    data = buf.tobytes()

    url = ""
    if tg.R2_ON:
        try:
            url = tg.r2_upload(data, f"imgedit/{iid}/out.jpg", "image/jpeg") or ""
        except Exception as e:
            print(f"::warning::R2 업로드 실패 {type(e).__name__} — git 폴백", flush=True)
    if not url:
        with open(os.path.join(outdir, "out.jpg"), "wb") as f:
            f.write(data)
        url = f"imgedit_out/{iid}/out.jpg"

    with open(os.path.join(outdir, "result.json"), "w", encoding="utf-8") as f:
        json.dump({"url": url, "ts": tr.kst_now(), "precise": precise}, f, ensure_ascii=False)
    print(f"[imgedit] {iid} 렌더 완료 {len(targets)}개(정밀={precise}) → {url}", flush=True)


if __name__ == "__main__":
    _iid = sys.argv[1] if len(sys.argv) > 1 else "_"
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        fail(_iid, "렌더 중 오류 — 다시 시도해줘.", f"unhandled: {type(e).__name__}: {e}")
