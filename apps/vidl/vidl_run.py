#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 영상 받기(vidl) — 설정 ▸ 다운로드의 영상 플랫폼 경로. 레퍼런스 = 운영자 로컬 Downloader.bat v7.0 조건 그대로(운영자 260728 요청):
#   ① 최고화질 1편(bv*+ba/b/best · 해상도 최우선) + 자막(en,ko srt→txt)
#   ② 최고프레임별 — 프레임 정렬(-S fps,res,br)의 fps가 ①보다 높을 때만(maxfps_ 표식)
#   ③ 1080p FHD 호환별 — 짧은 변>1080일 때만(가로=height≤1080 · 세로=width≤1080 · 1080p_ 표식)
#   · 재생목록 방지 = 기본 --no-playlist --playlist-items 1 · 게시물형 URL(/p/·/reel/·/status/ 등)은 --no-playlist만(bat v6.6)
#   · YT = 쿠키 미사용 선행 → 실패 시 쿠키 1회 재시도(bat v6.2) · 비YT = 쿠키 있으면 사용
#   · 파일명 = {KST TS}_{플랫폼}_{계정}_{제목}(bat 동일) — 단 **다운로드 중엔 ASCII 짧은 이름(%(id)s)으로 받고
#     끝난 뒤 pretty_rename이 바이트 상한(255B) 안에서 계정·제목을 복원**한다(260802 [Errno 36] 실측 봉합 · 아래 주석)
# 산출 = R2 vidl_res/<id>/<파일명>(뷰어가 api/dl 프록시로 저장 = 로컬 다운로드 폴더) + 드라이브 '내 드라이브/Shared' 업로드
#   (= bat의 robocopy 축 · GDRIVE_SA_JSON 있을 때만 · 실패는 비치명 = 로컬 저장은 계속) → viewer/vidl_out/<id>/result.json.
# 골격 = apps/conv/conv_run.py 미러(die/r2/커밋 문법) · 드라이브 인증 = .github/scripts/drive_shared_guard.py 정본 계승.
# 평의회 260729 반영: 서버 플랫폼 화이트리스트·총예산 데드라인·부분성공(루프 내 die 금지)·URL quote·절대경로·원자적 write·
#   쿠키 부가본 계승·구분자 파싱·캐러셀 인덱스·드라이브 토큰 재발급·http_code 검증·동명 덮어쓰기·n=0 정직표기.
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
SUBLANG = "en,ko"           # bat v4.9 기본
PROBE_TO = 120             # 사전조회 1회 타임아웃(초)
TOTAL_BUDGET = 1500        # 총 다운로드 예산(25분 — 스텝 캡 30분 내 업로드 여유 · 평의회5 P1)
DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UP = "https://www.googleapis.com/upload/drive/v3"
# 플랫폼 감지 = 서버측 정본(뷰어 _dgVidPlat과 이중 · 미매칭 = 거부 · 평의회1 P1). host 정확일치/서브도메인 + 경로 화이트리스트.
PLATS = (("youtube.com", "YT"), ("youtu.be", "YT"), ("instagram.com", "IG"), ("x.com", "X"),
         ("twitter.com", "X"), ("tiktok.com", "TT"), ("facebook.com", "FB"), ("fb.watch", "FB"),
         ("threads.net", "TH"), ("threads.com", "TH"))
_START = time.monotonic()


def budget_left():
    return TOTAL_BUDGET - (time.monotonic() - _START)


def die(msg, log=""):
    with open("/tmp/vidl_err.txt", "w", encoding="utf-8") as f:
        f.write(msg)
    print(f"::error::{log or msg}", flush=True)
    sys.exit(1)


