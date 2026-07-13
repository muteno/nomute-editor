#!/usr/bin/env bash
# ⑦ 블루스카이 인기 게시물 자동 번역 — 각 게시물에 topic(주제·부제)·ko(한국어 번역) 필드 부착(운영자 260713).
# 뷰어 bcard 렌더: [순위] 주제(부제) → 번역(제목) → @계정·원문(mut). 원문(text)은 그대로 보존(뷰어가 mut 병기).
# 게이트 3중(sns_brief.sh 계승): ① BSKY_TR=1(§📰-e 카나리아 — 기본 OFF 머지 → dispatch 실측 → 승격) ② 번역 대상 0 = 스킵(토큰 0) ③ 실패 = fail-soft(직전 번역 carry 유지 · rc 0 = 커밋 비차단).
# 증분: 직전 커밋(git HEAD)의 bsky[]에서 url+text 동일 항목의 topic/ko를 carry → 신규·본문변경분만 LLM(재번역 낭비 0 · sns_brief '입력 동일 스킵' 정신).
# 모델 = PIPE_MODEL(opus 4.8 · shared/model_env.sh — 생성/하드작업 축) · effort high(번역=판단 경량 · 리서치 아님) · turns 1 · timeout 300.
# --safe-mode(CLAUDE.md/스킬/MCP 비활성 · 내장도구 활성 · --bare 절대 금지 = OAuth 즉사 §📰-d) · 폴오버 SSOT 경유(§📰-f).
set -u
[ "${BSKY_TR:-0}" = "1" ] || { echo "bsky-tr: OFF(BSKY_TR!=1) — 스킵"; exit 0; }
cd "$(git rev-parse --show-toplevel)"
. shared/model_env.sh
. shared/claude_transient.sh
MODEL="${BSKY_TR_MODEL:-$PIPE_MODEL}"
JSON="viewer/sns_trends.json"
TGT="/tmp/bsky_targets.txt"

# ── 1) carry(직전 번역 승계) 반영 저장 + 번역 대상 추출 ──
#    직전 커밋 bsky[] {url,text → topic,ko} 를 현재 수집분에 url+text 동일 시 이식(결정론).
#    carry 실패(신규 게시물·본문 변경) = 번역 대상. 대상 프롬프트 = "i\t@계정\t원문" 탭 구분(TGT 파일).
NEED="$(python3 - "$JSON" "$TGT" <<'PY'
import json, sys, subprocess
path, tgt = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(path, encoding='utf-8'))
except Exception as e:
    print('ERR', e); sys.exit(0)   # 파일 파손 = 스킵(fail-soft)
cur = d.get('bsky') or []
# 직전 커밋 스냅샷(HEAD) — 이번 런 수집 전 버전(topic/ko 보유) · 없으면(첫 도입·최초 커밋) 빈 맵 = 전량 번역
prev_map = {}
try:
    raw = subprocess.run(['git', 'show', 'HEAD:' + path], capture_output=True, text=True, timeout=20)
    if raw.returncode == 0:
        for it in (json.loads(raw.stdout).get('bsky') or []):
            u = it.get('url')
            if u:
                prev_map[u] = it
except Exception:
    pass   # git 실패 = 전량 번역(과번역이지 손상 아님)
targets, lines = [], []
for i, it in enumerate(cur):
    p = prev_map.get(it.get('url'))
    if p and (p.get('text') or '') == (it.get('text') or '') and p.get('ko'):
        it['topic'] = p.get('topic') or ''   # carry(재번역 0)
        it['ko'] = p.get('ko') or ''
    else:
        txt = (it.get('text') or '').replace('\t', ' ').replace('\n', ' ').strip()
        if txt:
            targets.append(i)
            lines.append('%d\t@%s\t%s' % (i, it.get('account') or '', txt))
