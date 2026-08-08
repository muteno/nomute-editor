#!/usr/bin/env python3
# 오디오 파일 → faster-whisper large-v3 STT(로컬·키 불필요) → 타임코드 트랜스크립트(stdout).
# 그 트랜스크립트가 lymake.sh(claude -p)의 [입력]이 됨.
# STT 설정 경계(평의회10인·260709): vad_filter=True = *러너 의도값* — 무음 컷(ly_burn)의 발화 스팬 원천(작업이력 260708)이고
#   라이브 실적 정상(260707 산출 4건). 지침 STEP 0-2의 False는 *세션 환경* 과필터 실측(전 구간 0개) — 러너서 재현 시
#   아래 0개 폴백(vad_filter=False 1회 재시도)이 방어(폴백 성공 = 컷 정밀도만 저하·기능 생존).
# argv[2](선택) = 세그먼트 JSON 출력 경로 — word 타임스탬프 포함 원천 타이밍(뷰어 상세 편집기 + stdout `# 어절:` 라인·additive).
#   ⚠️ 정직(평의회1 실측): word_timestamps=True는 faster-whisper가 세그 경계를 word 정렬값으로 재산출하고
#   디코더 seek를 재배치한다 → stdout '포맷'은 불변이나 타임코드·경계(드물게 텍스트)는 종전(False)과 달라질 수 있다.
#   = 의역(claude) 입력이 미세 변동하는 의도된 트레이드오프(위험 수용 기록 = 작업이력 260706 · 카나리아 ko/en/es 의역 품질 정상 실측).
#   argv[2] 미전달("" 포함) = word_timestamps=False = 종전과 완전 동일. 지침 해시는 어느 쪽이든 무영향(전사는 지침 아님).
import sys
import json
import os

audio = sys.argv[1]
seg_json = sys.argv[2] if len(sys.argv) > 2 else ""
# device=cpu. large-v3 = 최고 정확도·3.1GB(운영자 260726 — turbo가 소음·현장음 클립서
#   발화 누락·오인식 상습이라 승격. 속도 ~4배 손해는 STT 스텝 백스톱 증량으로 수용).
# 연산 정밀도 — ⚠️ **가설은 러너 A/B로 반증됐다**(정직 기록 · docs/reports/260728_1447_STT정밀도AB.md).
#   착수 가설 = 「구본 int8이 가중치를 8비트로 뭉개 유사음 오인식을 키운다」(260728121555 '경찰서 가서'→'검찰서가' 어절확률 0.60).
#   실측 = 영상 3편(54.0s/45.0s/41.2s)을 int8 · int8_float32로 연속 전사 → **소요 시간·어절 확률 분포·전사 텍스트가 전부 동일**
#   (60.2s vs 60.1s · 저확률<0.70 개수 10/4/10 양쪽 같음 · 텍스트 글자 단위 일치). CPU CTranslate2에서 두 설정이
#   사실상 같은 경로였던 것으로 보인다 = **이 값을 바꿔서 얻는 정확도 이득은 실측상 0**.
#   그럼 왜 int8_float32로 두는가 = 속도 손해도 실측 0이고(동일), 이름이 연산 경로를 명시해 오해를 줄이며,
#   env 노브(아래)가 float32까지 열어두는 A/B 진입점이 되기 때문. **정확도 개선을 여기서 기대하지 마라** — 실측이 가리킨
#   진짜 후보는 오디오 조건 쪽이다(짧은 클립 전사 0개 = VAD 과필터 의심 · 배경음 분리 선행 미적용 · 원장 Q996).
#   ⚠️ 이 파일은 ly·edit·nb 3개 워크플로 공용이라 여기 한 줄이 3파이프를 동시에 움직인다.
PRECISION = os.environ.get("LY_STT_PRECISION", "int8_float32").strip() or "int8_float32"

