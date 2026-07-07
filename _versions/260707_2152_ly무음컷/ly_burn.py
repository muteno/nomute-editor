#!/usr/bin/env python3
# 영상 자막 번인(자동 합성) — 자막 텍스트를 ASS(libass)로 영상에 입혀 R2 업로드 → viewer/ly_out/<id>/video.json.
#   사용: ly_burn.py <id> <video_path>   (ly-make.yml 번인 스텝 전용 · ffmpeg+fonts-noto-cjk는 runner-setup가 설치)
#   env: OPTS = 뷰어 버튼 설정 JSON(스타일·위치·크기·카라오케·키워드) · R2 5종 = thumb_gen 재사용(카드·썸네일·/k 동일 파이프)
# 자막 소스 우선순위: subs.json(의역+타이밍 · lymake.sh가 claude 출력 꼬리 JSON 분리) → segments.json(받아쓴 원문 폴백).
# 실패 = fail-soft: video.json에 사유 기록 후 rc 0 (자막 텍스트 산출은 이미 정상 — 번인이 잡을 죽이면 안 됨).
# ASS 레시피 = 분신술 R1 기술 실측 확정본(260707): BorderStyle=3 금지(다줄 겹침) → 통박스는 4 + Outline==Back색 ·
#   한글 자동 줄바꿈 없음 → WrapStyle 2 + 수동 \N(줄당 폭/폰트 비례) ·
#   위치 = pos 게이지 %(0=하단 100=상단 · 구 bottom/middle/top 하위호환) → align 2 고정 + MarginV 연속(24% ≈ 구 하단 세이프존 22%) ·
#   배경 = bg 게이지 %(BackColour 알파 · 0=박스 없음 · 구 클라 박스 = 44 승계) ·
#   폰트 = "Noto Sans CJK KR"(fontconfig 자동 탐색 = fontsdir 불요) · 회전 메타 = autorotate 기본 유지 + PlayRes 스왑.
# 연속 축 3종(운영자 260707 플레이그라운드 선택값 배선): size = 높이비 소수(0.035 등 · 구 s/m/l 문자열 하위호환) ·
#   outline = 외곽선 두께 배율(×0.5 등 · bg=0 글리프 스트로크에만 의미) · pad = 박스 패딩 계수(fs×pad · bg>0 줄박스 패딩).
#   + 중앙 불변 배치: 게이지 = 1줄 기준점 고정 · 줄이 늘면 초과분 절반씩 내려 블록 세로중심 유지(이벤트별 MarginV).
# 팝 모드(opts.pop · 운영자 260707 배치 승인): 카라오케 대신 발화 중 어절만 콘텐츠 그린 점등 — 어절 창별 이벤트 분할(build_pop_frames) ·
#   타이밍 = \kf와 동일 글자수 비례 추정(진짜 발화 싱크 = Whisper word 타임스탬프 후속) · 카라오케와 상호배타(동시 수신 = 팝 우선).
# 키워드 강조색 = 콘텐츠 브랜드 형광그린 #0FFD02(릴스 오버레이 GREEN 계승 · UI 팔레트와 별개 축 = §핵심명령 3-b-1).
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # r2_upload · R2_ON 재사용(모듈 import = main 미실행 · k_refgen 선례)

GREEN_BGR = "&H02FD0F&"          # #0FFD02 → ASS BGR(콘텐츠 그린)
GIT_FALLBACK_MAX = 30 * 1024 * 1024   # R2 미설정 시 git 커밋 상한(레포 비대 방지)
MAX_DUR = 600                    # 릴스/쇼츠 도구 — 10분 초과 영상은 번인 거절(러너 시간 보호)
LINE_F = 1.0                     # libass 줄전진/폰트크기 비 = 1.0 실측(260707 ffmpeg+Noto CJK KR 프레임 픽셀 계측: 67px/fs67 — libass는 VSFilter 호환으로 fs를 줄높이로 정규화 · hhea 1.48 가정은 오류였음) · 중앙 불변 보정 전용


