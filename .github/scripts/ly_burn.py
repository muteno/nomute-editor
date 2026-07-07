#!/usr/bin/env python3
# 영상 자막 번인(자동 합성) — 자막 텍스트를 ASS(libass)로 영상에 입혀 R2 업로드 → viewer/ly_out/<id>/video.json.
#   사용: ly_burn.py <id> <video_path>   (ly-make.yml 번인 스텝 전용 · ffmpeg+fonts-noto-cjk는 runner-setup가 설치)
#   env: OPTS = 뷰어 버튼 설정 JSON(스타일·위치·크기·카라오케·키워드) · R2 5종 = thumb_gen 재사용(카드·썸네일·/k 동일 파이프)
# 자막 소스 우선순위: subs.json(의역+타이밍 · lymake.sh가 claude 출력 꼬리 JSON 분리) → segments.json(받아쓴 원문 폴백).
# 카라오케 타이밍: segments.json(ly_stt.py word 타임스탬프)의 실제 발화 곡선에 자막 어절을 태워 \kf 산출(노래방식 정확 동기) —
#   word 없으면(SRT·텍스트 입력·옛 STT) 글자수 비례 폴백 = 종전 동작(회귀 0). subs↔STT 세그 경계 불일치는 시간 겹침으로 흡수.
# 실패 = fail-soft: video.json에 사유 기록 후 rc 0 (자막 텍스트 산출은 이미 정상 — 번인이 잡을 죽이면 안 됨).
# ASS 레시피 = 분신술 R1 기술 실측 확정본(260707): BorderStyle=3 금지(다줄 겹침) → 통박스는 4 + Outline==Back색 ·
#   한글 자동 줄바꿈 없음 → WrapStyle 2 + 수동 \N(줄당 폭/폰트 비례) · MarginV = 하단 22%(릴스 UI 세이프존) ·
#   폰트 = "Noto Sans CJK KR"(fontconfig 자동 탐색 = fontsdir 불요) · 회전 메타 = autorotate 기본 유지 + PlayRes 스왑.
# 키워드 강조색 = 콘텐츠 브랜드 형광그린 #0FFD02(릴스 오버레이 GREEN 계승 · UI 팔레트와 별개 축 = §핵심명령 3-b-1).
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # r2_upload · R2_ON 재사용(모듈 import = main 미실행 · k_refgen 선례)

GREEN_BGR = "&H02FD0F&"          # #0FFD02 → ASS BGR(콘텐츠 그린)
GIT_FALLBACK_MAX = 30 * 1024 * 1024   # R2 미설정 시 git 커밋 상한(레포 비대 방지)
MAX_DUR = 600                    # 릴스/쇼츠 도구 — 10분 초과 영상은 번인 거절(러너 시간 보호)


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


def load_stt_words(outdir):
    # segments.json(ly_stt.py 사이드카)의 word 타임스탬프 평탄화 = 카라오케 실제 발화 곡선 소스.
    #   없거나(SRT·텍스트 입력) word 미포함(옛 word_timestamps=False STT) = 빈 리스트 → 글자수 비례 폴백(회귀 0).
    p = os.path.join(outdir, "segments.json")
    if not os.path.isfile(p):
        return []
    try:
        j = json.load(open(p, encoding="utf-8"))
        words = []
        for sg in (j.get("segs") or []):
            for w in (sg.get("w") or []):
                ws, we = w.get("s"), w.get("e")
                if isinstance(ws, (int, float)) and isinstance(we, (int, float)) and math.isfinite(ws) and math.isfinite(we) and str(w.get("t") or "").strip():
                    words.append({"t": str(w["t"]), "s": float(ws), "e": float(we)})   # isfinite = NaN/Inf 타임스탬프 배제(json.loads가 통과시키는 리터럴 NaN이 곡선 int() 크래시 유발 차단·평의회3)
        words.sort(key=lambda x: (x["s"], x["e"]))
        return words
    except Exception as e:
        print("::warning::segments.json word 로드 실패(카라오케 글자수 비례 폴백):", e)
        return []


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


def _interp_cs(ctrl, p):
    # ctrl = [(진행률x, 센티초y)…] x 오름차순 · p∈[0,1] → 구간 선형보간 y
    if p <= ctrl[0][0]:
        return ctrl[0][1]
    for i in range(1, len(ctrl)):
        x0, y0 = ctrl[i - 1]
        x1, y1 = ctrl[i]
        if p <= x1:
            return y1 if x1 <= x0 else y0 + (y1 - y0) * (p - x0) / (x1 - x0)
    return ctrl[-1][1]


