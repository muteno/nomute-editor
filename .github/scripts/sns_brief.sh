#!/usr/bin/env bash
# SNS 트렌드 AI 브리프 — 수집 스냅샷(TOP 10·검색어·레인)을 보고 '원인을 역추적'해 브리핑(운영자 260712 v6).
# 페르소나 = "친한 트렌드 애널리스트 · 호칭·이름 없이 친근 인사(KST · 운영자 260713) · SNS 결과→WebSearch로 원인·이상치 딥다이브·관련 링크 · 팬픽 문체 자연스러움 · 뉴스 신뢰선 사수".
# 게이트 3중: ① SNS_BRIEF=1(§📰-e 카나리아 — 기본 OFF 머지 → dispatch 실측 → 승격) ② 입력 다이제스트 동일 = 스킵(토큰 0 · 운영자 "내용 변화 없으면 낭비 말고 그대로") ③ 실패 = fail-soft(직전 brief 유지 · rc 0 — 뷰어는 파일 없으면 블록 미표시).
# 모델 = PIPE_MODEL(opus 4.8 · shared/model_env.sh — §🤖 생성/하드작업 축) · effort max · turns 8(리서치 = 원인·링크 다회 왕복) · timeout 600.
# --safe-mode(CLAUDE.md/스킬/MCP 비활성 · 내장 도구는 활성 유지 · --bare 절대 금지 = OAuth 즉사 §📰-d) · 폴오버 SSOT 경유(§📰-f).
# ⚠️ WebSearch/WebFetch = --allowedTools 명시 필수(analyze.sh·ask.sh·cardmake.sh 선례): 헤드리스는 미허용 도구를 '권한 대기'가 아니라 '즉시 거부(권한 없음)'로 처리 → 빠지면 원인 역추적이 6회 다 튕겨 '권한 열어줘' 반쪽 브리프만 나옴(실측 260713). --safe-mode는 도구를 켤 뿐 승인을 대신하지 않음.
set -u
[ "${SNS_BRIEF:-0}" = "1" ] || { echo "brief: OFF(SNS_BRIEF!=1) — 스킵"; exit 0; }
cd "$(git rev-parse --show-toplevel)"
. shared/model_env.sh
. shared/claude_transient.sh
MODEL="${SNS_BRIEF_MODEL:-$PIPE_MODEL}"
OUT_JSON="viewer/sns_brief.json"

# ── 입력 다이제스트(뷰어 mixTop 미러: 순위 정규화 라운드로빈 + 플랫폼 캡 4 — 표시 전용·랭킹 로직 무접촉) + 변화 해시 ──
DIG="$(python3 - <<'PY'
import json, math, hashlib, datetime as dt
KST = dt.timezone(dt.timedelta(hours=9))
_now = dt.datetime.now(KST)
def fresh(x):
    """[신규 진입] 판정 = first_seen(수집기 최초 관측 시각 · _annotate_rank 주입) 최근 6h 내 — 운영자 260714 "신상 딱지 ㄱ".
    구 스냅샷 무필드·파싱 실패 = 미표기(fail-soft). 프롬프트 전용(해시 미포함 = 딱지 소멸이 재생성 안 유발)."""
    try:
        return 0 <= (_now - dt.datetime.fromisoformat(str(x.get('first_seen')))).total_seconds() <= 6 * 3600
    except Exception:
        return False
