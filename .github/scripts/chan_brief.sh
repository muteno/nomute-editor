#!/usr/bin/env bash
# 채널 요약(메뉴4) AI 브리프 — 인스타 채널 지표(insta_data.json)를 보고 '성장 서사 + 지금 상황 + 관리 전략'을 짚어주는 브리핑(운영자 260714 "초등학생도 아 이 채널 이렇게 성장해왔네·이래야겠네 전략이 뿅뿅").
# ⚠️ SNS 트렌드 브리프(sns_brief.sh·viewer/sns_brief.json)와 완전 별개 축 — 골격만 미러(운영자 "트렌드 요약 참고만·덮어씌우지 말고") · 출력 = viewer/chan_brief.json.
# 페르소나 = "채널을 같이 키우는 친한 그로스 애널리스트 · 호칭·이름 없이 친근 인사(KST) · 성장 서사 → 급변 원인 콕 → 데이터 근거 실행 전략 · 쉬운 말 · 수치 신뢰선 사수"(sns_brief v8 톤 계승).
# 구성 = 기간 5부(운영자 260714 "1년 전반부 총론만 나옴 → 7일/14일/28일/3개월/전체 총론 구분") — 출력 = sections[{k,label,text}] + text(전문 = 하위호환·마커 파싱 실패 시 유일 렌더).
# 게이트 3중(sns_brief.sh 계승): ① CHAN_BRIEF=1(§📰-e 카나리아 — 기본 OFF 머지 → dispatch 실측 → 승격) ② 입력 다이제스트 동일 = 스킵(토큰 0 · 데이터 무변화 = 재생성 낭비 0) ③ 실패 = fail-soft(직전 brief 유지 · rc 0 — 뷰어는 파일 없으면 블록 미표시 = 조용한 공백).
# 모델 = PIPE_MODEL(opus 4.8 · shared/model_env.sh — §🤖 생성/하드작업 축) · effort max · turns 8 · timeout 600 · 운영자 "토큰 아끼지 말고" = 다이제스트에 전 축 탑재.
# --safe-mode(--bare 절대 금지 = OAuth 즉사 §📰-d) · 폴오버 SSOT 경유(§📰-f) · WebSearch/WebFetch = --allowedTools 명시(게시물 소재 사건 맥락 확인용 — 헤드리스는 미허용 도구 즉시 거부 · sns_brief 실측 260713 계승).
set -u
[ "${CHAN_BRIEF:-0}" = "1" ] || { echo "chan-brief: OFF(CHAN_BRIEF!=1) — 스킵"; exit 0; }
cd "$(git rev-parse --show-toplevel)"
[ -s viewer/insta_data.json ] || { echo "chan-brief: insta_data.json 없음 — 스킵(no-op 스캐폴드)"; exit 0; }
. shared/model_env.sh
. shared/claude_transient.sh
MODEL="${CHAN_BRIEF_MODEL:-$PIPE_MODEL}"
OUT_JSON="viewer/chan_brief.json"

# ── 입력 다이제스트(insta_signals 산출물의 표시 전용 요약 — 재계산 0 · 지침 §4-7 분업 유지) + 변화 해시 ──
DIG="$(python3 - <<'PY'
import json, hashlib
def fv(v):
    """조회수 → 만/억 단위 한국식(반올림) — 원시 콤마숫자를 모델에 먹이면 만단위 지시를 무시하던 근원 차단(sns_brief 분신술2 계승)."""
    v = v or 0
    if v >= 100_000_000:
        s = ("%.1f" % (v / 100_000_000)).rstrip('0').rstrip('.')
        return "%s억" % s
    if v >= 10_000:
        return "{:,}만".format(round(v / 10_000))
    return "{:,}".format(round(v))
def pm(x):
    return '—' if x is None else ("%.2f" % x).rstrip('0').rstrip('.')
d = json.load(open('viewer/insta_data.json'))
if not d.get('profile'):
    print(''); raise SystemExit
