#!/usr/bin/env python3
# 크로마키(특정 색상 키잉) 모듈 — 지정 색을 투명(알파)으로. 프리미어 Ultra Key 대응 노브(운영자 260712 모듈화 3종 중 ③).
# UI 무의존 엔진(MODULES.md 계약): 함수 run(src, opts, out_dir) + CLI — 워크플로·뷰어·R2 배선은 콜러 몫(나중에 UI에 붙임).
#   피사체 키잉(track_keying = SAM2 세그먼트)과 별개 축 — 여긴 색 기반(그린스크린류) = 순수 ffmpeg·모델 0·LLM 0.
# 파이프: chromakey(YUV·그린/블루 계열) 또는 colorkey(RGB·임의 색) → despill(그린/블루만) → 알파 후처리{choke=erosion/dilation · feather=gblur}
#   → 마스터 ProRes 4444 MOV(yuva444p10le·프리미어 네이티브 알파) + 프리뷰 VP9 webm(track_keying 출력 계약 동일).
# 실측(260712 · 4vCPU): 1080×1920 30fps 순수 필터+이중 인코딩 ≈ 2.2s/원본초 → 300s 캡 ≈ 11분(러너 캡 내).
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time

MAX_SEC = 300            # 길이 캡(변환·트래킹 분석 캡 선례 — 트림 후 유효 길이)
MAX_LONG = 1920          # 입력 해상도 캡(키잉·변환 선례)
FF_TIMEOUT = 1900        # ffmpeg 백스톱(conv 선례 — 스텝 타임아웃 전 정직 에러)
PREVIEW_LONG = 960       # 프리뷰 긴 변(track_keying 동일)

# Ultra Key 대응 노브(범위 = 검증 클램프 · 기본값 = 그린스크린 표준 시작점)
DEFAULTS = {
    "color": "#00FF00",   # 키 색(hex) — 프리미어 스포이드 대응(UI가 픽커/스포이드로 채움)
    "similarity": 0.15,   # 키 관용(0.01~0.5) — 프리미어 '허용 오차'. 클수록 넓게 빠짐
    "blend": 0.05,        # 경계 혼합(0~0.5) — 반투명 전이 폭
    "despill": 0.5,       # 스필 제거(0~1 · 그린/블루 계열만) — 피사체 가장자리 초록물 빼기
    "choke": 0,           # 매트 수축/팽창 px(−4~+4) — 프리미어 '가장자리 줄이기'. +수축 = 후광 제거
    "feather": 1,         # 매트 페더 px(0~10) — 가장자리 부드럽게
    "edge": "fast",       # fast | high — high = 키잉 전 yuv444 승격(테두리 계단 완화 · 속도 대가)
}


def die(msg, log=""):
    print(f"::error::{log or msg}", flush=True)
    raise SystemExit(json.dumps({"error": msg}, ensure_ascii=False))


def _num(v, lo, hi, dflt):
    try:
        x = float(v)
        if math.isnan(x):
            return dflt
        return max(lo, min(hi, x))
    except (TypeError, ValueError):
        return dflt


def _hex_color(v, dflt="#00FF00"):
    """6자리 hex 전용 — 미지정 = 기본 그린 · 형식 이상(#F00 축약·8자리 등) = 정직 에러(조용한 그린 폴백 = 엉뚱한 색 키잉 풋건 · 평의회2)."""
    if v is None or str(v).strip() == "":
        return dflt
    s = str(v).strip()
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", s):
        return "#" + s.lstrip("#").upper()
    die(f"키 색은 6자리 hex로 줘(#RRGGBB — 지금 {s[:12]!r}).")