def detect_plat(url):
    """host+경로 이중 화이트리스트 — 영상 게시물만 통과(미매칭 = '') · 뷰어 _dgVidPlat 미러."""
    try:
        x = urllib.parse.urlparse(url)
        h = (x.hostname or "").lower()
        if h.startswith("www."):
            h = h[4:]
        path = (x.path or "").lower()
    except Exception:
        return ""

    def host(d):
        return h == d or h.endswith("." + d)
    if host("youtu.be"):
        return "YT" if len(path) > 1 else ""
    if host("youtube.com"):
        return "YT" if re.match(r"^/(watch|shorts/|live/|embed/)", path) else ""
    if host("instagram.com"):
        return "IG" if re.match(r"^/(p|reel|reels|tv)/", path) else ""
    if host("x.com") or host("twitter.com"):
        return "X" if re.search(r"/status/\d", path) else ""
    if host("tiktok.com"):
        return "TT" if (re.search(r"/(video|photo)/\d", path) or re.match(r"^/(t|v)/", path)
                        or h.startswith("vm.") or h.startswith("vt.")) else ""
    if host("fb.watch"):
        return "FB" if len(path) > 1 else ""
    if host("facebook.com"):
        return "FB" if (re.search(r"/(videos|reel|watch)/", path) or path == "/watch") else ""
    if host("threads.net") or host("threads.com"):
        return "TH" if "/post/" in path else ""
    return ""


def ytd(args, timeout, cookies=None, capture=False):
    """python3 -m yt_dlp 공통 호출 — sys.executable(인터프리터 일치 · 평의회6 P1-2) · cookies=경로(없으면 미사용)."""
    cmd = [sys.executable, "-m", "yt_dlp", "--no-cache-dir", "--socket-timeout", "30"]
    if cookies:
        cmd += ["--cookies", cookies]
    if JSRT:
        cmd += ["--js-runtimes", "node"]
    cmd += args
    return subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)


def plopt(url, plat):
    """재생목록 방지(bat v6.6) — YT·비게시물형 = 1편 강제 · 게시물형 = --no-playlist만(IG 캐러셀 등 통짜 허용)."""
    if plat == "YT":
        return ["--no-playlist", "--playlist-items", "1"]
    u = url.lower()   # 평의회6 P1-1: u 정의(구판 NameError)
    post = any(m in u for m in ("instagram.com/p/", "instagram.com/reel/", "instagram.com/reels/", "instagram.com/tv/",
                                "/video/", "/videos/", "/photo/", "/status/", "/post/", "/watch?", "/watch/",
                                "fb.watch", "vm.tiktok", "vt.tiktok"))
    return ["--no-playlist"] if post else ["--no-playlist", "--playlist-items", "1"]


