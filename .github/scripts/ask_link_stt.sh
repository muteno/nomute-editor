#!/usr/bin/env bash
# 요약 요청 링크가 '미디어'일 때 — 그 영상·음성을 전사해 텍스트로 돌려준다(운영자 260731
#   "미디어면 large v3로 전사시킬 수 있어? 그래서 그 전사된 내용을 활용하게").
# 레일 = nb-make 정본 그대로 계승(재설계 0): 자막 우선(다운로드 없음·경량) → 없으면 오디오만 받아
#   Whisper large-v3 STT(ly_stt.py) → nb_sub.py 로 타임코드 전사 통일.
# 사용: bash ask_link_stt.sh <url> <출력 txt 경로>
#   출력 = "[mm:ss] 문장" 줄들(맨 앞 2줄 = 제목·출처 메타). 실패 = rc≠0 + stderr 사유(호출부가 fail-soft 처리).
# 캡 = 자막 경로 ASK_LINK_MAX_SEC(기본 4시간) · STT 폴백 ASK_LINK_STT_MAX_SEC(기본 1시간) — nb 와 동일 정직 거절.
set -uo pipefail

URL="${1:-}"
OUT="${2:-}"
[ -n "$URL" ] && [ -n "$OUT" ] || { echo "usage: ask_link_stt.sh <url> <out.txt>" >&2; exit 2; }

MAX_SEC="${ASK_LINK_MAX_SEC:-14400}"
STT_MAX_SEC="${ASK_LINK_STT_MAX_SEC:-3600}"
WD="$(mktemp -d)"
trap 'rm -rf "$WD"' EXIT

command -v yt-dlp >/dev/null 2>&1 || python3 -c "import yt_dlp" 2>/dev/null || timeout 240 pip3 install -q -U --pre "yt-dlp[default]" >&2 || { echo "yt-dlp 설치 실패" >&2; exit 1; }

COOKIES=""
if [ -n "${YT_COOKIES:-}" ]; then printf '%s\n' "$YT_COOKIES" > "$WD/ck.txt"; COOKIES="--cookies $WD/ck.txt"; fi

# 자가치유 래퍼(nb-make 정본) — 1차 실패 시 대체 클라이언트(nsig/서명 우회) 재시도
ydl() {   # $1=출력파일 나머지=yt-dlp 인자
  local out="$1"; shift
  python3 -m yt_dlp --socket-timeout 30 $COOKIES "$@" > "$out" 2>"$WD/err.txt" && return 0
  python3 -m yt_dlp --socket-timeout 30 $COOKIES --extractor-args "youtube:player_client=tv,mweb,web_safari,default" "$@" > "$out" 2>>"$WD/err.txt" && return 0
  tail -c 400 "$WD/err.txt" >&2
  return 1
}

# ── 메타(제목·길이·자막 유무) ──
ydl "$WD/meta_raw.json" --skip-download --no-playlist --dump-single-json "$URL" || { echo "링크 정보 조회 실패(비공개·삭제·지역제한·서명 잠금 등)" >&2; exit 1; }
WD="$WD" MAX_SEC="$MAX_SEC" python3 - <<'PY' || { echo "메타 파싱/길이 게이트 실패" >&2; exit 1; }
import json, os, sys
wd = os.environ["WD"]
y = json.load(open(f"{wd}/meta_raw.json", encoding="utf-8"))
dur = int(y.get("duration") or 0)
cap = int(os.environ["MAX_SEC"])
if dur and dur > cap:
    print(f"미디어 {dur//60}분 — 전사 상한({cap//60}분) 초과", file=sys.stderr)
    sys.exit(1)
meta = {"title": (y.get("title") or "")[:300], "channel": (y.get("channel") or y.get("uploader") or "")[:100],
        "url": y.get("webpage_url") or "", "dur": dur, "lang": (y.get("language") or "")[:8]}
json.dump(meta, open(f"{wd}/meta.json", "w", encoding="utf-8"), ensure_ascii=False)
PY

LANGP="$(python3 -c "import json;m=json.load(open('$WD/meta.json'));l=m.get('lang') or '';print((l+','+l.split('-')[0]+',' if l else '')+'ko,en')")"

# ── 자막 2패스(수동 → 자동) — 영상 다운로드 없음 ──
mkdir -p "$WD/sub_man" "$WD/sub_auto"
python3 -m yt_dlp --skip-download --no-playlist --socket-timeout 30 $COOKIES \
  --write-subs --no-write-auto-subs --sub-langs "$LANGP" --sub-format "vtt/srt/best" \
  -o "$WD/sub_man/x.%(ext)s" "$URL" >/dev/null 2>&1 || true
