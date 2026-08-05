#!/usr/bin/env python3
"""카드뉴스 이미지 합성기 - 1080×1350 캔버스 고정 방식

v3 변경사항:
- 자동 줄바꿈 제거 (사전 측정 → 외부에서 압축안 제시)
- 따옴표 들여쓰기 자동 처리 (x 오프셋 직접 시프트, 공백 패딩 X)
- 폭 검증 공식: (들여쓰기 + 텍스트) ≤ MAX_WIDTH
- 14종 따옴표 페어 지원 (한국어/ASCII/낫표/길레메)
"""
import sys, re, os
from datetime import datetime, timezone, timedelta

# 합성 의존성 — 폭 계산(글자 advance·줄 폭 검증)만 쓰는 호출부(card_gate.py lint)는 이게 없는
# 환경(Actions card_plan = 텍스트 전용 잡)에서도 이 모듈을 import 할 수 있어야 한다. 없으면 None 으로
# 두고, 합성 경로(generate/render_text/smart_crop)에서만 필요해진다 — 폭 판정 SSOT를 이 파일 하나로 유지.
try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    import cv2
except ImportError:
    np = Image = ImageDraw = ImageFont = ImageOps = cv2 = None

# ─── 고정 캔버스 ───
CANVAS_W = 1080
CANVAS_H = 1350

# ─── 텍스트 렌더링 설정 ───
FONT_SIZE = 54
LINE_HEIGHT = 88
MARGIN_LEFT = 87
MARGIN_RIGHT = 56
MARGIN_BOTTOM = 234
MAX_WIDTH = CANVAS_W - MARGIN_LEFT - MARGIN_RIGHT  # 937
START_X = MARGIN_LEFT  # 87 (캔버스 가로 8.1%)
START_Y = 888          # 캔버스 세로 65.8%
SAFE_BOTTOM = CANVAS_H - 40  # 1310
COLOR_DEFAULT = (255, 255, 255)
COLOR_HIGHLIGHT = (15, 253, 2)  # #0FFD02 형광그린 — 콘텐츠 상수 원복(운영자 260706 "제작물이 브랜드 컬러로 뒤집어씌어짐" 롤백 · 콘텐츠 색 = UI 팔레트와 별개 축, UI 개편에 동행 금지)

# ─── 폰트 ───
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

# ─── 따옴표 페어 (여는: 닫는) — 들여쓰기 추적용 ───
QUOTE_PAIRS = {
    '\u201C': '\u201D',  # " "  큰따옴표
    '\u2018': '\u2019',  # ' '  작은따옴표
    '\u300C': '\u300D',  # 「 」 홑낫표
    '\u300E': '\u300F',  # 『 』 겹낫표
    '\u00AB': '\u00BB',  # « »  길레메
    '\u2039': '\u203A',  # ‹ ›  싱글 길레메
}
OPENING_QUOTES = set(QUOTE_PAIRS.keys())
CLOSING_QUOTES = set(QUOTE_PAIRS.values())
ASCII_QUOTES = {'"', "'"}  # 같은 문자라 토글 방식

# ─── 글자 폭(advance) 폴백 표 — 폰트 없는 환경용 ───
# 왜: 폭 판정의 정본은 실제 폰트 실측(check_line_widths)이다. 그런데 카드 *텍스트만* 만드는 경로
#   (Actions card_plan = cardmake.sh MODE=text · 제미나이 0)엔 Noto CJK 가 설치돼 있지 않아,
#   게이트(card_gate.py lint)가 폰트를 못 잡고 근사 프록시(가중폭 0.5/1.0)로 판정해 왔다.
#   그 프록시는 실측과 어긋난다 — 공백 13px(0.26자)·숫자/영문/큰따옴표 31~32px(0.64자)인데
#   둘 다 0.5로 세니, 숫자 많은 줄은 통과시키고(렌더 초과 = FN) 공백 많은 줄은 붙잡았다(FP).
#   → FONT_PATH·FONT_SIZE 실측 advance 를 그대로 표로 박아, 폰트가 없어도 렌더러와 같은 판정을 낸다.
# 재생성·검증: `python3 apps/comp/card_news.py --advtable`  (폰트 있는 환경에서 실행 · 어긋나면 표를 갱신)
_ADV_GROUPS = {
    13: " ", 16: "|", 17: "ijl", 18: "',.:;I‘’", 20: "!-f",
    21: "()/[\\]{}", 23: "t", 24: "r", 27: "s", 28: "*?z", 29: "c",
    30: "–", 31: "\"J_vxy“”", 32: "#$+0123456789<=>FLY^ae~·",
    33: "Zgk", 34: "ESTVX`o", 35: "Abdhnpqu", 36: "CP", 37: "BKR", 39: "DG",
    40: "&", 41: "HNU", 42: "OQ", 46: "M", 47: "w", 49: "—", 50: "W",
    52: "%m", 55: "@",
}
ADV_TABLE = {ch: w for w, chars in _ADV_GROUPS.items() for ch in chars}
ADV_HANGUL = 50   # 한글 음절·자모 (전부 균일 — 실측)
ADV_WIDE = 54     # 한자·전각·낫표·… 등 광폭 (미등록 문자 보수 기본값도 이 값)