def fmt_view(v):
    """조회수 → 만/억 단위 한국식(반올림). 다이제스트가 원시 콤마숫자(89,697,957)를 모델에 먹이면
    모델이 그걸 복사해 만단위 지시를 무시하던 근원 차단(분신술2) — 포맷을 코드가 결정론으로 보증."""
    v = v or 0
    if v >= 100_000_000:                       # 억
        s = ("%.1f" % (v / 100_000_000)).rstrip('0').rstrip('.')
        return "%s억" % s
    if v >= 10_000:                            # 만(반올림)
        return "{:,}만".format(round(v / 10_000))
    return "{:,}".format(v)
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
        pool.append({'plat': plat, 'sc': 1 - r / L, 'ht': math.log10(1 + (vw(x) or 0)), 't': tit(x), 'v': vw(x) or 0, 'x': x})
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
# 해시용 L(기존 필드 그대로 = 변화 감도 불변 — 댓글·URL 요동이 재생성 스킵 게이트를 안 흔들게) ↔ 프롬프트용 E(채널·링크·댓글 동봉).
# 운영자 260714 "누가 올렸는지 알면 나아질 것·가장 좋은 건 댓글 반응" — 수집기엔 이미 있던 채널·URL이 다이제스트서 잘려
# 모델이 제목만 들고 WebSearch 하다 원본을 못 짚던 근원 봉합(1위 235만 쇼츠 = 채널 '말해보카…외교부' 실측 260714).
L, E = ['[통합 TOP 10]'], ['[통합 TOP 10 — 항목마다 채널(업로더)·링크, 큰 영상엔 시청자 인기 댓글 · [신규 진입] = 최근 6시간 내 처음 관측(신상)]']
for i, it in enumerate(top):
    ln = f"{i+1}위 [{it['plat']}] {it['t'][:70]}" + (f" · 조회 {fmt_view(it['v'])}" if it['v'] else '')
    L.append(ln)
    x = it.get('x') or {}
    ch = str(x.get('channel') or x.get('account') or '').strip()
    if ch: ln += f" · 채널 {ch[:40]}"
    u = str(x.get('url') or '')
    if u.startswith('http'): ln += f" · {u[:110]}"
    if fresh(x): ln += ' · [신규 진입]'
    E.append(ln)
    cm = [c for c in (x.get('comments') or []) if isinstance(c, dict) and c.get('text')]
    if cm:
        E.append('   ↳ 인기 댓글: ' + ' / '.join('"' + str(c['text'])[:70] + '"' + (f"(좋아요 {c.get('likes')})" if c.get('likes') else '') for c in cm[:3]))
tail = []
tail.append('[구글 급상승 검색어] ' + ' · '.join((g.get('query') or '') + '(' + (g.get('traffic') or '') + ')' for g in gt[:8]))
tail.append('[유튜브 인기] ' + ' / '.join((v.get('title') or '')[:40] for v in yt[:5]))
tail.append('[유튜브 뉴스] ' + ' / '.join((v.get('title') or '')[:40] for v in ytn[:5]))
tail.append('[쇼츠] ' + ' / '.join((v.get('title') or '')[:40] for v in sh[:5]))
tail.append('[틱톡] ' + ' / '.join(((t.get('title') or ('@' + (t.get('account') or '')))[:40]) for t in tk[:5]))
body = '\n'.join(L + tail)
PVER = 'brief-v11-260714-2tier-bold'   # 캐시 1회 무효화 = v11: 강조 2층(*별표1*=강조색 / **별표2**=볼드만 · 운영자 260714 "모두 통일" — 채널 브리프와 강조 문법 일치) · v10 [신규 진입] 신상 딱지(first_seen 6h) · v9 이슈 원장 감쇠+채널·URL·댓글, v8 호칭 제거, v7 참고자료 카드 유지
print(hashlib.sha256((PVER + '\n' + body).encode()).hexdigest()[:16])
print('\n'.join(E + tail))
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

KST_NOW="$(TZ='Asia/Seoul' date '+%Y-%m-%d %H:%M %A')"   # 발화 기준 = 항상 한국시(§📐-d)
# 구 BRIEF_TO(호칭) = 폐지(운영자 260713 "호칭 그냥 빼주셈" — 이름·호칭 없이 친근 톤만 유지)

# ── 이슈 원장(장기 투숙 이슈 감쇠 · 운영자 260714 "1번 말했으면, 2번은 언급만, 3번부터는 아예 빼줘") ──
# 직전 브리프들이 다룬 이슈 목록(sns_brief.json issues — git 이력은 리라이트·shallow라 부적격 → 파일 축적).
# 로드 실패·필드 부재 = 빈 원장(전부 새 이슈 취급 · fail-soft — 원장이 브리프를 못 죽임).
LEDGER="$(python3 - <<'PY' 2>/dev/null || true
import json
try:
    xs = json.load(open('viewer/sns_brief.json')).get('issues') or []
except Exception:
    xs = []