json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False)   # carry 반영 저장(대상 0이어도 이번 런 표시 보장)
open(tgt, 'w', encoding='utf-8').write('\n'.join(lines))
print(len(targets))
PY
)"
case "$NEED" in
  ERR*) echo "::warning::bsky-tr: sns_trends.json 파손 — 스킵($NEED)"; exit 0 ;;
  0)    echo "bsky-tr: 번역 대상 0(전량 carry) — 스킵(토큰 0)"; exit 0 ;;
  ''|*[!0-9]*) echo "::warning::bsky-tr: 대상 추출 실패($NEED) — 스킵"; exit 0 ;;
esac
echo "bsky-tr: 번역 대상 ${NEED}건 — LLM 호출"

# ── 2) LLM 배치 번역(1콜) ──
POSTS="$(cat "$TGT")"
PROMPT="아래는 블루스카이(주로 영어권 SNS) 인기 게시물이다. 각 게시물을 한국어로 자연스럽게 번역하고, 무슨 내용인지 주제를 짧은 명사구로 한 줄 붙여라.

규칙:
- 번역(ko) = 자연스러운 한국어. 원문 톤·뉘앙스 살리되 딱딱한 직역투 금지. 이모지·고유명사는 보존. 원문이 이미 한국어면 그대로.
- 주제(topic) = 5~16자 명사구(문장 아님). 예: '린지 그레이엄 발언 지적', '노르웨이 축구팀 찬사', '우울증 극복 감사 인사'. 인물·사건·감정의 핵심을 잡아라.
- 출력 = 게시물당 딱 한 줄 JSON: {\"i\":번호, \"topic\":\"주제\", \"ko\":\"번역\"}
- i(번호)는 입력의 앞 숫자 그대로. 순서·개수 그대로. JSON 줄들만 출력(설명·마크다운·코드펜스 금지).

[게시물 — '번호<탭>@계정<탭>원문']
${POSTS}"

out=""
for _try in 1 2 3 4; do
  out="$(printf '%s' "$PROMPT" | timeout 300 claude -p --model "$MODEL" --effort high --safe-mode --max-turns 1 \
    --disallowedTools "Bash,Edit,Write,Read,Glob,Grep,Task,NotebookEdit,TodoWrite,WebFetch,WebSearch" 2>/tmp/bskytr.err)"; rc=$?
  if [ $rc -ne 0 ] || [ -z "$out" ]; then
    if claude_failover "$out$(cat /tmp/bskytr.err 2>/dev/null)"; then continue; fi   # 쿼터 = 4계정 체인 1단씩(§📰-f)
    echo "::warning::bsky-tr 생성 실패(rc=$rc) — carry 유지(fail-soft)"; exit 0
  fi
  break
done
[ -z "$out" ] && { echo "::warning::bsky-tr 빈 출력 — carry 유지"; exit 0; }

# ── 3) 파싱·병합 저장(관용 3층 · 파손 줄 스킵 · i 매칭) ──
BSKY_OUT="$out" python3 - "$JSON" <<'PY'
import json, os, re, sys
path = sys.argv[1]
raw = os.environ.get('BSKY_OUT') or ''
try:
    d = json.load(open(path, encoding='utf-8'))
except Exception as e:
    print('::warning::bsky-tr 병합: 파일 재로드 실패', e); sys.exit(0)
cur = d.get('bsky') or []
by_i, n = {}, 0
for ln in raw.splitlines():
    ln = ln.strip().lstrip('-').strip()
    if not (ln.startswith('{') and ln.endswith('}')):
        continue
    try:
        r = json.loads(ln)
    except Exception:
        continue
    try:
        i = int(r.get('i'))
    except (TypeError, ValueError):
        continue
    if 0 <= i < len(cur) and (r.get('ko') or '').strip():
        by_i[i] = r
for i, r in by_i.items():
    cur[i]['topic'] = str(r.get('topic') or '').strip()[:40]
    cur[i]['ko'] = str(r.get('ko') or '').strip()[:300]
    n += 1
json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
print('bsky-tr: 번역 병합', n, '건 저장')
PY
echo "bsky-tr: 갱신 완료"
