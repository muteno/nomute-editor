#!/usr/bin/env python3
# 음량 통일(라우드니스 정규화) 공유 헬퍼 — 완성 영상(mp4)의 오디오만 −14 LUFS(TP −1.5·LRA 11)로 맞추고
#   좌우(L/R)를 모노합으로 통일(운영자 260710 확정: 0dB 절대 안 넘게 부족한 음량을 맞추고 좌우 차이 통일).
# 방식 = ffmpeg loudnorm 2패스{1패스 오디오만 측정(JSON) → 2패스 measured_*+linear=true = 가능하면 선형 게인(다이내믹 무손상),
#   불가하면 loudnorm 자체가 다이내믹 모드 폴백}. 측정 실패 = 단일패스 폴백(여전히 정규화·근사 표기).
# 비디오 스트림 = copy(재인코딩 0) → 완성본 후처리 몇 초~수십 초. 컷/배경음 제거 등 어떤 가공 뒤에 돌려도
#   *최종 믹스*를 측정하므로 의미가 정확하다(인라인 2패스는 가공 체인마다 측정 지점이 틀어짐 = 후처리가 정본인 이유).
# 사용처(SSOT): apps/conv/conv_run.py(변환 탭 음량 [통일]) · (예정) 통합 영상 편집기/ly_burn — 자체 loudnorm 재구현 금지
#   (ly_burn의 기존 -16 인라인은 배경음 제거 경로 한정 보정 = 별개 축·통합 시 이 헬퍼로 수렴 예정 · 작업이력 260710).
# 반환 = (ok, note): ok=True면 out 생성됨(호출자가 교체 사용). 오디오 없음·실패 = (False, 사유) — 호출자는 원본 유지(fail-soft).
import json
import math
import os
import re
import subprocess

# 목표 = SNS 표준 체감(−14LUFS · 운영자 260710 버튼 확답). TP는 −1.5dB — 버튼 문구(−1)보다 안전 측:
#   loudnorm 다이내믹 리미터·AAC 재인코딩 오버슈트가 최대 ~1dB 문헌 → −1.0이면 `0dB 절대 안 넘음`(운영자 하드 제약) 마진 0
#   → −1.5로 마진 확보(검증 평의회4 실측 권고 · 체감차 0). LRA 11 = loudnorm 표준.
TARGET_I, TARGET_TP, TARGET_LRA = -14.0, -1.5, 11.0
FLOOR_I = -55.0   # 근사무음 게이트 — 이보다 조용하면(룸톤·히스뿐) 정규화가 노이즈만 +40dB 증폭 → 스킵(평의회4)
# L/R 통일 = 스테레오 정규화 후 모노합(c0=c1) — 한쪽에 치우친 인터뷰/현장음 좌우 균일. 모노 소스는 aformat이 복제라 무해.
PRE = "aformat=channel_layouts=stereo,pan=stereo|c0=.5*c0+.5*c1|c1=.5*c0+.5*c1"


def has_audio(path, timeout=60):
    """True/False = 오디오 스트림 유/무 · None = 판별 실패(ffprobe 이상 — 사유 구분용·평의회6)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                            "stream=index", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=timeout)
        return bool((r.stdout or "").strip())
    except Exception:
        return None   # 판별 실패 = 보정 스킵(원본 유지가 안전 — 없는 오디오에 -af 걸면 ffmpeg 실패로 전체가 죽는다)


def _measure(src, timeout=90):
    # 1패스: 오디오만 디코드해 loudnorm 측정값 회수 — JSON은 stderr 꼬리 { } 블록(공식 print_format=json 동작)
    # timeout 90s = 캡 300초 클립 오디오 디코드 실측 수 초의 10배+ 마진(과대 provision이 성공영상 상실창 키우는 것 차단·평의회5)
    af = "{},loudnorm=I={:g}:TP={:g}:LRA={:g}:print_format=json".format(PRE, TARGET_I, TARGET_TP, TARGET_LRA)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", src, "-map", "0:a:0",
                        "-af", af, "-f", "null", "-"],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        return None
    for blob in reversed(re.findall(r"\{[^{}]+\}", r.stderr or "", re.S)):
        try:
            j = json.loads(blob)
            if "input_i" in j:
                return j
        except ValueError:
            continue
    return None


def normalize(src, out, abr="192k", timeout=180):
    """src(비디오+오디오 mp4) → out: 비디오 copy + 오디오 {L/R 모노합 → loudnorm 2패스 −14LUFS} → aac.
    반환 (ok, note) — note = 사용자 표기용 짧은 한국어(성공/스킵 사유). 어떤 예외도 밖으로 안 새어나감(전면 fail-soft
    = 호출자의 성공 인코딩 보존 · 평의회5·6). timeout 180s = 비디오 copy+오디오 aac 실측 수십 초의 마진."""
    aud = has_audio(src)
    if aud is None:
        return False, "음량 통일 건너뜀(오디오 확인 실패)"
    if not aud:
        return False, "음량 통일 건너뜀(오디오 없음)"
    try:
        meas = _measure(src)
    except Exception:
        meas = None   # 측정 인프라 실패 = 단일패스 폴백(비-Timeout 예외 포함 · 평의회6)
    ln = ""
    if meas:
        try:
            vals = [float(meas["input_i"]), float(meas["input_tp"]), float(meas["input_lra"]),
                    float(meas["input_thresh"]), float(meas.get("target_offset") or 0.0)]
            if not all(math.isfinite(v) for v in vals):
                # 디지털 무음·좌우 완전 역위상(모노합 상쇄) = 측정 −inf → 2패스에 넣으면 ffmpeg 거부(평의회1·4 실측)
                return False, "음량 통일 건너뜀(소리 감지 안 됨)"
            if vals[0] < FLOOR_I:
                return False, "음량 통일 건너뜀(소리가 거의 없음)"   # 룸톤만 = 히스 증폭 방지(평의회4)
            ln = ("loudnorm=I={:g}:TP={:g}:LRA={:g}:measured_I={:g}:measured_TP={:g}:measured_LRA={:g}:"
                  "measured_thresh={:g}:offset={:g}:linear=true").format(
                TARGET_I, TARGET_TP, TARGET_LRA, *vals)
        except (KeyError, TypeError, ValueError):
            ln = ""
    if not ln:
        ln = "loudnorm=I={:g}:TP={:g}:LRA={:g}".format(TARGET_I, TARGET_TP, TARGET_LRA)   # 단일패스 폴백(다이내믹 모드)
    af = "{},{},aresample=48000".format(PRE, ln)   # loudnorm 내부 192kHz 업샘플 → 48k 복원
    try:
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src,
                            "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
                            "-af", af, "-c:a", "aac", "-b:a", abr,
                            "-movflags", "+faststart", out], timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "음량 통일 건너뜀(시간 초과)"
    except Exception:
        return False, "음량 통일 건너뜀(처리 실패)"   # OSError 등 exec 계층 — fail-soft 완결(평의회6)
    if r.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) < 1024:
        return False, "음량 통일 건너뜀(처리 실패)"
    return True, "음량 통일(−14LUFS·L/R)" + ("" if meas else " · 근사(1패스)")