def kst_now():
    from datetime import datetime, timedelta, timezone
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    except Exception:
        return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def out_json(outdir, doc):
    doc["ts"] = kst_now()
    with open(os.path.join(outdir, "video.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print("video.json:", json.dumps(doc, ensure_ascii=False)[:200])


def probe(path):
    # 회전 메타(폰 세로영상 = 가로 저장+displaymatrix) — autorotate가 필터 앞에서 정립하므로 PlayRes는 표시 기준으로 스왑
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height:stream_side_data=rotation:format=duration",
                        "-of", "json", path], capture_output=True, text=True, timeout=60)
    j = json.loads(r.stdout or "{}")
    st = (j.get("streams") or [{}])[0]
    w, h = int(st.get("width") or 0), int(st.get("height") or 0)
    rot = 0
    for sd in (st.get("side_data_list") or []):
        if "rotation" in sd:
            try:
                rot = int(sd.get("rotation") or 0)
            except Exception:
                rot = 0
    if abs(rot) % 180 == 90:
        w, h = h, w
    try:
        dur = float((j.get("format") or {}).get("duration") or 0)   # 일부 webm/mkv = 'N/A' → 0(길이 체크만 생략·번인 진행)
    except Exception:
        dur = 0.0
    return w, h, dur


def load_segs(outdir):
    # subs.json = {"segs":[{"s","e","ko","src"?}]} (의역·*별표* 키워드) / segments.json = {"segs":[{"s","e","t"}]}
    p = os.path.join(outdir, "subs.json")
    if os.path.isfile(p):
        try:
            j = json.load(open(p, encoding="utf-8"))
            segs = [s for s in (j.get("segs") or [])
                    if isinstance(s.get("s"), (int, float)) and isinstance(s.get("e"), (int, float))
                    and (s.get("ko") or s.get("src"))]
            if segs:
                return segs, "subs"
        except Exception as e:
            print("::warning::subs.json 파싱 실패 — 받아쓴 자막으로 폴백:", e)
    p = os.path.join(outdir, "segments.json")
    if os.path.isfile(p):
        try:
            j = json.load(open(p, encoding="utf-8"))
            segs = [{"s": s["s"], "e": s["e"], "ko": s.get("t", ""), "src": ""}
                    for s in (j.get("segs") or [])
                    if isinstance(s.get("s"), (int, float)) and isinstance(s.get("e"), (int, float)) and s.get("t")]   # 세그별 필터 = 나쁜 세그 1개가 폴백 전체를 죽이지 않게(subs.json과 대칭)
            if segs:
                return segs, "stt"
        except Exception as e:
            print("::warning::segments.json 파싱 실패:", e)
    return [], ""


def sanitize(t):
    # ASS 오버라이드 태그 주입 차단({}·\) + 제어문자 제거 · 구두점 정리(마침표·쉼표 꼬리 제거, ?·! 유지 = 쇼츠 표준)
    t = re.sub(r"[{}\\\r\n\t]", " ", str(t or ""))
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"[.,、。]+(\s|$)", r"\1", t).strip()
    return t


def ass_time(sec):
    cs = max(0, int(round(float(sec) * 100)))   # 센티초 반올림 후 재분해 = 59.996→'0:01:00.00' 캐리업(60.00 무효 표기 차단)
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    return "{}:{:02d}:{:05.2f}".format(h, m, rem / 100.0)


def star_spans(text):
    # *별표* 키워드 → (평문, [(시작,끝)…]) — 강조 구간 문자 인덱스
    plain, spans, i = [], [], 0
    for part in re.split(r"(\*[^*\n]{1,24}\*)", text):
        if len(part) >= 3 and part.startswith("*") and part.endswith("*"):
            w = part[1:-1]
            spans.append((i, i + len(w))); plain.append(w); i += len(w)
        else:
            plain.append(part); i += len(part)
    return "".join(plain), spans


def text_w(s):
    # 표시 폭(전각 단위) — CJK 전각 1.0 · 공백 0.5 · 라틴/숫자 0.55(실측 근사)
    return sum(1.0 if ord(c) >= 0x1100 else (0.5 if c == " " else 0.55) for c in s)


