#!/usr/bin/env python3
# 영상 자막 번인(자동 합성) + 편집기 컴포지터 — 자막 ASS 번인·무음 컷·배경음 제거에 더해 편집기(edit) 축
#   {vid_ar/vid_fit(크롭·검정 여백·블러 여백[blur = 원본 블러 확대 배경 패드 · 260711])·vid_res(src=원본 4K 캡 3840·1080·720 — 결측 1920)·vid_fps(60i 보간·다운)·vid_t0/t1(트림 — 자막·컷과 동시 = 조각·word·스팬 동행 리맵 260711)·aud_norm(음량 통일)}을
#   한 ffmpeg 파이프로 합성해 R2 업로드 → viewer/ly_out/<id>/video.json. 편집기 축 전부 결측 = 종전 ly 경로 그대로(회귀 0 · 260710).
#   4K(운영자 260711): 4K급 = 캔버스 픽셀 > FHD 2배(긴 변 판별은 세로 1080×2340을 오분류 = 평의회4 교체) → EDIT_4K_MAX_SEC(180초) 선게이트 + 60i 보간 제외.
#   enc 백스톱 = 픽셀 비례(FHD 900s → 4K 2400s 캡) · 다운스케일은 note로 표면화(침묵 금지 — FHD 자막 경로는 종전 무note = 표면 회귀 0).
#   사용: ly_burn.py <id> <video_path>   (ly-make.yml 번인 스텝 + edit-make.yml 컴포즈 스텝 · ffmpeg+fonts-noto-cjk는 runner-setup가 설치)
#   env: OPTS = 뷰어 버튼 설정 JSON(스타일·위치·크기·카라오케·키워드) · R2 5종 = thumb_gen 재사용(카드·썸네일·/k 동일 파이프)
# 자막 소스 우선순위: subs.json(의역+타이밍 · lymake.sh가 claude 출력 꼬리 JSON 분리) → segments.json(받아쓴 원문 폴백).
# 실패 = fail-soft: video.json에 사유 기록 후 rc 0 (자막 텍스트 산출은 이미 정상 — 번인이 잡을 죽이면 안 됨).
# ASS 레시피 = 분신술 R1 기술 실측 확정본(260707): BorderStyle=3 금지(다줄 겹침) → 통박스는 4 + Outline==Back색 ·
#   한글 자동 줄바꿈 없음 → WrapStyle 2 + 수동 \N(줄당 폭/폰트 비례) ·
#   위치 = pos 게이지 %(0=하단 100=상단 · 구 bottom/middle/top 하위호환) → align 2 고정 + MarginV 연속(24% ≈ 구 하단 세이프존 22%) ·
#   배경 = bg 게이지 %(BackColour 알파 · 0=박스 없음 · 구 클라 박스 = 44 승계) ·
#   폰트 = opts.font 닫힌 집합{gothic(기본)=Noto Sans CJK KR·serif=Noto Serif CJK KR·nanum=NanumGothic·pen=Nanum Pen Script}(fontconfig 자동 탐색 = fontsdir 불요 · 미설치 = 기본 폴백+note) ·
#   음영 색 = opts.oc 닫힌 집합(OC_BGR · 외곽선/그림자/줄박스 단일 축 · 결측 = 검정 종전) · 회전 메타 = autorotate 기본 유지 + PlayRes 스왑.
# 연속 축 3종(운영자 260707 플레이그라운드 선택값 배선): size = 높이비 소수(0.035 등 · 구 s/m/l 문자열 하위호환) ·
#   outline = 외곽선 두께 배율(×0.5 등 · bg=0 글리프 스트로크에만 의미) · pad = 박스 패딩 계수(fs×pad · bg>0 줄박스 패딩).
#   + 중앙 불변 배치: 게이지 = 1줄 기준점 고정 · 줄이 늘면 초과분 절반씩 내려 블록 세로중심 유지(이벤트별 MarginV).
# 팝 모드(opts.pop · 운영자 260707 배치 승인): 카라오케 대신 발화 중 어절만 콘텐츠 그린 점등 — 어절 창별 이벤트 분할(build_pop_frames) ·
#   카라오케와 상호배타(동시 수신 = 팝 우선).
# 실싱크(운영자 260708 "어절 강조점 싱크"): 카라오케·팝의 어절 타이밍 = STT word 타임스탬프(ly_stt.py segments.json `w`)의
#   발화 진행 곡선에 자막 어절을 글자 진행률로 투영 = 침묵·속도변화 반영(구 글자수 균등 분배 대체). word 없으면 글자수 비례 폴백(회귀 0).
#   원문 모드(자막≈STT)=거의 정확 · 의역 모드=진행률 근사(균등보다 우수). segments.json word를 시간 겹침으로 subs 세그에 주입.
# 키워드 강조색 = 콘텐츠 브랜드 형광그린 #0FFD02(릴스 오버레이 GREEN 계승 · UI 팔레트와 별개 축 = §핵심명령 3-b-1).
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shared"))
import audio_norm   # 음량 통일 SSOT(−14LUFS 2패스·L/R 모노합 — 자체 loudnorm 재구현 금지 · 편집기 aud_norm)
import thumb_gen as tg   # r2_upload · R2_ON 재사용(모듈 import = main 미실행 · k_refgen 선례)

GREEN_BGR = "&H02FD0F&"          # #0FFD02 → ASS BGR(콘텐츠 그린)
KW = {"c": GREEN_BGR}            # 키워드 강조색 슬롯(운영자 260711 kwc — build_ass가 opts로 갱신 · 기본 그린 = 종전 바이트 동일)
# 자막 음영(외곽선·그림자·박스) 색 — 닫힌 집합(260711 운영자 "음영 색상 조정"). BGR 6자리(#RRGGBB 역순).
#   그린 #0FFD02(콘텐츠 그린)·핑크 #FF5EC8·블루 #3a6ddb·레몬 #FFE13D·레드 #e23b2a = 전부 콘텐츠 산출물 색 상수(§핵심명령 3-b-1 · UI 팔레트 비대상).
#   결측/black = 종전 검정과 바이트 동일(회귀 0). bg>0 줄박스 색·bg=0 글리프 외곽선·bold 그림자색 전부 이 한 색을 따른다(= '주변부 음영' 단일 축).
OC_BGR = {"black": "000000", "white": "FFFFFF", "green": "02FD0F", "pink": "C85EFF",
          "blue": "DB6D3A", "yellow": "3DE1FF", "red": "2A3BE2"}
# 자막 폰트 — 닫힌 집합(260711 운영자 "폰트 조정"). 러너 설치 = edit-make·ly-make 자막 경로 apt{fonts-noto-cjk + fonts-nanum + fonts-nanum-extra}.
#   패밀리명 = fc-scan 실측(NanumPen.ttf = "Nanum Pen Script" — 구글 웹폰트와 동명이라 뷰어 미리보기 정합). 미설치 = run()이 기본 폴백+note.
FONT_FAMILY = {"gothic": "Noto Sans CJK KR", "serif": "Noto Serif CJK KR",
               "nanum": "NanumGothic", "pen": "Nanum Pen Script"}