def _is_hangul(ch):
    o = ord(ch)
    return 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F


def char_adv(ch, font=None):
    """글자 1개의 진행폭(px). font 가 있으면 실측, 없으면 폴백 표."""
    if font is not None:
        bbox = font.getbbox("가" + ch + "가")
        base = font.getbbox("가가")
        return (bbox[2] - bbox[0]) - (base[2] - base[0])
    if _is_hangul(ch):
        return ADV_HANGUL
    return ADV_TABLE.get(ch, ADV_WIDE)


def text_width(s, font=None):
    """문자열 렌더 폭(px). font 있으면 실측 bbox, 없으면 폴백 합산(실측 대비 +1% 내외 보수)."""
    if not s:
        return 0
    if font is not None:
        bbox = font.getbbox(s)
        return bbox[2] - bbox[0]
    return sum(char_adv(ch) for ch in s)


def load_font():
    """합성용 폰트 로드 — 폰트·PIL 없으면 None(호출부는 폴백 표로 진행)."""
    if ImageFont is None or not os.path.isfile(FONT_PATH):
        return None
    try:
        return ImageFont.truetype(FONT_PATH, FONT_SIZE, index=1)
    except Exception:
        return None


def detect_subject_center(img_cv):
    """피사체 중심 검출 (fallback 체인: 얼굴 → 포즈 → 에지 → 기본값)"""
    h, w = img_cv.shape[:2]
    method = "기본값"

    try:
        import mediapipe as mp
        face_det = mp.solutions.face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.5)
        rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        results = face_det.process(rgb)
        if results.detections:
            biggest = max(results.detections,
                          key=lambda d: d.location_data.relative_bounding_box.width *
                          d.location_data.relative_bounding_box.height)
            bb = biggest.location_data.relative_bounding_box
            cx = int((bb.xmin + bb.width / 2) * w)
            cy = int((bb.ymin + bb.height / 2) * h)
            face_det.close()
            return cx, cy, "얼굴"
        face_det.close()
    except Exception:
        pass

    try:
        import mediapipe as mp
        pose = mp.solutions.pose.Pose(
            static_image_mode=True, min_detection_confidence=0.5)
        rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        if results.pose_landmarks:
            lm = results.pose_landmarks.landmark
            nose = lm[0]
            hip_l, hip_r = lm[23], lm[24]
            hip_y = (hip_l.y + hip_r.y) / 2
            cx = int(nose.x * w)
            cy = int(((nose.y + hip_y) / 2) * h)
            pose.close()
            return cx, cy, "포즈"
        pose.close()
    except Exception:
        pass

    try:
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        if np.sum(edges > 0) > 100:
            blur_radius = max(h, w) // 6
            if blur_radius % 2 == 0:
                blur_radius += 1
            heatmap = cv2.GaussianBlur(edges.astype(np.float32),
                                       (blur_radius, blur_radius), 0)
            _, _, _, max_loc = cv2.minMaxLoc(heatmap)
            best_cx, best_cy = max_loc
            return best_cx, best_cy, "에지"
    except Exception:
        pass

    return w // 2, int(h * 0.35), method


