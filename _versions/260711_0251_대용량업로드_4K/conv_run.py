#!/usr/bin/env python3
# 변환(conv) — ffmpeg 단일 파이프: 트림 → 비율 크롭/여백(패드) → 스케일 → fps(60 보간·다운) → h264+aac
#   (→ 음량 통일 = shared/audio_norm.py 후처리·비디오 copy) → R2 → video.json.
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shared"))
import audio_norm   # 음량 통일 SSOT(−14LUFS 2패스·L/R 모노합) — 자체 loudnorm 재구현 금지(§핵심명령식 단일정본)

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
                            "-show_entries", "stream=width,height,sample_aspect_ratio,avg_frame_rate,duration,side_data_list",
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
    sar = 1.0   # 아나모픽(SAR≠1) = 표시 폭이 저장 폭과 다름 — 크롭 비율 산술이 표시 공간이어야 프리뷰와 일치(평의회6)
    try:
        sn, sd = str(st.get("sample_aspect_ratio") or "1:1").split(":")
        if float(sd) > 0 and float(sn) > 0:
            sar = float(sn) / float(sd)
    except (ValueError, AttributeError):
        sar = 1.0
    return W, H, fps, float(dur), sar, rot


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
                       check=True, env=env, timeout=240)   # conv 산출 = 수십~수백MB(키잉 GB급 아님) — 스텝 캡 내 백스톱 겹침 완화(평의회2)
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

    W, H, fps, dur, sar, rot = probe(src)
    sar_fix = ""
    if abs(sar - 1.0) > 1e-3 and abs(rot) % 180 == 0:   # 비회전 아나모픽만 정규화(회전+SAR 동시는 희귀 = 지침 한계 · 평의회6)
        W = max(2, int(round(W * sar)) & ~1)
        sar_fix = f"scale={W}:{H},setsar=1"   # 표시 공간으로 선정규화 → 이후 크롭·산술 = 프리뷰와 동일 축
    if max(W, H) > MAX_LONG:
        die(f"변환은 긴 변 {MAX_LONG}px까지야(지금 {max(W, H)}px) — 1080p 이하로 다시 해줘(URL이면 낮은 화질 링크나 파일 업로드로).")

    # ── 트림(입력 옵션 -ss/-t = 재인코딩이라 프레임 정확) — api 클램프 + 여기 dur 재클램프 = 이중 방어
    t0 = _num(opts.get("t0"), 0, dur, 0.0)
    t1 = _num(opts.get("t1"), 0, dur, dur)
    if t1 <= t0 + 0.2:
        die("구간이 이상해 — 끝이 시작보다 커야 해(0.2초 이상).")
    eff = t1 - t0
    if eff > MAX_SEC + 1:
        die(f"변환은 {MAX_SEC}초까지야(지금 구간 {int(eff)}초) — 구간을 잘라줘.")

    # ── 비율 — fit=crop: 잘라서 맞춤(pos = 잘리는 축 팬 위치 0=좌/상 · 0.5=중앙 · 1=우/하) / fit=pad: 안 자르고
    #    목표비 캔버스 중앙 배치 + 남는 축 검정 여백(운영자 260710 "위아래 검정 채워 9:16 · 영상은 가운데" — pos 미적용).
    #    짝수 정렬 = 크로마 시프트 방지.
    ar = opts.get("ar") if opts.get("ar") in AR else None
    fit = opts.get("fit") if opts.get("fit") in ("crop", "pad") else "crop"
    pos = _num(opts.get("pos"), 0, 1, 0.5)
    cw, ch, cx, cy = W, H, 0, 0
    pad_t = 0.0   # 0 = 패드 없음(크롭 모드 또는 비율 미선택)
    if ar:
        target, cur = AR[ar], W / H
        if abs(target - cur) < 1e-3:
            ar = None   # 이미 그 비율 = 크롭/패드 생략
        elif fit == "pad":
            pad_t = target
        elif target < cur:
            cw = max(2, int(H * target) & ~1)
            cx = int(pos * (W - cw)) & ~1
        else:
            ch = max(2, int(W / target) & ~1)
            cy = int(pos * (H - ch)) & ~1

    # ── 해상도 스케일(다운만 — 업스케일 안 함) → 짝수. 패드 모드 = 캔버스(출력) 긴 변 기준 캡 · 원본은 캔버스 안 contain.
    res = opts.get("res") if opts.get("res") in RES else None
    sw, sh = cw, ch
    pw = ph = 0   # 패드 캔버스(0 = 패드 없음)
    if pad_t:
        if cw / ch > pad_t:                     # 원본이 목표보다 옆으로 넓음 = 위아래 여백
            pw, ph = cw, int(round(cw / pad_t))
        else:                                   # 원본이 목표보다 세로로 김 = 좌우 여백
            pw, ph = int(round(ch * pad_t)), ch
        cap = min(MAX_LONG, RES[res]) if res else MAX_LONG
        if max(pw, ph) > cap:                   # 캔버스 캡 = 목표비 정확 스냅(9:16 = 1080×1920처럼 떨어지게)
            if pw >= ph:
                pw, ph = cap, max(2, int(round(cap / pad_t)) & ~1)
            else:
                pw, ph = max(2, int(round(cap * pad_t)) & ~1), cap
        pw, ph = max(2, pw & ~1), max(2, ph & ~1)
        k = min(pw / cw, ph / ch, 1.0)          # 원본 contain(업스케일 없음)
        sw, sh = max(2, int(cw * k) & ~1), max(2, int(ch * k) & ~1)
    elif res and max(cw, ch) > RES[res]:
        k = RES[res] / max(cw, ch)
        sw, sh = max(2, int(cw * k) & ~1), max(2, int(ch * k) & ~1)
    sw, sh = sw & ~1, sh & ~1

    # ── fps — 60i = minterpolate 보간(캡+예산 가드) · 30/24 = 다운 · keep = 그대로
    mode = opts.get("fps") if opts.get("fps") in ("keep", "60i", "30", "24") else "keep"
    vf = []
    if sar_fix:
        vf.append(sar_fix)
    if ar and not pad_t:
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
    ow, oh = sw, sh   # 출력 치수(video.json 보고용)
    if pw:   # 여백(패드) = fps 뒤(보간은 원본 픽셀만 계산 = 예산 산식 sw·sh 그대로 유효) · 오프셋 짝수 = 크로마 안전
        px, py = max(0, (pw - sw) // 2) & ~1, max(0, (ph - sh) // 2) & ~1
        vf.append(f"pad={pw}:{ph}:{px}:{py}:black")
        vf.append("setsar=1")   # contain 짝수화가 남긴 미세 보정 SAR(≈0.25% 스퀴시) 제거 = 정사각픽셀 강제(평의회1 실측)
        ow, oh = pw, ph
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

    # ── 음량 통일(후처리·비디오 copy) — 실패/무음 = 원본 유지 + note로 사유 표면화(fail-soft·침묵 금지)
    audio = opts.get("audio") if opts.get("audio") in ("keep", "norm") else "keep"
    note = ""
    if audio == "norm":
        out_an = "/tmp/conv_out_an.mp4"
        try:
            ok_a, note = audio_norm.normalize(out, out_an)
        except Exception as e:   # 이중 가드 — 헬퍼가 못 잡은 예외도 성공한 본 인코딩을 보존(fail-soft 완결 · 평의회5·6)
            ok_a, note = False, "음량 통일 건너뜀(처리 실패)"
            print("::warning::audio_norm 예외:", e, flush=True)
        if ok_a:
            out = out_an
        print("음량:", note, flush=True)
    size_mb = os.path.getsize(out) / 1e6
    print(f"변환 완료 {ow}×{oh} {out_fps:g}fps {eff:.1f}s · {time.time() - t_run:.0f}s · {size_mb:.0f}MB", flush=True)

    url = r2_upload(out, f"conv_res/{vid_id}/out.mp4") + f"?v={int(time.time())}"   # stable 키 + 캐시버스트(ly·track 불변)
    doc = {"url": url, "w": ow, "h": oh, "fps": round(out_fps, 2), "dur": round(eff, 2),
           "size_mb": round(size_mb, 1), "ts": datetime.now(KST).isoformat(timespec="seconds")}
    if note:
        doc["note"] = note
    odir = os.path.join("viewer", "conv_out", vid_id)
    os.makedirs(odir, exist_ok=True)
    with open(os.path.join(odir, "video.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    print("video.json:", json.dumps(doc, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