GIT_FALLBACK_MAX = 30 * 1024 * 1024   # R2 미설정 시 git 커밋 상한(레포 비대 방지)
MAX_DUR = 600                    # 릴스/쇼츠 도구 — 10분 초과 영상은 번인 거절(러너 시간 보호)
CUT_PAD = 0.30                   # 무음 컷: 발화 구간 앞뒤 보존 여유(초) — 어두·어미 잘림 방지
CUT_MIN_REMOVE = 0.40            # 무음 컷: 이만큼도 안 줄어드는 갭은 붙여둠(미세컷 = 튐만 유발·자연스러운 호흡 보존)
# 컷 강도(운영자 260708 · 분신술 10인): 3단 칩 살짝/기본/많이 → (pad, min_remove, max_ratio) 테이블.
#   기본(std) = 위 상수 자체 + 천장 0.35 = 현행 파라미터 회귀 0(단 35% 천장·note %표기는 아래 참조 = 전 cut 경로 신규).
#   ⚠️ 강도별 천장(평의회9 P1): 단일 35% 천장은 무음 많은 영상에서 hard를 std로 되돌려 "많이"를 무의미하게 만듦
#     → hard만 0.45까지 허용해 "많이"가 실제로 더 자르게(soft/std는 0.35 보수 유지). 운영자가 '많이' 명시 선택 시에만 공격적.
#   하한(pad≥0.05·min_remove≥0.20)은 극단 안전(평의회8) — 현 3단은 전부 하한 위라 *현재는 비활성*(미래 테이블/커스텀 방어선).
CUT_LEVELS = {"soft": (0.45, 0.70, 0.35), "std": (CUT_PAD, CUT_MIN_REMOVE, 0.35), "hard": (0.15, 0.25, 0.45)}
CUT_PAD_MIN, CUT_MIN_REMOVE_MIN = 0.05, 0.20   # 극단 클램프 하한(평의회8 · 현 3단엔 비활성)


def cut_params(opts):
    # cutlv 3단 → (pad, min_remove, max_ratio). 결측·미지 = 'std'(현행 상수 = 파라미터 회귀 0). size_frac/coef 문자열 폴백 패턴 계승.
    p, m, r = CUT_LEVELS.get(opts.get("cutlv"), (CUT_PAD, CUT_MIN_REMOVE, 0.35))
    return max(CUT_PAD_MIN, p), max(CUT_MIN_REMOVE_MIN, m), r
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


def _span(a, b):
    # 유한 수치 스팬만 통과(NaN/Infinity 명시 거부 = 방어심층 · 평의회5) — json.load 기본은 allow_nan=True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
            and math.isfinite(a) and math.isfinite(b) and float(b) > float(a):
        return (float(a), float(b))
    return None


def load_speech_spans(outdir, segs):
    # 무음 컷 기준 = STT 원천(segments.json = Whisper 발화 구간·vad_filter)이 정본 — 의역(subs.json)은
    # 군더더기 빼기 등으로 실제 발화가 자막에서 빠질 수 있어 그걸로 컷하면 진짜 말이 잘림. 없으면 자막 타이밍 폴백.
    # 어절(word) 타임스탬프 있으면 그걸 발화 스팬으로(세그 내부 긴 침묵까지 컷 대상 · 평의회10) —
    #   어절 사이 미세 갭은 cut_keeps 패딩+병합(제거량 0.4s 미만 유지 = 실갭 1.0s 미만 보존)이 흡수 = 과컷 없음.
    p = os.path.join(outdir, "segments.json")
    if os.path.isfile(p):
        try:
            j = json.load(open(p, encoding="utf-8"))
            spans = []
            for s in (j.get("segs") or []):
                words = [w for w in (s.get("w") or []) if _span(w.get("s"), w.get("e"))]
                if words:
                    spans.extend(_span(w.get("s"), w.get("e")) for w in words)
                else:
                    sp = _span(s.get("s"), s.get("e"))
                    if sp:
                        spans.append(sp)
            if spans:
                return spans, True    # True = segments.json 유래 = 원본(트림 전) 좌표
        except Exception as e:
            print("::warning::segments.json 파싱 실패 — 자막 타이밍으로 컷 계산 폴백:", e)
    # segs 폴백 = 호출 시점 segs 좌표(트림 리맵 후면 이미 트림 좌표) — 호출부가 재시프트하면 이중 시프트(검증9 봉합)
    return [sp for sp in (_span(s.get("s"), s.get("e")) for s in segs) if sp], False


def inject_words(segs, outdir):
    # STT word 타임스탬프(segments.json `w`)를 각 번인 세그에 시간 겹침으로 주입(subs 의역·segments 원문 공통 · 운영자 260708 실싱크).
    #   subs.json 세그엔 word 없음(claude 의역) → segments.json 원천 word를 [s,e] 겹침으로 매핑. 이미 w 있으면(segments 폴백) 유지.
    if any(sg.get("w") for sg in segs):
        return   # 이미 word 보유(segments.json 직접 폴백 경로) = 주입 불요
    p = os.path.join(outdir, "segments.json")
    all_w = []
    try:
        j = json.load(open(p, encoding="utf-8"))
        for sseg in (j.get("segs") or []):
            for w in (sseg.get("w") or []):
                if isinstance(w.get("s"), (int, float)) and isinstance(w.get("e"), (int, float)) \
                        and math.isfinite(w.get("s")) and math.isfinite(w.get("e")) and w["e"] > w["s"]:
                    all_w.append(w)
    except Exception as ex:
        print("::warning::segments.json word 로드 실패(실싱크 스킵 · 글자수 비례 폴백):", ex)
        return
    if not all_w:
        return
    all_w.sort(key=lambda w: w["s"])
    for sg in segs:
        s0, e0 = float(sg["s"]), float(sg["e"])
        sg["w"] = [w for w in all_w if w["e"] > s0 and w["s"] < e0]   # 세그 시간창에 걸치는 word(발화 진행 곡선 재료)


def cut_keeps(spans, dur, pad=CUT_PAD, min_remove=CUT_MIN_REMOVE):
    # 발화 구간 ± pad 확장 → 제거량 min_remove 미만 갭은 병합 → keep(살릴 구간) 목록.
    # 머리(첫 발화 전)·꼬리(마지막 발화 후) 무음도 동일 규칙으로 컷(제거량이 작으면 유지).
    keeps = []
    for a, b in sorted(spans):
        a = max(0.0, a - pad)
        b = min(dur, b + pad) if dur > 0 else b + pad
        if b <= a:
            continue
        if keeps and a - keeps[-1][1] < min_remove:
            keeps[-1][1] = max(keeps[-1][1], b)
        else:
            keeps.append([a, b])
    if keeps and keeps[0][0] < min_remove:
        keeps[0][0] = 0.0
    if keeps and dur > 0 and dur - keeps[-1][1] < min_remove:
        keeps[-1][1] = dur
    return [(a, b) for a, b in keeps if b - a > 0.01]


def cut_remap(keeps):
    # 원본 타임라인 → 컷 후 타임라인 사상(컷-자막 싱크의 핵심). 갭 안 시각 = 직전 keep 끝점으로 붕괴.
    table, acc = [], 0.0
    for a, b in keeps:
        table.append((a, b, acc))
        acc += b - a
    def f(t):
        t = float(t)
        for a, b, c in table:
            if t < a:
                return c
            if t <= b:
                return c + (t - a)
        return acc
    return f, acc


def subtract_spans(keeps, removes):
    # keep 목록에서 명시 제거 스팬(대본 삭제 컷 · 260711)을 차감 — 무음컷 keeps와 같은 좌표축(트림 후) 전제.
    #   패딩·병합 없음(삭제 = 운영자 명시 의도 = 조각 경계 그대로) · 0.05s 미만 슬리버 keep은 드롭(프레임 미만 튐 방지).
    out = [(float(a), float(b)) for a, b in keeps]
    for ra, rb in removes:
        nxt = []
        for a, b in out:
            if rb <= a or ra >= b:
                nxt.append((a, b))
                continue
            if ra > a:
                nxt.append((a, ra))
            if rb < b:
                nxt.append((rb, b))
        out = nxt
    return [(a, b) for a, b in out if b - a > 0.05]