def smart_crop(img_rgb, img_rgba, target_w, target_h):
    """피사체 중심 기반 스마트 크롭 (4:5 비율은 리사이즈만)"""
    src_w, src_h = img_rgba.size

    if src_w == target_w and src_h == target_h:
        return img_rgba, "정확", 0, "exact"

    src_ratio = src_w / src_h
    target_ratio = target_w / target_h
    if abs(src_ratio - target_ratio) < 0.004:
        resized = img_rgba.resize((target_w, target_h), Image.LANCZOS)
        return resized, "4:5 리사이즈", 0, "resize_only"

    img_cv = cv2.cvtColor(np.array(img_rgb), cv2.COLOR_RGB2BGR)
    subj_x, subj_y, method = detect_subject_center(img_cv)

    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img_resized = img_rgba.resize((new_w, new_h), Image.LANCZOS)

    sx = int(subj_x * scale)
    sy = int(subj_y * scale)

    left = sx - target_w // 2
    top = sy - int(target_h * 0.35)

    text_zone_y = target_h - MARGIN_BOTTOM
    if sy > text_zone_y:
        top = sy - int(target_h * 0.25)

    left = max(0, min(left, new_w - target_w))
    top = max(0, min(top, new_h - target_h))

    cropped = img_resized.crop((left, top, left + target_w, top + target_h))

    crop_ratio = (1 - (target_w * target_h) / (new_w * new_h)) * 100
    return cropped, method, crop_ratio, "smart_crop"


def create_gradient_overlay(width, height):
    """그라데이션 오버레이 (상단 38.6% 투명 → 하단 alpha 최대 236)"""
    overlay = np.zeros((height, width, 4), dtype=np.uint8)
    start = int(height * 0.386)
    rows = np.arange(start, height)
    t = (rows - start) / (height - start)
    a, b = 1.268, 3.217
    alpha = (t**a / (t**a + (1 - t)**b)) * 236
    alpha = np.clip(alpha, 0, 236).astype(np.uint8)
    overlay[start:height, :, 3] = alpha[:, np.newaxis]
    return Image.fromarray(overlay)


def _strip_emphasis(line):
    """*강조* 마킹 제거 (실제 렌더링 텍스트만 남김)"""
    return re.sub(r'\*([^*]+)\*', r'\1', line)


def parse_segments(line):
    """*강조* 마킹 파싱 → [(type, text), ...]
    운영자 260720: 별표 run 1~2개 = 강조 델리미터(토글) · 3개 이상 연속 = 리터럴(글자 = 마스킹 보존).
    프론트 normEmph2 + 미리보기 renderEmph2 + nomute_overlay.parse와 로직 동일(정본 4면 일치)."""
    segments = []
    on = False
    buf = ''
    i = 0
    n = len(line)
    while i < n:
        if line[i] == '*':
            j = i
            while j < n and line[j] == '*':
                j += 1
            if j - i >= 3:                                    # 3+ = 리터럴
                buf += line[i:j]
            else:                                            # 1~2 = 델리미터 토글
                if buf:
                    segments.append(('h' if on else 'n', buf))
                    buf = ''
                on = not on
            i = j
        else:
            buf += line[i]
            i += 1
    if buf:
        segments.append(('h' if on else 'n', buf))
    return segments


def compute_line_offsets(text_lines, font=None):
    """각 줄 시작 시점의 x 오프셋 계산.

    여는 따옴표가 줄을 넘어 닫힐 때, 그 사이 줄들은 따옴표 폭만큼 들여쓰기됨.
    페어드 따옴표는 스택, ASCII 따옴표는 토글 방식.
    font=None = 폰트 없는 환경(게이트 전용) — 폴백 표로 같은 계산.
    """
    ascii_widths = {ch: char_adv(ch, font) for ch in ASCII_QUOTES}

    offsets = []
    paired_stack = []
    ascii_state = {ch: False for ch in ASCII_QUOTES}

    for line in text_lines:
        current_offset = sum(paired_stack)
        for ch, opened in ascii_state.items():
            if opened:
                current_offset += ascii_widths[ch]
        offsets.append(current_offset)

        clean = _strip_emphasis(line)
        for ch in clean:
            if ch in OPENING_QUOTES:
                paired_stack.append(char_adv(ch, font))
            elif ch in CLOSING_QUOTES:
                if paired_stack:
                    paired_stack.pop()
            elif ch in ASCII_QUOTES:
                ascii_state[ch] = not ascii_state[ch]

    return offsets