python3 .github/scripts/nb_sub.py --vtt "$WD/sub_man" "$LANGP" subs > "$WD/tr.json" 2>/dev/null || echo '{"src":"","rows":[]}' > "$WD/tr.json"
ROWS="$(python3 -c "import json;print(len(json.load(open('$WD/tr.json')).get('rows') or []))" 2>/dev/null || echo 0)"
if [ "$ROWS" -lt 5 ]; then
  python3 -m yt_dlp --skip-download --no-playlist --socket-timeout 30 $COOKIES \
    --write-auto-subs --no-write-subs --sub-langs "$LANGP" --sub-format "vtt/srt/best" \
    -o "$WD/sub_auto/x.%(ext)s" "$URL" >/dev/null 2>&1 || true
  python3 .github/scripts/nb_sub.py --vtt "$WD/sub_auto" "$LANGP" subs-auto > "$WD/tr.json" 2>/dev/null || echo '{"src":"","rows":[]}' > "$WD/tr.json"
  ROWS="$(python3 -c "import json;print(len(json.load(open('$WD/tr.json')).get('rows') or []))" 2>/dev/null || echo 0)"
fi
echo "자막 전사 ${ROWS}줄" >&2

# ── 자막 없으면 Whisper large-v3 STT 폴백(ly 레일) ──
if [ "$ROWS" -lt 5 ]; then
  DUR="$(python3 -c "import json;print(json.load(open('$WD/meta.json')).get('dur') or 0)")"
  if [ "${DUR:-0}" -gt "$STT_MAX_SEC" ] 2>/dev/null; then
    echo "자막 없음 + 길이 ${DUR}s > STT 상한 ${STT_MAX_SEC}s — 전사 거절" >&2; exit 1
  fi
  bash apps/ly/setup.sh >&2 || { echo "STT 환경 준비 실패" >&2; exit 1; }   # ffmpeg+faster-whisper+yt-dlp+large-v3(멱등·단일출처)
  python3 -m yt_dlp -x --audio-format mp3 --postprocessor-args "ffmpeg:-ar 16000 -ac 1 -b:a 48k" --no-playlist --socket-timeout 30 $COOKIES -o "$WD/audio.%(ext)s" "$URL" >/dev/null 2>&1 \
    || python3 -m yt_dlp -x --audio-format mp3 --postprocessor-args "ffmpeg:-ar 16000 -ac 1 -b:a 48k" --no-playlist --socket-timeout 30 $COOKIES --extractor-args "youtube:player_client=tv,mweb,web_safari,default" -o "$WD/audio.%(ext)s" "$URL" >/dev/null 2>&1 \
    || { echo "오디오 다운로드 실패" >&2; exit 1; }
  python3 .github/scripts/ly_stt.py "$WD/audio.mp3" "" > "$WD/stt.txt" 2>/dev/null || { echo "Whisper large-v3 전사 실패" >&2; exit 1; }
  python3 .github/scripts/nb_sub.py --stt "$WD/stt.txt" > "$WD/tr.json" || { echo "전사 파싱 실패" >&2; exit 1; }
  ROWS="$(python3 -c "import json;print(len(json.load(open('$WD/tr.json')).get('rows') or []))" 2>/dev/null || echo 0)"
  echo "Whisper large-v3 전사 ${ROWS}줄" >&2
fi

[ "$ROWS" -ge 1 ] || { echo "전사 결과가 비었음" >&2; exit 1; }

WD="$WD" OUT="$OUT" ELAPSED="$SECONDS" METRICS="${ASK_LINK_METRICS:-metrics/asklink}" python3 - <<'PY'
import json, os
wd, out = os.environ["WD"], os.environ["OUT"]
m = json.load(open(f"{wd}/meta.json", encoding="utf-8"))
d = json.load(open(f"{wd}/tr.json", encoding="utf-8"))
src = {"subs": "제작자 자막", "subs-auto": "자동 자막", "stt": "Whisper large-v3 전사"}.get(d.get("src") or "", d.get("src") or "")
L = [f"제목: {m.get('title','')}" + (f" · {m['channel']}" if m.get("channel") else ""),
     f"원본: {m.get('url','')} · 길이 {int(m.get('dur') or 0)//60}분 · 전사 출처: {src}", ""]
for r in d.get("rows") or []:
    s = int(r.get("s") or 0)
    L.append(f"[{s//60:02d}:{s%60:02d}] {r.get('t','')}")
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
rows = len(d.get("rows") or [])
el = int(os.environ.get("ELAPSED") or 0)
dur = int(m.get("dur") or 0)
print(f"전사 저장: {out} ({rows}줄) · 영상 {dur}s · 소요 {el}s · 배율 {(el / dur):.2f}×RT" if dur else f"전사 저장: {out} ({rows}줄) · 소요 {el}s")
# 실측 shard(운영자 260731 "걸린시간을 유튜브 시간과 대조") — 뷰어 예상시간(nmEta 시드) 갱신 근거.
#   {영상길이·소요·경로}만 남기는 append-only 조각(런별 고유 파일 = 병렬 커밋 충돌 0 · metrics 관용구 계승).
try:
    md = os.environ.get("METRICS") or "metrics/asklink"
    os.makedirs(md, exist_ok=True)
    tag = (os.environ.get("GITHUB_RUN_ID") or "local") + "-" + (os.environ.get("GITHUB_RUN_ATTEMPT") or "1")
    rec = {"dur": dur, "elapsed": el, "src": d.get("src") or "", "rows": rows}
    p = f"{md}/{tag}.jsonl"
    with open(p, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
except Exception:
    pass   # 계측 실패가 전사를 막지 않는다
PY