def prop_cs(words, cs_total):
    # 글자수 비례 분배(word 타임스탬프 없을 때 폴백 = 종전 카라오케 동작 그대로)
    total = max(1, sum(len(w) for w in words))
    out, used = [], 0
    for k, w in enumerate(words):
        cs = max(1, cs_total - used) if k == len(words) - 1 else max(1, int(round(cs_total * len(w) / total)))   # 마지막도 하한 1 = 음수 \kf 차단
        used += cs
        out.append(cs)
    return out


def karaoke_cs(words, seg_s, seg_dur, stt_words):
    # (리드인 센티초, 어절별 \kf 센티초 리스트) — STT word 타임스탬프가 있으면 실제 발화 곡선에 어절을 태우고(노래방식 동기),
    #   없으면 글자수 비례(폴백). 리드인+합 = cs_total(세그 표시길이 정합).
    #   한국어 원본(어절≈word 1:1) = 실발화에 정확 수렴 · 의역(외국어 어순반전)은 좌→우 카라오케 본질 한계라 균등과 대등
    #   (자막 표시 s/e는 claude 정렬 유지 = 최악도 블록 내 스윕 미관). word 없을 때 폴백 = 종전 비트 동일(회귀 0).
    n = len(words)
    cs_total = max(10, int(seg_dur * 100))   # int(버림) = 종전 build_line과 동일(폴백 비트 일치 · round면 부동소수 경계서 1cs 벌어짐)
    if not stt_words or n == 0:
        return 0, prop_cs(words, cs_total)
    chars = [max(1, len(w["t"].replace(" ", ""))) for w in stt_words]
    tot = sum(chars)
    # 리드인 = 자막 표시 시작 ~ 첫 발화까지의 침묵(카라오케 채움을 실제 발화에 정렬 · 0.12초 미만은 흡수 = 잡음 방지)
    lead = int(round(max(0.0, (float(stt_words[0]["s"]) - seg_s) * 100.0)))
    lead = min(lead, cs_total - n) if lead >= 12 else 0   # 어절당 최소 1cs 확보·과도 리드인 상한
    if lead < 0:
        lead = 0
    # STT 발화 곡선 = (누적 글자비율, 세그 상대 센티초) 제어점 — 시작=리드인·끝=세그끝·세그 클램프·시간 단조증가
    ctrl, acc, prev = [(0.0, float(lead))], 0, float(lead)
    for w, ch in zip(stt_words, chars):
        acc += ch
        rel = (min(seg_s + seg_dur, max(seg_s, float(w["e"]))) - seg_s) * 100.0
        rel = max(prev, min(float(cs_total), rel))
        ctrl.append((acc / tot, rel))
        prev = rel
    ctrl[-1] = (1.0, float(cs_total))   # 끝 앵커 = 세그 끝(마지막 어절이 세그 끝까지 채워지게 · 마지막 word가 못 미쳐도 보정)
    # 자막 어절 → 누적 글자비율 → 곡선 시간 → 어절별 fill(곡선 절대위치로 t_prev 추적 = 하한 걸린 어절이 뒤 타이밍 안 밀게)
    kc = [max(1, len(w)) for w in words]
    ktot = sum(kc)
    out, kacc, t_prev = [], 0, float(lead)
    for i, ch in enumerate(kc):
        kacc += ch
        t = _interp_cs(ctrl, 1.0 if i == n - 1 else kacc / ktot)
        out.append(max(1, int(round(t - t_prev))))
        t_prev = t
    diff = cs_total - lead - sum(out)   # 반올림·하한 보정 → 리드인+합 = cs_total 정확히
    if diff >= 0:
        out[-1] += diff                 # 부족분 = 마지막 어절이 흡수
    else:
        i = len(out) - 1                # 초과분 = 뒤 어절부터 1까지 깎음(하한 유지 · 어절수>cs_total 극단서도 음수 \kf 0)
        while diff < 0 and i >= 0:
            take = min(-diff, out[i] - 1)
            out[i] -= take; diff += take; i -= 1
    out[-1] = max(1, out[-1])
    return lead, out


