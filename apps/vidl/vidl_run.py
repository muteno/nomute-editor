#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 영상 받기(vidl) — 설정 ▸ 다운로드의 영상 플랫폼 경로. 레퍼런스 = 운영자 로컬 Downloader.bat v7.0 조건 그대로(운영자 260728 요청):
#   ① 최고화질 1편(bv*+ba/b/best · 해상도 최우선) + 자막(en,ko srt→txt)
#   ② 최고프레임별 — 프레임 정렬(-S fps,res,br)의 fps가 ①보다 높을 때만(maxfps_ 표식)
#   ③ 1080p FHD 호환별 — 짧은 변>1080일 때만(가로=height≤1080 · 세로=width≤1080 · 1080p_ 표식)
#   · 재생목록 방지 = 기본 --no-playlist --playlist-items 1 · 게시물형 URL(/p/·/reel/·/status/ 등)은 --no-playlist만(bat v6.6)
#   · YT = 쿠키 미사용 선행 → 실패 시 쿠키 1회 재시도(bat v6.2) · 비YT = 쿠키 있으면 사용
#   · 파일명 = {KST TS}_{플랫폼}_{계정}_{제목}(bat 동일 · --trim-filenames 120 --windows-filenames)
# 산출 = R2 vidl_res/<id>/<파일명>(뷰어가 api/dl 프록시로 저장 = 로컬 다운로드 폴더) + 드라이브 '내 드라이브/Shared' 업로드
#   (= bat의 robocopy 축 · GDRIVE_SA_JSON 있을 때만 · 실패는 비치명 = 로컬 저장은 계속) → viewer/vidl_out/<id>/result.json.
# 골격 = apps/conv/conv_run.py 미러(die/r2/커밋 문법) · 드라이브 인증 = .github/scripts/drive_shared_guard.py 정본 계승.
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
SUBLANG = "en,ko"          # bat v4.9 기본
PROBE_TO = 180             # 사전조회 1회 타임아웃(초)
DL_TO = 1500               # 다운로드 1회 타임아웃(25분 — 스텝 캡 내 3회+업로드 여유)
DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UP = "https://www.googleapis.com/upload/drive/v3"


def die(msg, log=""):
    with open("/tmp/vidl_err.txt", "w", encoding="utf-8") as f:
        f.write(msg)
    print(f"::error::{log or msg}", flush=True)
    sys.exit(1)


def ytd(args, timeout, cookies=None, capture=False):
    """python3 -m yt_dlp 공통 호출 — cookies=경로(없으면 미사용)."""
    cmd = ["python3", "-m", "yt_dlp", "--no-cache-dir", "--socket-timeout", "30"]
    if cookies:
        cmd += ["--cookies", cookies]
    if JSRT:
        cmd += ["--js-runtimes", "node"]
    cmd += args
    return subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)


def detect_plat(url):
    u = url.lower()
    for key, plat in (("youtube.com", "YT"), ("youtu.be", "YT"), ("instagram.com", "IG"),
                      ("x.com", "X"), ("twitter.com", "X"), ("tiktok.com", "TT"),
                      ("facebook.com", "FB"), ("fb.watch", "FB"), ("threads.net", "TH"), ("threads.com", "TH")):
        if key in u:
            return plat
    return "ETC"


def plopt(url, plat):
    """재생목록 방지(bat v6.6) — YT·비게시물형 = 1편 강제 · 게시물형 = --no-playlist만(IG 캐러셀 등 통짜 허용)."""
    if plat == "YT":
        return ["--no-playlist", "--playlist-items", "1"]
    u = url.lower()
    post = any(m in u for m in ("instagram.com/p/", "instagram.com/reel/", "instagram.com/reels/", "instagram.com/tv/",
                                "/video/", "/videos/", "/photo/", "/status/", "/post/", "/watch?", "/watch/",
                                "fb.watch", "vm.tiktok", "vt.tiktok"))
    return ["--no-playlist"] if post else ["--no-playlist", "--playlist-items", "1"]


def probe(url, fmt, extra, cookies, pl):
    """사전조회(--print = 다운로드 안 함) → (w, h, fps, format_id) 또는 None — bat 3축 조회 미러."""
    args = ["--no-warnings", "-f", fmt] + extra + pl + [
        "--print", "%(width)s %(height)s %(fps)s %(format_id)s", "--playlist-items", "1", url]
    try:
        r = ytd(args, PROBE_TO, cookies=cookies, capture=True)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None
    line = (r.stdout or "").strip().splitlines()
    if not line:
        return None
    p = line[0].split()
    if len(p) < 4:
        return None

    def n(v):
        try:
            return float(v)
        except ValueError:
            return 0.0
    w, h, fps = int(n(p[0])), int(n(p[1])), n(p[2])
    return {"w": w, "h": h, "fps": fps, "fid": p[3]} if w and h else None