for x in xs:
    k = str(x.get('key') or '').strip()
    if k:
        print(f"- {k[:40]} · 등장 {int(x.get('n') or 1)}회 · 마지막 {str(x.get('last') or '')[:10]}")
PY
)"

PROMPT="너는 지금 소셜 트렌드를 짚어주는 친한 트렌드 애널리스트다. 단순 목록·요약이 아니라, 'SNS에서 뭐가 떴는지'를 보고 '왜 떴는지 그 원인'을 직접 찾아 확인해서 이야기해준다. 지금 시각(한국): ${KST_NOW}.

[여는 인사]
가볍고 친근하게, 호칭·이름 없이 열어라 — 예: '월요일 아침이니까 트렌드 빠르게 짚어줄게.' (이름 부르기·'안녕 ○○'·'사장님' 류 호칭 전면 금지 · 딱딱한 비서 톤 금지 · 매번 똑같은 문장은 피하기.)

[핵심 임무 — 원인을 역추적하라 (제일 중요 · 항상)]
아래 데이터는 'SNS 결과'다. 화면엔 SNS가 먼저 보이지만, 너는 그 결과를 보고 '뒤로 원인을 파헤쳐' 확인해야 한다. 이건 예외 없는 규칙 — 주제가 축구든 정치든 연예든 밈이든 재난이든 사건이 뭐든, **무조건 매번** 원인을 역추적한다(아래 축구는 방식을 보여주는 예시일 뿐 · 거기 얽매이지 마라). 순서:
1. 크로스플랫폼으로 크게 뜬 주제(여러 플랫폼서 동시에 터진 것)를 먼저 잡아라.
2. 그 주제가 왜 지금 떴는지 원인(실제 사건·경기·발표·이슈·인물 등 무엇이든)을 WebSearch로 찾아라. 예시(형식 이해용): 축구·월드컵이 떴으면 '한국시 어제~오늘 무슨 경기가 있었나'를 검색해 실제 경기/사건을 확인해 서사로 풀어라(누가 붙었고 누가 활약했는지 등 — 검색으로 확인된 사실만). 다른 주제도 똑같이: 정치면 무슨 발표·사건, 연예면 무슨 컴백·논란, 밈이면 어디서 시작됐는지를 찾아라.
3. SNS 트렌드와 찾은 원인이 실제로 맞물리는지 확인하라. 맞으면 그 인과로 설명, 안 맞으면 다른 원인을 더 찾고, 정 원인을 못 찾으면 원인 없이 그냥 트렌드만 담백하게 브리핑하라(억지로 지어내지 마라).
4. 표준편차를 벗어난 이상치(나머지 대비 압도적인 단일 영상·계정)는 따로 딥다이브. TOP 10 각 항목엔 채널(업로더)·링크가, 큰 영상엔 시청자 인기 댓글이 붙어 있다 — 이걸 출발점으로: ① '누가 올렸나'부터 짚어라(채널명이 곧 업로더 — 기업·기관·앱 채널이면 광고·캠페인 영상일 확률이 높다) ② 붙은 유튜브 링크를 WebFetch로 직접 열어 설명·맥락을 확인하고, 막히면 https://www.youtube.com/oembed?url=<링크>&format=json 으로 제목·채널을 재확인하라 ③ 채널명+제목 키워드로 WebSearch. 확인되면 제목(원문 + 한국어 뜻)·내용·등장 인물·다루는 사건을 짧게 설명하고 확인한 관련 링크 1개를 붙이고, 인기 댓글이 있으면 시청자 반응으로 1개쯤 자연스럽게 녹여라. 그래도 정체를 못 짚으면 지금처럼 솔직하게 '못 짚었다'로(날조 금지).