def _kind(color):
    """키 색 분류 — chromakey(YUV)는 그린/블루 스크린에서 colorkey(RGB)보다 경계 우수 · despill도 그린/블루 전용.
    지배 채널이 그린/블루면 그 타입, 아니면 'other'(colorkey 경로·despill 생략)."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    if g > r * 1.2 and g > b * 1.2:
        return "green"
    if b > r * 1.2 and b > g * 1.2:
        return "blue"
    return "other"


def probe(src):
    """ffprobe → (W, H, fps, dur) — 회전 표시 치수 스왑(conv_run probe 미러). SAR = 의도적 생략(색 키잉은 픽셀당 색 연산 = 좌표·비율 무관 · 마스터가 입력 SAR 그대로 전파 = 프리미어 네이티브 해석 · 평의회3)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,avg_frame_rate,duration,side_data_list",
                            "-show_entries", "format=duration", "-of", "json", src],
                           capture_output=True, text=True, timeout=120, check=True)
        d = json.loads(r.stdout or "{}")
    except Exception as e:
        die("영상 정보를 못 읽었어 — 파일이 손상됐거나 형식이 이상해.", f"ffprobe 실패: {e}")
    st = (d.get("streams") or [{}])[0]
    W, H = int(st.get("width") or 0), int(st.get("height") or 0)
    rot = 0
    for sd in st.get("side_data_list") or []:
        if "rotation" in sd:
            try:
                rot = int(round(float(sd["rotation"])))
            except (TypeError, ValueError):
                rot = 0
    if abs(rot) % 180 == 90:
        W, H = H, W
    fr = str(st.get("avg_frame_rate") or "0/1")
    try:
        num, den = fr.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except ValueError:
        fps = 0.0
    dur = _num(st.get("duration"), 0, 1e9, 0) or _num((d.get("format") or {}).get("duration"), 0, 1e9, 0)
    if W < 2 or H < 2 or dur <= 0:
        die("영상 정보를 못 읽었어 — 다시 올려줘.", f"probe 이상: {W}x{H} dur={dur}")
    if not fps or fps <= 1 or fps > 240 or math.isnan(fps):
        fps = 30.0
    return W, H, fps, float(dur)


def build_filter(o, kind):
    """키잉 필터그래프 문자열 — 마스터/프리뷰 분기 전 공통 구간(알파 완성까지)."""
    col = "0x" + o["color"].lstrip("#")
    steps = []
    if o.get("edge") == "high":
        steps.append("format=yuv444p")   # 키잉 전 풀크로마 승격 — 420 크로마 계단(테두리 얽힘) 완화(평의회1 · 운영자 260712 테두리 우선) · 비용 = 속도
    if kind in ("green", "blue"):
        steps.append(f"chromakey={col}:{o['similarity']:.3f}:{o['blend']:.3f}")   # YUV 키 = 압축 그린스크린 경계 우수
        if o["despill"] > 0:
            steps.append(f"despill=type={kind}:mix={o['despill']:.3f}")            # 가장자리 스필(초록물) 제거
    else:
        steps.append(f"colorkey={col}:{o['similarity']:.3f}:{o['blend']:.3f}")     # 임의 색 = RGB 키(despill 비적용 = 정직 한계)
    # 매트 후처리 — choke(수축/팽창)·feather(블러)는 알파 평면만 분리 가공 후 재합성(RGB 불변)
    ch, fe = int(o["choke"]), o["feather"]
    if ch or fe > 0:
        alpha_ops = []
        if ch > 0:
            alpha_ops += ["erosion"] * min(4, ch)          # 수축 = 후광(키 잔여 테두리) 제거
        elif ch < 0:
            alpha_ops += ["dilation"] * min(4, -ch)        # 팽창 = 과식각 복구
        if fe > 0:
            alpha_ops.append(f"gblur=sigma={fe:.2f}")      # 페더 = 경계 연화
        steps.append("split[c][a];[a]alphaextract," + ",".join(alpha_ops) + "[af];[c][af]alphamerge")
    return ",".join(steps)   # -vf도 단일 입출력이면 내부 라벨 그래프(split;…;alphamerge) 수용 — E2E 실측 확인