def load_del_spans(outdir):
    # 대본 삭제 컷 스팬(운영자 260711 텍스트 컷) = subs.json 'del'(상세 편집기 삭제 조각·원본 시간축 [s,e] 쌍) →
    #   검증·정렬·근접 병합. 쓰는 쪽 = ly-make '편집 자막 반영'(ly.js del 검증 통과분) — 없으면 [](종전 경로 회귀 0).
    p = os.path.join(outdir, "subs.json")
    if not os.path.isfile(p):
        return []
    try:
        j = json.load(open(p, encoding="utf-8"))
    except Exception:
        return []
    raw = []
    for d in (j.get("del") or [])[:400]:
        if not isinstance(d, (list, tuple)) or len(d) != 2:
            continue
        sp = _span(d[0], d[1])
        if sp:
            raw.append(sp)
    raw.sort()
    merged = []
    for a, b in raw:
        if merged and a <= merged[-1][1] + 0.01:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def has_audio(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                            "stream=index", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=60)
        return bool((r.stdout or "").strip())
    except Exception:
        return True   # 판별 실패 = 오디오 있다고 가정 — 무음 파일 오판 시 컷 ffmpeg가 실패해도 평문 번인 폴백이 받음(소리 있는 영상의 오디오를 조용히 떨구는 반대 방향보다 안전 · 평의회6)


