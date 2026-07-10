#!/usr/bin/env python3
# 변환(conv) — ffmpeg 단일 파이프: 트림 → 비율 크롭 → 스케일 → fps(60 보간·다운) → h264+aac → R2 → video.json.
# LLM 0콜·모델 0(순수 ffmpeg — 과금 = Actions 분 + R2). 실패 = /tmp/conv_err.txt → 워크플로 failure()가 error.log 커밋(트래킹 미러).
# 캡·예산(운영자 260710 확정 + 실측 260710):
#   일반(크롭·트림·스케일·fps다운) = 트림 후 유효 길이 300초(트래킹 분석 캡 선례)
#   60fps 보간 = 120초 캡 + 발사 전 예산 가드 — minterpolate 기본 프리셋 실측 270ms/출력프레임@1080×1920(4vCPU=러너 동급)
#     → 1080×1920 풀은 약 83초·720p급은 120초 풀까지(해상도 비례) = 초과 시 해상도/구간 안내 메시지로 정직 거절(키잉 예산 가드 문법).
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
MAX_SEC = 300            # 일반 캡(트림 후 유효 길이)
INTERP_MAX_SEC = 120     # 60fps 보간 캡(운영자 승인)
INTERP_S_PF = 0.30       # 실측 단가: minterpolate 기본(mci·obmc·bilat·epzs) s/출력프레임@1080×1920 + 마진(실측 .27)
INTERP_BUDGET = 1500     # 보간 예산 25분(스텝 33분 캡 내 다운로드·인코딩·업로드 여유)
FF_TIMEOUT = 1900        # 메인 ffmpeg 백스톱(예산 추정이 빗나가도 스텝 타임아웃 전에 정직 에러)
MAX_LONG = 1920          # 입력 해상도 캡(키잉 선례 — 4K = 시간·디스크 폭발)
AR = {"9:16": 9 / 16, "1:1": 1.0, "4:5": 4 / 5, "16:9": 16 / 9}
RES = {"1080": 1080, "720": 720}


def die(msg, log=""):
    with open("/tmp/conv_err.txt", "w", encoding="utf-8") as f:
        f.write(msg)
    print(f"::error::{log or msg}", flush=True)
    sys.exit(1)


def _num(v, lo, hi, dflt):
    try:
        x = float(v)
        if math.isnan(x):
            return dflt
        return max(lo, min(hi, x))
    except (TypeError, ValueError):
        return dflt


