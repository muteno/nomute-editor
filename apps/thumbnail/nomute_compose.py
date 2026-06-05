#!/usr/bin/env python3
"""
NO MUTE Phase 2 합성 스크립트 (실행 가능 버전)

Usage:
  python3 nomute_compose.py <reels|post> <overlay> <background> <output> [options]

Options:
  --offset-x N    크롭 X 오프셋 수동 조정 (픽셀, +→오른쪽, -→왼쪽)
  --offset-y N    크롭 Y 오프셋 수동 조정 (픽셀, +→아래, -→위)
  --scale F       리사이즈 배율 수동 보정 (1.0=기본, 1.2=20% 확대)
  --blur          블러 배경 모드 강제 사용 (유튜브 쇼츠 스타일)
"""

import sys
import os
import argparse
import cv2
import numpy as np
import mediapipe as mp
from PIL import Image, ImageFilter


# ── 포맷별 스펙 ───────────────────────────────────────────
SPECS = {
    "reels": {"w": 1080, "h": 1920, "ty": 1119},
    "post":  {"w": 1080, "h": 1350, "ty": 822},
}


# ── 피사체 중심 검출 (fallback 체인) ──────────────────────
def detect_subject(img_path):
    """
    Returns (cx, cy, method) in original image pixel coordinates.
    Fallback chain: 얼굴 → 포즈 → 에지 → 기본값
    """
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        raise FileNotFoundError(f"배경 이미지를 읽을 수 없음: {img_path}")

    h, w = img_bgr.shape[:2]

    # BGR→RGB 한 번만 변환
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # 1) Face Detection
    try:
        with mp.solutions.face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.5
        ) as face_det:
            res = face_det.process(rgb)
            if res.detections:
                best = max(
                    res.detections,
                    key=lambda d: d.location_data.relative_bounding_box.width
                                * d.location_data.relative_bounding_box.height
                )
                bb = best.location_data.relative_bounding_box
                cx = int((bb.xmin + bb.width / 2) * w)
                cy = int((bb.ymin + bb.height / 2) * h)
                return cx, cy, "얼굴"
    except Exception as e:
        print(f"WARN: Face detection 실패 ({e}), 다음 단계로")

    # 2) Pose Detection
    try:
        with mp.solutions.pose.Pose(
            static_image_mode=True, min_detection_confidence=0.5
        ) as pose:
            res = pose.process(rgb)
            if res.pose_landmarks:
                lm = res.pose_landmarks.landmark
                nose = lm[mp.solutions.pose.PoseLandmark.NOSE]
                l_hip = lm[mp.solutions.pose.PoseLandmark.LEFT_HIP]
                r_hip = lm[mp.solutions.pose.PoseLandmark.RIGHT_HIP]
                hip_y = (l_hip.y + r_hip.y) / 2
                cy = int(((nose.y + hip_y) / 2) * h)
                cx = int(nose.x * w)
                return cx, cy, "포즈"
    except Exception as e:
        print(f"WARN: Pose detection 실패 ({e}), 다음 단계로")

    # 3) Edge Density
    try:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        blurred = cv2.GaussianBlur(edges.astype(np.float32), (0, 0), sigmaX=w // 10)
        peak = np.unravel_index(blurred.argmax(), blurred.shape)
        if blurred[peak] > 0:
            return int(peak[1]), int(peak[0]), "에지"
    except Exception as e:
        print(f"WARN: Edge detection 실패 ({e}), 기본값 사용")

    # 4) Fallback
    return w // 2, int(h * 0.35), "기본값"


# ── Case 분기 + 리사이즈 & 크롭 ──────────────────────────
def prepare_background(img_path, target_w, target_h, fmt,
                       adj_offset_x=0, adj_offset_y=0, adj_scale=1.0):
    """
    Returns (bg_image: PIL.Image RGBA, case_num, method, crop_ratio)
    """
    img = Image.open(img_path).convert("RGB")
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    # Case 1: 정확히 일치
    if src_w == target_w and src_h == target_h:
        return img.convert("RGBA"), 1, "-", 0.0

    # Case 2: 비율 동일 (오차 0.5% 이내)
    if abs(src_ratio - target_ratio) / target_ratio < 0.005:
        img = img.resize((target_w, target_h), Image.LANCZOS)
        return img.convert("RGBA"), 2, "-", 0.0

    # Case 3: 스마트 크롭
    cx, cy, method = detect_subject(img_path)

    # cover 리사이즈 (짧은 변 기준) + 수동 배율 보정
    scale = max(target_w / src_w, target_h / src_h) * adj_scale
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)

    # 리사이즈 후 타겟보다 작아지면 안 됨
    if new_w < target_w or new_h < target_h:
        scale = max(target_w / src_w, target_h / src_h)
        new_w = int(src_w * scale)
        new_h = int(src_h * scale)
        print(f"WARN: scale 보정값이 너무 작아 기본 cover 배율로 복원")

    img = img.resize((new_w, new_h), Image.LANCZOS)

    # 피사체 중심도 스케일링
    cx = int(cx * scale)
    cy = int(cy * scale)

    # 크롭 오프셋 (피사체 중심 → 타겟의 상단 35% 위치)
    target_cy = int(target_h * 0.35)
    off_y = cy - target_cy
    off_x = cx - target_w // 2

    # 텍스트 충돌 검증
    ty = SPECS[fmt]["ty"]
    subject_in_text_zone = (cy - off_y) > ty
    if subject_in_text_zone:
        off_y = cy - int(ty * 0.8)

    # 수동 오프셋 조정 적용
    off_x += adj_offset_x
    off_y += adj_offset_y

    # 클램프
    off_x = max(0, min(off_x, new_w - target_w))
    off_y = max(0, min(off_y, new_h - target_h))

    cropped = img.crop((off_x, off_y, off_x + target_w, off_y + target_h))

    # 크롭률
    crop_ratio = (1 - (target_w * target_h) / (new_w * new_h)) * 100

    return cropped.convert("RGBA"), 3, method, crop_ratio


