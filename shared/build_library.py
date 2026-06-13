#!/usr/bin/env python3
"""노뮤트 /k 라이브러리 — 단일 정본(SSOT) ↔ 도메인 유닛 빌드·검증.

구조(앵글 B · 사용자 확정 260613):
  통합본(SSOT) = `apps/k/library/archive_media_master.tsv`  ← 편집은 여기서만
       │  build  (SSOT → 유닛 자동 투영)
       ▼
  유닛 = 01a~01e · 02~11 · 08a · 09 · 00_module_index  ← 워크플로가 로드(파일명·내용 불변)

SSOT 포맷 = 태그드 TSV:
  각 줄 = "<유닛파일명>\\t<그 유닛의 원본 줄 그대로>"
  → 유닛별 헤더행·BOM·모든 컬럼이 원본 그대로 보존됨(무손실).
  → build는 같은 태그 줄을 모아 1열만 떼고 파일로 복원 = 바이트 단위 정확.

서브커맨드:
  pack   : 현재 유닛들 → SSOT 생성(부트스트랩·역방향)
  build  : SSOT → 유닛 파일 재생성 (기본 동작)
  check  : SSOT를 임시폴더에 build → 현재 유닛과 바이트 대조. 불일치 = exit 1.
  verify : 기준 폴더(예: 백업)와 build 결과를 대조.

안전: pack/check 는 유닛을 '읽기만'. build 만 유닛을 쓴다. check 가 커밋 게이트.
사용: python3 shared/build_library.py check
"""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBDIR = os.path.join(ROOT, "apps", "k", "library")
SSOT = os.path.join(LIBDIR, "archive_media_master.tsv")

# SSOT를 구성하는 유닛 = 로드 순서. (08_style_addendum_image.md = 산문+코드블록 챕터, 줄 단위 보존 편입.)
UNITS = [
    "00_module_index.tsv",
    "01a_camera_lens_focal_length.tsv",
    "01b_camera_shot_size.tsv",
    "01c_camera_height_tilt.tsv",
    "01d_camera_orientation.tsv",
    "01e_camera_relationship_pov.tsv",
    "02_style_modules.tsv",
    "03_lighting_modules.tsv",
    "04_environment_modules.tsv",
    "05_negative_control.tsv",
    "06_camera_movement_video.tsv",
    "07_pov_video.tsv",
    "08_style_addendum_image.md",
    "08a_style_addendum_index.tsv",
    "09_style_kling_video.tsv",
    "10_audio_music.tsv",
    "11_acting_shadow_light.tsv",
    # 백과사전 흡수분 (260613 — /news 출신 지식: 감정조명·뉴스화풍·색이론·수사학·큐레이션·합성)
    "12_lighting_emotion.tsv",
    "13_style_news_canon.tsv",
    "14_color_grading.tsv",
    "15_visual_rhetoric.tsv",
    "16_curation_dispatch.tsv",
    "17_composition.tsv",
    "18_english_tails.tsv",
    "19_safety_frame_prompts.tsv",
    # 400% 보강 신규 챕터 (260613 — 새 인덱싱 축: 화면비·전환·표정감정·날씨·영화사조·VFX·프롬프트공학)
    "20_aspect_ratio_format.tsv",
    "21_transitions_editing.tsv",
    "22_expression_emotion.tsv",
    "23_weather_atmosphere.tsv",
    "24_film_movements.tsv",
    "25_vfx_effects.tsv",
    "26_prompt_engineering_meta.tsv",
    # 400% 보강 wave2 신규 챕터 (260613 — 재질·세트미술·의상소품·장르문법·자막타이틀·블로킹)
    "27_materials_texture.tsv",
    "28_set_production_design.tsv",
    "29_wardrobe_props.tsv",
    "30_genre_conventions.tsv",
    "31_graphic_title_design.tsv",
    "32_blocking_staging.tsv",
    "33_gesture_interaction.tsv",
]

SSOT_BANNER = (
    "# ⛔ 통합본(SSOT) — /k 라이브러리 전 도메인 단일 정본. "
    "편집은 이 파일에서만 → `python3 shared/build_library.py build` 로 유닛 자동 생성. "
    "각 줄 1열 = 대상 유닛 파일명. 수정·삭제 = 사용자 이중 허락(라우터 §기틀 보호)."
)


def _read_lines(path):
    """파일을 (줄 리스트, 끝-newline 여부)로. BOM 은 첫 줄 안에 그대로 보존."""
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    ends_nl = text.endswith("\n")
    if ends_nl:
        text = text[:-1]  # 마지막 newline 1개 제거(분할 인공물 방지)
    lines = text.split("\n")
    return lines, ends_nl


def _write_bytes(path, text):
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def pack():
    """현재 유닛들 → SSOT(태그드 TSV) 생성. 역방향 부트스트랩."""
    out = [SSOT_BANNER]
    for name in UNITS:
        p = os.path.join(LIBDIR, name)
        lines, ends_nl = _read_lines(p)
        for ln in lines:
            out.append(f"{name}\t{ln}")
    _write_bytes(SSOT, "\n".join(out) + "\n")
    print(f"pack ✓ SSOT 생성: {os.path.relpath(SSOT, ROOT)} ({len(UNITS)}개 유닛)")