def probe(src):
    """ffprobe → (W, H, fps, dur) — 회전 메타(90/270)는 표시 치수로 스왑(ffmpeg 디코드 자동회전과 좌표 공간 일치)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,avg_frame_rate,duration,side_data_list",
                            "-show_entries", "format=duration", "-of", "json", src],
                           capture_output=True, text=True, timeout=120, check=True)
        d = json.loads(r.stdout or "{}")
    except Exception as e:
        die("영상 정보를 못 읽었어 — 파일이 손상됐거나 형식이 이상해. 다시 올려줘.", f"ffprobe 실패: {e}")
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


def r2_upload(path, key):
    """aws s3 cp 파일 직접 업로드(키잉 마스터 문법 — bytes 적재 금지) → 공개 URL. R2 미설정·실패 = 정직 에러."""
    acct, bucket = os.environ.get("R2_ACCOUNT_ID", ""), os.environ.get("R2_BUCKET", "")
    pub = os.environ.get("R2_PUBLIC_BASE", "").rstrip("/")
    ak, sk = os.environ.get("R2_ACCESS_KEY_ID", ""), os.environ.get("R2_SECRET_ACCESS_KEY", "")
    if not (acct and bucket and pub and ak and sk):
        die("저장소(R2)가 설정 안 돼 있어 — 관리자 설정 후 다시.", "R2 시크릿 미설정")
    env = dict(os.environ, AWS_ACCESS_KEY_ID=ak, AWS_SECRET_ACCESS_KEY=sk, AWS_DEFAULT_REGION="auto",
               AWS_REQUEST_CHECKSUM_CALCULATION="when_required", AWS_RESPONSE_CHECKSUM_VALIDATION="when_required")
    try:
        subprocess.run(["aws", "s3", "cp", path, f"s3://{bucket}/{key}",
                        "--endpoint-url", f"https://{acct}.r2.cloudflarestorage.com",
                        "--content-type", "video/mp4", "--only-show-errors"],
                       check=True, env=env, timeout=900)
    except Exception as e:
        die("결과 업로드에 실패했어 — 잠시 후 다시 해줘.", f"R2 업로드 실패: {e}")
    return f"{pub}/{key}"


def main():
    if len(sys.argv) < 3:
        die("변환 실행 인자 부족 — 다시 시도해줘.", "usage: conv_run.py <id> <src>")
    vid_id, src = sys.argv[1], sys.argv[2]
    try:
        opts = json.loads(os.environ.get("CONV_OPTS") or "{}")
        if not isinstance(opts, dict):
            opts = {}
    except ValueError:
        opts = {}

    W, H, fps, dur = probe(src)
    if max(W, H) > MAX_LONG:
        die(f"변환은 긴 변 {MAX_LONG}px까지야(지금 {max(W, H)}px) — 1080p로 줄여서 올려줘.")

    # ── 트림(입력 옵션 -ss/-t = 재인코딩이라 프레임 정확) — api 클램프 + 여기 dur 재클램프 = 이중 방어
    t0 = _num(opts.get("t0"), 0, dur, 0.0)
    t1 = _num(opts.get("t1"), 0, dur, dur)
    if t1 <= t0 + 0.2:
        die("구간이 이상해 — 끝이 시작보다 커야 해(0.2초 이상).")
    eff = t1 - t0
    if eff > MAX_SEC + 1:
        die(f"변환은 {MAX_SEC}초까지야(지금 구간 {int(eff)}초) — 구간을 잘라줘.")

    # ── 비율 크롭 — pos = 잘리는 축의 팬 위치(0=좌/상 · 0.5=중앙 · 1=우/하) · 짝수 정렬 = 크로마 시프트 방지
    ar = opts.get("ar") if opts.get("ar") in AR else None
    pos = _num(opts.get("pos"), 0, 1, 0.5)
    cw, ch, cx, cy = W, H, 0, 0
    if ar:
        target, cur = AR[ar], W / H
        if abs(target - cur) < 1e-3:
            ar = None   # 이미 그 비율 = 크롭 생략
        elif target < cur:
            cw = max(2, int(H * target) & ~1)
            cx = int(pos * (W - cw)) & ~1
        else:
            ch = max(2, int(W / target) & ~1)
            cy = int(pos * (H - ch)) & ~1

    # ── 해상도 스케일(다운만 — 업스케일 안 함) → 짝수
    res = opts.get("res") if opts.get("res") in RES else None
    sw, sh = cw, ch
    if res and max(cw, ch) > RES[res]:
        k = RES[res] / max(cw, ch)
        sw, sh = max(2, int(cw * k) & ~1), max(2, int(ch * k) & ~1)
    sw, sh = sw & ~1, sh & ~1

    # ── fps — 60i = minterpolate 보간(캡+예산 가드) · 30/24 = 다운 · keep = 그대로
    mode = opts.get("fps") if opts.get("fps") in ("keep", "60i", "30", "24") else "keep"
    vf = []
    if ar:
        vf.append(f"crop={cw}:{ch}:{cx}:{cy}")
    if (sw, sh) != (cw, ch):
        vf.append(f"scale={sw}:{sh}")
    out_fps = fps
    if mode == "60i":
        if eff > INTERP_MAX_SEC + 1:
            die(f"60fps 보간은 {INTERP_MAX_SEC}초까지야(지금 구간 {int(eff)}초) — 구간을 잘라줘.")
        if fps >= 59:
            die("이미 60fps야 — 보간이 필요 없어(유지로 변환해줘).")
        est = eff * 60 * INTERP_S_PF * (sw * sh / 2_073_600.0)
        if est > INTERP_BUDGET:
            max_s = int(INTERP_BUDGET / (60 * INTERP_S_PF * (sw * sh / 2_073_600.0)))
            die(f"이 해상도({sw}×{sh})로 60fps 보간은 약 {max_s}초까지야 — 해상도를 720p로 낮추거나 구간을 잘라줘.")
        vf.append("minterpolate=fps=60")   # 기본 프리셋(mci·obmc) — 실측 270ms/f@1080×1920 · 상위 프리셋(bidir 등)은 2배 비용이라 예산 밖
        out_fps = 60.0
    elif mode in ("30", "24"):
        tgt = float(mode)
        if fps > tgt + 0.5:
            vf.append(f"fps={mode}")
            out_fps = tgt
    vf.append("format=yuv420p")   # 재생 호환(브라우저·프리미어)

    out = "/tmp/conv_out.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t", f"{eff:.3f}", "-i", src,
           "-map", "0:v:0", "-map", "0:a?", "-vf", ",".join(vf),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    print("ffmpeg:", " ".join(cmd), flush=True)
    t_run = time.time()
    try:
        r = subprocess.run(cmd, timeout=FF_TIMEOUT)
    except subprocess.TimeoutExpired:
        die("변환 시간 초과 — 구간·해상도를 줄여서 다시 해줘.")
    if r.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) < 1024:
        die("변환에 실패했어 — 영상을 mp4로 바꿔서 다시 올려줘.", f"ffmpeg rc={r.returncode}")
    size_mb = os.path.getsize(out) / 1e6
    print(f"변환 완료 {sw}×{sh} {out_fps:g}fps {eff:.1f}s · {time.time() - t_run:.0f}s · {size_mb:.0f}MB", flush=True)

    url = r2_upload(out, f"conv_res/{vid_id}/out.mp4") + f"?v={int(time.time())}"   # stable 키 + 캐시버스트(ly·track 불변)
    doc = {"url": url, "w": sw, "h": sh, "fps": round(out_fps, 2), "dur": round(eff, 2),
           "size_mb": round(size_mb, 1), "ts": datetime.now(KST).isoformat(timespec="seconds")}
    odir = os.path.join("viewer", "conv_out", vid_id)
    os.makedirs(odir, exist_ok=True)
    with open(os.path.join(odir, "video.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    print("video.json:", json.dumps(doc, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
