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
# 받아쓰기 폴백(운영자 260802 · Handy 개념 이식) — 플랫폼 자막이 0개면 ①본에서 Whisper STT로 srt/txt를 만들어
#   같이 납품한다(X·틱톡 클립 대부분이 자막 없음 → ly 자막기 돌릴 때 STT 단계가 이미 끝나 있게).
#   실행체 = .github/scripts/ly_stt.py 재사용(faster-whisper large-v3 · ly·edit·nb 공용 정본 — 모델·정밀도 창작 0).
#   전 구간 fail-soft: 스킵·실패 = 영상만 납품(종전과 동일) · 사유는 result.json "stt"로 정직 표기.
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
VID_EXT = (".mp4", ".mkv", ".webm", ".mov", ".m4v")
STT_MAX_DUR = 600           # 받아쓰기 폴백 대상 상한(초) — ly 번인 길이 게이트와 동일 축(10분 · large-v3 CPU ~2x실시간)
STT_RESERVE = 300           # STT 후 업로드 몫으로 남겨둘 예산(초) — 부족하면 영상 납품 우선·받아쓰기 생략
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
        return "TH" if re.search(r"/(post|t|share)/", path) else ""   # 공유 시트 형식(/share/<코드>/ · /t/<코드>)도 수용 — 뷰어·엣지 게이트와 3면 동값(260802)
    return ""


# 스레드(Threads) = yt-dlp 코어에 extractor가 없어 종전 TH 경로는 구조적 100% 실패였다(260802 러너 실측
#   "ERROR: Unsupported URL" → generic 폴백). 운영자 제공 플러그인이 포스트 HTML의
#   <script type="application/json" data-sjs> SSR JSON에서 서명 CDN 주소를 뽑는다 = 토큰·로그인·추가요청 0.
# ⚠ 배선은 **홈 설정 경로 복사만** 통한다 — `--plugin-dirs`(상대·절대 both)는 "Plugin directories: none"으로
#   무시됐다(260802 로컬 실측 + 러너 실측 2회). 유효 경로 = ~/.config/yt-dlp/plugins/<pkg>/yt_dlp_plugins/extractor/.
# ⚠ 파일명은 반드시 파이썬 모듈명으로 유효해야 한다(하이픈·숫자 시작 = import 조용히 실패 · 실측).
PLUGIN_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins", "yt_dlp_plugins", "extractor")
PLUGIN_DST = os.path.expanduser("~/.config/yt-dlp/plugins/nomute/yt_dlp_plugins/extractor")


def install_plugins():
    """레포 동봉 extractor 플러그인을 yt-dlp가 실제로 읽는 홈 경로에 깐다. 실패해도 비치명(스레드만 못 받음)."""
    try:
        os.makedirs(PLUGIN_DST, exist_ok=True)
        n = 0
        for fn in sorted(os.listdir(PLUGIN_SRC)):
            if fn.endswith(".py"):
                shutil.copyfile(os.path.join(PLUGIN_SRC, fn), os.path.join(PLUGIN_DST, fn))
                n += 1
        print(f"[플러그인] {n}개 설치 → {PLUGIN_DST}", flush=True)
    except Exception as e:
        print(f"::warning::플러그인 설치 실패(스레드 경로만 영향): {e}", flush=True)


def ytd(args, timeout, cookies=None, capture=False):
    """python3 -m yt_dlp 공통 호출 — sys.executable(인터프리터 일치 · 평의회6 P1-2) · cookies=경로(없으면 미사용)."""
    cmd = [sys.executable, "-m", "yt_dlp", "--no-cache-dir", "--socket-timeout", "30",
           "--concat-playlist", "never"]   # 캐러셀 = 개별 파일 납품(bat v7.0 동일) — 기본값 multi_video가 TH 캐러셀 jpg 6장을 이어붙이려다 "different streams/codecs" 전량 실패(260802 러너 실측 run 30743201191)
    if cookies:
        cmd += ["--cookies", cookies]
    if JSRT:
        cmd += ["--js-runtimes", "node"]
    if EJS:
        # 유튜브 n챌린지 해결기(EJS) 원격 컴포넌트 — **yt-dlp가 로그로 직접 지시한 처방**(260804 실측 run 30874184405):
        #   "[jsc] Remote component challenge solver script (node) was skipped. It may be required to solve JS
        #    challenges. You can enable the download with --remote-components ejs:github (recommended)."
        #   그 다음 줄이 "n challenge solving failed" → "Only images are available" → "Requested format is not
        #   available" = **쿠키로 인증까지 통과한 뒤 포맷이 통째로 증발**해 유튜브가 100% 실패했다.
        #   (node 런타임 자체는 러너에 있고 잡히기까지 한다 — 빠진 건 해결기 스크립트 하나뿐이다.)
        # 스코프 = 전 플랫폼 공통 플래그지만 실제 fetch는 yt-dlp가 **필요할 때만**(= 유튜브 챌린지) 한다 = 비YT 무영향.
        cmd += ["--remote-components", "ejs:github"]
    cmd += args
    return subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)