def chunk_lines(words, budget):
    # 한글 자동 줄바꿈 없음(실측) → 단어 경계 수동 청킹(실폭 기준). 반환 = [[단어idx…], …]
    lines, cur, cur_w = [], [], 0.0
    for i, w in enumerate(words):
        add = text_w(w) + (0.5 if cur else 0.0)
        if cur and cur_w + add > budget:
            lines.append(cur); cur, cur_w = [i], text_w(w)
        else:
            cur.append(i); cur_w += add
    if cur:
        lines.append(cur)
    return lines


def size_frac(opts):
    # 크기 = 연속 높이비(0.035 등 · 운영자 260707)가 1급 — 구 s/m/l 문자열은 등가 소수로 하위호환
    s = opts.get("size")
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        try:
            v = float(s)
            if 0.02 <= v <= 0.2:
                return v
        except Exception:
            pass
    return {"s": 0.032, "m": 0.038, "l": 0.045}.get(s or "l", 0.045)


def coef(opts, key, dflt, lo, hi):
    # 연속 계수 축(outline·pad) 안전 파서 — 숫자 아님·NaN·범위 밖 = 기본값/클램프
    try:
        v = float(opts.get(key, dflt))
    except Exception:
        return dflt
    if v != v:
        return dflt
    return max(lo, min(hi, v))


def prep_line(text, seg_dur, keyword, fs, avail_px):
    # 한 조각 공용 준비(카라오케/일반 build_line·팝 build_pop_frames 공유): 새니타이즈·키워드 스팬·어절·청킹·축소·어절별 cs
    plain, spans = star_spans(sanitize(text))
    if not keyword:
        spans = []
    words = [w for w in plain.split(" ") if w]
    if not words:
        return None
    # 줄폭 예산(전각 단위) — 2줄 초과분은 조각 한정 인라인 축소(하한 0.62배 · 그래도 넘치면 3줄+ 허용)
    eff_fs = fs
    budget = avail_px / eff_fs
    total_w = text_w(plain)
    if total_w > 2 * budget:
        scale = max(0.62, (2 * budget) / total_w)
        eff_fs = max(16, int(fs * scale))
        budget = avail_px / eff_fs
    # 단어별 문자 스팬(강조 판정) — plain 상의 위치
    pos, bounds = 0, []
    for w in words:
        st = plain.find(w, pos); st = pos if st < 0 else st
        bounds.append((st, st + len(w))); pos = st + len(w)
    total = max(1, sum(len(w) for w in words))
    cs_total = max(10, int(seg_dur * 100))
    used, cs_list = 0, []
    for k, w in enumerate(words):
        cs = max(1, cs_total - used) if k == len(words) - 1 else max(1, int(round(cs_total * len(w) / total)))   # 마지막도 하한 1 = 음수 시간 차단
        used += cs
        cs_list.append(cs)
    hits = [any(a < en and st < b for a, b in spans) for (st, en) in bounds]
    lines = chunk_lines(words, budget)
    return words, hits, cs_list, lines, eff_fs


def _word(w, green, eff_fs, fs):
    # 어절 1개 렌더 — 그린 강조면 \1c + \r(축소 조각은 \fs 재적용 짝가드)
    if green:
        return "{\\1c" + GREEN_BGR + "}" + w + "{\\r" + ("" if eff_fs == fs else "}{\\fs" + str(eff_fs)) + "}"
    return w


def _assemble(rendered, lines, eff_fs, fs):
    body = "\\N".join(" ".join(rendered[i] for i in ln) for ln in lines)
    return ("{\\fs" + str(eff_fs) + "}" + body) if eff_fs != fs else body


def build_line(text, seg_dur, karaoke, keyword, fs, avail_px):
    # 한 조각 → (ASS 텍스트, 줄 수, 실폰트크기): 수동 \N + 카라오케 \kf + 키워드 \1c(콘텐츠 그린)
    #   줄 수·실크기 반환 = 중앙 불변 배치(이벤트별 MarginV 보정)의 블록 높이 산정용(260707)
    prep = prep_line(text, seg_dur, keyword, fs, avail_px)
    if not prep:
        return "", 0, fs
    words, hits, cs_list, lines, eff_fs = prep
    rendered = []
    for k, w in enumerate(words):
        seg = ("{\\kf" + str(cs_list[k]) + "}") if karaoke else ""
        rendered.append(seg + _word(w, hits[k], eff_fs, fs))
    return _assemble(rendered, lines, eff_fs, fs), len(lines), eff_fs


