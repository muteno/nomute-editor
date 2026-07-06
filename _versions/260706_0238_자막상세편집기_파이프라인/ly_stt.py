#!/usr/bin/env python3
# 오디오 파일 → faster-whisper large-v3-turbo STT(로컬·키 불필요) → 타임코드 트랜스크립트(stdout).
# 그 트랜스크립트가 lymake.sh(claude -p)의 [입력]이 됨. 정본 STT 설정 = apps/ly/00_지침_자막기 STEP 0-2.
import sys
from faster_whisper import WhisperModel

audio = sys.argv[1]
# device=cpu/int8 = 러너 기본(GPU 없음). large-v3-turbo = 정확도≈large-v3·4배 빠름·1.6GB.
model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
segments, info = model.transcribe(audio, language=None, vad_filter=True)
print(f"# STT: Whisper large-v3-turbo · lang={info.language} ({info.language_probability:.2f})",
      file=sys.stderr)
n = 0
for seg in segments:
    t = seg.text.strip()
    if not t:
        continue
    n += 1
    print(f"[{seg.start:.1f}-{seg.end:.1f}] {t}")
print(f"# STT 완료: {n}개 세그먼트", file=sys.stderr)
if n == 0:
    sys.exit(3)