def _fnum(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def probe(url, fmt, extra, cookies, pl):
    """사전조회(--print = 다운로드 안 함) → dict 또는 None. 구분자 | 파싱(공백 format_id 방어 · 평의회6 P3-1)."""
    if budget_left() < 60:
        return None
    args = ["--no-warnings", "-f", fmt] + extra + pl + [
        "--print", "%(width)s|%(height)s|%(fps)s|%(format_id)s|%(uploader_id)s|%(title)s",
        "--playlist-items", "1", url]   # uid·title = 사후 예쁜이름 복원용(pretty_rename) — title은 마지막이라 내부 | 허용
    try:
        r = ytd(args, PROBE_TO, cookies=cookies, capture=True)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None
    ls = (r.stdout or "").strip().splitlines()
    if not ls:
        return None
    p = ls[0].split("|", 5)
    if len(p) < 4:
        return None
    w, h, fps = int(_fnum(p[0])), int(_fnum(p[1])), _fnum(p[2])
    uid = p[4].strip() if len(p) > 4 else ""
    title = p[5].strip() if len(p) > 5 else ""
    return ({"w": w, "h": h, "fps": fps, "fid": p[3].strip(),
             "uid": "" if uid == "NA" else uid, "title": "" if title == "NA" else title} if w and h else None)


# ── 파일명 바이트 안전(260802 실측 봉합) ────────────────────────────────────────────
# 사고: 리눅스 파일명 상한은 255 **바이트**인데 --trim-filenames는 **문자 수** 기준이라,
#   한글·이모지(3~4B/자) 제목에서 trim 120이 발동조차 않고(실측 110자=215B) yt-dlp가 뒤에 붙이는
#   ".fhls-audio-128000-Audio.mp4.part-Frag1.part"(44B)까지 더해 259B → [Errno 36] File name too long
#   → 조각 전부 스킵 → "The downloaded file is empty" → 받기 전량 실패(운영자 260802 "무한로딩만 걸린다").
# 처방: 다운로드 중 이름은 ASCII 짧은 이름(%(id)s)으로 고정하고, 끝난 뒤 바이트 상한으로 잘라 예쁜 이름 복원.
FN_MAX = 255            # ext4/overlayfs 파일명 상한(바이트)
FN_HEADROOM = 12        # 업로드·후처리가 덧댈 여유(.tmp 등)
FN_STEM_CAP = 180       # 예쁜 이름 stem 자체 상한(드라이브·R2 키 부담 억제)


def _fnsafe(s):
    """경로·윈도 금지문자 및 제어문자 제거(yt-dlp --windows-filenames가 하던 몫을 rename 쪽에서 담당)."""
    s = re.sub(r"[\\/:*?\"<>|\x00-\x1f\x7f]+", " ", str(s or ""))
    return re.sub(r"\s+", " ", s).strip().strip(".")


def _bytecap(s, cap):
    """UTF-8 바이트 기준으로 자르되 문자 경계 보존(멀티바이트 중간 절단 = 깨진 이름 방지)."""
    b = s.encode("utf-8")
    if len(b) <= cap:
        return s
    return b[:cap].decode("utf-8", "ignore").rstrip()


def pretty_rename(outdir, uid, title):
    """{TS}_{PLAT}_{tag}{idx}{id} → …_{계정}_{제목}(bat 파일명 규약) · 바이트 상한 초과분만 제목이 잘린다."""
    uid, title = _fnsafe(uid), _fnsafe(title)
    if not (uid or title):
        return
    for fn in sorted(os.listdir(outdir)):
        src = os.path.join(outdir, fn)
        if not os.path.isfile(src):
            continue
        stem, dot, suf = fn.partition(".")   # 다운로드 이름엔 점이 없다(%(id)s) → 첫 점 뒤 전부가 확장자류
        if not dot:
            continue
        room = FN_MAX - FN_HEADROOM - len(dot.encode()) - len(suf.encode())
        want = "_".join(x for x in (stem, uid, title) if x)
        new = _bytecap(want, max(len(stem.encode()), min(room, FN_STEM_CAP)))
        n, cand = 1, new
        while cand != stem and os.path.exists(os.path.join(outdir, cand + dot + suf)):
            n += 1
            cand = _bytecap(new, max(1, min(room, FN_STEM_CAP) - 3)) + f"_{n}"
        if cand != stem:
            os.rename(src, os.path.join(outdir, cand + dot + suf))


def download(url, outdir, name_tag, fmt, extra, cookies, pl, subs, post):
    """다운로드 1회 — 파일명 = {TS}_{PLAT}_{tag}_{계정}_{제목}(bat 동일). 남은 예산으로 타임아웃 산정. rc 반환."""
    to = int(max(60, budget_left()))
    tag = f"{name_tag}_" if name_tag else ""
    idx = "%(playlist_index|1)s_" if post else ""   # 캐러셀 다중 항목 파일명 충돌 방지(평의회6 P2-4)
    out = f"{TS}_{PLAT}_{tag}{idx}%(id).40s.%(ext)s"   # 다운로드 중엔 ASCII 짧은 이름(최악 ~114B) = [Errno 36] 원천 차단 · 계정·제목은 pretty_rename이 사후 복원
    args = ["--ffmpeg-location", os.environ.get("FFMPEG_DIR", "/usr/bin"),
            "--trim-filenames", "120", "--windows-filenames",
            "-P", outdir, "-o", out, "-f", fmt, "--merge-output-format", "mp4", "-N", "4"] + extra + pl
    if subs:
        args += ["--write-subs", "--write-auto-subs", "--sub-langs", SUBLANG, "--convert-subs", "srt"]
    else:
        args += ["--no-write-subs", "--no-write-auto-subs"]
    args.append(url)
    try:
        return ytd(args, to, cookies=cookies).returncode
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
    """aws s3 cp 파일 직접 업로드 → 공개 URL(quote · 평의회6 P2-3). 미설정 = die(전역 전제) · 개별 실패 = 예외(부분성공)."""
    acct, bucket = os.environ.get("R2_ACCOUNT_ID", ""), os.environ.get("R2_BUCKET", "")
    pub = os.environ.get("R2_PUBLIC_BASE", "").rstrip("/")
    ak, sk = os.environ.get("R2_ACCESS_KEY_ID", ""), os.environ.get("R2_SECRET_ACCESS_KEY", "")
    if not (acct and bucket and pub and ak and sk):
        die("저장소(R2)가 설정 안 돼 있어 — 관리자 설정 후 다시.", "R2 시크릿 미설정")
    env = dict(os.environ, AWS_ACCESS_KEY_ID=ak, AWS_SECRET_ACCESS_KEY=sk, AWS_DEFAULT_REGION="auto",
               AWS_REQUEST_CHECKSUM_CALCULATION="when_required", AWS_RESPONSE_CHECKSUM_VALIDATION="when_required")
    subprocess.run(["aws", "s3", "cp", path, f"s3://{bucket}/{key}",
                    "--endpoint-url", f"https://{acct}.r2.cloudflarestorage.com",
                    "--content-type", ctype, "--only-show-errors"],
                   check=True, env=env, timeout=900)
    return f"{pub}/" + urllib.parse.quote(key)


# ── 드라이브(= bat robocopy 축) — 인증 = drive_shared_guard.py 정본 계승 ──
def drive_token():
    """(access_token, '') 또는 (None, 사유) — 항상 2-튜플."""
    raw = os.environ.get("GDRIVE_SA_JSON", "")
    if not raw.strip():
        return None, "드라이브가 연결 안 돼 있어요"
    try:
        info = json.loads(raw)
        if info.get("type") == "service_account":
            return None, "드라이브 설정이 이상해요(서비스계정 키)"
        body = urllib.parse.urlencode({
            "client_id": info["client_id"], "client_secret": info["client_secret"],
            "refresh_token": info["refresh_token"], "grant_type": "refresh_token"}).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["access_token"], ""
    except Exception as e:
        return None, f"드라이브 인증 실패({str(e)[:60]})"


def drive_call(tok, method, path, params=None, body=None):
    url = f"{DRIVE_API}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def drive_shared(tok):
    """루트 Shared 폴더 id — createdTime 정렬로 결정적(평의회7 P3-ⓔ). (id, note)."""
    q = "name='Shared' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false"
    fs = drive_call(tok, "GET", "/files", {"q": q, "fields": "files(id,createdTime)", "orderBy": "createdTime"}).get("files", [])
    if not fs:
        return None, "드라이브에 Shared 폴더가 없어요"
    note = f"Shared 중복 {len(fs)}개 — 최초본 사용" if len(fs) > 1 else ""
    return fs[0]["id"], note


def drive_find(tok, sid, name):
    """동명 파일 id(덮어쓰기용 · 폰 rclone 중복 스킵 방지 · 평의회7 P2-ⓔ)."""
    safe = name.replace("'", r"\'")
    q = f"name='{safe}' and '{sid}' in parents and trashed=false"
    fs = drive_call(tok, "GET", "/files", {"q": q, "fields": "files(id)"}).get("files", [])
    return fs[0]["id"] if fs else None


def drive_upload(tok, sid, path, ctype):
    """resumable 세션(urllib) → curl -T 단일 PUT. http_code 검증(3xx 실패 처리 · 평의회7 P2-ⓑ). 동명은 PATCH 덮어쓰기."""
    name = os.path.basename(path)
    fid = drive_find(tok, sid, name)
    if fid:
        up = f"{DRIVE_UP}/files/{fid}?uploadType=resumable"
        meth = "PATCH"
        meta = json.dumps({}).encode()
    else:
        up = f"{DRIVE_UP}/files?uploadType=resumable"
        meth = "POST"
        meta = json.dumps({"name": name, "parents": [sid]}).encode()
    req = urllib.request.Request(up, data=meta, method=meth,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                                          "X-Upload-Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=30) as r:
        loc = r.headers.get("Location", "")
    if not loc:
        raise RuntimeError("업로드 세션 없음")
    to = int(max(1800, os.path.getsize(path) / 1e6 * 4))   # 크기 유도 타임아웃(평의회7 P2-ⓐ)
    r = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "-X", "PUT",
                        "-H", f"Authorization: Bearer {tok}", "-H", f"Content-Type: {ctype}",
                        "-T", path, loc], capture_output=True, text=True, timeout=to)
    code = (r.stdout or "").strip()
    if code not in ("200", "201"):
        raise RuntimeError(f"HTTP {code or '?'}")