def strip_bgm(video):
    # 배경음 제거(운영자 260707) = Demucs 보컬 분리(htdemucs·로컬·키 불필요·과금 0) — 목소리 트랙만 남긴 wav 반환.
    # 실패/미설치/시간초과 = "" 반환(fail-soft: 원본 소리로 계속 = 컷과 동일 강등 문법). 설치 = ly-make.yml bgm 게이트 스텝.
    # 예산 = 추출 120s + 분리 600s(릴스/쇼츠 수 분 여유 · 장영상은 스킵될 수 있음 — note로 표면화 · 평의회9).
    try:
        r = subprocess.run([sys.executable, "-c", "import demucs.separate"],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:   # 미설치 선행 감지 = 추출 낭비 제거(평의회3) — 설치 실패 런은 여기서 즉시 강등
            print("::warning::배경음 제거 스킵 — demucs 미설치(설치 스텝 로그 확인)")
            return ""
        wav = "/tmp/ly_bgm_in.wav"
        r = subprocess.run(["ffmpeg", "-y", "-i", video, "-vn", "-ar", "44100", "-ac", "2", wav],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0 or not os.path.isfile(wav):
            print("::warning::배경음 제거 스킵 — 오디오 추출 실패:", (r.stderr or "")[-160:])
            return ""
        r = subprocess.run([sys.executable, "-m", "demucs.separate", "--two-stems=vocals",
                            "-n", "htdemucs", "-o", "/tmp/ly_demucs", wav],
                           capture_output=True, text=True, timeout=600)
        out = "/tmp/ly_demucs/htdemucs/ly_bgm_in/vocals.wav"
        # 유효성 = rc·실존·최소 크기(1KB) — 0바이트/절단 wav가 인코딩 양쪽(컷·폴백)을 다 죽이는 구멍 봉합(평의회3 P1)
        if r.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) < 1024:
            print("::warning::배경음 제거 실패(demucs 산출 무효) —", (r.stderr or r.stdout or "")[-200:])
            return ""
        return out
    except subprocess.TimeoutExpired:
        print("::warning::배경음 제거 시간 초과 — 원본 소리로 합성")
        return ""
    except Exception as e:
        print("::warning::배경음 제거 실패 —", str(e)[:160])
        return ""


def cut_filter(keeps, audio, mid, ass_path, asrc="[0:a]", ass_on=True):
    # 단일 패스 select+setpts 시프트 — trim+concat 팬아웃은 브랜치 버퍼링으로 keep 10개에 피크 RSS 4.7GB 실측
    # (러너 7GB OOM 위험 · 평의회8) → select가 한 패스에서 갭 프레임만 드롭 = 메모리 O(1).
    # new_pts = t − (그 keep 앞 제거 누적) = cut_remap과 동일 사상 → 자막·영상·오디오 드리프트 구조적 0(VFR 포함 · 평의회1).
    # -filter_complex_script 파일로 전달(구간 수십 개여도 argv 한도 무관). 한계 = 컷 경계 정밀도는 프레임/오디오프레임(약 21ms) 단위.
    sel, off, acc = [], [], 0.0
    for a, b in keeps:
        # [a,b) — 경계 프레임 이중 포함/누락 없음. 시간 변수 = select는 소문자 t · setpts는 대문자 T(다르면 파싱 실패 실측)
        sel.append("gte(t,{:.6f})*lt(t,{:.6f})".format(a, b))
        off.append("{:.6f}*gte(T,{:.6f})*lt(T,{:.6f})".format(a - acc, a, b))
        acc += b - a
    sel_e, off_e = "+".join(sel), "+".join(off)
    parts = ["[0:v]select='{}',setpts='(T-({}))/TB'[vs];".format(sel_e, off_e)]
    if audio:
        loud = ",loudnorm=I=-16:TP=-1.5:LRA=11" if asrc != "[0:a]" else ""   # 보컬 분리 후 체감 음량 하락 보정(SNS 표준 -16 LUFS · 원본 경로 무변경 = 회귀 0 · 평의회8 P1)
        parts.append("{}aselect='{}',asetpts='(T-({}))/TB'{}[ac];".format(asrc, sel_e, off_e, loud))   # asrc = 배경음 제거 시 보컬 입력 [1:a](배경음 먼저 → 컷 순서 보장)
    tail = ((mid + ",") if mid else "") + ("ass={}".format(ass_path) if ass_on else "")
    parts.append("[vs]" + (tail.rstrip(",") or "null") + "[vo]")   # mid = 편집기 지오메트리(크롭·스케일·fps·패드) — 컷 시간축 뒤에 적용
    return "\n".join(parts)


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


def font_avail(family):
    # 폰트 설치 실측(fc-list) — 판별 실패 = True(fail-soft: 워크플로가 설치 · libass 폴백도 있어 잡을 안 죽임 · 오탐 시 대가 = 기본 고딕 합성+note뿐)
    try:
        r = subprocess.run(["fc-list", ":family={}".format(family), "family"],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            return True
        return family.lower().replace(" ", "") in (r.stdout or "").lower().replace(" ", "")
    except Exception:
        return True


def coef(opts, key, dflt, lo, hi):
    # 연속 계수 축(outline·pad) 안전 파서 — 숫자 아님·NaN·범위 밖 = 기본값/클램프
    try:
        v = float(opts.get(key, dflt))
    except Exception:
        return dflt
    if v != v:
        return dflt
    return max(lo, min(hi, v))


def _interp(x, knots):
    # piecewise linear 보간(knots = (x,y) x오름차순) — 글자진행률 x → 시간진행률 y
    if x <= knots[0][0]:
        return knots[0][1]
    for i in range(1, len(knots)):
        x0, y0 = knots[i - 1]
        x1, y1 = knots[i]
        if x <= x1:
            return y1 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return knots[-1][1]


def _sync_cs(word_lens, seg_words, cs_total):
    # 자막 어절(글자수 word_lens)을 STT word 타임스탬프(seg_words=[{t,s,e}])의 발화 진행 곡선에 투영 → 어절별 cs.
    #   곡선 = STT word 누적 글자비율 → 발화 시간비율(침묵·속도 반영). 자막 어절 끝 글자비율 → 곡선 보간 시간비율 → cs_total 스케일.
    #   반환 = 어절별 cs 리스트(합=cs_total) · word 부족/부적격이면 None(→ 글자수 비례 폴백).
    sw = [w for w in (seg_words or [])
          if isinstance(w.get("s"), (int, float)) and isinstance(w.get("e"), (int, float))
          and math.isfinite(w.get("s")) and math.isfinite(w.get("e")) and w["e"] > w["s"]]
    if not sw:
        return None
    t0 = sw[0]["s"]
    span = sw[-1]["e"] - t0
    if span <= 0:
        return None
    tot_ch = max(1, sum(len(w.get("t") or "") for w in sw))
    cum, knots = 0, [(0.0, 0.0)]
    for w in sw:
        cum += len(w.get("t") or "")
        knots.append((cum / tot_ch, max(0.0, min(1.0, (w["e"] - t0) / span))))   # 시간비율 [0,1] 클램프(word 경계 역전 방어)
    tot = max(1, sum(word_lens))
    cum, prev_tr, used, cs_list = 0, 0.0, 0, []
    for k, wl in enumerate(word_lens):
        cum += wl
        if k == len(word_lens) - 1:
            cs = max(1, cs_total - used)                 # 마지막 = 잔여(합 보존)
        else:
            tr = _interp(cum / tot, knots)
            tr = max(prev_tr, tr)                         # 단조 증가 강제(보간 흔들림 방어)
            cs = max(1, int(round(cs_total * (tr - prev_tr))))
            prev_tr = tr
        cs_list.append(cs)
        used += cs
    return cs_list


def prep_line(text, seg_dur, keyword, fs, avail_px, seg_words=None):
    # 한 조각 공용 준비(카라오케/일반 build_line·팝 build_pop_frames 공유): 새니타이즈·키워드 스팬·어절·청킹·축소·어절별 cs
    #   seg_words = 그 세그 STT word 타임스탬프(있으면 실싱크 · 없으면 글자수 비례 폴백)
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
    cs_list = _sync_cs([len(w) for w in words], seg_words, cs_total)   # 실싱크(STT word 발화 리듬 · 운영자 260708)
    if cs_list is None:                                                # word 없음 = 글자수 비례 폴백(종전)
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
        return "{\\1c" + KW["c"] + "}" + w + "{\\r" + ("" if eff_fs == fs else "}{\\fs" + str(eff_fs)) + "}"   # 강조색 = KW 슬롯(260711 kwc)
    return w


def _assemble(rendered, lines, eff_fs, fs):
    body = "\\N".join(" ".join(rendered[i] for i in ln) for ln in lines)
    return ("{\\fs" + str(eff_fs) + "}" + body) if eff_fs != fs else body


def build_line(text, seg_dur, karaoke, keyword, fs, avail_px, seg_words=None):
    # 한 조각 → (ASS 텍스트, 줄 수, 실폰트크기): 수동 \N + 카라오케 \kf + 키워드 \1c(콘텐츠 그린)
    #   줄 수·실크기 반환 = 중앙 불변 배치(이벤트별 MarginV 보정)의 블록 높이 산정용(260707) · seg_words = 실싱크(260708)
    prep = prep_line(text, seg_dur, keyword, fs, avail_px, seg_words)
    if not prep:
        return "", 0, fs
    words, hits, cs_list, lines, eff_fs = prep
    rendered = []
    for k, w in enumerate(words):
        seg = ("{\\kf" + str(cs_list[k]) + "}") if karaoke else ""
        rendered.append(seg + _word(w, hits[k], eff_fs, fs))
    return _assemble(rendered, lines, eff_fs, fs), len(lines), eff_fs


def build_pop_frames(text, seg_dur, keyword, fs, avail_px, seg_words=None):
    # 팝 모드(운영자 260707 승인): 발화 중인 어절만 콘텐츠 그린 점등 — 어절 시간창마다 라인 전체를 다시 그린 이벤트 프레임 목록.
    #   창 경계 = \kf와 동일한 글자수 비례 분배(진짜 발화 싱크 = Whisper word 타임스탬프 후속) · 키워드(*별표*)는 전 창 상시 그린.
    #   레이아웃(청킹·축소·줄수)은 프레임 간 동일 → 박스·위치 픽셀 불변 = 창 전환 시 어절 색만 바뀜(깜빡임 0).
    prep = prep_line(text, seg_dur, keyword, fs, avail_px, seg_words)
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
    ocb = OC_BGR.get(opts.get("oc") or "black", OC_BGR["black"])   # 음영 색(260711) — 결측/미지 값 = 검정(종전과 바이트 동일)
    KW["c"] = "&H" + OC_BGR.get(str(opts.get("kwc") or "green"), OC_BGR["green"]) + "&"   # 키워드 강조색(운영자 260711 kwc · 결측 = 그린 &H02FD0F& 종전 동일)
    fgc = OC_BGR.get(str(opts.get("fg") or "white"), OC_BGR["white"])   # 자막 글자색(운영자 260711 fg · 결측 = 흰 FFFFFF 종전 동일)
    back = "&H{:02X}".format(255 - int(round(bg * 2.55))) + ocb    # ASS 알파 = 00 불투명·FF 투명 · 44% → 0x8F ≈ 구 &H90(스타일 라인 = & 접미 없음)
    if bg > 0:               # 배경 게이지 ON = 줄 단위 박스(BorderStyle 4 · 3은 다줄 겹침 = 금지) — 전 모양 수렴(260707)
        # 패딩 = Outline값(구 box 전용 oc==back 패딩 겸용 메서드를 전 모양으로 승격 · pad 계수 = 운영자 선택 ×0.16).
        # 글리프 외곽선색도 back 동일 = 박스 위 이중 테두리 0(같은 색 박스 위 같은 색 스트로크 = 어차피 비가시 · 모양 분기는 bg=0에서만 의미).
        border_style, outline, shadow, oc = 4, max(2, int(fs * pad)), 0, back
    else:                    # 배경 0% — bold/clean = 종전 그대로(omul 배율만) · box = 얇은 외곽선 폴백(흰 글자 보호)
        back = "&H90" + ocb  # BorderStyle 1의 BackColour = 그림자색(bold shadow=1) — 알파 &H90 종전값 유지·색만 음영 색 추종(260711)
        if style == "clean" or style == "box":
            border_style, outline, shadow, oc = 1, max(1, int(fs * 0.032 * omul)), 0, "&H00" + ocb
        else:                # bold(기본) = 흰 글자+외곽선+그림자(쇼츠 정석) — 외곽선 색 = 음영 색(기본 검정)
            border_style, outline, shadow, oc = 1, max(1, int(fs * 0.064 * omul)), 1, "&H00" + ocb
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
        "Style: nomute,{font},{fs},&H00{fgc},&H00B8C4BE,{oc},{back},1,0,0,0,100,100,0,0,"
        "{bs},{ol},{sh},{al},{ml},{mr},{mv},1".format(
            font=FONT_FAMILY.get(opts.get("font") or "gothic", FONT_FAMILY["gothic"]),   # 폰트(260711) — 닫힌 집합이라 콤마 유입 불가(ASS 포맷 안전) · 결측 = 종전 고딕
            fgc=fgc,
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
        sw_ts = sg.get("w")   # STT word 타임스탬프(실싱크 · 없으면 None → 글자수 비례 폴백)
        if pop and ko:
            frames, n_main, m_fs = build_pop_frames(ko, e - s, keyword, fs, avail, sw_ts)
            main = frames[0][2] if frames else ""
        else:
            main, n_main, m_fs = build_line(ko, e - s, karaoke, keyword, fs, avail, sw_ts) if ko else ("", 0, fs)
        if not main and src:
            main, n_main, m_fs = build_line(src, e - s, karaoke, False, fs, avail, sw_ts)   # 원문 폴백 = STT 원문이라 word 1:1 = 최상 싱크
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


EDIT_KEYS = ("vid_ar", "vid_fit", "vid_pos", "vid_res", "vid_fps", "vid_t0", "vid_t1", "aud_norm")   # 편집기 축(재입히기 승계 대상 — cut·bgm은 ly 자막 축이라 제외)


def run(vid_id, video, outdir):
    try:
        opts = json.loads(os.environ.get("OPTS") or "{}")
    except Exception:
        opts = {}
    # 재입히기 승계(운영자 후보7 260711): reburn(자막 다시 굽기)의 opts엔 편집기 축이 없다(ly 탭 = 자막 축만) —
    #   직전 산출 video.json의 edit_opts 스냅샷을 병합해 여백·해상도·보간·음량·트림이 유지되게("지금은 자막만" 소실 봉합).
    #   이번 opts에 편집기 축이 하나라도 명시되면 병합 안 함(명시 우선 = 편집기 폼 발사) · 첫 발사·ly 순수 작업 =
    #   video.json 부재/스냅샷 없음 → 무해. 스냅샷은 아래 성공 페이로드에 재도장 = reburn 연쇄에도 승계 유지.
    inherited = []   # 승계된 EDIT_KEYS 목록(note를 실승계 축으로 정직 표기 · 검증3 — 고정문은 트림 승계 때 괴리)
    if not any(k in opts for k in EDIT_KEYS):
        try:
            _prev_eo = (json.load(open(os.path.join(outdir, "video.json"), encoding="utf-8")).get("edit_opts") or {})
            _take = {k: v for k, v in _prev_eo.items() if k in EDIT_KEYS}
            if _take:
                opts.update(_take); inherited = [k for k in EDIT_KEYS if k in _take]
        except Exception:
            pass
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
    if segs and opts.get("burn") is not False:   # no_burn(컷 단독) = word 주입 불요 — build_ass 미호출이라 순수 낭비(검증9)
        try:
            inject_words(segs, outdir)   # STT word 타임스탬프 주입(실싱크 · 실패해도 글자수 비례 폴백 = 무해)
        except Exception as ex:
            print("::warning::word 주입 예외(실싱크 스킵):", ex)
    # 대본 삭제 컷(260711) — 삭제 조각 스팬(원본 시간축). opts.cutdel = 번인 게이트(검증④): subs.json에 del이
    #   커밋돼 있어도 토글 OFF(재번인 opts.cutdel 부재/false)면 컷 미적용 = 토글이 켜기·끄기 양방향으로 동작.
    del_spans = load_del_spans(outdir) if (segs and opts.get("cutdel")) else []
    # ── 편집기(edit) 축 파싱 — 전부 결측 = 순수 ly 경로(회귀 0 · 운영자 260710 골격 B 확정)
    V_AR = {"9:16": 9 / 16, "1:1": 1.0, "4:5": 4 / 5, "16:9": 16 / 9}
    vid_ar = opts.get("vid_ar") if opts.get("vid_ar") in V_AR else None
    vid_fit = opts.get("vid_fit") if opts.get("vid_fit") in ("crop", "pad", "blur") else "crop"   # blur = 원본 블러 확대 배경 여백(260711)
    vid_res = {"1080": 1080, "720": 720, "src": 3840}.get(str(opts.get("vid_res") or ""))   # src = 원본 유지(4K 캡 3840 · 운영자 260711 — 결측 기본은 종전 1920)
    vid_fps = opts.get("vid_fps") if opts.get("vid_fps") in ("60i", "30", "24") else None
    no_burn = opts.get("burn") is False   # 컷 단독(STT-only) 발사 신호(편집기 260711) — 전사 segs는 컷 계산에만 쓰고 번인 억제(키 부재 = 종전대로 번인 = ly·reburn 회귀 0)
    aud_on = bool(opts.get("aud_norm"))
    try:
        vid_pos = min(1.0, max(0.0, float(opts.get("vid_pos", 0.5))))
    except Exception:
        vid_pos = 0.5
    def _sec(k):
        try:
            v = float(opts.get(k))
            return v if math.isfinite(v) and v > 0 else None
        except Exception:
            return None
    t0_req, t1_req = _sec("vid_t0"), _sec("vid_t1")
    has_vid = bool(vid_ar or vid_res or vid_fps or t0_req or t1_req)
    _EK_LBL = {"vid_ar": "비율", "vid_fit": "채움", "vid_pos": "위치", "vid_res": "해상도", "vid_fps": "프레임", "vid_t0": "구간", "vid_t1": "구간", "aud_norm": "음량"}
    edit_notes = (["이전 편집 설정 승계(" + "·".join(dict.fromkeys(_EK_LBL[k] for k in inherited)) + ")"] if inherited else [])   # 실승계 축만 표기(침묵 금지·과대 표기 금지 · 검증3)
    f_key = opts.get("font")
    if segs and not no_burn and f_key and f_key in FONT_FAMILY and f_key != "gothic" and not font_avail(FONT_FAMILY[f_key]):
        opts["font"] = "gothic"   # 폰트 미설치 = 기본 폴백(fail-soft · 260711) — 이후 전 build_ass 호출(컷 실패 폴백 포함)이 이 opts를 봄 · 게이트 = 번인 실행 경로(segs·not no_burn)에만(컷 단독·전사 없음 = fc-list 불요·오해 note 차단 · v2평의회1 F2)
        edit_notes.append("선택 폰트 미설치 — 기본 고딕으로 합성")
    if not segs and not (has_vid or aud_on or opts.get("bgm")):   # bgm 단독도 유효 편집(보컬 트랙 교체 · P2평의회3 게이트 불일치 봉합)
        out_json(outdir, {"error": "전사가 안 돼 컷 불가 — 소리 있는 영상인지 확인해줘" if opts.get("cut")
                          else "자막 타이밍 데이터 없음(subs.json·segments.json) — 자막 텍스트만"}); return 0   # 컷 단독(STT-only) = 컷 맥락 문구(260711)
    if opts.get("cut") and not segs:
        edit_notes.append("무음 컷 건너뜀(전사 없음)")   # 컷 기준 = STT 발화 스팬 — 전사가 없으면(STT 실패·미실행) 컷 원천이 없다(STT-only 겸용 문구 · 검증7)
    # ── 트림(구간) — 컷·자막보다 *먼저* 확정(운영자 260711 트림×자막 동시): 입력 -ss/-t가 시간축 원점을 옮기므로
    #    자막 조각·word·(아래 컷 블록의) 전사 스팬을 전부 트림 좌표로 동행 리맵 = 컷 remap과 동일 정신(시간축 = 한 몸).
    trim = None
    if t0_req is not None or t1_req is not None:
        if dur <= 0:   # probe N/A(webm 등) = 범위 검증 불가 — 무검증 -ss/-t는 t0>실길이면 빈 출력이라 트림 자체를 접는다(검증9 봉합)
            edit_notes.append("영상 길이 미상 — 트림 건너뜀")
        else:
            a = min(max(0.0, t0_req or 0.0), dur)
            b = min(t1_req, dur) if t1_req is not None else dur
            if b > a + 0.2:
                trim = (a, b - a)
                dur = b - a
                if segs:
                    remapped = []
                    for sg in segs:
                        ns, ne = float(sg["s"]) - trim[0], float(sg["e"]) - trim[0]
                        if ne <= 0.05 or ns >= dur - 0.01:
                            continue   # 구간 밖 조각 드롭 · 경계 걸친 조각 = 클립
                        nsg = dict(sg, s=max(0.0, round(ns, 3)), e=min(dur, round(ne, 3)))
                        if sg.get("w"):
                            nw = []
                            for wd in sg["w"]:
                                try:
                                    ws, we = float(wd["s"]) - trim[0], float(wd["e"]) - trim[0]
                                except Exception:
                                    continue
                                if we > 0.02 and ws < dur:
                                    nw.append(dict(wd, s=round(max(0.0, ws), 3), e=round(min(dur, we), 3)))
                            nsg["w"] = nw   # 전부 밖 = 빈 리스트 → _sync_cs 글자수 비례 폴백(컷 리맵과 동일 회귀 0)
                        remapped.append(nsg)
                    segs = remapped
                    if not segs:
                        edit_notes.append("구간 안에 자막 없음 — 자막 없이 합성")
                if del_spans:   # 삭제 스팬도 트림 시간축으로 동행(원본 좌표 = segments 스팬과 동형 · 창 밖 = 드롭)
                    del_spans = [(max(0.0, x - trim[0]), min(dur, y - trim[0])) for x, y in del_spans if y > trim[0] and x < trim[0] + dur]
            else:
                edit_notes.append("구간이 이상해 — 트림 건너뜀")
    if lang == "src":   # 원문 그대로 모드 = src(없으면 ko) 단일
        segs = [{"s": s["s"], "e": s["e"], "ko": s.get("src") or s.get("ko") or "", "src": ""} for s in segs]
    if del_spans and segs:   # 생존 자막 보호(검증④): 타이밍 조절·병합으로 삭제 스팬이 생존 조각과 겹치면 그 겹침은 컷 제외(남기려던 발화 오컷 차단)
        alive = [sp for sp in (_span(sg.get("s"), sg.get("e")) for sg in segs) if sp]
        if alive:
            del_spans = subtract_spans(del_spans, alive)
    # 무음 컷(운영자 260707 · 발화 기준): keep 계산 → 자막 타이밍 재매핑 → trim+concat.
    #   컷과 자막이 같은 파이프라인이어야 하는 이유 = 컷하면 뒤 자막 시각이 전부 당겨짐(remap이 그 싱크 담당).
    #   자를 갭이 없거나 cut OFF = keeps 빈 목록 = 종전 단일 -vf 경로 그대로(회귀 0).
    aud = has_audio(video)   # 판별 실패 = True 가정 — 오판이어도 폴백이 컷/배경음만 포기하고 정상 번인(무음 오디오 강제 삽입보다 안전 · 평의회6)
    # 배경음 제거(운영자 260707 · 기능2) — 컷보다 *먼저*(운영자: 둘 다 켜면 배경음부터). 타임라인 불변(오디오 트랙 교체)이라 컷 계산 무영향.
    # 트레이드오프(정직 · 평의회7): STT는 업스트림에서 *원본(배경음 포함)* 오디오로 이미 전사됨 — 분리를 STT 앞에 두면
    #   소음 큰 클립의 전사 품질이 오를 수 있으나 매 전사에 분리 비용(수 분)이 붙어 비채택. 분리 = 번인 산출에만 적용.
    vocals, bgm_note = "", ""
    if opts.get("bgm") and aud:
        vocals = strip_bgm(video)
        bgm_note = "배경음 제거" if vocals else "배경음 제거 실패 — 원본 소리로 합성"
    cut_note, keeps = "", []
    segs_orig, dur_orig = segs, dur   # 컷 실패 폴백용(평의회6) — 재매핑 전 원본 타이밍·길이 보존
    sil_note, del_note = "", ""
    if opts.get("cut") and dur > 0:
        pad, min_rm, max_ratio = cut_params(opts)   # 컷 강도(운영자 260708) — 살짝/기본/많이 → pad·min_remove·천장
        spans, spans_raw = load_speech_spans(outdir, segs)
        if trim and spans_raw:   # segments.json(원본 좌표) 스팬만 트림 시간축으로 — segs 폴백은 이미 리맵된 좌표 = 재시프트 금지(260711)
            spans = [(max(0.0, x - trim[0]), min(dur, y - trim[0])) for x, y in spans if y > trim[0] and x < trim[0] + dur]
        keeps = cut_keeps(spans, dur, pad, min_rm)
        removed = dur - sum(b - a for a, b in keeps)
        # 과잉 컷 천장(평의회3): 제거 비율이 강도별 천장 초과면 pad를 0.05씩 넓혀 되돌림(무음 많은 영상 보호) — 침묵 클램프 금지, note로 표면화
        #   pad<1.0 상한이라 초무음(80%+) 영상은 천장 못 지킬 수 있음 = best-effort(정당한 침묵 = 발화 삭제보다 안전 · 평의회1·10)
        relaxed = False
        while keeps and dur > 0 and removed / dur > max_ratio and pad < 1.0:
            pad += 0.05
            keeps = cut_keeps(spans, dur, pad, min_rm)
            removed = dur - sum(b - a for a, b in keeps)
            relaxed = True
        if keeps and removed >= min_rm:
            n_gap = len(keeps) - 1 + (1 if keeps[0][0] > 0.005 else 0) + (1 if dur - keeps[-1][1] > 0.005 else 0)
            pct = int(round(removed / dur * 100))
            sil_note = "무음 {:.1f}초 컷({}군데·{}%↓)".format(removed, n_gap, pct)
            if relaxed:
                sil_note += " · 과잉 컷 방지로 자동 완화"
        else:
            keeps = []
    elif opts.get("cut"):
        cut_note = "영상 길이 미상 — 무음 컷 건너뜀"   # dur=0(probe N/A) 침묵 스킵 표면화(평의회3·6 260709) — 조용한 무력화 금지
    # 대본 삭제 컷(운영자 260711 텍스트 컷): 상세 편집기 삭제 조각 스팬 = 명시 의도 → 무음컷과 달리 min_remove 임계 없음.
    #   무음 keeps(있으면)에서 추가 차감·없으면 전체에서 차감 · 전부 삭제 = 컷 포기(빈 출력 방지 · fail-soft).
    if del_spans and dur > 0:
        base = keeps if keeps else [(0.0, dur)]
        k2 = subtract_spans(base, del_spans)
        cut_d = sum(b - a for a, b in base) - sum(b - a for a, b in k2)
        if k2 and cut_d > 0.05:
            keeps = k2
            del_note = "대본 삭제 {}조각 {:.1f}초 컷".format(len(del_spans), cut_d)
        elif not k2:
            del_note = "전부 삭제 구간 — 삭제 컷 건너뜀"
    elif del_spans:
        del_note = "영상 길이 미상 — 삭제 컷 건너뜀"
    if keeps:
        remap, new_dur = cut_remap(keeps)
        remapped = []
        for sg in segs:
            ns, ne = remap(sg["s"]), remap(sg["e"])
            if ne - ns < 0.05 and float(sg["e"]) - float(sg["s"]) >= 0.15:
                continue   # 갭에 통째로 빠져 붕괴한 조각 드롭 = 컷 이음매 0.05s 자막 플래시 방지(평의회1) — 원래 짧던 조각은 보존
            nsg = dict(sg, s=ns, e=ne)
            if sg.get("w"):   # word 타임스탬프도 컷 시간축으로 동행 리맵(평의회3 260709) — 안 옮기면 카라오케/팝
                nw = []       #   어절 하이라이트가 원본 시각 기준으로 어긋남(컷 경계 걸친 세그 최대 1초+ 선행 재현)
                for wd in sg["w"]:
                    try:
                        ws, we = remap(float(wd["s"])), remap(float(wd["e"]))
                    except Exception:
                        continue
                    if we - ws >= 0.02:   # 갭에 통째 붕괴한 어절 드롭(그 자리엔 발화 없음 = 안전)
                        nw.append(dict(wd, s=round(ws, 3), e=round(we, 3)))
                nsg["w"] = nw   # 전부 붕괴 = 빈 리스트 → _sync_cs가 글자수 비례 폴백(회귀 0)
            remapped.append(nsg)
        segs = remapped or segs_orig   # 전 조각 붕괴(교차 출처 극단) = 컷 포기가 안전
        if not remapped:
            keeps = []
        else:
            cut_note = " · ".join(p for p in [cut_note, sil_note, del_note] if p)   # 무음·대본삭제 결합 표기(무음 단독 = 종전 포맷 그대로 · 조용한 클램프 금지)
            print("컷:", cut_note, "· keep", len(keeps), "구간 ·", round(dur, 1), "→", round(new_dur, 1), "초")
            dur = new_dur
    elif del_note:
        cut_note = " · ".join(p for p in [cut_note, del_note] if p)   # 컷 미실행이어도 삭제 컷 스킵 사유는 표면화(침묵 금지)
    # ── 지오메트리 확정 — 크롭 → 캡 스케일 → fps → 패드 · ASS PlayRes = 최종 캔버스(자막이 검정 여백 위에도 앉게 · 260710).
    #    트림은 위에서 선확정(자막·스팬 동행 리맵 · 260711) — 여기선 tcut(입력 -ss/-t)로만 소비. 편집기 축 결측 = 종전 ly 캡·체인 그대로.
    cw, ch, cx, cy = w, h, 0, 0
    pad_t = 0.0
    if vid_ar:
        target, cur = V_AR[vid_ar], w / h
        if abs(target - cur) < 1e-3:
            if vid_fit == "blur":
                edit_notes.append("이미 그 비율 — 블러 여백 생략")   # 신규 축만 표면화(pad/crop 종전 무note 유지 = 회귀 0 · 검증② N2)
            vid_ar = None   # 이미 그 비율 = 크롭/패드 생략
        elif vid_fit in ("pad", "blur"):
            pad_t = target   # blur = pad와 동일 캔버스·contain 산식(채움만 검정→원본 블러 확대 배경 · 260711)
        elif target < cur:
            cw = max(2, int(h * target) & ~1)
            cx = int(vid_pos * (w - cw)) & ~1
        else:
            ch = max(2, int(w / target) & ~1)
            cy = int(vid_pos * (h - ch)) & ~1
    cropf = "crop={}:{}:{}:{}".format(cw, ch, cx, cy) if (cw, ch) != (w, h) else ""
    pw = ph = 0
    if has_vid:   # 편집기 경로 = conv 캡 문법(긴 변 캡·res 캡·패드 캔버스 목표비 스냅·contain) — 결측=1920 · '원본(4K)'=3840
        cap = vid_res if vid_res else 1920
        tw, th = cw, ch
        if pad_t:
            if cw / ch > pad_t:
                pw, ph = cw, int(round(cw / pad_t))
            else:
                pw, ph = int(round(ch * pad_t)), ch
            if max(pw, ph) > cap:
                if pw >= ph:
                    pw, ph = cap, max(2, int(round(cap / pad_t)) & ~1)
                else:
                    pw, ph = max(2, int(round(cap * pad_t)) & ~1), cap
            pw, ph = max(2, pw & ~1), max(2, ph & ~1)
            k = min(pw / cw, ph / ch, 1.0)
            tw, th = max(2, int(cw * k) & ~1), max(2, int(ch * k) & ~1)
        elif max(cw, ch) > cap:
            k = cap / max(cw, ch)
            tw, th = max(2, int(cw * k) & ~1), max(2, int(ch * k) & ~1)
        tw, th = tw & ~1, th & ~1
        if max(cw, ch) > cap and (not vid_res or vid_res == 3840):   # 침묵 다운스케일 표면화(운영자 260711 + src 초과 소스 평의회4) — 명시 1080/720 선택은 본인 선택이라 제외
            edit_notes.append("원본 {}×{} → 긴 변 {} 축소{}".format(w, h, cap, "" if vid_res else "(4K 유지 = 해상도 카드 '원본(4K)')"))
    else:         # 종전 ly 다운스케일 캡(비용 보호·업스케일 없음) 그대로 = 회귀 0
        tw, th = cw, ch
        if tw > 1080:
            th = int(round(th * 1080 / tw / 2) * 2)
            tw = 1080
            if cw > 1920:   # note는 2K+/4K 소스만(평의회3·10) — FHD(1920)의 일상 자막 잡은 종전대로 무note = 표면 회귀 0
                edit_notes.append("원본 폭 {} → 1080 축소(4K 유지 = 해상도 카드 '원본(4K)')".format(cw))
    canvas_w, canvas_h = (pw or tw), (ph or th)
    canvas_px = canvas_w * canvas_h
    # 4K급 판별 = 픽셀 수(FHD 2배 초과) — 긴 변>1920 판별은 세로 1080×2340(폰 화면녹화 2.5MP)을 4K로 오분류해 순수 자막 경로를 거절시킴(평의회4 불가 → 교체)
    is4k = canvas_px > 2 * 2073600
    if is4k and dur > 0:   # 4K 출력 예산(기틀 캡 · 운영자 260711 — 완화 = 운영자 확인): 픽셀 4배 = 인코딩 폭발이라 별도 선게이트
        max4k = int(os.environ.get("EDIT_4K_MAX_SEC") or 180)
        if dur > max4k + 1:
            out_json(outdir, {"error": "원본(4K) 유지는 {}초까지 — 해상도를 1080p로 내리거나 구간을 잘라줘".format(max4k)}); return 0
    # fps(편집기) — 60i = minterpolate 보간 + 예산 가드(0.30s/출력프레임@1080×1920 실측 · 초과 = 정직 스킵+note) · 30/24 = 다운
    fpsf, interp_est = "", 0
    if vid_fps:
        src_fps = 0.0
        try:
            rf = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                 "stream=avg_frame_rate", "-of", "csv=p=0", video], capture_output=True, text=True, timeout=60)
            n_, d_ = (rf.stdout or "0/1").strip().split("/")
            src_fps = float(n_) / float(d_) if float(d_) else 0.0
        except Exception:
            src_fps = 0.0
        if vid_fps == "60i":
            eff = dur if dur > 0 else float(MAX_DUR)
            unit = 60 * 0.30 * (tw * th / 2073600.0)
            est = eff * unit
            if is4k:
                edit_notes.append("60fps 보간은 1080p까지 — 4K에선 건너뜀")   # 4K급 보간 = 단가 4배(예산 밖) · 정직 스킵(운영자 260711 · 판별 = canvas_px)
            elif src_fps >= 59:
                edit_notes.append("이미 60fps — 보간 건너뜀")
            elif est > 900:   # 잡 캡 보호(자막·배경음과 동일 잡 공존 예산 · 평의회2 260710)
                edit_notes.append("60fps 보간 건너뜀 — 이 해상도로 {}초까지(변환 탭 720p = 120초)".format(int(900 / unit) if unit else 0))
            else:
                fpsf, interp_est = "minterpolate=fps=60", int(est)
        elif src_fps > float(vid_fps) + 0.5:
            fpsf = "fps=" + vid_fps
    padf = ""
    if pw:
        px_, py_ = max(0, (pw - tw) // 2) & ~1, max(0, (ph - th) // 2) & ~1
        if vid_fit == "blur":
            # 블러 여백(운영자 260711 승인): 검정 pad 대신 같은 프레임을 캔버스로 커버-스케일+박스블러한 배경 위에 contain 원본 오버레이
            #   — 숏폼 표준 미감 · 생성 0(원본 재사용 = 사실왜곡 0). 입력 = 직전 scale의 tw×th 스트림(fps도 종전 위치 그대로 tw×th에서) →
            #   split 후 bg 가지만 업스케일(블러가 덮어 업스케일 열화 비가시). 라벨 그래프 = -vf·filter_complex 양쪽 유효(ffmpeg 단입단출).
            rad = max(2, min(pw, ph) // 26)   # 블러 반경 = 캔버스 비례(광학 보정값 · boxblur luma_power 2)
            padf = ("split=2[bg0][fg0];"
                    "[bg0]scale={pw}:{ph}:force_original_aspect_ratio=increase,crop={pw}:{ph},boxblur={rad}:2[bgb];"
                    "[bgb][fg0]overlay={px}:{py},setsar=1").format(pw=pw, ph=ph, rad=rad, px=px_, py=py_)
        else:
            padf = "pad={}:{}:{}:{}:black,setsar=1".format(pw, ph, px_, py_)   # setsar=1 = contain 짝수화 미세 SAR 제거(conv 동형)
    scalef = "scale={}:{}".format(tw, th) if (tw, th) != (cw, ch) else ""
    sarf = "setsar=1" if (has_vid and scalef and not padf) else ""   # 스케일 짝수화 잔여 SAR 제거 — 패드 경로(padf 내장)와 대칭(P2평의회9 실측)
    mid = ",".join(x for x in [cropf, scalef, fpsf, padf, sarf] if x)
    ass = build_ass(segs, canvas_w, canvas_h, opts) if (segs and not no_burn) else ""   # no_burn = 컷 계산용 전사만 · 번인 0
    ass_path = "/tmp/ly_subs.ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)
    out_mp4 = "/tmp/ly_subbed.mp4"

    tcut = ["-ss", "{:.3f}".format(trim[0]), "-t", "{:.3f}".format(trim[1])] if trim else []
    ins = tcut + ["-i", video] + ((tcut + ["-i", vocals]) if vocals else [])   # 배경음 제거 = 보컬 wav 2번 입력 · 트림 시 두 입력 동일 -ss/-t = 동기 유지

    def plain_cmd():
        # ⚠️ -shortest 금지: vocals가 영상보다 짧으면 영상을 절단(6.4s→5.0s 실측 회귀 · 평의회1 P1) — 영상 길이가 출력을 주도(꼬리 무음 = 무해)
        vf = ((mid + ",") if mid else "") + ("ass={}".format(ass_path) if ass else "")
        vf = vf.rstrip(",") or "null"   # 자막 없는 편집 경로에서 mid도 비면 무변환 통과(null) — 오디오만 손대는 조합
        return ["ffmpeg", "-y"] + ins + ["-vf", vf] \
            + (["-map", "0:v:0", "-map", "1:a:0", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11"] if vocals else []) \
            + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_mp4]

    enc_base = min(2400, int(900 * max(1.0, canvas_px / 2073600.0)))   # 백스톱 = 캔버스 픽셀 비례(x264 실단가 비례 · FHD 900 → 4K 2400 캡 · 세로 2340 = ~1015 — 이진 오분류 없음 · 평의회4)
    enc_to = enc_base + int(interp_est * 1.5)   # 60i 보간 예산(≤900s)만큼 백스톱 연장(1080p 최대 2250s · 4K 2400s) — 스텝 내 최악 스택{probe+Demucs 분리(≤780)+본 인코딩+음량(≤270)}은 컴포즈 스텝 60분 캡이 수용(P2평의회2 산술 + 4K 260711)
    def encode(c, to=None):   # 15분 백스톱(폴백은 600+보간 = 예산 스택 축소 · 평의회2·3) — 잡 하드킬 전에 우아하게 실패 기록
        to = enc_to if to is None else to
        r = subprocess.run(c, capture_output=True, text=True, timeout=to)
        return (r.returncode == 0 and os.path.isfile(out_mp4) and os.path.getsize(out_mp4) >= 1024), (r.stderr or "")

    try:
        if keeps or vocals:   # 컷·배경음 어느 쪽이든 = 가공 경로(컷 = 단일 패스 select 필터체인 · 재인코딩은 어차피 번인이 하므로 추가 열화 0)
            if keeps:
                fc_path = "/tmp/ly_cut.filter"
                with open(fc_path, "w", encoding="utf-8") as f:
                    f.write(cut_filter(keeps, aud, mid, ass_path, "[1:a]" if vocals else "[0:a]", bool(ass)))
                cmd = ["ffmpeg", "-y"] + ins + ["-filter_complex_script", fc_path, "-map", "[vo]"] \
                    + (["-map", "[ac]"] if aud else []) \
                    + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_mp4]
                ok, err = encode(cmd)
            else:
                ok, err = encode(plain_cmd())
            if not ok:   # 가공 실패 = 가공만 포기·번인은 지킨다(평의회6·3 P1) — 컷·배경음 다 버리고 원본으로 확실한 산출(무효 vocals가 양쪽을 죽이는 구멍 봉합)
                print("::warning::가공(컷/배경음) 합성 실패 — 원본으로 재시도:", err[-300:])
                if keeps:
                    if ass:   # no_burn(컷 단독)은 ASS 재작성도 불요 — vf에 ass 필터 자체가 없다(STT-only 260711)
                        with open(ass_path, "w", encoding="utf-8") as f:
                            f.write(build_ass(segs_orig, canvas_w, canvas_h, opts))
                    cut_note, dur = ("무음 컷 실패 — 컷 없이 합성" if sil_note else "삭제 컷 실패 — 컷 없이 합성"), dur_orig   # 라벨 = 컷 출처 분기(검증① — del 단독 폴백 오표기 방지)
                if vocals:
                    vocals, ins = "", tcut + ["-i", video]   # 트림 보존(-ss/-t 유지) — 폴백이 구간을 잃지 않게
                    bgm_note = "배경음 제거 실패 — 원본 소리로 합성"
                ok, err = encode(plain_cmd(), 600 + (enc_base - 900) + int(interp_est * 1.5))   # 폴백 백스톱도 4K분 확장(1080p = 종전 600 유지)
        else:
            ok, err = encode(plain_cmd())
        if not ok:
            tail = err[-400:]
            print("::warning::ffmpeg 번인 실패:", tail)
            out_json(outdir, {"error": "영상 합성 실패 — 자막 텍스트는 정상", "detail": tail[-160:]}); return 0
    except subprocess.TimeoutExpired:
        out_json(outdir, {"error": "영상 합성 시간 초과 — 자막 텍스트는 정상"}); return 0
    # ── 음량 통일(편집기 aud_norm) — 완성본 후처리·비디오 copy·전면 fail-soft(성공 합성 보존 = conv 동형)
    if aud_on:
        try:
            ok_a, a_note = audio_norm.normalize(out_mp4, "/tmp/ly_an.mp4")
        except Exception as e:
            ok_a, a_note = False, "음량 통일 건너뜀(처리 실패)"
            print("::warning::audio_norm 예외:", e)
        if ok_a:
            out_mp4 = "/tmp/ly_an.mp4"
        edit_notes.append(a_note)
    data = open(out_mp4, "rb").read()
    ed_note = {"1": "편집 자막 반영", "fail": "편집 반영 실패 — 이전 자막으로 합성", "restore": "원본 의역 복원"}.get(os.environ.get("LY_EDITED") or "", "")   # 편집분 번인 결과 표면화(기능평의회9 P1 — 반영/실패/복원이 무신호로 수렴하던 침묵 봉합 · env = ly-make '편집 자막 반영' 스텝)
    note = " · ".join(p for p in [
        ed_note,
        "받아쓴 자막(원문)으로 합성" if (src_kind == "stt" and not no_burn) else "",   # no_burn = 전사는 컷 계산용일 뿐(자막 합성 아님)
        bgm_note, cut_note] + edit_notes if p)   # 처리 순서대로 표기: 편집 → 배경음 → 컷 → 편집기(트림/보간/음량)
    sub_burned = bool(segs) and not no_burn   # 자막이 실제로 번인됐는가 — 완료 알림 표면화용(운영자 260717 "자막 삽입 포함 알람"). 컷단독(no_burn)·전사없음·구간내 자막0(segs 소거) = False = 정직
    snap = {k: opts[k] for k in EDIT_KEYS if k in opts}   # 재입히기 승계 스냅샷 — 성공 산출에 도장(reburn이 읽어 병합)
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
            out_json(outdir, dict({"url": url + "?v=" + bust, "src": src_url, "bytes": len(data), "dur": round(dur, 1), "note": note, "sub": sub_burned},
                                  **({"edit_opts": snap} if snap else {}))); return 0
        print("::warning::R2 업로드 실패 — git 폴백 시도")
    if len(data) <= GIT_FALLBACK_MAX:
        with open(os.path.join(outdir, "subbed.mp4"), "wb") as f:
            f.write(data)
        out_json(outdir, dict({"url": "ly_out/{}/subbed.mp4?v={}".format(vid_id, bust), "src": src_url, "bytes": len(data), "dur": round(dur, 1),
                               "note": (note + " · " if note else "") + "git 저장(R2 미설정)", "sub": sub_burned},
                              **({"edit_opts": snap} if snap else {}))); return 0   # src 승계 = 폴백서도 재합성 버튼 유지(평의회)
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