def plopt(url, plat):
    """재생목록 방지(bat v6.6) — YT·비게시물형 = 1편 강제 · 게시물형 = --no-playlist만(IG 캐러셀 등 통짜 허용)."""
    if plat == "YT":
        return ["--no-playlist", "--playlist-items", "1"]
    if plat == "TH":
        # 스레드 = 전 형식(/post/·/t/·/share/)이 게시물이다. 구판은 아래 표식에 /share/·/t/가 없어 공유 링크가
        # 비게시물형 → --playlist-items 1이 붙었고, 4장 캐러셀이 1장만 받아졌다(260802 run 30752917025
        # "Downloading 1 items of 4" + 운영자 "여러 이미지인데 메인 1개만" 실측). 표식 나열이 아니라 플랫폼으로 판정.
        return ["--no-playlist"]
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


def download(url, outdir, name_tag, fmt, extra, cookies, pl, subs, post, desc=False):
    """다운로드 1회 — 파일명 = {TS}_{PLAT}_{tag}_{계정}_{제목}(bat 동일). 남은 예산으로 타임아웃 산정. rc 반환."""
    to = int(max(60, budget_left()))
    tag = f"{name_tag}_" if name_tag else ""
    idx = "%(playlist_index|1)s_" if post else ""   # 캐러셀 다중 항목 파일명 충돌 방지(평의회6 P2-4)
    out = f"{TS}_{PLAT}_{tag}{idx}%(id).40s.%(ext)s"   # 다운로드 중엔 ASCII 짧은 이름(최악 ~114B) = [Errno 36] 원천 차단 · 계정·제목은 pretty_rename이 사후 복원
    args = ["--ffmpeg-location", os.environ.get("FFMPEG_DIR", "/usr/bin"),
            "--trim-filenames", "120", "--windows-filenames",
            "-P", outdir, "-o", out, "-f", fmt, "--merge-output-format", "mp4", "-N", "4"] + extra + pl
    if desc:
        args.append("--write-description")   # 게시물 본문 동봉 재료(①본만 · 운영자 260803 "텍스트 내용도 가져오게") — caption_txt가 사후 1파일 승격
    if subs:
        args += ["--write-subs", "--write-auto-subs", "--sub-langs", SUBLANG, "--convert-subs", "srt"]
    else:
        args += ["--no-write-subs", "--no-write-auto-subs"]
    args.append(url)
    try:
        return ytd(args, to, cookies=cookies).returncode
    except subprocess.TimeoutExpired:
        return 1


def qual_parse(q):
    """'2160-30' → (2160, 30) · '1080-60' → (1080, 0). 둘째 값 = fps **상한**(0 = 제한 없음).
    60 선택 = 「고프레임 허용」이라 상한을 안 건다(있으면 60을 그냥 집는다) · 30 선택 = fps<=30 강제
    (= 운영자 260804 "60fps 있으면 30fps 고를수도 있어야 함" — 진짜 주문은 **60을 피하는 수단**이다)."""
    m = re.fullmatch(r"(\d+)-(\d+)", q or "")
    if not m:
        return 0, 0
    return int(m.group(1)), (30 if int(m.group(2)) <= 30 else 0)


