#!/usr/bin/env python3
"""GPT 감독 레인 — OpenAI chat.completions 1회 호출(sbmake.sh gpt 분기 전용 · 260714 운영자 "지피티도 가능하게").
stdin = 프롬프트 전문(sb-make.md + 스킬 인라인 + 이야기) → stdout = 콘티 본문.
재시도 3회(429/5xx·네트워크) · usage 계측은 stderr 러너 로그(클로드 레인의 계측 셸 SSOT와 별개 경량 대응 — 이 파일은 OpenAI 호출만·클로드 호출 0 = 폴오버 게이트 비대상).
인증 = env OPENAI_API_KEY(레포 Actions 시크릿 · 계정 단위 키 = 이미지용 발급분 재사용 가능 · 설계확정 §0-2).
모델 = env OPENAI_MODEL(기본 gpt-5.6-sol — 미가용 계정이면 시크릿과 함께 vars로 교체)."""
import json
import os
import sys
import time
import urllib.error
import urllib.request

prompt = sys.stdin.read()
model = os.environ.get("OPENAI_MODEL", "gpt-5.6-sol")
key = os.environ.get("OPENAI_API_KEY", "")
if not key:
    sys.stderr.write("OPENAI_API_KEY 미설정 — 레포 Actions 시크릿 등록 필요\n")
    sys.exit(2)

body = json.dumps({
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "max_completion_tokens": 16000,   # 콘티 12~16컷 + 캐릭터 블록 여유(실측 출력 수천~1.5만 tok 범위)
}).encode()

delay = 10
for attempt in range(1, 4):
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions", data=body,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:   # 900s = sbmake 클로드 레인 계측 셸 상한과 통일
            resp = json.load(r)
        u = resp.get("usage", {})
        sys.stderr.write("usage in=%s out=%s model=%s\n" % (u.get("prompt_tokens"), u.get("completion_tokens"), model))
        txt = (resp.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        if not txt.strip():
            sys.stderr.write("빈 응답(choices.message.content 공백)\n")
            sys.exit(1)
        sys.stdout.write(txt)
        sys.exit(0)
    except urllib.error.HTTPError as e:
        msg = e.read()[:400].decode("utf-8", "replace")
        sys.stderr.write("HTTP %s (시도 %d/3): %s\n" % (e.code, attempt, msg))
        if e.code in (429, 500, 502, 503, 529) and attempt < 3:   # 쿼터·일시 장애만 재시도(401/404 = 즉시 실패 = 정직한 error.log)
            time.sleep(delay)
            delay *= 2
            continue
        sys.exit(1)
    except Exception as e:  # noqa: BLE001 — 네트워크 계열 총괄(러너 1회성 스크립트)
        sys.stderr.write("호출 실패(시도 %d/3): %s\n" % (attempt, e))
        if attempt < 3:
            time.sleep(delay)
            delay *= 2
            continue
        sys.exit(1)