# ── 블러 배경 모드 ────────────────────────────────────────
def blur_background(img_path, target_w, target_h):
    """유튜브 쇼츠 스타일: 블러 배경 + 중앙 원본"""
    img = Image.open(img_path).convert("RGB")
    src_w, src_h = img.size

    # 블러 배경
    bg = img.resize((target_w, target_h), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=30))

    # 원본 비율 유지 리사이즈
    scale = min(target_w / src_w, target_h / src_h)
    fit_w = int(src_w * scale)
    fit_h = int(src_h * scale)
    fit = img.resize((fit_w, fit_h), Image.LANCZOS)

    # 중앙 배치
    paste_x = (target_w - fit_w) // 2
    paste_y = (target_h - fit_h) // 2
    bg.paste(fit, (paste_x, paste_y))

    return bg.convert("RGBA")


# ── 최종 합성 ─────────────────────────────────────────────
def compose(bg_rgba, overlay_path, output_path):
    """배경(RGBA) + 오버레이(RGBA) → alpha_composite → PNG 저장"""
    if not os.path.exists(overlay_path):
        raise FileNotFoundError(f"오버레이 파일을 찾을 수 없음: {overlay_path}")

    overlay = Image.open(overlay_path).convert("RGBA")

    if bg_rgba.size != overlay.size:
        raise ValueError(
            f"배경({bg_rgba.size})과 오버레이({overlay.size}) 크기 불일치"
        )

    result = Image.alpha_composite(bg_rgba, overlay)
    result.save(output_path, format="PNG")

    # 결과 검증
    v = Image.open(output_path)
    assert v.mode == "RGBA", f"SAVE ERROR: mode={v.mode}"
    assert v.size == bg_rgba.size, f"SAVE ERROR: size={v.size}"
    print(f"COMPOSED: {output_path} ({v.size},{v.mode})")


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="NO MUTE Phase 2 합성 스크립트"
    )
    parser.add_argument("fmt", choices=["reels", "post"],
                        help="포맷 (reels|post)")
    parser.add_argument("overlay", help="오버레이 PNG 경로")
    parser.add_argument("background", help="배경 이미지 경로")
    parser.add_argument("output", help="출력 파일 경로")
    parser.add_argument("--offset-x", type=int, default=0,
                        help="크롭 X 오프셋 조정 (픽셀)")
    parser.add_argument("--offset-y", type=int, default=0,
                        help="크롭 Y 오프셋 조정 (픽셀)")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="리사이즈 배율 보정 (1.0=기본)")
    parser.add_argument("--blur", action="store_true",
                        help="블러 배경 모드 강제 사용")

    args = parser.parse_args()

    spec = SPECS[args.fmt]
    tw, th = spec["w"], spec["h"]

    if args.blur:
        # 블러 배경 모드
        bg = blur_background(args.background, tw, th)
        compose(bg, args.overlay, args.output)
        print(f"MODE: 블러 배경")
    else:
        bg, case_num, method, crop_ratio = prepare_background(
            args.background, tw, th, args.fmt,
            adj_offset_x=args.offset_x,
            adj_offset_y=args.offset_y,
            adj_scale=args.scale,
        )

        # 크롭률 50% 이상 경고
        if crop_ratio >= 50:
            print(f"WARN: 크롭률 {crop_ratio:.1f}% — 잘리는 영역이 큼. "
                  f"--blur 옵션으로 블러 배경 모드 사용 가능")

        compose(bg, args.overlay, args.output)
        print(f"CASE: {case_num} | 검출: {method} | 크롭률: {crop_ratio:.1f}%")


if __name__ == "__main__":
    main()