def qual_fmt(best, q):
    """화질 상한판 포맷 선택자 — ③FHD판 정본(`bv*[{dimk}<=1080]…`) **값만 바꾼 사본**(신규 문법 0).
    가로/세로 축도 bat v6.4 그대로: 가로영상 = height 필터 · 세로영상 = width 필터
    (세로 1080x1920에 height 필터를 걸면 1920이 상한을 넘어 아예 안 잡힌다 — bat v6.1의 실패 원인).
    ⚠ 꼬리 `bv*+ba/b/best`(최대화질) = 상한 밑에 아무것도 없을 때의 마지막 수단 —
      **운영자 260804 3차 지정**("1080p가 안될 경우에는 무조건 최대 화질인 거로").
      구판은 반대로 `wv*+ba/w`(가장 낮은 것)였다 = 「작게」 우선 해석 → 운영자 판단으로 뒤집었다."""
    cap, fcap = qual_parse(q)
    dimk = "width" if (best and best.get("w") and best.get("h") and best["w"] < best["h"]) else "height"
    f = f"[fps<={fcap}]" if fcap else ""
    return (f"bv*[{dimk}<={cap}]{f}[ext=mp4]+ba[ext=m4a]/b[{dimk}<={cap}]{f}[ext=mp4]/"
            f"bv*[{dimk}<={cap}]{f}+ba/b[{dimk}<={cap}]{f}/bv*+ba/b/best")