# ── 엔진 = Scribe v2(기본) → 실패 시 large-v3 폴백(운영자 260808 "무조건 반영") ──────────────
#   실측 근거(run 31230435185 · docs/reports/260808_0936_STT정밀도AB.md · 한국어 19.6s):
#     추론 28.1s→1.0s(1.43×RT→0.05×RT) · 저확률(<0.70) 어절 3/26(11.5%)→1/29(3.4%)
#     · large-v3가 틀린 「검찰서가」를 Scribe가 「경찰서 가서」로 정확히 · 누락 어절(제가·여러분들)·구두점 회수
#     · 과금 $0.0012/19.6초($0.22/시간). ⚠ 표본 1클립 = 확률 개선의 증거이지 재현 보증 아님.
#   ⚠ 폴백이 계약이다 — 키 부재·API 오류·응답 이상·어절 0개 = **그 자리에서 large-v3로 내려앉는다**(종전 동작 100%).
#     외부 벤더가 죽어도 자막 파이프는 안 죽는다(fail-soft = 이 레포 관례).
#   ⚠ 킬스위치 = 레포 변수 `LY_STT_ENGINE=whisper`(즉시 종전 경로 · 코드 변경 0). `scribe` = 폴백 없이 강제(A/B용).
#   ⚠ 지연 import = Scribe가 성공하면 faster_whisper·3.1GB 모델을 **아예 안 올린다**(로드 4.2s·메모리 절감).
ENGINE = (os.environ.get("LY_STT_ENGINE") or "auto").strip().lower() or "auto"
EL_KEY = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
SCRIBE_MODEL = "scribe_v2"
_SENT_END = ".?!。？！…"
# ⚠ 언어코드 정규화가 **실효 조건**이다 — Scribe는 ISO-639-3(`kor`)로 주는데 whisper는 2자(`ko`)를 주고,
#   소비자가 2자 리터럴로 분기한다: 뷰어 `LY_LANG !== 'ko'` = 「외국어 영상」 판정(편집분을 번인에 안 싣는 방벽 · ly.html)
#   · `lyJoin`의 무공백 문자권 집합(ja|zh|yue|th|lo|my|km). 정규화를 빼면 **한국어 영상이 외국어로 오판**된다.
#   3자→2자 사본은 위 소비자가 실제로 쓰는 코드 + 상위 사용 언어만(전체 ISO 표 복제 금지 · 미지 코드는 앞 2자 폴백).
_L3 = {"kor": "ko", "eng": "en", "jpn": "ja", "zho": "zh", "cmn": "zh", "yue": "yue", "tha": "th",
       "lao": "lo", "mya": "my", "bur": "my", "khm": "km", "vie": "vi", "ind": "id", "spa": "es",
       "por": "pt", "fra": "fr", "fre": "fr", "deu": "de", "ger": "de", "rus": "ru", "ara": "ar",
       "hin": "hi", "ita": "it", "nld": "nl", "dut": "nl", "tur": "tr", "pol": "pl", "ukr": "uk"}


def _lang2(code):
    c = (code or "").strip().lower().split("-")[0]
    if len(c) <= 2:
        return c
    return _L3.get(c, c[:2])


def _scribe_rows():
    """ElevenLabs Scribe v2 전사 → whisper 경로와 **같은 rows 구조**로 환산(소비자 코드 무접촉).
    실패 = None 반환(호출부가 whisper로 폴백)."""
    import math
    import subprocess
    cp = subprocess.run(["curl", "-sS", "--max-time", "900", "-X", "POST",
                         "https://api.elevenlabs.io/v1/speech-to-text",
                         "-H", "xi-api-key: %s" % EL_KEY,
                         "-F", "file=@%s" % audio,
                         "-F", "model_id=%s" % SCRIBE_MODEL,
                         "-F", "timestamps_granularity=word"],
                        capture_output=True, text=True)
    if cp.returncode != 0:
        print("# Scribe 실패(curl rc=%s) — %s" % (cp.returncode, (cp.stderr or "")[:200]), file=sys.stderr)
        return None
    try:
        j = json.loads(cp.stdout or "{}")
    except Exception as e:
        print("# Scribe 응답 파싱 실패(%s) — %s" % (e, (cp.stdout or "")[:200]), file=sys.stderr)
        return None
    if not isinstance(j, dict) or j.get("text") is None:
        print("# Scribe 응답 이상 — %s" % (cp.stdout or "")[:200], file=sys.stderr)
        return None
    ws = [w for w in (j.get("words") or [])
          if (w.get("type") or "word") == "word" and (w.get("text") or "").strip()
          and isinstance(w.get("start"), (int, float)) and isinstance(w.get("end"), (int, float))]
    if not ws:
        print("# Scribe 어절 0개 — 폴백", file=sys.stderr)
        return None

    # 조각(세그먼트) 조립 — Scribe는 words만 준다(whisper의 segment 개념 없음).
    #   ⚠ 경계 술어 = ① 문장부호 종료 ② 발화 공백 GAP_S 이상 ③ 길이 상한(초·글자) — 자막 조각의 통상 규격.
    #     구두점이 실제로 오는 게 Scribe의 이점이라 ①이 1순위(large-v3는 구두점 0개라 이 축이 아예 없었다).
    #   ⚠ 조각 경계는 어차피 claude 의역 단계가 `# 어절:` 실측 타임스탬프로 다시 나눈다(260728 계약) —
    #     여기 값은 그 입력의 뼈대이지 최종 자막 경계가 아니다.
    GAP_S, MAX_S, MAX_CH = 0.8, 12.0, 80
    rows, cur = [], []

    def _flush():
        if not cur:
            return
        t = " ".join(w["t"] for w in cur).strip()
        if not t:
            cur.clear(); return
        lps = [w["lp"] for w in cur if w["lp"] is not None]
        rows.append({"s": cur[0]["s"], "e": cur[-1]["e"], "t": t,
                     "w": [{"t": w["t"], "s": round(w["s"], 2), "e": round(w["e"], 2), "p": w["p"]} for w in cur],
                     "lp": (sum(lps) / len(lps)) if lps else None,   # whisper avg_logprob 자리 = is_unc ② 축 보존
                     "ns": None})                                    # Scribe는 no_speech 축 없음 = is_unc ③ 미적용
        cur.clear()

    for i, w in enumerate(ws):
        lp = w.get("logprob")
        lp = float(lp) if isinstance(lp, (int, float)) else None
        p = round(math.exp(lp), 2) if lp is not None else 1.0        # 어절 확률 = exp(logprob) → is_unc ① 임계 0.70 그대로
        cur.append({"t": (w.get("text") or "").strip(), "s": float(w["start"]), "e": float(w["end"]),
                    "p": min(p, 1.0), "lp": lp})
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        gap = (float(nxt["start"]) - float(w["end"])) if nxt else 0.0
        span = cur[-1]["e"] - cur[0]["s"]
        chars = sum(len(x["t"]) for x in cur)
        if (nxt is None or cur[-1]["t"][-1:] in _SENT_END or gap >= GAP_S
                or span >= MAX_S or chars >= MAX_CH):
            _flush()
    _flush()
    return rows, _lang2(j.get("language_code"))