[장기 투숙 이슈 — 재탕 감쇠 (운영자 확립 260714 · 항상)]
아래 '이슈 원장'은 직전 브리핑들이 이미 다룬 이슈 목록이다(등장 n회). 데이터 순위에 계속 떠 있어도 이 규칙대로:
- 원장에 없는 이슈 = 평소대로 원인 역추적 풀서사.
- 등장 1회였던 이슈 = 이번엔 서사 금지 — 지나가는 한 줄만('파장이 기네'·'아직 안 식었네' 식 · 지난 수치·링크 재반복 금지).
- 등장 2회 이상이었던 이슈 = 아예 빼라(순위에 있어도 언급 0 — 그 자리는 다른 이슈에 줘라).
- 유일한 예외 = '새 국면': 그 이슈에 새 사건·발표·반전·후속타가 WebSearch로 확인될 때만 새 이슈처럼 다루되, 새 국면 내용만(지난 얘기 재요약 금지).
- 감쇠로 비운 자리 = [신규 진입] 딱지 항목부터 우선 검토해 채워라(최근 6시간 내 처음 관측된 신상 = 오늘의 진짜 새 소식). 단 '[신규 진입]' 딱지 문구 자체는 판단 재료일 뿐 — 본문에 베껴 쓰지 마라. 이슈 원장 규칙이 딱지보다 우선이다(원장에 있는 이슈는 딱지가 붙어도 감쇠 그대로 — 딱지는 '원장에 없는 새 이슈' 고를 때만 쓰는 신호).
<이슈 원장>
${LEDGER:-(비어 있음 — 전부 새 이슈)}

[근거·신뢰선 — 절대 준수]
- 원인·사건·인물·번역·링크는 반드시 WebSearch/WebFetch로 실제 확인한 것만 써라. 확인 안 된 건 단정 말고 빼거나 '~로 보인다' 수준으로.
- 링크는 실제로 검색·확인한 URL만(지어낸 주소 절대 금지). 못 찾으면 링크 없이.
- 조회수·순위 등 수치는 데이터에 적힌 표기 그대로. 날조·과장 절대 금지.

[말투 — 살아있게(팬픽·웹소설 문체)]
친근한 소식통 톤. 단문으로 툭툭 끊되 길이 섞기 · 종결을 '~다'에 가두지 말고 '~더라(현장 톤)·~네(발견)·~거든(배경)'을 1~2번 · 수치는 끊어 던지고 자기정정으로 강조('8,970만 조회. 그것도 하루 만에.') · '무려·심지어·하필·그것도' 훅 · 감정은 장면으로 보여주기('충격'→'댓글이 만 개 넘었다') · 대시(—)·쉼표로 뜸. 금지: 느낌표 떡칠·하트·2인칭 호칭(여러분/너)·신파·오글·말줄임(...) 남발.

[형식]
- 자연스러운 문단 흐름: 인사 → 크게 뜬 주제와 그 원인(서사) → 이상치 딥다이브 + 링크. 6~14줄 안팎.
- 강조는 2층: 가장 크게 튄 주제·수치 = *별표 하나*(1층 = 강조색·표준편차 벗어나는 것만) · 그다음 어느정도 중요한 대목 = **별표 둘**(2층 = 볼드만·강조색 아님 · 문장에서 눈이 먼저 가야 할 핵심 명사·동사구). 1층 0~1개·2층 1~3개 정도. 별표 사이 줄바꿈 금지 · 별표 짝 반드시 닫기.
- 관련 링크는 [보이는 텍스트](URL) 형식 또는 URL 그대로 붙여라. 헤더·번호목록·마크다운 제목·이모지 금지.