def ffprobe_dur(path):
    """영상 길이(초) — 실패 = 0.0(받아쓰기 게이트가 스킵으로 처리)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", path], capture_output=True, text=True, timeout=60)
        return _fnum((r.stdout or "").strip())
    except Exception:
        return 0.0


def _srt_tc(x):
    """초 → SRT 타임코드(00:00:00,000)."""
    x = max(0.0, float(x))
    return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{x % 60:06.3f}".replace(".", ",")


def stt_fallback(outdir):
    """자막 0개 → ①본 Whisper 받아쓰기 폴백(Handy 개념 이식 · 운영자 260802) → {stem}.stt.srt.
    실행체 = .github/scripts/ly_stt.py(large-v3 정본 공용) · 전 구간 fail-soft = {"on": bool, "why": 사유}."""
    files = out_files(outdir)
    if any(f.endswith(".srt") for f in files):
        return {"on": False, "why": ""}   # 플랫폼 자막 확보 = 폴백 불요(정상·무사유)
    vids = ([f for f in files if f.endswith(VID_EXT) and "maxfps_" not in f and "1080p_" not in f]
            or [f for f in files if f.endswith(VID_EXT)])   # ①본 우선(부가본 = 동일 음성 중복)
    if not vids:
        return {"on": False, "why": "영상 없음"}
    src = os.path.join(outdir, vids[0])
    dur = ffprobe_dur(src)
    if not dur:
        return {"on": False, "why": "길이 판독 실패 — 받아쓰기 생략"}
    if dur > STT_MAX_DUR:
        return {"on": False, "why": f"영상 {int(dur // 60)}분 — 받아쓰기는 {STT_MAX_DUR // 60}분 이하만"}
    need = dur * 2.5 + 180   # large-v3 CPU ~2x실시간(ly 실측) + 모델 로드·오디오 추출 여유
    if budget_left() - STT_RESERVE < need:
        return {"on": False, "why": "시간 예산 부족 — 영상 납품 우선(받아쓰기 생략)"}
    wav = "/tmp/vidl_stt.wav"   # 16kHz 모노(ly STEP 0-1 정본 미러)
    try:
        subprocess.run(["ffmpeg", "-y", "-i", src, "-vn", "-ar", "16000", "-ac", "1", wav],
                       capture_output=True, timeout=300)
        if not os.path.exists(wav):
            return {"on": False, "why": "오디오 추출 실패(음성 트랙 없음?)"}
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        r = subprocess.run([sys.executable, os.path.join(root, ".github", "scripts", "ly_stt.py"), wav],
                           capture_output=True, text=True, timeout=int(need))
        segs = re.findall(r"^\[(\d+\.?\d*)-(\d+\.?\d*)\]\s*(\S.*)$", r.stdout or "", re.M)
        if r.returncode != 0 or not segs:   # rc 3 = 세그먼트 0(ly_stt 정본) 포함
            return {"on": False, "why": "받아쓰기 실패(음성 인식 불가)"}
        srt = os.path.join(outdir, vids[0].partition(".")[0] + ".stt.srt")   # 첫 점 앞 = 영상과 같은 stem → pretty_rename 동반 개명
        with open(srt + ".tmp", "w", encoding="utf-8") as f:
            for i, (s0, e0, t0) in enumerate(segs, 1):
                f.write(f"{i}\n{_srt_tc(s0)} --> {_srt_tc(e0)}\n{t0.strip()}\n\n")
        os.replace(srt + ".tmp", srt)
        return {"on": True, "why": f"자막 0개 → Whisper large-v3 받아쓰기 {len(segs)}조각"}
    except subprocess.TimeoutExpired:
        return {"on": False, "why": "받아쓰기 시간 초과 — 영상만 납품"}
    except Exception as e:
        return {"on": False, "why": f"받아쓰기 실패({str(e)[:40]})"}
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass


def caption_txt(outdir):
    """게시물 본문(텍스트) 동봉(운영자 260803 "다운로드 하게 되면 기본적으로 텍스트 내용도 가져오게").

    재료 = ①본이 --write-description으로 받은 yt-dlp description(= X 트윗 전문 · TH/IG 캡션 · YT 설명 —
    추가 요청 0 · 전문 규칙 정본 = scraper/sns_trends.py X 상세 축과 동일 내용물). 캐러셀은 슬라이드마다
    같은 캡션이 N개 나오므로 첫 비어있지 않은 1개만 {TS}_{PLAT}_본문.txt로 승격하고 원본은 걷는다.
    전 구간 fail-soft: 본문 없는 게시물 = 파일 미생성(종전과 동일 납품)."""
    text = ""
    for fn in sorted(os.listdir(outdir)):
        if not fn.endswith(".description"):
            continue
        p = os.path.join(outdir, fn)
        try:
            if not text:
                with open(p, encoding="utf-8", errors="replace") as f:
                    text = f.read().strip()
        except OSError:
            pass
        try:
            os.remove(p)   # 원본 .description은 항상 걷는다(잔존 = R2에 중복 N개 올라감)
        except OSError:
            pass
    if text:
        dst = os.path.join(outdir, f"{TS}_{PLAT}_본문.txt")
        with open(dst + ".tmp", "w", encoding="utf-8") as f:
            f.write(text + "\n")
        os.replace(dst + ".tmp", dst)


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
    if fn.endswith((".mp4", ".m4v", ".mov", ".webm", ".mkv")):
        return "video/mp4"
    if fn.endswith((".jpg", ".jpeg")):
        return "image/jpeg"   # 스레드 사진 게시물(260802 실측 — TH extractor는 이미지 포스트도 최고해상 1장으로 뽑는다)
    if fn.endswith(".png"):
        return "image/png"
    if fn.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


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

    # ── 3축 사전조회(bat v6.8) — 자막만 모드는 화질 판단이 무의미하나 계정·제목(pretty_rename 재료)은 여기서 나온다 ──
    best = probe(url, "bv*/b/best", [], ck_use, pl)
    if best is None and PLAT == "YT" and cookies:
        # YT 무쿠키 선행(bat v6.2 = 쿠키를 붙이면 android_vr이 배제돼 화질이 떨어진다)은 **러너 IP에선 100% 봇검문**에
        #   막힌다(260804 실측 "Sign in to confirm you're not a bot"). 구판은 다운로드만 쿠키로 1회 재시도하고
        #   **사전조회는 안 했다** = best/fps/fhd 전건 None → ⓐ pretty_rename 재료가 없어 파일명이 짧은 id로 남고
        #   ⓑ ②프레임별·③FHD판 판정이 구조적으로 항상 False = 유튜브만 부가본이 영영 안 나온다.
        #   여기서 쿠키로 한 번 승격시키면 그 뒤 전 구간이 쿠키를 계승 = 다운로드 헛발 1회도 같이 사라진다.
        b2 = probe(url, "bv*/b/best", [], cookies, pl)
        if b2:
            best, ck_use = b2, cookies
            print("[사전조회] YT 무쿠키 실패 → 쿠키로 승격(이후 전 구간 계승)", flush=True)
    # 스레드 = video_versions에 fps가 아예 없다(플러그인 실측 · 전부 0) → 프레임별 판정이 구조적으로 항상 False
    #   = fps 사전조회는 페이지 fetch 1회를 그냥 버리는 것 → 생략(260802 · 사전조회 1회당 수 초).
    # 화질 상한판(QUAL≠best)은 ②프레임별·③FHD판이 **개념상 성립하지 않는다** — 「작게 1편」이 주문이니
    #   부가본 2판은 주문 위반이자 시간·용량 낭비다. 사전조회도 그만큼 건너뛴다(1회당 수 초 · 260802 절약 축 동일).
    capped = QUAL != "best"
    fpsb = probe(url, "bv*/b/best", ["-S", "fps,res,br"], ck_use, pl) if MODE != "subs" and PLAT != "TH" and not capped else None
    short_side = (best["w"] if best["w"] < best["h"] else best["h"]) if best else 0
    fhd = None
    if best and MODE != "subs" and short_side > 1080 and not capped:   # 짧은 변 ≤1080 = ③FHD판 자체가 불성립(get_1080 항상 False) → 사전조회도 생략(구판은 전 플랫폼서 무조건 1회 낭비 · 260802)
        dimk = "width" if best["w"] < best["h"] else "height"   # 세로영상 = width 필터(bat v6.4)
        ffilt = f"bv*[{dimk}<=1080][ext=mp4]/b[{dimk}<=1080][ext=mp4]/bv*[{dimk}<=1080]/b[{dimk}<=1080]"
        fhd = probe(url, ffilt, [], ck_use, pl)
    get_fps = bool(best and fpsb and fpsb["fps"] > best["fps"])
    get_1080 = bool(best and fhd and short_side > 1080)
    if get_1080 and fhd and ((get_fps and fhd["fid"] == fpsb["fid"]) or fhd["fid"] == best["fid"]):
        get_1080 = False   # 중복 판(fps판·최고화질판과 동일 format) 차단(bat v6.8 + 평의회4 P2)
    print(f"[화질] best={best} / fps={fpsb} get_fps={get_fps} / fhd={fhd} get_1080={get_1080}", flush=True)

    # ── ① 본편 — MODE에 따라 {영상+자막 / 영상만 / 자막만}. YT 실패 시 쿠키 1회 재시도(성공 시 부가본도 쿠키 계승 · 평의회6 P2-1) ──
    want_sub = MODE in ("both", "subs")
    want_vid = MODE in ("both", "video")
    mainfmt = qual_fmt(best, QUAL) if capped else "bv*+ba/b/best"   # 화질 상한판 = ①본 자체를 상한으로 받는다(부가본 없음 = 1편)
    if want_vid:
        rc = download(url, outdir, "", mainfmt, [], ck_use, pl, subs=want_sub, post=post, desc=True)
        if rc != 0 and PLAT == "YT" and cookies:
            print("[재시도] 쿠키 달아 1회 재시도(연령제한·멤버십 가능성)", flush=True)
            rc = download(url, outdir, "", mainfmt, [], cookies, pl, subs=want_sub, post=post, desc=True)
            if rc == 0:
                ck_use = cookies
    else:   # 자막만 — 영상 트랙을 아예 받지 않는다(--skip-download) = 몇 초면 끝난다
        rc = download(url, outdir, "", "bv*+ba/b/best", ["--skip-download"], ck_use, pl, subs=True, post=post, desc=True)
        if rc != 0 and PLAT == "YT" and cookies:
            rc = download(url, outdir, "", "bv*+ba/b/best", ["--skip-download"], cookies, pl, subs=True, post=post, desc=True)
    VID_EXT = (".mp4", ".mkv", ".webm", ".mov", ".m4v")
    IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")   # 스레드 사진 게시물 = 이미지도 성과(260802 실측 — jpg 100% 받고도 영상 게이트에 걸려 실패 처리되던 것 교정)
    got = out_files(outdir)
    if want_vid:
        ok = rc == 0 and any(f.endswith(VID_EXT + IMG_EXT) for f in got)   # 성공 게이트 = 미디어 존재(자막만=실패 · 평의회6 P3-3)
        fail_msg = "영상 다운로드 실패 — 주소·연령 제한·로그인 전용 여부를 확인해줘."
    else:
        ok = any(f.endswith((".srt", ".vtt")) for f in got)      # 자막만 모드 = 자막 존재가 성공 게이트(rc는 영상 스킵 탓에 흔들린다)
        fail_msg = "이 영상엔 플랫폼 자막이 없어 — [다운로드+자막]으로 받으면 영상과 함께 받아쓰기(STT) 자막을 만들어줘."
    if not ok:
        die(fail_msg, f"yt-dlp 실패(mode={MODE}): {url}")

    # ── ② 프레임별 · ③ FHD별(각 실패 = 비치명 · 예산 남을 때만) — 자막만 모드는 건너뛴다 ──
    if want_vid and get_fps and budget_left() > 90:
        download(url, outdir, "maxfps", "bv*+ba/b/best", ["-S", "fps,res,br"], ck_use, pl, subs=False, post=post)
    if want_vid and get_1080 and budget_left() > 90:
        dimk = "width" if best["w"] < best["h"] else "height"
        f1080 = (f"bv*[{dimk}<=1080][ext=mp4]+ba[ext=m4a]/b[{dimk}<=1080][ext=mp4]/"
                 f"bv*[{dimk}<=1080]+ba/b[{dimk}<=1080]")
        download(url, outdir, "1080p", f1080, [], ck_use, pl, subs=False, post=post)

    caption_txt(outdir)   # 게시물 본문 .description → {TS}_{PLAT}_본문.txt 승격(전 모드 기본 동봉 · 운영자 260803) — 업로드 루프 전에 걷어야 .description 원본이 R2에 안 샌다
    stt = stt_fallback(outdir) if want_sub else {"on": False, "why": ""}   # 자막 0개 → Whisper 받아쓰기 폴백(비치명 · srt_to_txt 앞 = .stt.txt까지 동일 후처리) — [다운로드](영상만) 선택 시엔 안 돈다(3택 계약 · 260802)
    if stt["why"]:
        print(f"[받아쓰기] on={stt['on']} · {stt['why']}", flush=True)
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
                          "kind": ("video" if ctype_of(fn).startswith("video/")
                                   else "img" if ctype_of(fn).startswith("image/") else "sub")})
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
    doc = {"plat": PLAT, "ts": TS, "mode": MODE, "qual": QUAL, "best": best, "fps": fpsb if get_fps else None,
           "fhd": fhd if get_1080 else None, "files": files, "up_err": up_err, "drive": drive,
           "stt": stt}   # mode(3택 260802) + 받아쓰기 폴백 정직 표기(additive — 뷰어 파서는 미지 키 무시)
    dst = os.path.join(odir, "result.json")
    with open(dst + ".tmp", "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    os.replace(dst + ".tmp", dst)
    print("result.json:", json.dumps(doc, ensure_ascii=False), flush=True)


MODE_OK = ("both", "video", "subs")
# 화질 = **해상도×프레임 한 축**(운영자 260804 3차 "묶어서 6개 선택자중 하나로 하는게 맞다 · 소스 안에 다양한 영상이 있는경우가 별로 없음").
#   2칸으로 쪼개면 조합 6가지를 두 번 조작해야 하는데, 실제로 한 게시물 안에 화질이 뒤섞인 경우가 드물다는 게 운영자 판단.
#   ⚠ "best"는 **UI에 없다** — 인자 미지정·옛 클라이언트용 하위호환 값으로만 존치(종전 3판 동작 = 무회귀).
QUAL_OK = ("best", "2160-60", "2160-30", "1440-60", "1440-30", "1080-60", "1080-30")
if __name__ == "__main__":
    URL = sys.argv[2] if len(sys.argv) > 2 else ""
    MODE = (sys.argv[3] if len(sys.argv) > 3 else "both").strip().lower()
    QUAL = (sys.argv[4] if len(sys.argv) > 4 else "best").strip().lower()
    if QUAL not in QUAL_OK:
        QUAL = "best"   # 미지정·오타 = 종전 동작 = 하위호환(MODE 축과 같은 문법)
    install_plugins()   # yt-dlp 첫 호출(사전조회) 전에 깔아야 스레드가 [threads]로 잡힌다
    if MODE not in MODE_OK:
        MODE = "both"   # 미지정·오타 = 종전 동작(영상+자막) = 하위호환
    PLAT = detect_plat(URL)
    TS = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    try:  # JS 런타임(node) 지원 여부 — SABR 대응 최고화질(bat v6.7) · 미지원 구버전이면 플래그 생략
        JSRT = subprocess.run([sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--version"],
                              capture_output=True, timeout=60).returncode == 0
    except Exception:
        JSRT = False
    try:  # EJS 원격 컴포넌트 지원 여부 — 구버전 yt-dlp면 플래그 자체가 없어 rc≠0(그땐 생략 = 종전 동작)
        EJS = subprocess.run([sys.executable, "-m", "yt_dlp", "--remote-components", "ejs:github", "--version"],
                             capture_output=True, timeout=60).returncode == 0
    except Exception:
        EJS = False
    print(f"[런타임] node={JSRT} · ejs={EJS}", flush=True)   # 유튜브 실패 재발 시 「무엇이 빠졌나」를 로그 첫 줄에서 본다
    main()