class _Info:   # whisper info 객체 자리 — 소비자(로그·segments.json)가 쓰는 속성만 갖춘다
    def __init__(self, lang, dur):
        self.language = lang or "?"
        self.language_probability = 1.0
        self.duration = dur


model = None


def _load_whisper():
    global model
    if model is None:
        from faster_whisper import WhisperModel
        model = WhisperModel("large-v3", device="cpu", compute_type=PRECISION)
    return model


def transcribe(vad):
    # word_timestamps는 JSON 요청 시에만(미요청 = 종전과 완전 동일 동작·비용)
    # condition_on_previous_text=False = 반복 환각 루프 억제(지침 STEP 0-2 정본 — 소음·노래 입력 방어 · 평의회4)
    segments, info = _load_whisper().transcribe(audio, language=None, vad_filter=vad,
                                                    condition_on_previous_text=False,
                                                    word_timestamps=bool(seg_json))
    rows = []
    for seg in segments:
        t = seg.text.strip()
        if not t:
            continue
        words = []
        if seg_json:
            words = [{"t": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2),
                      "p": round(getattr(w, "probability", 1.0) or 1.0, 2)}   # p = 어절 확률(additive · 뭉개짐 의심 원천 — 뷰어 파서는 미지 키 무시)
                     for w in (seg.words or []) if w.word.strip()]
        rows.append({"s": seg.start, "e": seg.end, "t": t, "w": words,
                     "lp": getattr(seg, "avg_logprob", None), "ns": getattr(seg, "no_speech_prob", None)})   # s/e = raw 유지(stdout 구본 바이트 등가) — 라운딩은 JSON 직전에만(재평의회1·4 이중 라운드 드리프트 봉합) · lp/ns = 조각 신뢰도(뭉개짐 의심 플래그 원천 · Q581)
    return rows, info


def is_unc(r):
    # 뭉개짐(오인식) 의심 휴리스틱(Q581 · 운영자 "오인 발화 부분만 재생성 알림") — 3중 신호:
    # ① 어절 확률 < 0.70(주 신호 — 임계 실측 260726: 오인식 '신질병' 0.64 vs 정상 어절 ≥0.78·대부분 ≥0.85.
    #    조각 평균 lp는 문장 나머지가 또렷하면 오인 어절을 가려 못 잡음을 같은 클립서 실측 = 어절 단위가 정답)
    # ② avg_logprob < -0.8(조각 전체 뭉개짐) ③ no_speech_prob > 0.6(발화 아님 의심).
    # 플래그 = 정보 표면화일 뿐 자막 내용 무접촉 · ①은 word_timestamps 요청(seg_json) 시에만 존재.
    lp, ns = r.get("lp"), r.get("ns")
    return ((lp is not None and lp < -0.8) or (ns is not None and ns > 0.6)
            or any(w.get("p", 1.0) < 0.70 for w in (r.get("w") or [])))


