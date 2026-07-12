#!/usr/bin/env bash
# SNS 트렌드 AI 브리프 — 수집 스냅샷(TOP 10·검색어·레인)을 비서 페르소나 1콜로 브리핑(운영자 260712).
# 페르소나 = "사장에게 보고하는 비서 · 1분 독해 · 흐름/최대 이슈 놓침 없이"(운영자 문구 그대로).
# 게이트 3중: ① SNS_BRIEF=1(§📰-e 카나리아 — 기본 OFF 머지 → dispatch 실측 → 승격) ② 입력 다이제스트 동일 = 스킵(토큰 0 · 운영자 "내용 변화 없으면 낭비 말고 그대로") ③ 실패 = fail-soft(직전 brief 유지 · rc 0 — 뷰어는 파일 없으면 블록 미표시).
# 모델 = PIPE_MODEL(opus 4.8 · shared/model_env.sh — §🤖 생성/하드작업 축) · effort max(운영자 지정 · 단발 분석·도구 0·turns 1) ·
# --safe-mode(stdin 자기완결 = CLAUDE.md/도구/스킬 불필요 — judge 선례 cache_w −97.2% · --bare 절대 금지 = OAuth 즉사 §📰-d) · 폴오버 SSOT 경유(§📰-f).
set -u
[ "${SNS_BRIEF:-0}" = "1" ] || { echo "brief: OFF(SNS_BRIEF!=1) — 스킵"; exit 0; }
cd "$(git rev-parse --show-toplevel)"
. shared/model_env.sh
. shared/claude_transient.sh
MODEL="${SNS_BRIEF_MODEL:-$PIPE_MODEL}"
OUT_JSON="viewer/sns_brief.json"

# ── 입력 다이제스트(뷰어 mixTop 미러: 순위 정규화 라운드로빈 + 플랫폼 캡 4 — 표시 전용·랭킹 로직 무접촉) + 변화 해시 ──
DIG="$(python3 - <<'PY'
import json, math, hashlib
d = json.load(open('viewer/sns_trends.json'))
gt = d.get('gtrends') or []; yt = d.get('youtube') or []; ytn = d.get('youtube_news') or []
sh = d.get('shorts') or []; tk = (d.get('tiktok') or {}).get('videos') or []
pool, seen = [], set()
def lane(plat, arr, n, key, tit, vw):
    s = arr[:n]; L = len(s) or 1
    for r, x in enumerate(s):
        k = key(x)
        if not k or k in seen: continue
        seen.add(k)
        pool.append({'plat': plat, 'sc': 1 - r / L, 'ht': math.log10(1 + (vw(x) or 0)), 't': tit(x), 'v': vw(x) or 0})
lane('구글검색', gt, 8, lambda g: 'g:' + (g.get('query') or ''), lambda g: g.get('query') or '', lambda g: 0)
lane('유튜브', yt, 5, lambda v: v.get('url'), lambda v: v.get('title') or '', lambda v: v.get('views'))
lane('유튜브', ytn, 5, lambda v: v.get('url'), lambda v: v.get('title') or '', lambda v: v.get('views'))
lane('유튜브쇼츠', sh, 12, lambda v: v.get('url'), lambda v: v.get('title') or '', lambda v: v.get('views'))
lane('틱톡', tk, 10, lambda t: t.get('url'), lambda t: (t.get('title') or ('@' + (t.get('account') or ''))), lambda t: t.get('views'))
pool.sort(key=lambda x: (-x['sc'], -x['ht']))
top, cap = [], {}
for it in pool:
    p = '유튜브' if it['plat'].startswith('유튜브') else it['plat']
    if cap.get(p, 0) >= 4: continue
    cap[p] = cap.get(p, 0) + 1
    top.append(it)
    if len(top) >= 10: break
L = ['[통합 TOP 10]']
for i, it in enumerate(top):
    L.append(f"{i+1}위 [{it['plat']}] {it['t'][:70]}" + (f" · 조회 {it['v']:,}" if it['v'] else ''))