def ctype_of(fn):
    return "video/mp4" if fn.endswith((".mp4", ".m4v", ".mov", ".webm", ".mkv")) else "application/octet-stream"


def out_files(outdir):
    return sorted(f for f in os.listdir(outdir)
                  if os.path.isfile(os.path.join(outdir, f)) and not f.endswith((".part", ".ytdl")))


def main():
    if len(sys.argv) < 3:
        die("실행 인자 부족 — 다시 시도해줘.", "usage: vidl_run.py <id> <url>")
    vid_id, url = sys.argv[1], sys.argv[2]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", vid_id):   # 경로 탈출 차단(평의회6 P2-5)
        die("작업 id가 이상해 — 다시 시도해줘.", f"잘못된 id: {vid_id}")
    if not PLAT:   # 서버측 플랫폼 화이트리스트(평의회1 P1) — 미매칭 = 거부
        die("영상 게시물 주소가 아니야 — 유튜브·인스타·X·틱톡·페북·스레드 영상 주소를 넣어줘.", f"플랫폼 미매칭: {url}")

    outdir = "/tmp/vidl_out"
    shutil.rmtree(outdir, ignore_errors=True)   # 로컬 재실행 잔재 방어(평의회6 무혐의-보험)
    os.makedirs(outdir, exist_ok=True)

    cookies = None
    ck = os.environ.get("YT_COOKIES", "")
    if ck.strip():
        with open("/tmp/ck.txt", "w", encoding="utf-8") as f:
            f.write(ck)
        cookies = "/tmp/ck.txt"
    ck_use = None if PLAT == "YT" else cookies   # YT = 쿠키 미사용 선행(bat v6.2) · 비YT = 쿠키 사용
    pl = plopt(url, PLAT)
    post = "--playlist-items" not in pl   # 게시물형(캐러셀 통짜) = 파일명 인덱스 부여

    # ── 3축 사전조회(bat v6.8) ──
    best = probe(url, "bv*/b/best", [], ck_use, pl)
    fpsb = probe(url, "bv*/b/best", ["-S", "fps,res,br"], ck_use, pl)
    fhd = None
    if best:
        dimk = "width" if best["w"] < best["h"] else "height"   # 세로영상 = width 필터(bat v6.4)
        ffilt = f"bv*[{dimk}<=1080][ext=mp4]/b[{dimk}<=1080][ext=mp4]/bv*[{dimk}<=1080]/b[{dimk}<=1080]"
        fhd = probe(url, ffilt, [], ck_use, pl)
    get_fps = bool(best and fpsb and fpsb["fps"] > best["fps"])
    short_side = (best["w"] if best["w"] < best["h"] else best["h"]) if best else 0
    get_1080 = bool(best and fhd and short_side > 1080)
    if get_1080 and fhd and ((get_fps and fhd["fid"] == fpsb["fid"]) or fhd["fid"] == best["fid"]):
        get_1080 = False   # 중복 판(fps판·최고화질판과 동일 format) 차단(bat v6.8 + 평의회4 P2)
    print(f"[화질] best={best} / fps={fpsb} get_fps={get_fps} / fhd={fhd} get_1080={get_1080}", flush=True)

    # ── ① 최고화질 + 자막(항상) — YT 실패 시 쿠키 1회 재시도, 성공 시 부가본도 쿠키 계승(평의회6 P2-1) ──
    rc = download(url, outdir, "", "bv*+ba/b/best", [], ck_use, pl, subs=True, post=post)
    if rc != 0 and PLAT == "YT" and cookies:
        print("[재시도] 쿠키 달아 1회 재시도(연령제한·멤버십 가능성)", flush=True)
        rc = download(url, outdir, "", "bv*+ba/b/best", [], cookies, pl, subs=True, post=post)
        if rc == 0:
            ck_use = cookies
    VID_EXT = (".mp4", ".mkv", ".webm", ".mov", ".m4v")
    if rc != 0 or not any(f.endswith(VID_EXT) for f in out_files(outdir)):   # 성공 게이트 = 영상 존재(자막만=실패 · 평의회6 P3-3)
        die("영상 다운로드 실패 — 주소·연령 제한·로그인 전용 여부를 확인해줘.", f"yt-dlp 실패: {url}")

    # ── ② 프레임별 · ③ FHD별(각 실패 = 비치명 · 예산 남을 때만) ──
    if get_fps and budget_left() > 90:
        download(url, outdir, "maxfps", "bv*+ba/b/best", ["-S", "fps,res,br"], ck_use, pl, subs=False, post=post)
    if get_1080 and budget_left() > 90:
        dimk = "width" if best["w"] < best["h"] else "height"
        f1080 = (f"bv*[{dimk}<=1080][ext=mp4]+ba[ext=m4a]/b[{dimk}<=1080][ext=mp4]/"
                 f"bv*[{dimk}<=1080]+ba/b[{dimk}<=1080]")
        download(url, outdir, "1080p", f1080, [], ck_use, pl, subs=False, post=post)

    srt_to_txt(outdir)
    meta = best or fpsb or fhd or {}   # 예쁜 이름 재료 = 사전조회 부산물(추가 호출 0) · 전부 실패면 짧은 id 이름 그대로 유지
    pretty_rename(outdir, meta.get("uid", ""), meta.get("title", ""))

    # ── R2 업로드(부분 성공 · 루프 내 die 금지 · 평의회6 P2-2) ──
    files, up_err = [], 0
    for fn in out_files(outdir):
        p = os.path.join(outdir, fn)
        try:
            u = r2_upload(p, f"vidl_res/{vid_id}/{fn}", ctype_of(fn))
            files.append({"name": fn, "url": u, "size": os.path.getsize(p),
                          "kind": "video" if ctype_of(fn).startswith("video/") else "sub"})
        except SystemExit:
            raise   # R2 미설정(전제 붕괴)은 die 그대로
        except Exception as e:
            up_err += 1
            print(f"::warning::R2 업로드 실패 {fn}: {e}", flush=True)
    if not files:
        die("결과 업로드에 실패했어 — 잠시 후 다시 해줘.", "R2 업로드 전량 실패")

    # ── 드라이브 Shared 업로드(= bat robocopy 축) — 토큰 45분 재발급·부분사유 누적(평의회7) ──
    drive = {"on": False, "n": 0, "why": ""}
    tok, why = drive_token()
    if not tok:
        drive["why"] = why
    else:
        try:
            sid, note = drive_shared(tok)
            if not sid:
                drive["why"] = note
            else:
                whys, tstamp = ([note] if note else []), time.monotonic()
                for fn in out_files(outdir):
                    p = os.path.join(outdir, fn)
                    if time.monotonic() - tstamp > 45 * 60:   # 토큰 만료 전 재발급(대용량 다중 · 평의회7 P2-ⓒ)
                        t2, _ = drive_token()
                        if t2:
                            tok, tstamp = t2, time.monotonic()
                    try:
                        drive_upload(tok, sid, p, ctype_of(fn))
                        drive["n"] += 1
                    except Exception as e:
                        whys.append(f"{fn}: {str(e)[:40]}")
                drive["on"] = drive["n"] > 0   # n=0 = 실패(성공 포장 금지 · 평의회7 P1-ⓖ)
                drive["why"] = " · ".join(whys)[:300]
        except Exception as e:
            drive["why"] = f"드라이브가 잠깐 응답을 안 해요({str(e)[:50]})"

    # ── result.json 원자적 기록(절대경로 · 평의회6 P2-5·P3-4) ──
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    odir = os.path.join(root, "viewer", "vidl_out", vid_id)
    os.makedirs(odir, exist_ok=True)
    doc = {"plat": PLAT, "ts": TS, "best": best, "fps": fpsb if get_fps else None,
           "fhd": fhd if get_1080 else None, "files": files, "up_err": up_err, "drive": drive}
    dst = os.path.join(odir, "result.json")
    with open(dst + ".tmp", "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    os.replace(dst + ".tmp", dst)
    print("result.json:", json.dumps(doc, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    URL = sys.argv[2] if len(sys.argv) > 2 else ""
    PLAT = detect_plat(URL)
    TS = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    try:  # JS 런타임(node) 지원 여부 — SABR 대응 최고화질(bat v6.7) · 미지원 구버전이면 플래그 생략
        JSRT = subprocess.run([sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--version"],
                              capture_output=True, timeout=60).returncode == 0
    except Exception:
        JSRT = False
    main()