def _ssot_to_units():
    """SSOT 파싱 → {유닛파일명: 복원 바이트}. 순수 함수(디스크 미기록)."""
    with open(SSOT, "rb") as f:
        text = f.read().decode("utf-8")
    if text.endswith("\n"):
        text = text[:-1]
    bucket = {}  # name -> [lines]
    order = []
    for ln in text.split("\n"):
        if ln.startswith("#"):  # 배너 줄 스킵
            continue
        if "\t" not in ln:
            continue
        name, rest = ln.split("\t", 1)
        if name not in bucket:
            bucket[name] = []
            order.append(name)
        bucket[name].append(rest)
    result = {}
    for name in order:
        result[name] = ("\n".join(bucket[name]) + "\n").encode("utf-8")
    return result


def build():
    """SSOT → 유닛 파일 재생성(디스크에 씀)."""
    units = _ssot_to_units()
    for name, data in units.items():
        with open(os.path.join(LIBDIR, name), "wb") as f:
            f.write(data)
    print(f"build ✓ 유닛 {len(units)}개 재생성")


def _diff_against(ref_dir, label):
    """SSOT build 결과를 ref_dir 의 같은 파일과 바이트 대조. 불일치 목록 반환."""
    units = _ssot_to_units()
    mismatches, missing = [], []
    for name, data in units.items():
        rp = os.path.join(ref_dir, name)
        if not os.path.exists(rp):
            missing.append(name)
            continue
        with open(rp, "rb") as f:
            ref = f.read()
        if data != ref:
            # 어디가 다른지 첫 불일치 줄 찾기
            a = data.decode("utf-8").split("\n")
            b = ref.decode("utf-8").split("\n")
            detail = f"줄수 {len(a)} vs {len(b)}"
            for i in range(min(len(a), len(b))):
                if a[i] != b[i]:
                    detail = f"L{i+1} 불일치"
                    break
            mismatches.append((name, detail))
    return mismatches, missing


def _check_addendum_refs():
    """전 유닛의 S-N(화풍 애드덤) 참조가 생존 S코드만 가리키는지 검증.
    삭제된 애드덤 코드(예: 08 큐레이션 때 컷된 S-9·S-33 등)를 다른 챕터가
    아직 참조하면 위반으로 잡는다 — 09 '원본'·04 비고 같은 stale 재발 방지."""
    import re
    alive = set()
    idx = os.path.join(LIBDIR, "08a_style_addendum_index.tsv")
    if os.path.exists(idx):
        for ln in open(idx, encoding="utf-8"):
            m = re.match(r"(S-\d+)\b", ln)
            if m:
                alive.add(m.group(1))
    if not alive:
        return []  # 08a 없으면 검사 스킵(오탐 방지)
    viol = []
    for name in UNITS:
        if name.startswith("08"):  # 정의처(08·08a) 자신은 제외
            continue
        p = os.path.join(LIBDIR, name)
        if not os.path.exists(p):
            continue
        for i, ln in enumerate(open(p, encoding="utf-8"), 1):
            for tok in re.findall(r"S-\d+", ln):
                if tok not in alive:
                    viol.append(f"{name}:{i} → {tok} (삭제된 애드덤 코드 참조)")
    return viol


def check():
    """왕복 검증: SSOT→유닛 재생성이 '현재 유닛'과 바이트 동일 + 애드덤 참조 정합."""
    mism, miss = _diff_against(LIBDIR, "현재")
    # SSOT 가 모든 UNITS 를 빠짐없이 담았는지
    units = _ssot_to_units()
    notin = [n for n in UNITS if n not in units]
    addref = _check_addendum_refs()  # 삭제 S코드 참조 게이트(재발 방지)
    ok = not (mism or miss or notin or addref)
    if ok:
        print(f"check ✓ 완전 일치 — SSOT→유닛 재생성 = 현재 유닛 ({len(units)}개) 바이트 동일 · 애드덤 참조 정합.")
        return 0
    print("check ✗ 불일치:")
    for n, d in mism:
        print(f"  - {n}: {d}")
    for n in miss:
        print(f"  - {n}: 현재 유닛에 없음")
    for n in notin:
        print(f"  - {n}: SSOT 에 누락")
    for v in addref:
        print(f"  - {v}")
    return 1


def verify(ref_dir):
    mism, miss = _diff_against(ref_dir, ref_dir)
    if not (mism or miss):
        print(f"verify ✓ build 결과 = {os.path.relpath(ref_dir, ROOT)} 바이트 동일.")
        return 0
    print(f"verify ✗ vs {ref_dir}:")
    for n, d in mism:
        print(f"  - {n}: {d}")
    for n in miss:
        print(f"  - {n}: 기준에 없음")
    return 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "pack":
        pack()
    elif cmd == "build":
        build()
    elif cmd == "check":
        sys.exit(check())
    elif cmd == "verify":
        sys.exit(verify(sys.argv[2]))
    else:
        print(__doc__)
        sys.exit(2)