def build_pop_frames(text, seg_dur, keyword, fs, avail_px):
    # 팝 모드(운영자 260707 승인): 발화 중인 어절만 콘텐츠 그린 점등 — 어절 시간창마다 라인 전체를 다시 그린 이벤트 프레임 목록.
    #   창 경계 = \kf와 동일한 글자수 비례 분배(진짜 발화 싱크 = Whisper word 타임스탬프 후속) · 키워드(*별표*)는 전 창 상시 그린.
    #   레이아웃(청킹·축소·줄수)은 프레임 간 동일 → 박스·위치 픽셀 불변 = 창 전환 시 어절 색만 바뀜(깜빡임 0).
    prep = prep_line(text, seg_dur, keyword, fs, avail_px)
    if not prep:
        return [], 0, fs
    words, hits, cs_list, lines, eff_fs = prep
    frames, off = [], 0   # (시작 오프셋 cs, 길이 cs, ASS 텍스트)
    for cur in range(len(words)):
        rendered = [_word(w, k == cur or hits[k], eff_fs, fs) for k, w in enumerate(words)]
        frames.append((off, cs_list[cur], _assemble(rendered, lines, eff_fs, fs)))
        off += cs_list[cur]
    return frames, len(lines), eff_fs


def pos_pct(opts):
    # 위치 게이지 %(0=하단 100=상단 · 운영자 260707) — 구 3칩 문자열(bottom/middle/top)은 등가 %로 하위호환 매핑
    p = opts.get("pos")
    if isinstance(p, str):
        p = {"bottom": 24, "middle": 55, "top": 100}.get(p, 24)
    try:
        p = float(p)
    except Exception:
        p = 24.0
    return max(0.0, min(100.0, p))


def bg_pct(opts, style):
    # 배경 불투명도 %(0=없음 100=완전 불투명 · 운영자 260707) — 구 클라(bg 없음) = 박스만 종전 &H90(≈44%) 승계
    try:
        b = int(round(float(opts.get("bg"))))
    except Exception:
        b = 44 if style == "box" else 0
    return max(0, min(100, b))