p = d['profile']; a = d.get('account_day') or {}; avg = d.get('avg') or {}
L = ['[계정 지금]']
L.append(f"팔로워 {fv(p.get('followers_count'))} · 최근일 조회 {fv(a.get('views'))} · 도달 {fv(a.get('reach'))} · 공유 {fv(a.get('shares'))} · 저장 {fv(a.get('saves'))} · 프로필 방문 {fv(a.get('profile_views'))}")
AVL = {'views': '조회', 'reach': '도달', 'profile_views': '방문', 'interactions': '상호작용', 'follows': '팔로우', 'posts': '게시'}
rows = []
for k, lb in AVL.items():
    v = avg.get(k) or {}
    if v.get('ratio_7d') is None: continue
    rows.append(f"{lb} 최근7일평균 {fv(v.get('avg_7d'))}/일 = 전기간평균({fv(v.get('avg_all'))}/일)의 {round(v['ratio_7d']*100)}%")
if rows: L.append('[7일 대 전기간 평균] ' + ' · '.join(rows))
if d.get('online_peak_kst'): L.append(f"[팔로워 접속 피크(KST)] {d['online_peak_kst']}")
eras = d.get('eras') or {}
if eras:
    L.append('[성장 3기(게시물 성과 기준)]')
    for k in sorted(eras):
        v = eras[k]
        L.append(f"{k}: 게시물 {v.get('n')}개 · 조회 중앙 {fv(v.get('views_med'))}(평균 {fv(v.get('views_avg'))}) · 1천뷰당 공유 {pm(v.get('share_pm_med'))}·저장 {pm(v.get('save_pm_med'))}·댓글 {pm(v.get('cmt_pm_med'))}·좋아요 {pm(v.get('like_pm_med'))}")
ev = (d.get('daily_meta') or {}).get('events') or []
if ev:
    L.append('[운영자 관측 변곡 이벤트] ' + ' / '.join(f"{e.get('date')} {e.get('label')}({e.get('note','')})" for e in ev))
series = d.get('daily_series') or []
if series:
    L.append('[최근 30일 일일 계정 조회(만)·게시 수]')
    for r in series[-30:]:
        L.append(f"{str(r.get('date',''))[5:]} 조회 {fv(r.get('views')) if r.get('views') is not None else '—'} · 게시 {r.get('posts') if r.get('posts') is not None else 0}")
# ── 기간 창별 실측(운영자 260714 "7일·14일·28일·3개월·전체 총론 구분 요약") — 각 기간 섹션의 수치 근거(표시용 합산만 · 신호 원본 = insta_signals §4-7 분업 유지) ──
if series:
    import datetime as _dt
    _anchor = max(_dt.date.fromisoformat(r['date']) for r in series if r.get('date'))
    _allv = [r['views'] for r in series if r.get('views') is not None]
    _base = (sum(_allv) / len(_allv)) if _allv else 0
    pall = d.get('posts') or []
    L.append('[기간 창별 실측(창 = 최신일서 거슬러) — 기간 섹션 요약의 근거]')
    for _days, _lb in ((7, '7일'), (14, '14일'), (28, '28일'), (90, '3개월')):
        _lo = _anchor - _dt.timedelta(days=_days - 1)
        _rows = [r for r in series if r.get('date') and _dt.date.fromisoformat(r['date']) >= _lo]
        _vs = [r['views'] for r in _rows if r.get('views') is not None]
        if not _vs: continue
        _avgd = sum(_vs) / len(_vs)
        _pn = sum(r.get('posts') or 0 for r in _rows)
        _pp = sorted((x for x in pall if str(x.get('iso') or '')[:10] >= _lo.isoformat()), key=lambda x: -(x.get('views') or 0))[:3]
        _ln = f"{_lb}: 일평균 조회 {fv(_avgd)}(전기간 일평균의 {round(_avgd / _base * 100) if _base else 0}%) · 조회 합계 {fv(sum(_vs))} · 게시 {_pn}개"
        if _pp: _ln += ' · 창 내 톱 게시물: ' + ' / '.join(f"{str(x.get('name') or '(무캡션)')[:28]}(조회 {fv(x.get('views'))})" for x in _pp)
        L.append(_ln)