[참고자료 스크랩 카드 — 본문 링크와 짝 (매번)]
본문에 [보이는 텍스트](URL)로 붙인 참고 기사·어려운 키워드·딥다이브 주제 각각에 대해, 응답 맨 끝에 '===참고자료===' 한 줄을 쓰고 그 아래 **한 줄에 카드 하나씩** JSON으로 적어라(블록 안에 다른 텍스트·마크다운 금지):
{\"url\":\"본문 링크와 완전히 동일한 URL\",\"term\":\"본문에서 링크로 쓴 보이는 텍스트 그대로\",\"title\":\"기사/영상 원제목\",\"source\":\"매체·채널명\",\"body\":\"보도자료 리드문처럼 사실 위주 3~5문장. 누가·언제·무엇을·왜가 담기게, WebSearch/WebFetch로 확인한 내용만.\"}
- url이 본문 링크와 다르면 짝이 안 맞아 카드가 안 뜬다 — 반드시 동일하게.
- 확인 못 한 항목은 카드를 만들지 마라(날조 금지). 카드 1~4개.
- body는 뉴스 요약 톤(담백·사실)으로 — 본문 산문의 팬픽 톤과 달리 건조하게.

[이슈 원장 갱신 — 응답 맨 끝 (매번)]
'===참고자료===' 블록이 끝나면 '===이슈원장===' 한 줄을 쓰고, 그 아래 **한 줄에 하나씩** JSON으로 이번 원장 전체를 다시 적어라(블록 안에 다른 텍스트 금지):
{\"key\":\"이슈를 알아볼 짧은 이름(30자 안)\",\"n\":등장횟수}
- 이번에 풀서사로 새로 다룬 이슈 = n:1로 추가.
- 원장에 있던 이슈 = 빠짐없이 그대로 옮겨 적되, 이번에 또 등장시켰으면(스치는 한 줄 포함) n+1.
- 새 국면으로 다뤘으면 그 새 국면을 별도 이슈 n:1로 추가(옛 이슈 줄은 그대로).
- 원장에 있는데 이번에 안 다룬 이슈도 그대로 옮겨 적어라(지우기·지어내기 금지).

[데이터 = SNS 결과(여기서 원인을 역추적)]
$BODY"

claude_preflight "$MODEL" || true   # 죽은 활성계정 침묵 행 공회전 소거(운영자 260717 — 실측: 침묵 행은 본선 600s를 통째로 태움 · 산 계정 = 수초 · 전멸 = 본선 강행 fail-soft)
out=""
for _try in 1 2 3 4; do
  out="$(printf '%s' "$PROMPT" | timeout 600 claude -p --model "$MODEL" --effort max --safe-mode --max-turns 8 \
    --allowedTools "WebFetch,WebSearch" \
    --disallowedTools "Bash,Edit,Write,Read,Glob,Grep,Task,NotebookEdit,TodoWrite" 2>/tmp/brief.err)"; rc=$?
  if [ $rc -ne 0 ] || [ -z "$out" ]; then
    if claude_failover "$out$(cat /tmp/brief.err 2>/dev/null)"; then continue; fi   # 쿼터 = 4계정 체인 1단씩(§📰-f)
    echo "::warning::brief 생성 실패(rc=$rc) — 직전 brief 유지(fail-soft)"; exit 0
  fi
  break
done
[ -z "$out" ] && { echo "::warning::brief 빈 출력 — 직전 유지"; exit 0; }

BRIEF_TEXT="$out" BRIEF_SHA="$SHA" python3 - <<'PY'
import json, os, datetime, re, ssl, urllib.request
KST = datetime.timezone(datetime.timedelta(hours=9))
raw = (os.environ.get('BRIEF_TEXT') or '').strip()
# ── 참고자료 스크랩 카드 분리(v7 · 운영자 260712 "참고 기사 = 인앱 팝업") — 관용 3층(§📰-c 정신):
#    구분자 유무·JSON 줄 파손 전부 fail-soft(파손 줄 스킵 · 블록 전체 실패 = refs [] · 본문은 항상 산다)
body_txt, refs = raw, []
# 마커 2종(참고자료·이슈원장) 분리 — 순서 무관(모델이 블록 순서를 바꿔도 산다) · 마커 부재 = 본문 전체 유지(기존 관용 동일)
parts = re.split(r'\n=+\s*(참고자료|이슈원장)\s*=+\s*\n?', raw)
blocks = {}
if len(parts) > 2:
    body_txt = parts[0]
    for _i in range(1, len(parts) - 1, 2):
        blocks.setdefault(parts[_i], parts[_i + 1])
if blocks.get('참고자료'):
    for ln in blocks['참고자료'].splitlines():
        ln = ln.strip().lstrip('-').strip()
        if not (ln.startswith('{') and ln.endswith('}')):
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        u = str(r.get('url') or '')
        if not u.startswith(('http://', 'https://')):
            continue
        refs.append({'url': u[:500], 'term': str(r.get('term') or '')[:80], 'title': str(r.get('title') or '')[:160],
                     'source': str(r.get('source') or '')[:60], 'body': str(r.get('body') or '')[:900]})
        if len(refs) >= 4:
            break
# ── og:image 후처리(결정론 · 모델 부담 0) — 기사 대표 이미지: 실패 = 이미지 없이(fail-soft · 데이터센터 403 매체 상정) ──
CTX = ssl.create_default_context()
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
      'Accept-Language': 'ko-KR,ko;q=0.9'}
for r in refs:
    try:
        req = urllib.request.Request(r['url'], headers=UA)
        html = urllib.request.urlopen(req, timeout=8, context=CTX).read(400_000).decode('utf-8', 'ignore')
        im = re.search(r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']', html) \
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']', html)
        if im:
            u = im.group(1).strip()
            if u.startswith('//'):
                u = 'https:' + u
            if u.startswith(('http://', 'https://')):
                r['image'] = u[:600]
    except Exception:
        pass   # 이미지 = 있으면 좋고(뷰어 onerror 숨김) — 실패가 브리프를 못 죽임