def build_line(text, seg_s, seg_dur, karaoke, keyword, fs, avail_px, stt_words):
    # 한 조각 → ASS 텍스트: 수동 \N(최대 2줄 · 넘치면 그 조각만 \fs 자동 축소) + 카라오케 \kf + 키워드 \1c(콘텐츠 그린)
    plain, spans = star_spans(sanitize(text))
    if not keyword:
        spans = []
    words = [w for w in plain.split(" ") if w]
    if not words:
        return ""
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
    lead, cs_list = karaoke_cs(words, seg_s, seg_dur, stt_words) if karaoke else (0, None)
    rendered = []
    for k, w in enumerate(words):
        st, en = bounds[k]
        hit = any(a < en and st < b for a, b in spans)
        seg = ""
        if karaoke:
            if k == 0 and lead > 0:
                seg += "{\\k" + str(lead) + "}"   # 리드인 = 첫 발화 전 대기(카라오케 채움 시작을 실제 발화에 정렬)
            seg += "{\\kf" + str(cs_list[k]) + "}"
        if hit:
            seg += "{\\1c" + GREEN_BGR + "}" + w + "{\\r" + ("" if eff_fs == fs else "}{\\fs" + str(eff_fs)) + "}"
        else:
            seg += w
        rendered.append(seg)
    lines = chunk_lines(words, budget)
    body = "\\N".join(" ".join(rendered[i] for i in ln) for ln in lines)
    return ("{\\fs" + str(eff_fs) + "}" + body) if eff_fs != fs else body


def build_ass(segs, w, h, opts, stt_words):
    size_f = {"s": 0.032, "m": 0.038, "l": 0.045}.get(opts.get("size") or "l", 0.045)
    fs = max(18, int(h * size_f))
    pos = opts.get("pos") or "bottom"
    align = {"bottom": 2, "middle": 5, "top": 8}.get(pos, 2)
    margin_v = int(h * (0.22 if pos == "bottom" else 0.06))   # 하단 = 릴스/틱톡 UI 세이프존 22%(실측 420@1920)
    margin_lr = int(w * 0.074)
    style = opts.get("style") or "bold"
    if style == "box":       # 통박스 = BorderStyle 4 + Outline색==Back색(패딩 겸용 · 3은 다줄 겹침 = 금지)
        border_style, outline, shadow, oc, back = 4, max(4, int(fs * 0.10)), 0, "&H90000000", "&H90000000"
    elif style == "clean":
        border_style, outline, shadow, oc, back = 1, max(1, int(fs * 0.032)), 0, "&H00000000", "&H90000000"
    else:                    # bold(기본) = 흰 글자+검정 외곽선+그림자(쇼츠 정석)
        border_style, outline, shadow, oc, back = 1, max(2, int(fs * 0.064)), 1, "&H00000000", "&H90000000"
    karaoke = opts.get("karaoke", True)
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
    for sg in segs:
        s, e = float(sg["s"]), float(sg["e"])
        if e - s < 0.05:
            e = s + 0.05
        ko = sg.get("ko") or ""
        src = sanitize(sg.get("src") or "")
        sw = [x for x in stt_words if s <= (x["s"] + x["e"]) / 2 < e] if (karaoke and stt_words) else []   # 이 세그의 STT word = 중심점 기준(옆 세그 word 오염 차단·시간겹침보다 net-우수 실측). 한계 = claude 세밀분할 경계에 걸친 word는 소수 세그서 STT 앵커 잃음(≤0.6s 미관·문자열-인지 배정은 후속 후보)
        main = build_line(ko, s, e - s, karaoke, keyword, fs, avail, sw) if ko else ""
        if not main and src:
            main = build_line(src, s, e - s, karaoke, False, fs, avail, sw)
            src = ""
        if not main:
            continue
        txt = main
        if lang == "dual" and src and ko:
            sw = src.split(" ")
            src_chunks = chunk_lines(sw, avail / small)
            src_txt = "\\N".join(" ".join(sw[i] for i in ln) for ln in src_chunks)
            txt = "{\\fs" + str(small) + "}" + src_txt + "{\\r}\\N" + main   # 원문(작게) 위 · 한글 아래
        lines.append("Dialogue: 0,{},{},nomute,,0,0,0,,{}".format(ass_time(s), ass_time(e), txt))
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
    stt_words = load_stt_words(outdir) if opts.get("karaoke", True) else []   # 카라오케 실제 발화 곡선(word 타임스탬프) — 없으면 글자수 비례 폴백
    ass = build_ass(segs, tw, th, opts, stt_words)
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