fmt = d.get('fmt') or {}
if fmt:
    L.append('[포맷별(전 기간)] ' + ' / '.join(f"{k}: n={v.get('n')} · 조회 중앙 {fv(v.get('views_med'))} · 1천뷰당 공유 {pm(v.get('share_pm_med'))}·저장 {pm(v.get('save_pm_med'))}" for k, v in fmt.items()))
tp = d.get('topics') or {}
tk = sorted((k for k in tp if (tp[k].get('n') or 0) >= 5), key=lambda k: -(tp[k].get('views_med') or 0))
if tk:
    L.append('[주제별 조회 중앙] ' + ' · '.join(f"{k} {fv(tp[k].get('views_med'))}(n={tp[k].get('n')})" for k in tk[:10]))
axes = (d.get('signals') or {}).get('axes') or {}
AXL = [('format', '포맷'), ('naming_style', '네이밍 스타일'), ('hour_band', '업로드 시간대'), ('dow', '업로드 요일')]
sg = []
for ax, lb in AXL:
    for b in (axes.get(ax) or [])[:3]:
        lift = b.get('lift') or {}
        sg.append(f"{lb}={b.get('bucket')}: 공유 ×{lift.get('share_pm','—')} · 저장 ×{lift.get('save_pm','—')} · n={b.get('n')}{' (표본부족)' if b.get('low_sample') else ''}")
if sg: L.append('[호응 신호(평균 대비 배율)] ' + ' / '.join(sg))
posts = d.get('posts') or []
if posts:
    L.append('[TOP 게시물(점수순 12)]')
    for i, x in enumerate(posts[:12]):
        L.append(f"{i+1}위 [{x.get('iso','')} {x.get('format','')}·{x.get('style','')}·{x.get('cat','')}·{x.get('era','')}] {str(x.get('name') or '(무캡션)')[:60]} · 조회 {fv(x.get('views'))} · 1천뷰당 공유 {pm(x.get('share_pm'))}·저장 {pm(x.get('save_pm'))}")
    L.append('[최근 게시물(최신 10)]')
    for x in sorted(posts, key=lambda x: str(x.get('iso') or ''), reverse=True)[:10]:
        L.append(f"[{x.get('iso','')} {x.get('format','')}·{x.get('style','')}·{x.get('cat','')}] {str(x.get('name') or '(무캡션)')[:60]} · 조회 {fv(x.get('views'))} · 1천뷰당 공유 {pm(x.get('share_pm'))}")
body = '\n'.join(L)
PVER = 'chanbrief-v3-260714-windows'   # 프롬프트 버전 — 바뀌면 해시 불일치 = 다음 run 강제 재생성 · v3 = 기간 5부 구성(7일/14일/28일/3개월/전체 총론 — 운영자 260714 "구분해서 요약") · v2 = 서두 확인 멘트·'---' 구분선 금지(카나리아 1차 실측 봉합)
print(hashlib.sha256((PVER + '\n' + body).encode()).hexdigest()[:16])
print(body)
PY
)" || { echo "::warning::chan-brief 다이제스트 실패 — 직전 유지"; exit 0; }
SHA="$(printf '%s\n' "$DIG" | head -1)"
BODY="$(printf '%s\n' "$DIG" | tail -n +2)"
[ -z "$BODY" ] && { echo "::warning::chan-brief 입력 빈 값(profile 없음 등) — 직전 유지"; exit 0; }
PREV="$(python3 -c "import json;print(json.load(open('$OUT_JSON')).get('src_hash',''))" 2>/dev/null || echo '')"
if [ -n "$SHA" ] && [ "$SHA" = "$PREV" ]; then
  echo "chan-brief: 입력 동일($SHA) — 스킵(토큰 0)"
  exit 0
fi

KST_NOW="$(TZ='Asia/Seoul' date '+%Y-%m-%d %H:%M %A')"   # 발화 기준 = 항상 한국시(§📐-d)

