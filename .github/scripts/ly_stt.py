#!/usr/bin/env python3
# 오디오 파일 → faster-whisper large-v3 STT(로컬·키 불필요) → 타임코드 트랜스크립트(stdout).
# 그 트랜스크립트가 lymake.sh(claude -p)의 [입력]이 됨.
# STT 설정 경계(평의회10인·260709): vad_filter=True = *러너 의도값* — 무음 컷(ly_burn)의 발화 스팬 원천(작업이력 260708)이고
#   라이브 실적 정상(260707 산출 4건). 지침 STEP 0-2의 False는 *세션 환경* 과필터 실측(전 구간 0개) — 러너서 재현 시
#   아래 0개 폴백(vad_filter=False 1회 재시도)이 방어(폴백 성공 = 컷 정밀도만 저하·기능 생존).
# argv[2](선택) = 세그먼트 JSON 출력 경로 — word 타임스탬프 포함 원천 타이밍(뷰어 상세 편집기 전용·additive).
#   ⚠️ 정직(평의회1 실측): word_timestamps=True는 faster-whisper가 세그 경계를 word 정렬값으로 재산출하고
#   디코더 seek를 재배치한다 → stdout '포맷'은 불변이나 타임코드·경계(드물게 텍스트)는 종전(False)과 달라질 수 있다.
#   = 의역(claude) 입력이 미세 변동하는 의도된 트레이드오프(위험 수용 기록 = 작업이력 260706 · 카나리아 ko/en/es 의역 품질 정상 실측).
#   argv[2] 미전달("" 포함) = word_timestamps=False = 종전과 완전 동일. 지침 해시는 어느 쪽이든 무영향(전사는 지침 아님).
import sys
import json
import os
from faster_whisper import WhisperModel

audio = sys.argv[1]
seg_json = sys.argv[2] if len(sys.argv) > 2 else ""
# device=cpu/int8 = 러너 기본(GPU 없음). large-v3 = 최고 정확도·3.1GB(운영자 260726 — turbo가 소음·현장음 클립서
#   발화 누락·오인식 상습이라 승격. 속도 ~4배 손해는 STT 스텝 백스톱 증량으로 수용).
model = WhisperModel("large-v3", device="cpu", compute_type="int8")


def transcribe(vad):
    # word_timestamps는 JSON 요청 시에만(미요청 = 종전과 완전 동일 동작·비용)
    # condition_on_previous_text=False = 반복 환각 루프 억제(지침 STEP 0-2 정본 — 소음·노래 입력 방어 · 평의회4)
    segments, info = model.transcribe(audio, language=None, vad_filter=vad,
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


rows, info = transcribe(True)
if not rows:   # VAD 과필터(전 구간 무음 오판 → 0개 = 지침 STEP 0-2 실측 모드) 폴백 — 그래도 0개면 종전대로 rc 3
    print("# VAD 0개 → vad_filter=False 재시도(과필터 폴백)", file=sys.stderr)
    rows, info = transcribe(False)
print(f"# STT: Whisper large-v3 · lang={info.language} ({info.language_probability:.2f})",
      file=sys.stderr)
n = 0
segs = []
unc = []
for r in rows:
    n += 1
    print(f"[{r['s']:.1f}-{r['e']:.1f}] {r['t']}")   # 본문 라인 포맷 불변(구본 바이트 등가 — 소비자 = claude 프롬프트·wc -l)
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
    doc = {"v": 1, "model": "large-v3", "lang": info.language,
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