def measure_line_widths(text_lines, font=None):
    """각 줄의 (들여쓰기 + 텍스트) 총 폭 px — **초과 여부와 무관하게 전 줄**.

    check_line_widths(초과만 반환 = 상한 방향)의 **하한 방향 짝**. 카드 한 줄이 상한 937px 중
    몇 px를 실제로 쓰는지 재려면 통과 줄의 폭도 필요한데 구 API는 그걸 버렸다 = 「덱이 얇아지는가」
    가 관측 축 자체로 없었다(260805 실측 = cards/ 전량 499덱 11,315줄 평균 64.7% · 70% 미만 줄
    61.2% · 단 월별로 크게 다르다 = 2606 56.1% → 2607 70.8% → 2608 74.1%로 상승 중이라
    **풀링 평균은 스테일** · 소비자는 같은 자·같은 창끼리만 비교할 것).
    빈 줄(강조 별표만 등) = None. 오프셋·폭 계산은 compute_line_offsets/text_width 재사용 =
    렌더러와 **같은 자**(게이트가 별도 산식을 복제하면 드리프트한다).
    """
    offsets = compute_line_offsets(text_lines, font)
    widths = []
    for i, line in enumerate(text_lines):
        clean = _strip_emphasis(line)
        widths.append(None if not clean else offsets[i] + text_width(clean, font))
    return widths


def check_line_widths(text_lines, font=None, max_width=MAX_WIDTH):
    """각 줄의 (들여쓰기 + 텍스트) 폭 측정. 초과 항목 리스트 반환.

    font=None = 폴백 표(폰트 미설치 환경) — card_gate.py lint 가 이 경로로 렌더러와 같은 판정을 낸다.
    """
    offsets = compute_line_offsets(text_lines, font)
    overflows = []
    for i, line in enumerate(text_lines):
        clean = _strip_emphasis(line)
        if not clean:
            continue
        text_w = text_width(clean, font)
        total_w = offsets[i] + text_w
        if total_w > max_width:
            overflows.append({
                'idx': i,
                'line': line,
                'indent': offsets[i],
                'text_width': text_w,
                'total': total_w,
                'overflow': total_w - max_width,
                'max': max_width,
            })
    return overflows


def render_text(canvas, text_lines, font):
    """텍스트를 캔버스에 렌더링.

    - 자동 줄바꿈 없음 (사용자 줄바꿈만 사용)
    - 따옴표 들여쓰기 자동 적용 (x 오프셋 시프트)
    - 사전 검증 통과한 텍스트만 들어와야 함
    """
    start_x = START_X
    start_y = START_Y

    offsets = compute_line_offsets(text_lines, font)

    total_lines = len(text_lines)
    last_top_y = start_y + (total_lines - 1) * LINE_HEIGHT
    # 하단 = 마지막 줄 *실측 잉크* 하단 — 구 FONT_SIZE(54) 근사는 실제 잉크(한글 ~68px·라틴 디센더 ~77px)보다
    #   얕아 5줄 케이스가 검사만 통과하고 렌더는 SAFE_BOTTOM 침범(Pillow 실측 260710). getbbox[3] =
    #   draw.text 기본 앵커 기준 잉크 하단 오프셋이라 렌더와 동일 좌표계(한글-온리 5줄은 실측대로 계속 통과).
    plain_last = "".join(seg for _, seg in parse_segments(text_lines[-1])) if text_lines else ""
    ink_bottom = font.getbbox(plain_last)[3] if plain_last.strip() else FONT_SIZE
    last_bottom_y = last_top_y + ink_bottom

    if last_bottom_y > SAFE_BOTTOM:
        print(f"⚠ 텍스트 {total_lines}줄 — 하단 끝({last_bottom_y}px)이 "
              f"안전 영역({SAFE_BOTTOM}px)을 넘어. 줄 수를 줄여줘.")
        return False

    draw = ImageDraw.Draw(canvas)
    for i, line in enumerate(text_lines):
        x = start_x + offsets[i]
        y = start_y + i * LINE_HEIGHT
        for seg_type, seg_text in parse_segments(line):
            color = COLOR_HIGHLIGHT if seg_type == 'h' else COLOR_DEFAULT
            draw.text((x, y), seg_text, font=font, fill=color)
            bbox = font.getbbox(seg_text)
            x += bbox[2] - bbox[0]
    return True