PROMPT="너는 이 인스타 뉴스 채널(@no_mute)을 운영자와 같이 키우는 친한 그로스 애널리스트다. 아래는 이 채널의 실제 지표 데이터다. 지표 나열이 아니라, 이걸 읽고 '이 채널이 어떻게 성장해왔고 · 지금 무슨 일이 벌어지고 있고 · 그래서 뭘 하면 되는지'를 이야기해준다. 지금 시각(한국): ${KST_NOW}.

[여는 인사]
가볍고 친근하게, 호칭·이름 없이 열어라 — 예: '일요일 밤이니까 이번 주 채널 상태 짚고 갈게.' (이름 부르기·'안녕 ○○'·'사장님' 류 호칭 전면 금지 · 딱딱한 비서 톤 금지 · 매번 똑같은 문장은 피하기.)

[출력 구조 — 기간별 5부 · 절대 준수]
아래 5개 섹션 마커를 정확히 이 표기 그대로, 이 순서로, 각각 단독 줄로 쓴다(마커 줄에 다른 글자 금지 · 첫 마커 위에 아무것도 쓰지 마라):
[7일]
[14일]
[28일]
[3개월]
[전체 총론]
- [7일] = 이번 주 벌어진 일. 여는 인사 한 줄로 시작 → 최근 7일이 전 기간 평균 대비 어떤지, 뭐가 튀었는지(급증·급락), 그걸 끌고 간 게시물을 TOP·최근 게시물에서 콕. 게시물 소재(사건)가 원인 이해에 필요하면 WebSearch로 그 사건을 확인해 한 줄로(확인된 것만). 4~6줄.
- [14일] = 최근 2주의 흐름 — 이번 주와 그 전 주가 어떻게 다른지, 반등·둔화의 방향. 3~4줄.
- [28일] = 최근 한 달의 파도 — 추세·전환점·게시 리듬(게시 수와 조회의 맞물림). 3~5줄.
- [3개월] = 중기 서사 — 성장 3기·운영자 관측 변곡 이벤트와 맞물려 채널이 지금 어디쯤인지. 4~6줄.
- [전체 총론] = 처음부터 지금까지 성장 스토리 총정리(처음 보는 사람·초등학생도 '아, 이 채널 이렇게 커왔구나'가 한 번에) + 관리 전략 '→ '로 시작하는 줄 3~4줄(각 줄 = '→ 무엇을 하자 — 근거(수치)' 꼴 · 예: '→ 릴스 비중을 더 올리자 — 릴스가 피드보다 1천뷰당 공유가 ×1.7 높다.' · 뻔한 일반론 금지 — 반드시 이 데이터에서만 나올 수 있는 말로) + 맺음 한 줄. 7~10줄.
- 각 섹션 = 그 기간 창 데이터([기간 창별 실측]·일일 흐름·TOP·최근 게시물)가 근거. 섹션 간 같은 문장 복붙 금지 — 창이 넓어질수록 시야도 넓어지게.

[근거·신뢰선 — 절대 준수]
- 수치는 데이터에 적힌 표기 그대로(만/억 단위 유지). 데이터에 없는 수치·사건 날조 절대 금지.
- share_pm 같은 원어·전문용어를 그대로 노출하지 마라 — '1천뷰당 공유'처럼 쉬운 말로. 어려운 개념은 반 줄로 풀어서.
- 외부 사건은 WebSearch/WebFetch로 확인한 것만. 못 찾으면 사건 언급 없이 지표만 담백하게.

[말투 — 살아있게(팬픽·웹소설 문체)]
친근한 소식통 톤. 단문으로 툭툭 끊되 길이 섞기 · 종결을 '~다'에 가두지 말고 '~더라(현장 톤)·~네(발견)·~거든(배경)'을 1~2번 · 수치는 끊어 던지고 자기정정으로 강조('97만 조회. 평소의 세 배.') · '무려·심지어·하필·그것도' 훅 · 대시(—)·쉼표로 뜸. 금지: 느낌표 떡칠·하트·2인칭 호칭(여러분/너)·신파·오글·말줄임(...) 남발.