L.append('[구글 급상승 검색어] ' + ' · '.join((g.get('query') or '') + '(' + (g.get('traffic') or '') + ')' for g in gt[:8]))
L.append('[유튜브 인기] ' + ' / '.join((v.get('title') or '')[:40] for v in yt[:5]))
L.append('[유튜브 뉴스] ' + ' / '.join((v.get('title') or '')[:40] for v in ytn[:5]))
L.append('[쇼츠] ' + ' / '.join((v.get('title') or '')[:40] for v in sh[:5]))
L.append('[틱톡] ' + ' / '.join(((t.get('title') or ('@' + (t.get('account') or '')))[:40]) for t in tk[:5]))
body = '\n'.join(L)
PVER = 'brief-v2-260712'   # 프롬프트 개정 시 올림 = 입력 동일해도 캐시 1회 무효화(줄바꿈·별표강조·만단위 반올림 페르소나)
print(hashlib.sha256((PVER + '\n' + body).encode()).hexdigest()[:16])
print(body)
PY
)" || { echo "::warning::brief 다이제스트 실패 — 직전 유지"; exit 0; }
SHA="$(printf '%s\n' "$DIG" | head -1)"
BODY="$(printf '%s\n' "$DIG" | tail -n +2)"
[ -z "$BODY" ] && { echo "::warning::brief 입력 빈 값 — 직전 유지"; exit 0; }
PREV="$(python3 -c "import json;print(json.load(open('$OUT_JSON')).get('src_hash',''))" 2>/dev/null || echo '')"
if [ -n "$SHA" ] && [ "$SHA" = "$PREV" ]; then
  echo "brief: 입력 동일($SHA) — 스킵(토큰 0 · 운영자 '변화 없으면 그대로')"
  exit 0
fi

PROMPT="너는 사장에게 SNS 트렌드를 브리핑하는 유능하고 감각 있는 비서다. 사장이 1분 안에 흐름·최대 이슈·플랫폼별 유행을 놓침 없이 파악하게 하라.
말투 = 딱딱한 보고서 말고 곁에서 짚어주는 비서 톤(간결하되 생기·과하지 않은 위트 · '사장님,'으로 시작해도 좋다). 단 사실은 데이터에 있는 것만 — 날조·과장·데이터 밖 배경지식 추정 절대 금지.
형식(엄수):
- 요점별로 줄을 바꿔라(한 줄에 몰아쓰지 말 것). 총 4~7줄.
- 가장 중요한 포인트·핵심 수치는 *별표*로 감싸 강조하라(예: *조회 8,970만*, *틱톡이 압도*).
- 수치는 만 단위로 반올림해 표기(예: 8,970만 · 1.2억 · 63만+). 원시 숫자(89,697,957) 금지.
- 헤더·번호목록·마크다운 제목·이모지는 쓰지 마라. 줄바꿈과 *별표 강조*만 허용.

[데이터]
$BODY"

out=""
for _try in 1 2 3 4; do
  out="$(printf '%s' "$PROMPT" | timeout 300 claude -p --model "$MODEL" --effort max --safe-mode --max-turns 1 \
    --disallowedTools "Bash,Edit,Write,Read,Glob,Grep,WebSearch,WebFetch,Task,NotebookEdit,TodoWrite" 2>/tmp/brief.err)"; rc=$?
  if [ $rc -ne 0 ] || [ -z "$out" ]; then
    if claude_failover "$out$(cat /tmp/brief.err 2>/dev/null)"; then continue; fi   # 쿼터 = 4계정 체인 1단씩(§📰-f)
    echo "::warning::brief 생성 실패(rc=$rc) — 직전 brief 유지(fail-soft)"; exit 0
  fi
  break
done
[ -z "$out" ] && { echo "::warning::brief 빈 출력 — 직전 유지"; exit 0; }

BRIEF_TEXT="$out" BRIEF_SHA="$SHA" python3 - <<'PY'
import json, os, datetime, re
KST = datetime.timezone(datetime.timedelta(hours=9))
t = (os.environ.get('BRIEF_TEXT') or '').strip()
# 줄바꿈 보존(요점별 개행 = 운영자 요구 · 구 ' '.join(split())는 개행 뭉갬) — 줄별 trim + 빈줄 3+ → 1 + 상한
lines = [ln.rstrip() for ln in t.replace('\r\n', '\n').split('\n')]
t = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()[:1000]   # 1분 독해 상한(과출력 가드)
json.dump({'text': t, 'updated': datetime.datetime.now(KST).isoformat(timespec='seconds'),
           'src_hash': os.environ.get('BRIEF_SHA') or ''},
          open('viewer/sns_brief.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('brief 저장:', len(t), '자', '·', t.count(chr(10)) + 1, '줄')
PY
echo "brief: 갱신 완료($SHA)"