def build_ass(segs, w, h, opts):
    size_f = size_frac(opts)
    fs = max(18, int(h * size_f))
    omul = coef(opts, "outline", 1.0, 0.25, 3.0)   # 외곽선 두께 배율(운영자 260707 ×0.5)
    pad = coef(opts, "pad", 0.10, 0.02, 0.5)       # 박스 패딩 계수 fs×pad(운영자 260707 ×0.16 · 구 box 0.10 승계 기본)
    # 위치 = 하단 앵커(align 2) 고정 + MarginV 연속값 — 게이지가 전 높이를 선형 커버(구 중앙/상단 앵커 분기 폐지)
    #   0% = 바닥 2% · 24% ≈ 구 하단 세이프존 22%(실측 420@1920) · 100% = 84% 명목 상한
    p = pos_pct(opts)
    align = 2
    lang = opts.get("lang") or "auto"
    margin_v = int(h * (0.02 + 0.0082 * p))
    # 상단 클립 캡(평의회 260707) — 하단 앵커는 위로 쌓여 libass가 프레임 밖 윗줄을 클립(밀어내기 없음).
    #   fs 기반 줄예산으로 상한: 평문 = 2줄(축소 포함)+패딩 3.1fs · dual = +원문(0.62fs) 2줄 4.9fs.
    #   84% 명목 상한이 fs 하한(max 18)·dual 추가 줄에서 깨지는 케이스(240p·원문 2줄)를 픽셀 기준으로 봉합.
    #   (260707부터 = 스타일 폴백 안전값 — 실제 상한은 아래 이벤트별 블록 실측 캡이 정밀 처리)
    margin_v = min(margin_v, max(0, h - int(fs * (4.9 if lang == "dual" else 3.1))))
    margin_lr = int(w * 0.074)
    style = opts.get("style") or "bold"
    bg = bg_pct(opts, style)
    back = "&H{:02X}000000".format(255 - int(round(bg * 2.55)))   # ASS 알파 = 00 불투명·FF 투명 · 44% → 0x8F ≈ 구 &H90(스타일 라인 = & 접미 없음)
    if bg > 0:               # 배경 게이지 ON = 줄 단위 박스(BorderStyle 4 · 3은 다줄 겹침 = 금지) — 전 모양 수렴(260707)
        # 패딩 = Outline값(구 box 전용 oc==back 패딩 겸용 메서드를 전 모양으로 승격 · pad 계수 = 운영자 선택 ×0.16).
        # 글리프 외곽선색도 back 동일 = 박스 위 이중 테두리 0(검정 박스 위 검정 스트로크 = 어차피 비가시 · 모양 분기는 bg=0에서만 의미).
        border_style, outline, shadow, oc = 4, max(2, int(fs * pad)), 0, back
    else:                    # 배경 0% — bold/clean = 종전 그대로(omul 배율만) · box = 얇은 외곽선 폴백(흰 글자 보호)
        back = "&H90000000"  # BorderStyle 1의 BackColour = 그림자색(bold shadow=1) — 게이지와 무관 종전값 유지
        if style == "clean" or style == "box":
            border_style, outline, shadow, oc = 1, max(1, int(fs * 0.032 * omul)), 0, "&H00000000"
        else:                # bold(기본) = 흰 글자+검정 외곽선+그림자(쇼츠 정석)
            border_style, outline, shadow, oc = 1, max(1, int(fs * 0.064 * omul)), 1, "&H00000000"
    karaoke = opts.get("karaoke", True)
    pop = bool(opts.get("pop", False))   # 팝 = 발화 중 어절만 그린 점등(운영자 260707) — 카라오케와 상호배타(UI 동시 불가 · 동시 수신 시 팝 우선)
    if pop:
        karaoke = False
    keyword = opts.get("keyword", True)
    lang = opts.get("lang") or "auto"
    avail = max(200, w - 2 * margin_lr)   # 자막 가용 폭(px)
    head = "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: {}".format(w),
        "PlayResY: {}".format(h),
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: nomute,Noto Sans CJK KR,{fs},&H00FFFFFF,&H00B8C4BE,{oc},{back},1,0,0,0,100,100,0,0,"
        "{bs},{ol},{sh},{al},{ml},{mr},{mv},1".format(
            fs=fs, oc=oc, back=back, bs=border_style, ol=outline, sh=shadow, al=align,
            ml=margin_lr, mr=margin_lr, mv=margin_v),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])
    lines = []
    small = max(14, int(fs * 0.62))
    ref_px = fs * LINE_F   # 중앙 불변 기준 = 본선(한글) 1줄 높이 — 게이지가 가리키는 배치는 1줄 기준으로 고정(운영자 캡처 보존)
    floor_v = max(1, int(h * 0.01))   # ASS Dialogue MarginV=0은 '스타일값 사용' 폴백이라 1 이상 강제
    for sg in segs:
        s, e = float(sg["s"]), float(sg["e"])
        if e - s < 0.05:
            e = s + 0.05
        ko = sg.get("ko") or ""
        src = sanitize(sg.get("src") or "")
        frames = None
        if pop and ko:
            frames, n_main, m_fs = build_pop_frames(ko, e - s, keyword, fs, avail)
            main = frames[0][2] if frames else ""
        else:
            main, n_main, m_fs = build_line(ko, e - s, karaoke, keyword, fs, avail) if ko else ("", 0, fs)
        if not main and src:
            main, n_main, m_fs = build_line(src, e - s, karaoke, False, fs, avail)
            src = ""
            frames = None
        if not main:
            continue
        src_pre = ""
        block_px = n_main * m_fs * LINE_F
        if lang == "dual" and src and ko:
            sw = src.split(" ")
            src_chunks = chunk_lines(sw, avail / small)
            src_txt = "\\N".join(" ".join(sw[i] for i in ln) for ln in src_chunks)
            src_pre = "{\\fs" + str(small) + "}" + src_txt + "{\\r}\\N"   # 원문(작게) 위 · 한글 아래 — 팝 프레임에도 매 창 동일 부착
            block_px += len(src_chunks) * small * LINE_F
        # 중앙 불변 배치(운영자 260707 "1줄/2줄 중앙점 동일선"): 하단 앵커는 위로만 자라 줄이 늘면 블록 중심이 떠오름 →
        #   초과 높이의 절반만큼 MarginV를 내려 블록 세로중심 고정(1줄 = 보정 0 = 종전·캡처 그대로). 패딩은 전 이벤트 동일이라 상쇄.
        mv_e = margin_v - int(round((block_px - ref_px) / 2))
        mv_e = min(mv_e, max(floor_v, h - int(block_px) - floor_v))   # 상단 캡 = 이벤트 블록 실측(전역 줄예산 추정보다 정밀)
        mv_e = max(floor_v, mv_e)
        if frames:   # 팝 = 어절 창마다 이벤트(레이아웃 동일·MarginV 동일 = 색만 이동)
            for fi, (off, dur, ftxt) in enumerate(frames):
                fst = s + off / 100.0
                if fst >= e - 0.004:
                    break   # 초단컷(0.05s대) 보호 — cs 하한 분배가 실구간을 넘치면 잔여 창 스킵
                fe = e if fi == len(frames) - 1 else min(e, s + (off + dur) / 100.0)
                lines.append("Dialogue: 0,{},{},nomute,,0,0,{},,{}".format(ass_time(fst), ass_time(fe), mv_e, src_pre + ftxt))
        else:
            lines.append("Dialogue: 0,{},{},nomute,,0,0,{},,{}".format(ass_time(s), ass_time(e), mv_e, src_pre + main))
    return head + "\n" + "\n".join(lines) + "\n"


