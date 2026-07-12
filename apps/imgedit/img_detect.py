#!/usr/bin/env python3
"""편집 탭 — 단일 이미지 피사체 검출(모자이크 지정용).

track_analyze의 검출 함수를 import 재사용(YuNet 얼굴 + YOLO11n 피사체) · 영상 기계(트래킹·군집·ffmpeg)는
전량 미사용 = 이미지 1장 검출 1콜. 출력 = viewer/imgedit_out/<id>/boxes.json (뷰어가 이미지 위에 박스
오버레이 → 탭해서 지정). 원본은 R2 imgedit_src/<id>.<ext>(렌더 재사용) 또는 git 폴백(outdir/src.<ext>).

사용: python3 img_detect.py <id> <image_path>

토큰 0(순수 OpenCV) · 과금 = Actions 분 + R2뿐. 골격 = track_analyze 미러(검출부만).
"""
import json
import os
import shutil
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "track"))
sys.path.insert(0, os.path.join(HERE, "..", "..", ".github", "scripts"))
import track_analyze as ta   # 검출 함수·모델·상수 재사용(import 안전 = __main__ 가드) — load_models·load_subj_net·yolo_detect·SUBJ_CLS·kst_now
import thumb_gen as tg       # R2 업로드(원본 보관) — r2_upload(bytes, key, ctype)·R2_ON

OUT_ROOT = os.path.join(HERE, "..", "..", "viewer", "imgedit_out")
DET_LONG = 1600   # 검출 입력 긴 변(이미지 = 고정 1장이라 영상 DET_LONG 960보다 크게 = 소형 얼굴·피사체도 포착)
FACE_MIN = 16     # 최소 얼굴 변(px)
CARD_CAP = 24     # 카드 상한(과다 검출 컷 · 큰 것 우선)


def die(user_msg, log_msg=""):
    """분석 실패 = /tmp 사유 기록 후 exit 1 → 워크플로 failure() 스텝이 error.log 커밋(뷰어 즉시 표시 · track 동일)."""
    try:
        with open("/tmp/imgedit_err.txt", "w", encoding="utf-8") as f:
            f.write(user_msg)
    except Exception:
        pass
    print(f"::error::{log_msg or user_msg}", flush=True)
    sys.exit(1)


def load_image_bgr(path):
    """EXIF 회전 적용 로드(검출↔렌더 좌표 일치 = 반드시 동일 로더 · track의 CAP_PROP_ORIENTATION_AUTO 대응).
    cv2.imread는 EXIF 무시라 세로 사진이 뒤집힐 수 있어 PIL exif_transpose로 정규화 → BGR np."""
    from PIL import Image, ImageOps
    im = Image.open(path)
    im = ImageOps.exif_transpose(im).convert("RGB")
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


def detect(img):
    """단일 이미지 → 피사체 카드 리스트. 얼굴(YuNet) + 전신·사물(YOLO11n · fail-soft). 큰 것 우선·캡."""
    H, W = img.shape[:2]
    det, _rec = ta.load_models()   # rec(SFace 임베딩)는 단일 이미지엔 군집 불필요 = 미사용
    scale = min(1.0, DET_LONG / max(W, H))
    small = cv2.resize(img, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_AREA) if scale < 1.0 else img
    det.setInputSize((small.shape[1], small.shape[0]))
    _, faces = det.detect(small)
    items = []
    if faces is not None:
        for row in faces:
            x, y, w, h = row[0] / scale, row[1] / scale, row[2] / scale, row[3] / scale
            if w < FACE_MIN or h < FACE_MIN:
                continue
            items.append({"kind": "face", "label": "얼굴",
                          "box": [int(max(0, x)), int(max(0, y)), int(w), int(h)], "score": float(row[-1])})
    # 피사체(전신·사물) — YOLO11n cv2.dnn · 없거나 실패 = 얼굴만(fail-soft · 얼굴 파이프 무영향)
    net = ta.load_subj_net()
    if net is not None:
        try:
            for (x, y, w, h, score, cls) in ta.yolo_detect(net, img):
                cls = int(cls)
                label = ta.SUBJ_CLS.get(cls, "물체")
                items.append({"kind": "person" if cls == 0 else "object", "label": label,
                              "box": [int(max(0, x)), int(max(0, y)), int(w), int(h)], "score": float(score)})
        except Exception as e:
            print(f"::warning::피사체 검출 오류 {type(e).__name__} — 얼굴만 사용", flush=True)
    # 큰 것 우선 정렬 + 캡 + id 부여(1..N · 뷰어 박스 라벨·렌더 타깃 계약)
    items.sort(key=lambda it: -(it["box"][2] * it["box"][3]))
    items = items[:CARD_CAP]
    for i, it in enumerate(items, 1):
        it["id"] = i
    return items, W, H


def main():
    if len(sys.argv) < 3:
        die("입력 오류", "usage: img_detect.py <id> <image>")
    iid, path = sys.argv[1], sys.argv[2]
    outdir = os.path.join(OUT_ROOT, iid)
    os.makedirs(outdir, exist_ok=True)
    try:
        img = load_image_bgr(path)
    except Exception as e:
        die("이미지를 못 읽었어 — 다른 파일로 해줘.", f"load: {type(e).__name__}: {e}")
    if img is None or img.size == 0:
        die("이미지를 못 읽었어 — 다른 파일로 해줘.", "empty image")

    items, W, H = detect(img)

    # 원본 보관(렌더 재사용) — R2 우선, 폴백 = git(outdir/src.<ext>). 렌더가 이 둘 중 하나로 원본 재로드.
    ext = (os.path.splitext(path)[1] or ".jpg").lower()
    src_url = ""
    if tg.R2_ON:
        try:
            with open(path, "rb") as f:
                data = f.read()
            ctype = "image/png" if ext == ".png" else ("image/webp" if ext == ".webp" else "image/jpeg")
            src_url = tg.r2_upload(data, f"imgedit_src/{iid}{ext}", ctype) or ""
        except Exception as e:
            print(f"::warning::R2 원본 업로드 실패 {type(e).__name__} — git 폴백", flush=True)
    if not src_url:
        try:
            shutil.copy(path, os.path.join(outdir, f"src{ext}"))   # 렌더가 로컬 src 재로드(R2 미설정 폴백)
        except Exception as e:
            die("원본 보관 실패 — 다시 시도해줘.", f"src copy: {type(e).__name__}: {e}")

    boxes = {"meta": {"w": W, "h": H, "src_url": src_url, "src_ext": ext, "made": ta.kst_now()},
             "items": items}
    with open(os.path.join(outdir, "boxes.json"), "w", encoding="utf-8") as f:
        json.dump(boxes, f, ensure_ascii=False)
    print(f"[imgedit] {iid} 검출 {len(items)}개(얼굴 {sum(1 for i in items if i['kind']=='face')}) → boxes.json", flush=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        die("검출 중 오류 — 다른 이미지로 해보거나 다시 시도해줘.", f"unhandled: {type(e).__name__}: {e}")
