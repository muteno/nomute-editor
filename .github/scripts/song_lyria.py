#!/usr/bin/env python3
# 음원 구글 생성(운영자 260712) — req.json(prompt·가사) → Lyria 3 REST(interactions) → 오디오 → R2(미설정 = git 폴백)
#   → viewer/song_out/<id>/song.json {engine:'lyria', url, …}. 유료(곡당 $0.08 급 · Pro preview) — 수동 발사 전용 파이프에서만 호출.
#   실패 = error.log + exit 1(뷰어 폴 표면화 · 4xx = 재시도 없이 정직 거절 표면화 — 안전필터·키/티어 문제를 감추지 않는다).
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".github/scripts")
import thumb_gen as tg  # r2_upload/R2_ON 재사용(카드·썸네일과 동일 SSOT — 자체 업로더 재구현 금지)

ID = os.environ.get("SONG_ID") or ""
if not re.fullmatch(r"[0-9a-f-]+", ID):
    print("::error::잘못된 id"); sys.exit(1)
OUT = "viewer/song_out/{}".format(ID)
os.makedirs(OUT, exist_ok=True)

def fail(msg, head=""):
    body = msg + (("\n---- 응답 head ----\n" + head[:400]) if head else "")
    with open(os.path.join(OUT, "error.log"), "w", encoding="utf-8") as f:
        f.write(body)
    print("::error::{}".format(msg)); sys.exit(1)

KEY = os.environ.get("GEMINI_API_KEY") or ""
if not KEY:
    fail("GEMINI_API_KEY 미설정 — 레포 Secrets 확인(썸네일과 동일 키)")
try:
    req = json.load(open(os.path.join(OUT, "req.json"), encoding="utf-8"))
except Exception as e:
    fail("req.json 없음/파손 — 가사 생성 단계 확인 ({})".format(e))
prompt = (req.get("prompt") or "").strip()
if len(prompt) < 40:
    fail("생성 프롬프트가 비었어 — 가사 생성 단계 확인")

MODEL = os.environ.get("LYRIA_MODEL") or "lyria-3-pro-preview"   # 전곡 $0.08 급(공식 가격표 260712) · clip(30s)=lyria-3-clip-preview
body = json.dumps({"model": MODEL, "input": prompt}).encode("utf-8")
j = None
last = ""
for attempt in range(3):   # 5xx·타임아웃만 재시도 — 4xx(안전필터·키·티어·쿼터)는 즉시 표면화(과금 이중 방지)
    try:
        r = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            data=body, headers={"x-goog-api-key": KEY, "content-type": "application/json"})
        with urllib.request.urlopen(r, timeout=420) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        break
    except urllib.error.HTTPError as e:
        try:
            last = "HTTP {} — {}".format(e.code, e.read().decode("utf-8", "replace")[:400])
        except Exception:
            last = "HTTP {}".format(e.code)
        if e.code < 500:
            fail("Lyria 호출 거절(키 티어·안전필터·쿼터 가능)", last)
    except Exception as e:
        last = str(e)[:300]
    if attempt < 2:
        print("  ⏳ Lyria 일시 오류 — 20s 후 재시도({}/3): {}".format(attempt + 1, last))
        time.sleep(20 * (attempt + 1))
if j is None:
    fail("Lyria 호출 실패(3회)", last)

# 오디오·텍스트 블록 추출 — 문서 계약: steps[].content[] {type:'audio', data:b64} · {type:'text', text}(실제 부른 가사).
#   preview 스키마 변동 대비 = 재귀 방어 탐색(§📰 관용 파싱 정신 — 미검출은 소리나는 실패).
audio_b64 = None
texts = []
def walk(o):
    global audio_b64
    if isinstance(o, dict):
        if o.get("type") == "audio" and isinstance(o.get("data"), str) and len(o["data"]) > 1000 and audio_b64 is None:
            audio_b64 = o["data"]
        if o.get("type") == "text" and isinstance(o.get("text"), str) and o["text"].strip():
            texts.append(o["text"].strip())
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)
walk(j)
if not audio_b64:
    fail("Lyria 응답에 오디오 없음(안전필터 차단 가능)", json.dumps(j, ensure_ascii=False)[:400])

try:
    raw = base64.b64decode(audio_b64)
except Exception as e:
    fail("오디오 디코드 실패 ({})".format(e))
ext, ctype = (".wav", "audio/wav") if raw[:4] == b"RIFF" else (".mp3", "audio/mpeg")   # 기본 MP3 · Pro WAV 옵션(문서)
key = "song_out/{}/song{}".format(ID, ext)
url = tg.r2_upload(raw, key, ctype) if tg.R2_ON else None
if not url:   # git 폴백(같은 출처 서빙 = 직다운 가능 · thumb_gen 폴백 관례)
    with open(os.path.join(OUT, "song" + ext), "wb") as f:
        f.write(raw)
    url = "song_out/{}/song{}".format(ID, ext)
    print("저장소: git 폴백(R2 미설정/실패)")

try:
    from zoneinfo import ZoneInfo
    ts = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")   # KST(§표기표준 d)
except Exception:
    ts = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
doc = {"v": 1, "ts": ts, "engine": "lyria", "model": MODEL,
       "title": (req.get("title") or "")[:60], "lyrics": (req.get("lyrics") or "")[:4000],
       "prompt": prompt[:2000], "url": url, "bytes": len(raw)}
if texts:
    doc["sung"] = texts[0][:4000]   # Lyria가 실제 부른 가사(응답 텍스트 블록) — 요청 가사와 다를 수 있어 정직 병기
p = os.path.join(OUT, "song.json")
tmp = p + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
os.replace(tmp, p)   # 원자 교체 = 레포 표준
print("song.json: 오디오 {}KB → {}".format(len(raw) // 1024, url))
