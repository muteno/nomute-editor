#!/usr/bin/env python3
# 오디오 파일 → faster-whisper large-v3-turbo STT(로컬·키 불필요) → 타임코드 트랜스크립트(stdout).
# 그 트랜스크립트가 lymake.sh(claude -p)의 [입력]이 됨. 정본 STT 설정 = apps/ly/00_지침_자막기 STEP 0-2.
# argv[2](선택) = 세그먼트 JSON 출력 경로 — word 타임스탬프 포함 원천 타이밍(뷰어 상세 편집기 전용·additive).
#   stdout 트랜스크립트는 argv[2] 유무와 무관하게 바이트 동일(= claude 의역 입력·지침 해시 무영향).
import sys
import json
import os
from faster_whisper import WhisperModel

audio = sys.argv[1]
seg_json = sys.argv[2] if len(sys.argv) > 2 else ""
# device=cpu/int8 = 러너 기본(GPU 없음). large-v3-turbo = 정확도≈large-v3·4배 빠름·1.6GB.
model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
# word_timestamps는 JSON 요청 시에만(미요청 = 종전과 완전 동일 동작·비용)
segments, info = model.transcribe(audio, language=None, vad_filter=True,
                                  word_timestamps=bool(seg_json))
print(f"# STT: Whisper large-v3-turbo · lang={info.language} ({info.language_probability:.2f})",
      file=sys.stderr)
n = 0
segs = []
for seg in segments:
    t = seg.text.strip()
    if not t:
        continue
    n += 1
    print(f"[{seg.start:.1f}-{seg.end:.1f}] {t}")
    if seg_json:
        words = [{"t": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)}
                 for w in (seg.words or []) if w.word.strip()]
        segs.append({"s": round(seg.start, 2), "e": round(seg.end, 2), "t": t, "w": words})
print(f"# STT 완료: {n}개 세그먼트", file=sys.stderr)
if seg_json and segs:
    from datetime import datetime
    from zoneinfo import ZoneInfo   # 시각 = KST 강제(§표기표준)
    doc = {"v": 1, "model": "large-v3-turbo", "lang": info.language,
           "dur": round(float(getattr(info, "duration", 0) or 0), 2),
           "created": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
           "segs": segs}
    d = os.path.dirname(seg_json)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(seg_json, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"# 세그먼트 JSON: {seg_json} ({len(segs)}개·word 타임스탬프)", file=sys.stderr)
if n == 0:
    sys.exit(3)