ENGINE_USED = "large-v3"
rows, info = None, None
if ENGINE in ("auto", "scribe") and EL_KEY:
    got = _scribe_rows()
    if got:
        rows, lang = got
        info = _Info(lang, max((r["e"] for r in rows), default=0.0))
        ENGINE_USED = SCRIBE_MODEL
    elif ENGINE == "scribe":
        print("::error::Scribe 강제 모드에서 실패 — 폴백 금지 설정", file=sys.stderr)
        sys.exit(4)
elif ENGINE == "scribe" and not EL_KEY:
    print("::error::LY_STT_ENGINE=scribe 인데 ELEVENLABS_API_KEY 없음", file=sys.stderr)
    sys.exit(4)

if rows is None:   # ── large-v3 경로(폴백 또는 LY_STT_ENGINE=whisper) ──
    rows, info = transcribe(True)
    if not rows:   # VAD 과필터(전 구간 무음 오판 → 0개 = 지침 STEP 0-2 실측 모드) 폴백 — 그래도 0개면 종전대로 rc 3
        print("# VAD 0개 → vad_filter=False 재시도(과필터 폴백)", file=sys.stderr)
        rows, info = transcribe(False)

print(f"# STT: {ENGINE_USED} · {PRECISION if ENGINE_USED == 'large-v3' else 'api'} · lang={info.language} ({info.language_probability:.2f})",
      file=sys.stderr)   # 어느 엔진으로 뽑힌 자막인지 로그·산출물 양쪽에 남긴다(폴백 발생 여부 = 이 한 줄로 사후 판정)
n = 0
segs = []
unc = []
for r in rows:
    n += 1
    print(f"[{r['s']:.1f}-{r['e']:.1f}] {r['t']}")   # 본문 라인 포맷 불변(구본 바이트 등가 — 소비자 = claude 프롬프트·wc -l)
    if r["w"]:   # 어절 타임스탬프 동봉(운영자 260728 "시간단위로 흐르면 저렇게 끊길거야") — 조각 경계·s/e를 *추정*이 아니라 실측 발화시각에서 가져오게 하는 재료.
        #   구본은 세그 단위 [s-e]만 줘서 claude가 분할 조각의 타임코드를 글자수로 추정 → 끊는 자리·싱크 동시 열화(260728 실측: 원본 2조각 → 12조각 전부 추정).
        #   `#` 접두 = 기존 메타 주석 계열(본문 라인 파서·wc -l 무영향 · 미지 라인은 claude가 문맥으로 소비 = 불명확 꼬리 주석 선례).
        print("# 어절: " + " ".join(f"{w['t']}={w['s']:.2f}-{w['e']:.2f}" for w in r["w"]))
    if is_unc(r):
        unc.append(r)
    if seg_json:
        d = {"s": round(r["s"], 2), "e": round(r["e"], 2), "t": r["t"], "w": r["w"]}
        if r.get("lp") is not None:
            d["lp"] = round(r["lp"], 2)
        if r.get("ns") is not None:
            d["ns"] = round(r["ns"], 2)
        if is_unc(r):
            d["unc"] = 1   # additive — 뷰어·번인 파서는 미지 키 무시(편집기 ⚠ 배지·fastpath subs.md 표시 원천)
        segs.append(d)
if unc:   # 꼬리 주석 = claude 의역 입력에 '어느 조각이 뭉개짐 의심인지' 실데이터 전달(지침 STEP 0-3 별도 보고 근거 · 본문 라인은 무접촉)
    print("# 불명확(뭉개짐 의심) %d조각 — 오인식 가능·재생성(교정) 후보: %s"
          % (len(unc), " · ".join(f"[{r['s']:.1f}-{r['e']:.1f}]" for r in unc)))
print(f"# STT 완료: {n}개 세그먼트 (불명확 의심 {len(unc)}개)", file=sys.stderr)
if seg_json and segs:
    from datetime import datetime, timedelta, timezone
    try:   # 시각 = KST 강제(§표기표준) — 표기용 필드가 tzdata 부재로 성공한 STT를 죽이면 안 됨(평의회1 F2 · 고정 오프셋 폴백)
        from zoneinfo import ZoneInfo
        created = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    except Exception:
        created = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    doc = {"v": 1, "model": ENGINE_USED, "prec": PRECISION if ENGINE_USED == "large-v3" else "api", "lang": info.language,   # prec = 이 전사가 어느 연산 정밀도로 나왔는지(A/B 대조 · 미지 키는 뷰어·번인 파서가 무시)
           "dur": round(float(getattr(info, "duration", 0) or 0), 2),
           "created": created,
           "segs": segs}
    d = os.path.dirname(seg_json)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(seg_json, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"# 세그먼트 JSON: {seg_json} ({len(segs)}개·word 타임스탬프)", file=sys.stderr)
if n == 0:
    sys.exit(3)