def run(src, opts, out_dir):
    """크로마키 실행 — src 영상에서 opts 색을 투명화 → out_dir/chroma.mov(마스터)+chroma_preview.webm.
    반환 = {"master","preview","w","h","fps","dur","kind","opts"} (opts = 해소값+t0/t1 에코 · 업로드는 콜러 몫)."""
    o = dict(DEFAULTS)
    o["color"] = _hex_color((opts or {}).get("color"), DEFAULTS["color"])
    o["similarity"] = _num((opts or {}).get("similarity"), 0.01, 0.5, DEFAULTS["similarity"])
    o["blend"] = _num((opts or {}).get("blend"), 0, 0.5, DEFAULTS["blend"])
    o["despill"] = _num((opts or {}).get("despill"), 0, 1, DEFAULTS["despill"])
    o["choke"] = int(_num((opts or {}).get("choke"), -4, 4, DEFAULTS["choke"]))
    o["feather"] = _num((opts or {}).get("feather"), 0, 10, DEFAULTS["feather"])
    o["edge"] = "high" if (opts or {}).get("edge") == "high" else "fast"   # high = 키잉 전 yuv444(테두리 우선 · 속도 대가)
    t0 = _num((opts or {}).get("t0"), 0, 1e9, 0.0)
    t1 = _num((opts or {}).get("t1"), 0, 1e9, 0.0)

    W, H, fps, dur = probe(src)
    if max(W, H) > MAX_LONG:
        die(f"크로마키는 긴 변 {MAX_LONG}px까지야(지금 {max(W, H)}px) — 1080p 이하로 해줘.")
    t0 = min(t0, dur)
    t1 = t1 if 0 < t1 <= dur else dur
    if t1 <= t0 + 0.2:
        die("구간이 이상해 — 끝이 시작보다 커야 해(0.2초 이상).")
    eff = t1 - t0
    if eff > MAX_SEC + 1:
        die(f"크로마키는 {MAX_SEC}초까지야(지금 구간 {int(eff)}초) — 구간을 잘라줘.")

    kind = _kind(o["color"])
    vf = build_filter(o, kind)
    os.makedirs(out_dir, exist_ok=True)
    out_mov = os.path.join(out_dir, "chroma.mov")
    out_webm = os.path.join(out_dir, "chroma_preview.webm")
    pscale = min(1.0, PREVIEW_LONG / max(W, H))
    pw, ph = max(2, int(W * pscale) & ~1), max(2, int(H * pscale) & ~1)

    # 마스터 = ProRes 4444(알파 · q:v 11 = 키잉 실측 −44% 용량) · 프리뷰 = VP9 알파 webm — track_keying 인코딩 계약 미러
    base = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t", f"{eff:.3f}", "-i", src]
    t_run = time.time()
    try:
        r1 = subprocess.run(base + ["-map", "0:v:0", "-map", "0:a?", "-vf", vf + ",format=yuva444p10le",
                                    "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                                    "-alpha_bits", "8", "-q:v", "11",
                                    "-c:a", "aac", "-b:a", "160k", out_mov], timeout=FF_TIMEOUT)
        r2 = subprocess.run(base + ["-map", "0:v:0", "-map", "0:a?",
                                    "-vf", vf + f",scale={pw}:{ph},format=yuva420p",
                                    "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "34", "-b:v", "0",
                                    "-cpu-used", "6", "-row-mt", "1",
                                    "-c:a", "libopus", "-b:a", "64k", out_webm], timeout=FF_TIMEOUT)
    except subprocess.TimeoutExpired:
        die("크로마키 시간 초과 — 구간·해상도를 줄여서 다시 해줘.")
    if r1.returncode != 0 or not os.path.isfile(out_mov) or os.path.getsize(out_mov) < 1024:
        die("크로마키에 실패했어 — 영상을 mp4로 바꿔서 다시 해줘.", f"master rc={r1.returncode}")
    if r2.returncode != 0 or not os.path.isfile(out_webm) or os.path.getsize(out_webm) < 1024:
        die("프리뷰 인코딩 실패 — 다시 시도해줘.", f"preview rc={r2.returncode}")
    print(f"크로마키 완료 {W}×{H} {eff:.1f}s · kind={kind} · {time.time() - t_run:.0f}s "
          f"· 마스터 {os.path.getsize(out_mov) // 1_000_000}MB", flush=True)
    o["t0"], o["t1"] = round(t0, 2), round(t1, 2)   # 해소된 트림창 에코(dur = 트림 후 유효 길이 · 평의회2)
    return {"master": out_mov, "preview": out_webm, "w": W, "h": H, "fps": round(fps, 2),
            "dur": round(eff, 2), "kind": kind, "opts": o}


def main():
    ap = argparse.ArgumentParser(description="크로마키(색상 키잉) 모듈 — MODULES.md 계약")
    ap.add_argument("--src", required=True, help="입력 영상 경로")
    ap.add_argument("--out-dir", required=True, help="산출 폴더(chroma.mov·chroma_preview.webm)")
    ap.add_argument("--opts", default="{}", help='JSON {"color":"#00FF00","similarity":0.15,"blend":0.05,"despill":0.5,"choke":0,"feather":1,"edge":"fast|high","t0":s,"t1":s}')
    a = ap.parse_args()
    try:
        opts = json.loads(a.opts or "{}")
        if not isinstance(opts, dict):
            opts = {}
    except ValueError:
        opts = {}
    res = run(a.src, opts, a.out_dir)
    print(json.dumps(res, ensure_ascii=False))   # 마지막 줄 = 기계가독 결과(콜러 파싱 계약)


if __name__ == "__main__":
    main()