# ── 이슈 원장 병합(장기 투숙 감쇠 · 운영자 260714 "1번=서사·2번=언급만·3번부터=제외"의 기억장치) ──
# 모델 = 원장 전체 재기술 → 코드가 보증: {정형 검증 · 직전 원장과 합집합(모델 누락 = 망각 방지 carry) · n 불변 항목 =
# last 보존(만료 시계 유지)·n 변동/신규 = 오늘 도장 · 7일 무등장 만료 · 캡 24}. 블록 부재·전줄 파손 = 직전 원장 그대로(fail-soft).
try:
    prev_led = json.load(open('viewer/sns_brief.json')).get('issues') or []
except Exception:
    prev_led = []
prev_by = {}
for x in prev_led:
    k = str(x.get('key') or '').strip()[:40]
    if k:
        try: pn = max(1, min(99, int(x.get('n') or 1)))
        except Exception: pn = 1
        prev_by[k] = {'key': k, 'n': pn, 'last': str(x.get('last') or '')[:10]}
today = datetime.datetime.now(KST).date().isoformat()
led = {}
for ln in (blocks.get('이슈원장') or '').splitlines():
    ln = ln.strip().lstrip('-').strip()
    if not (ln.startswith('{') and ln.endswith('}')):
        continue
    try: r = json.loads(ln)
    except Exception: continue
    k = str(r.get('key') or '').strip()[:40]
    if not k: continue
    try: n = max(1, min(99, int(r.get('n') or 1)))
    except Exception: n = 1
    pv = prev_by.get(k)
    led[k] = {'key': k, 'n': n, 'last': (pv['last'] if pv and pv['n'] == n and pv['last'] else today)}
    if len(led) >= 40: break
issues = list(led.values()) if led else []
for k, x in prev_by.items():   # 모델이 빠뜨린 직전 항목 carry(망각 방지) — 원장 블록 자체가 없으면 직전 전체 유지
    if k not in led:
        issues.append(x)
cut = (datetime.datetime.now(KST) - datetime.timedelta(days=7)).date().isoformat()
issues = [x for x in issues if (x.get('last') or today) >= cut]
issues.sort(key=lambda x: (x.get('last') or '', x.get('n') or 0), reverse=True)
issues = issues[:24]
# 줄바꿈 보존(요점별 개행 = 운영자 요구 · 구 ' '.join(split())는 개행 뭉갬) — 줄별 trim + 빈줄 3+ → 1 + 상한
lines = [ln.rstrip() for ln in body_txt.replace('\r\n', '\n').split('\n')]
t = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()[:1600]   # 독해 상한(원인+딥다이브 = 길어짐 · 과출력 가드 · refs 분리 후 본문에만 적용)
json.dump({'text': t, 'updated': datetime.datetime.now(KST).isoformat(timespec='seconds'),
           'src_hash': os.environ.get('BRIEF_SHA') or '', 'refs': refs, 'issues': issues},
          open('viewer/sns_brief.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('brief 저장:', len(t), '자', '·', t.count(chr(10)) + 1, '줄', '· refs', len(refs), '개(이미지', sum(1 for r in refs if r.get('image')), ') · 이슈원장', len(issues), '건')
PY
echo "brief: 갱신 완료($SHA)"