[형식]
- 응답 첫 줄 = [7일] 마커 그 자체. 그 위에 '확인됐어/찾아봤어/이야기 풀게' 류 준비·확인 멘트, '---' 같은 구분선, 서두 사족 전면 금지(그건 네 사고 과정이지 브리핑이 아니다).
- 제일 크게 튄 수치·전환점은 *별표*로 강조(진짜 특별한 것만 · 별표 사이 줄바꿈 금지).
- 헤더·번호목록·마크다운 제목·이모지 금지(섹션 마커 5줄과 전략 줄의 '→ '만 예외).

[데이터 = 이 채널의 실제 지표]
$BODY"

out=""
for _try in 1 2 3 4; do
  out="$(printf '%s' "$PROMPT" | timeout 600 claude -p --model "$MODEL" --effort max --safe-mode --max-turns 8 \
    --allowedTools "WebFetch,WebSearch" \
    --disallowedTools "Bash,Edit,Write,Read,Glob,Grep,Task,NotebookEdit,TodoWrite" 2>/tmp/chanbrief.err)"; rc=$?
  if [ $rc -ne 0 ] || [ -z "$out" ]; then
    if claude_failover "$out$(cat /tmp/chanbrief.err 2>/dev/null)"; then continue; fi   # 쿼터 = 4계정 체인 1단씩(§📰-f)
    echo "::warning::chan-brief 생성 실패(rc=$rc) — 직전 brief 유지(fail-soft)"; exit 0
  fi
  break
done
[ -z "$out" ] && { echo "::warning::chan-brief 빈 출력 — 직전 유지"; exit 0; }

BRIEF_TEXT="$out" BRIEF_SHA="$SHA" python3 - <<'PY'
import json, os, datetime, re
KST = datetime.timezone(datetime.timedelta(hours=9))
raw = (os.environ.get('BRIEF_TEXT') or '').strip()
# 줄바꿈 보존(요점별 개행 · sns_brief 계승) — 줄별 trim + 빈줄 3+ → 1 + 독해 상한(5부 구성 = 길어짐 · 과출력 가드 2000→9000)
# + 단독 구분선(---·***) 줄 제거(결정론 — 프롬프트 금지의 안전망 · 수평선은 tbrief에서 맨 텍스트로 노출) · 구분선 앞 서두 프리앰블은 프롬프트 가드가 담당(카나리아 1차 실측 봉합)
lines = [ln.rstrip() for ln in raw.replace('\r\n', '\n').split('\n') if not re.fullmatch(r'\s*[-*_]{3,}\s*', ln)]
t = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()[:9000]
# 기간 5부 파싱(운영자 260714 "7일·14일·28일·3개월·전체 총론 구분") — 마커 단독 줄 분할 · 마커 미출력/1개뿐 = sections 생략 → 뷰어 fail-soft(전문 단일 렌더 = 구 스키마 하위호환)
SECS = [('d7', '7일'), ('d14', '14일'), ('d28', '28일'), ('m3', '3개월'), ('all', '전체 총론')]
parts = re.split(r'^\[(7일|14일|28일|3개월|전체 총론)\]\s*$', t, flags=re.M)
seen = {}
for i in range(1, len(parts) - 1, 2):
    seen.setdefault(parts[i], parts[i + 1].strip())
secs = [{'k': k, 'label': lb, 'text': seen[lb][:1800]} for k, lb in SECS if seen.get(lb)]
if secs and parts[0].strip():   # 첫 마커 위 잔여 서두(가드 뚫림 대비) = 첫 섹션에 흡수
    secs[0]['text'] = (parts[0].strip() + '\n' + secs[0]['text'])[:1800]
doc = {'text': t[:6000], 'updated': datetime.datetime.now(KST).isoformat(timespec='seconds'),
       'src_hash': os.environ.get('BRIEF_SHA') or ''}
if len(secs) >= 2: doc['sections'] = secs
json.dump(doc, open('viewer/chan_brief.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('chan-brief 저장:', len(t), '자', '·', len(secs), '섹션')
PY
echo "chan-brief: 갱신 완료($SHA)"