def run(vid_id, video, outdir):
    try:
        opts = json.loads(os.environ.get("OPTS") or "{}")
    except Exception:
        opts = {}
    if not video or not os.path.isfile(video):
        out_json(outdir, {"skip": "영상 확보 실패(음성 입력 또는 다운로드 막힘) — 자막 텍스트만"}); return 0
    lang = opts.get("lang") or "auto"
    try:
        w, h, dur = probe(video)
    except Exception as e:
        out_json(outdir, {"error": "영상 정보 읽기 실패: {}".format(str(e)[:120])}); return 0
    if not w or not h:
        out_json(outdir, {"error": "영상 스트림 없음(오디오 파일) — 자막 텍스트만"}); return 0
    if dur > MAX_DUR:
        out_json(outdir, {"error": "영상이 {}분 — 10분 이하만 합성(릴스/쇼츠용)".format(int(dur // 60))}); return 0
    segs, src_kind = load_segs(outdir)
    if not segs:
        out_json(outdir, {"error": "자막 타이밍 데이터 없음(subs.json·segments.json) — 자막 텍스트만"}); return 0
    if lang == "src":   # 원문 그대로 모드 = src(없으면 ko) 단일
        segs = [{"s": s["s"], "e": s["e"], "ko": s.get("src") or s.get("ko") or "", "src": ""} for s in segs]
    # 다운스케일 캡(비용 보호·업스케일 없음) — 목표 치수를 먼저 확정해 PlayRes와 일치시킴(왜곡 0)
    tw, th = w, h
    if w > 1080:
        tw = 1080
        th = int(round(h * tw / w / 2) * 2)
    ass = build_ass(segs, tw, th, opts)
    ass_path = "/tmp/ly_subs.ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)
    out_mp4 = "/tmp/ly_subbed.mp4"
    vf = ("scale={}:{},".format(tw, th) if (tw, th) != (w, h) else "") + "ass={}".format(ass_path)
    cmd = ["ffmpeg", "-y", "-i", video, "-vf", vf,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_mp4]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)   # 15분 백스톱 — 잡 하드킬(45분) 전에 우아하게 실패 기록(평의회)
        if r.returncode != 0 or not os.path.isfile(out_mp4) or os.path.getsize(out_mp4) < 1024:
            tail = (r.stderr or "")[-400:]
            print("::warning::ffmpeg 번인 실패:", tail)
            out_json(outdir, {"error": "영상 합성 실패 — 자막 텍스트는 정상", "detail": tail[-160:]}); return 0
    except subprocess.TimeoutExpired:
        out_json(outdir, {"error": "영상 합성 시간 초과(15분) — 자막 텍스트는 정상"}); return 0
    data = open(out_mp4, "rb").read()
    note = "받아쓴 자막(원문)으로 합성" if src_kind == "stt" else ""
    # 원본 보관(재합성용 · ≤60MB) — 의역 재사용 '다시 입히기'의 소스. reburn 실행은 기존 src 승계(재업로드 0).
    src_url = ""
    try:
        prev = json.load(open(os.path.join(outdir, "video.json"), encoding="utf-8")) if os.path.isfile(os.path.join(outdir, "video.json")) else {}
        src_url = prev.get("src") or ""
    except Exception:
        src_url = ""
    if tg.R2_ON and not src_url and os.environ.get("REBURN") != "1":
        try:
            if os.path.getsize(video) <= 60 * 1024 * 1024:
                ext = (os.path.splitext(video)[1] or ".mp4").lower()
                ctype = {"webm": "video/webm", "mov": "video/quicktime", "mkv": "video/x-matroska"}.get(ext.lstrip("."), "video/mp4")
                src_url = tg.r2_upload(open(video, "rb").read(), "ly_out/{}/src{}".format(vid_id, ext), ctype) or ""
        except Exception as e:
            print("::warning::원본 보관 실패(재합성 버튼만 비활성·무해):", e)
    bust = re.sub(r"[^0-9]", "", kst_now())[:14]   # 같은 R2 키 덮어쓰기 = 브라우저 캐시 잔존 → ?v= 버스트(재합성 반영 보장)
    if tg.R2_ON:
        url = tg.r2_upload(data, "ly_out/{}/subbed.mp4".format(vid_id), "video/mp4")
        if url:
            out_json(outdir, {"url": url + "?v=" + bust, "src": src_url, "bytes": len(data), "dur": round(dur, 1), "note": note}); return 0
        print("::warning::R2 업로드 실패 — git 폴백 시도")
    if len(data) <= GIT_FALLBACK_MAX:
        with open(os.path.join(outdir, "subbed.mp4"), "wb") as f:
            f.write(data)
        out_json(outdir, {"url": "ly_out/{}/subbed.mp4?v={}".format(vid_id, bust), "src": src_url, "bytes": len(data), "dur": round(dur, 1),
                          "note": (note + " · " if note else "") + "git 저장(R2 미설정)"}); return 0   # src 승계 = 폴백서도 재합성 버튼 유지(평의회)
    out_json(outdir, {"error": "R2 미설정 + 파일 {}MB(30MB 초과) — 저장 불가".format(len(data) // 1048576)})
    return 0


def main():
    if len(sys.argv) < 3:
        print("usage: ly_burn.py <id> <video>"); return 0
    vid_id, video = sys.argv[1], sys.argv[2]
    if not re.match(r"^[A-Za-z0-9_-]{1,64}$", vid_id):   # 경로 탈출 차단(수동 dispatch 임의 id 방어 — 라이브 id는 ly.js 서버 생성)
        print("::warning::잘못된 id 형식 — 번인 스킵:", vid_id[:40]); return 0
    outdir = os.path.join("viewer", "ly_out", vid_id)
    os.makedirs(outdir, exist_ok=True)
    try:
        return run(vid_id, video, outdir)
    except Exception as e:   # 어떤 예외도 video.json에 사유 기록 = 뷰어 8분 헛폴 차단(전면 fail-soft)
        try:
            out_json(outdir, {"error": "영상 합성 실패 — 자막 텍스트는 정상 ({})".format(str(e)[:120])})
        except Exception:
            pass
        print("::warning::ly_burn 예외:", e)
        return 0


if __name__ == "__main__":
    sys.exit(main())