def download(url, outdir, name_tag, fmt, extra, cookies, pl, subs):
    """다운로드 1회 — 파일명 = {TS}_{PLAT}{tag}_{계정}_{제목}(bat 동일). rc 반환(변주별 실패 = 비치명)."""
    out = f"{TS}_{PLAT}{name_tag}_%(uploader_id)s_%(title)s.%(ext)s"
    args = ["--ffmpeg-location", os.environ.get("FFMPEG_DIR", "/usr/bin"),
            "--trim-filenames", "120", "--windows-filenames",
            "-P", outdir, "-o", out, "-f", fmt, "--merge-output-format", "mp4", "-N", "4"] + extra + pl
    if subs:
        args += ["--write-subs", "--write-auto-subs", "--sub-langs", SUBLANG, "--convert-subs", "srt"]
    else:
        args += ["--no-write-subs", "--no-write-auto-subs"]
    args.append(url)
    try:
        return ytd(args, DL_TO, cookies=cookies).returncode
    except subprocess.TimeoutExpired:
        return 1


def srt_to_txt(outdir):
    """자막 후처리(bat v4.9 미러) — 번호·타임코드·태그 제거 + 연속 중복 접기 → 같은 이름 .txt."""
    for fn in os.listdir(outdir):
        if not fn.endswith(".srt"):
            continue
        lines = []
        with open(os.path.join(outdir, fn), encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.isdigit() or "-->" in ln:
                    continue
                ln = re.sub(r"<[^>]+>", "", ln).strip()
                if ln and (not lines or lines[-1] != ln):
                    lines.append(ln)
        if lines:
            with open(os.path.join(outdir, fn[:-4] + ".txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))


def r2_upload(path, key, ctype):
    """conv_run.r2_upload 미러 — content-type만 파일별(영상=video/mp4 · 자막=octet-stream = api/dl 통과형)."""
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
                        "--content-type", ctype, "--only-show-errors"],
                       check=True, env=env, timeout=900)
    except Exception as e:
        die("결과 업로드에 실패했어 — 잠시 후 다시 해줘.", f"R2 업로드 실패: {e}")
    return f"{pub}/{key}"


def drive_token():
    """drive_shared_guard.access_token 정본 계승 — 사용자 OAuth token.json(refresh)."""
    raw = os.environ.get("GDRIVE_SA_JSON", "")
    if not raw.strip():
        return None, "드라이브 미설정(GDRIVE_SA_JSON 없음)"
    try:
        info = json.loads(raw)
        if info.get("type") == "service_account":
            return None, "서비스계정 키 — 사용자 OAuth 필요"
        body = urllib.parse.urlencode({
            "client_id": info["client_id"], "client_secret": info["client_secret"],
            "refresh_token": info["refresh_token"], "grant_type": "refresh_token"}).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["access_token"], ""
    except Exception as e:
        return None, f"드라이브 인증 실패: {e}"


def drive_shared_id(tok):
    q = "name='Shared' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false"
    url = f"{DRIVE_API}/files?" + urllib.parse.urlencode({"q": q, "fields": "files(id)"})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        fs = json.load(r).get("files", [])
    return fs[0]["id"] if fs else None


def drive_upload(tok, sid, path, ctype):
    """재개형 업로드(대용량 안전) — 세션 개시 = urllib · 본문 = curl -T(스트리밍)."""
    meta = json.dumps({"name": os.path.basename(path), "parents": [sid]}).encode()
    req = urllib.request.Request(f"{DRIVE_UP}/files?uploadType=resumable", data=meta, method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                                          "X-Upload-Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=30) as r:
        loc = r.headers.get("Location", "")
    if not loc:
        raise RuntimeError("업로드 세션 없음")
    subprocess.run(["curl", "-sfS", "-o", "/dev/null", "-X", "PUT",
                    "-H", f"Authorization: Bearer {tok}", "-H", f"Content-Type: {ctype}",
                    "-T", path, loc], check=True, timeout=1200)


def ctype_of(fn):
    return "video/mp4" if fn.endswith((".mp4", ".m4v", ".mov", ".webm", ".mkv")) else "application/octet-stream"


def main():
    if len(sys.argv) < 3:
        die("실행 인자 부족 — 다시 시도해줘.", "usage: vidl_run.py <id> <url>")
    vid_id, url = sys.argv[1], sys.argv[2]
    outdir = "/tmp/vidl_out"
    os.makedirs(outdir, exist_ok=True)

    cookies = None
    ck = os.environ.get("YT_COOKIES", "")
    if ck.strip():
        with open("/tmp/ck.txt", "w", encoding="utf-8") as f:
            f.write(ck)
        cookies = "/tmp/ck.txt"
    ck_probe = None if PLAT == "YT" else cookies   # YT = 쿠키 미사용 선행(bat v6.2 — 쿠키 = 로그인 취급 = 고화질 봉쇄)
    pl = plopt(url, PLAT)

    # ── 3축 사전조회(bat v6.8) — ①해상도 기본정렬 ②프레임정렬 ③FHD(방향별) ──
    best = probe(url, "bv*/b/best", [], ck_probe, pl)
    fpsb = probe(url, "bv*/b/best", ["-S", "fps,res,br"], ck_probe, pl)
    fhd = None
    if best:
        dimk = "width" if best["w"] < best["h"] else "height"   # 세로영상 = width 필터(bat v6.4 — height 필터는 1080x1920을 놓침)
        ffilt = f"bv*[{dimk}<=1080][ext=mp4]/b[{dimk}<=1080][ext=mp4]/bv*[{dimk}<=1080]/b[{dimk}<=1080]"
        fhd = probe(url, ffilt, [], ck_probe, pl)
    get_fps = bool(best and fpsb and fpsb["fps"] > best["fps"])                       # 프레임별 = fps 우위일 때만
    get_1080 = bool(best and fhd and (best["w"] if best["w"] < best["h"] else best["h"]) > 1080)
    if get_1080 and get_fps and fhd["fid"] == fpsb["fid"]:
        get_1080 = False                                                              # 중복 판(같은 format) 차단(bat v6.8)
    print(f"[화질] 최고해상도={best} / 프레임={fpsb} get_fps={get_fps} / FHD={fhd} get_1080={get_1080}", flush=True)

    # ── ① 최고화질 + 자막(항상) — YT 실패 시 쿠키 1회 재시도(bat v6.2 연령제한·멤버십 폴백) ──
    rc = download(url, outdir, "", "bv*+ba/b/best", [], ck_probe, pl, subs=True)
    if rc != 0 and PLAT == "YT" and cookies:
        print("[재시도] 쿠키 달아 1회 재시도(연령제한·멤버십 가능성)", flush=True)
        rc = download(url, outdir, "", "bv*+ba/b/best", [], cookies, pl, subs=True)
    if rc != 0 or not any(not f.endswith((".srt", ".txt", ".part")) for f in os.listdir(outdir)):
        die("영상 다운로드 실패 — 주소·연령 제한·로그인 전용 여부를 확인해줘.", f"yt-dlp 실패: {url}")

    # ── ② 프레임별 · ③ FHD별(각 실패 = 비치명 · bat 동일) ──
    if get_fps:
        download(url, outdir, "_maxfps", "bv*+ba/b/best", ["-S", "fps,res,br"], ck_probe, pl, subs=False)
    if get_1080:
        dimk = "width" if best["w"] < best["h"] else "height"
        f1080 = (f"bv*[{dimk}<=1080][ext=mp4]+ba[ext=m4a]/b[{dimk}<=1080][ext=mp4]/"
                 f"bv*[{dimk}<=1080]+ba/b[{dimk}<=1080]")
        download(url, outdir, "_1080p", f1080, [], ck_probe, pl, subs=False)

    srt_to_txt(outdir)

    # ── R2 업로드(전 산출) → api/dl 프록시로 로컬 저장 경로 ──
    files = []
    for fn in sorted(os.listdir(outdir)):
        p = os.path.join(outdir, fn)
        if not os.path.isfile(p) or fn.endswith(".part"):
            continue
        u = r2_upload(p, f"vidl_res/{vid_id}/{fn}", ctype_of(fn))
        files.append({"name": fn, "url": u, "size": os.path.getsize(p),
                      "kind": "video" if ctype_of(fn).startswith("video/") else "sub"})

    # ── 드라이브 Shared 업로드(= bat robocopy 축) — 실패 = 비치명·사유 보고(bat GD_WHY 미러) ──
    drive = {"on": False, "n": 0, "why": ""}
    tok, why = drive_token()
    if not tok:
        drive["why"] = why
    else:
        try:
            sid = drive_shared_id(tok)
            if not sid:
                drive["why"] = "내 드라이브에 Shared 폴더 없음"
            else:
                drive["on"] = True
                for fn in sorted(os.listdir(outdir)):
                    p = os.path.join(outdir, fn)
                    if not os.path.isfile(p) or fn.endswith(".part"):
                        continue
                    try:
                        drive_upload(tok, sid, p, ctype_of(fn))
                        drive["n"] += 1
                    except Exception as e:
                        drive["why"] = f"일부 업로드 실패: {e}"
        except Exception as e:
            drive["why"] = f"드라이브 오류: {e}"

    odir = os.path.join("viewer", "vidl_out", vid_id)
    os.makedirs(odir, exist_ok=True)
    doc = {"plat": PLAT, "ts": TS, "best": best, "fps": fpsb if get_fps else None,
           "fhd": fhd if get_1080 else None, "files": files, "drive": drive}
    with open(os.path.join(odir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    print("result.json:", json.dumps(doc, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    URL = sys.argv[2] if len(sys.argv) > 2 else ""
    PLAT = detect_plat(URL)
    TS = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    try:  # JS 런타임(node) 지원 여부 — SABR 대응 최고화질(bat v6.7) · 미지원 구버전이면 플래그 생략
        JSRT = subprocess.run(["python3", "-m", "yt_dlp", "--js-runtimes", "node", "--version"],
                              capture_output=True, timeout=60).returncode == 0
    except Exception:
        JSRT = False
    main()