def generate(image_path, text_lines, output_path):
    """카드뉴스 합성 메인"""
    if not os.path.isfile(image_path):
        print(f"❌ 이미지 파일을 찾을 수 없어: {image_path}")
        return False

    if not os.path.isfile(FONT_PATH):
        print(f"❌ 폰트 파일을 찾을 수 없어: {FONT_PATH}")
        return False

    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE, index=1)
    except Exception as e:
        print(f"❌ 폰트 로드 실패: {e}")
        return False

    # 가로 폭 사전 검증 — (들여쓰기 + 텍스트) ≤ MAX_WIDTH
    overflows = check_line_widths(text_lines, font, MAX_WIDTH)
    if overflows:
        print(f"❌ 가로 초과 줄 {len(overflows)}건 — 합성 중단")
        for ov in overflows:
            print(f"  줄 {ov['idx']+1}: \"{ov['line']}\"")
            print(f"    들여쓰기 {ov['indent']}px + 텍스트 {ov['text_width']}px "
                  f"= {ov['total']}px / {ov['max']}px ({ov['overflow']:+}px 오버)")
        return False

    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        print(f"❌ 이미지 로드 실패: {e}")
        return False

    if img.mode == 'RGBA':
        bg = Image.new('RGBA', img.size, (0, 0, 0, 255))
        img = Image.alpha_composite(bg, img)

    img_rgb = img.convert('RGB')
    img_rgba = img.convert('RGBA')

    base, method, crop_ratio, mode = smart_crop(img_rgb, img_rgba, CANVAS_W, CANVAS_H)
    print(f"📐 원본: {img.size} → 모드: {mode} | 검출: {method} | 크롭률: {crop_ratio:.1f}%")

    gradient = create_gradient_overlay(CANVAS_W, CANVAS_H)
    composited = Image.alpha_composite(base, gradient)

    ok = render_text(composited, text_lines, font)
    if not ok:
        return False

    final = composited.convert('RGB')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # subsampling=0(4:4:4) — 기본 4:2:0은 형광그린(#0FFD02) 강조 텍스트 가장자리 크로마 번짐(분신11 감사 260709)
    final.save(output_path, format='JPEG', quality=90, subsampling=0, optimize=True)   # q90 = 전 산출 통일값(운영자 260805 "투명일 필요 없는 건 모두 jpg 90" · 구 95) · 4:4:4 유지 = 강조색 크로마 번짐 방지
    print(f"OK: {output_path} ({final.size})")
    return True


def _advtable_check():
    """폴백 표 ↔ 실제 폰트 실측 대조(드리프트 감시). 어긋난 글자를 출력하고 rc=1."""
    font = load_font()
    if font is None:
        print("폰트 없음(%s) — 대조 불가. 폰트 있는 환경에서 실행할 것." % FONT_PATH)
        return 1
    bad = []
    for ch in list(ADV_TABLE) + ["가", "힣", "法", "「", "…"]:
        real, tab = char_adv(ch, font), char_adv(ch)
        if real != tab:
            bad.append("%r 표 %d ≠ 실측 %d" % (ch, tab, real))
    if bad:
        print("ADVTABLE ✗ 드리프트 %d건:" % len(bad))
        for b in bad:
            print("  - " + b)
        return 1
    print("ADVTABLE ✓ %d자 일치 (FONT_SIZE=%d · MAX_WIDTH=%d)" % (len(ADV_TABLE), FONT_SIZE, MAX_WIDTH))
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--advtable":
        sys.exit(_advtable_check())
    if len(sys.argv) < 3:
        print("Usage: python3 card_news.py <image_path> <line1> [line2] ...")
        print("       python3 card_news.py --advtable   (폭 폴백 표 ↔ 폰트 실측 대조)")
        sys.exit(1)

    image_path = sys.argv[1]
    text_lines = sys.argv[2:]

    kst = timezone(timedelta(hours=9))
    ts = datetime.now(kst).strftime("%y%m%d_%H%M%S")
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    output_path = f"/mnt/user-data/outputs/{ts}_{base_name}.jpg"

    success = generate(image_path, text_lines, output_path)
    if not success:
        sys.exit(1)
