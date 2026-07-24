#!/usr/bin/env bash
# 페이스북 채널 요약(메뉴4 · FB 소스) AI 브리프 — chan_brief.sh(인스타) 자매·기계부 100% 미러(운영자 260724 "페이스북도 요약 따로 · 동일한 조건").
# ⚠️ 차이 = 데이터 현실 적응만: FB는 게시물별 조회(views)·저장(save)·per-post 공유율 부재 → **반응(reactions+댓글+공유 = eng)이 핵심 지표**.
#   IG 전용 축(eras·timing·audience_sample·echo·online_peak·fmt·save_pm·style·fp·exp·reach·profile_views)은 fb_data에 없어 다이제스트서 제외(오해성 0 남발 차단 = "수치 신뢰선 사수").
# 출력 = viewer/chan_brief_fb.json(인스타 chan_brief.json 스키마 동일 {text,updated,src_hash,sections}) · 뷰어 renderChan이 CHAN_SRC=fb 분기로 소비.
# 게이트 3중(chan_brief.sh 계승): ① CHAN_BRIEF=1 ② 입력 다이제스트 동일 = 스킵(토큰 0) ③ 실패 = fail-soft(직전 유지·rc 0).
# 모델·폴오버·--safe-mode·allowedTools = chan_brief.sh 기계부 그대로(§🤖·§📰-d·§📰-f).
set -u
[ "${CHAN_BRIEF:-0}" = "1" ] || { echo "fb-brief: OFF(CHAN_BRIEF!=1) — 스킵"; exit 0; }
cd "$(git rev-parse --show-toplevel)"
[ -s viewer/fb_data.json ] || { echo "fb-brief: fb_data.json 없음 — 스킵(no-op 스캐폴드)"; exit 0; }
. shared/model_env.sh
. shared/claude_transient.sh
MODEL="${CHAN_BRIEF_MODEL:-$PIPE_MODEL}"
OUT_JSON="viewer/chan_brief_fb.json"

# ── 입력 다이제스트(fb_data.json 표시 전용 요약 · 재계산 0) + 변화 해시 — FB 지표 = 반응 기반 ──
DIG="$(python3 - <<'PY'
import json, hashlib
def fv(v):
    """수치 → 만/억 한국식(반올림) · FB 반응·조회 공용."""
    v = v or 0
    if v >= 100_000_000:
        return "%s억" % ("%.1f" % (v / 100_000_000)).rstrip('0').rstrip('.')
    if v >= 10_000:
        return "{:,}만".format(round(v / 10_000))
    return "{:,}".format(round(v))
d = json.load(open('viewer/fb_data.json'))
if not d.get('profile'):
    print(''); raise SystemExit
p = d['profile']; a = d.get('account_day') or {}; avg = d.get('avg') or {}; tot = d.get('fb_totals') or {}
L = ['[페이지 지금]']
_av = a.get('views'); _ai = a.get('interactions')   # 결측 가드(평의회 260724) — 2025 메타 인사이트 폐지로 views/interactions 사멸 시 None → fv(None)='0' 둔갑 차단(daily_series 줄과 정합 · '조회 0' 오실측 방지)
_acct = f"팔로워 {fv(p.get('followers_count'))} · 최근일 조회 {fv(_av) if _av is not None else '—'} · 상호작용 {fv(_ai) if _ai is not None else '—'}"
if tot:
    _acct += f" · 최근 {tot.get('n_posts','?')}게시물 반응 합 {fv(tot.get('reactions'))}(좋아요류)·댓글 {fv(tot.get('comments'))}·공유 {fv(tot.get('shares'))}"
L.append(_acct)
AVL = {'views': '조회', 'interactions': '상호작용', 'follows': '팔로우', 'posts': '게시'}   # FB 실측 축만(reach·profile_views = 2025 메타 폐지라 제외)
rows = []
for k, lb in AVL.items():
    v = avg.get(k) or {}
    if v.get('ratio_7d') is None: continue
    rows.append(f"{lb} 최근7일평균 {fv(v.get('avg_7d'))}/일 = 전기간평균({fv(v.get('avg_all'))}/일)의 {round(v['ratio_7d']*100)}%")
if rows: L.append('[7일 대 전기간 평균] ' + ' · '.join(rows))
series = d.get('daily_series') or []
if series:
    L.append('[최근 일일 계정 조회·게시 수·새 팔로우·영상조회(— = 미수집)]')
    for r in series[-30:]:
        _f = ('+' + format(r['follows'], ',')) if isinstance(r.get('follows'), int) and r['follows'] > 0 else '—'
        _vv = fv(r.get('video_views')) if r.get('video_views') is not None else '—'
        L.append(f"{str(r.get('date',''))[5:]} 조회 {fv(r.get('views')) if r.get('views') is not None else '—'} · 게시 {r.get('posts') if r.get('posts') is not None else 0} · 팔로우 {_f} · 영상조회 {_vv}")
# 기간 창별 실측(chan_brief.sh 계승 · FB는 반응 기반 창 요약) — 각 기간 섹션 근거
if series:
    import datetime as _dt
    _dates = [_dt.date.fromisoformat(r['date']) for r in series if r.get('date')]
    if _dates:
        _anchor = max(_dates)
        _allv = [r['views'] for r in series if r.get('views') is not None]
        _base = (sum(_allv) / len(_allv)) if _allv else 0
        pall = d.get('posts') or []
        L.append('[기간 창별 실측(창 = 최신일서 거슬러) — 기간 섹션 요약의 근거]')
        for _days, _lb in ((3, '3일'), (7, '7일'), (28, '28일'), (90, '3개월')):
            _lo = _anchor - _dt.timedelta(days=_days - 1)
            _rows = [r for r in series if r.get('date') and _dt.date.fromisoformat(r['date']) >= _lo]
            _vs = [r['views'] for r in _rows if r.get('views') is not None]
            _pn = sum(r.get('posts') or 0 for r in _rows)
            _pp = sorted((x for x in pall if str(x.get('iso') or '')[:10] >= _lo.isoformat()), key=lambda x: -(x.get('eng') or 0))[:3]
            _ln = f"{_lb}: "
            if _vs:
                _avgd = sum(_vs) / len(_vs)
                _ln += f"일평균 조회 {fv(_avgd)}(전기간 일평균의 {round(_avgd / _base * 100) if _base else 0}%) · "
            _ln += f"게시 {_pn}개"
            if _pp: _ln += ' · 창 내 반응 톱: ' + ' / '.join(f"{str(x.get('name') or '(무캡션)')[:28]}(반응 {fv(x.get('eng'))})" for x in _pp)
            L.append(_ln)
tp = d.get('topics') or {}
tk = sorted((k for k in tp if (tp[k].get('n') or 0) >= 5), key=lambda k: -(tp[k].get('views_med') or 0))
if tk:
    L.append('[주제별 반응 중앙(반응 = 좋아요류+댓글+공유)] ' + ' · '.join(f"{k} {fv(tp[k].get('views_med'))}(n={tp[k].get('n')})" for k in tk[:10]))
axes = (d.get('signals') or {}).get('axes') or {}
AXL = [('hour_band', '업로드 시간대'), ('dow', '업로드 요일')]   # FB signals = 시간대·요일 2축(eng 기반 lift)
sg = []
for ax, lb in AXL:
    for b in (axes.get(ax) or [])[:4]:
        lift = b.get('lift') or {}
        sg.append(f"{lb}={b.get('bucket')}: 반응 ×{lift.get('share_pm','—')} · n={b.get('n')}{' (표본부족)' if b.get('low_sample') else ''}")
if sg: L.append('[시간대별 반응(전체 평균 대비 배율 · ×1=채널 중앙)] ' + ' / '.join(sg))
posts = d.get('posts') or []
if posts:
    _bye = sorted(posts, key=lambda x: -(x.get('eng') or 0))
    L.append('[반응 TOP 게시물(반응순 12 · FB는 조회 대신 반응 = 좋아요류+댓글+공유)]')
    for i, x in enumerate(_bye[:12]):
        L.append(f"{i+1}위 [{x.get('date_kst') or str(x.get('iso',''))[:10]}·{x.get('cat','')}] {str(x.get('name') or '(무캡션)')[:60]} · 반응 {fv(x.get('eng')) if x.get('eng') is not None else '—'}")
    L.append('[최근 게시물(최신 10)]')
    for x in sorted(posts, key=lambda x: str(x.get('iso') or ''), reverse=True)[:10]:
        L.append(f"[{x.get('date_kst') or str(x.get('iso',''))[:10]}·{x.get('cat','')}] {str(x.get('name') or '(무캡션)')[:60]} · 반응 {fv(x.get('eng')) if x.get('eng') is not None else '—'}")
body = '\n'.join(L)
PVER = 'fbbrief-v1-260724-reaction-basis'   # FB 브리프 프롬프트 버전 — chan_brief v9.3 구조 미러 + FB 반응 기반 적응 · 바뀌면 해시 불일치 = 강제 재생성
print(hashlib.sha256((PVER + '\n' + body).encode()).hexdigest()[:16])
print(body)
PY
)" || { echo "::warning::fb-brief 다이제스트 실패 — 직전 유지"; exit 0; }
SHA="$(printf '%s\n' "$DIG" | head -1)"
BODY="$(printf '%s\n' "$DIG" | tail -n +2)"
[ -z "$BODY" ] && { echo "::warning::fb-brief 입력 빈 값(profile 없음 등) — 직전 유지"; exit 0; }
PREV="$(python3 -c "import json;print(json.load(open('$OUT_JSON')).get('src_hash',''))" 2>/dev/null || echo '')"
if [ -n "$SHA" ] && [ "$SHA" = "$PREV" ]; then
  echo "fb-brief: 입력 동일($SHA) — 스킵(토큰 0)"
  exit 0
fi

KST_NOW="$(TZ='Asia/Seoul' date '+%Y-%m-%d %H:%M %A')"

# 직전 브리핑 동봉(연재 축 · chan_brief.sh 계승)
PREV_TXT="$(python3 - <<'PY' 2>/dev/null || true
import json
try:
    d = json.load(open('viewer/chan_brief_fb.json'))
    t = (d.get('text') or '').strip()
    if t:
        print(str(d.get('updated') or '')[:10])
        print(t[:1500])
except Exception:
    pass
PY
)"
PREV_BLOCK=""
if [ -n "$PREV_TXT" ]; then
  PREV_BLOCK="
[직전 브리핑($(printf '%s\n' "$PREV_TXT" | head -1)) — 참고: 반복 말고 이어서. 그때 짚은 흐름이 이어지는지 꺾였는지 비교해 연재처럼(단, 직전 표현 복붙 금지)]
$(printf '%s\n' "$PREV_TXT" | tail -n +2)
"
fi

PROMPT="너는 이 페이스북 뉴스 페이지(Nomute)를 운영자와 같이 키우는 친한 그로스 애널리스트다. 아래는 이 페이지의 실제 지표 데이터다. 지표 나열이 아니라, 이걸 읽고 '이 페이지가 어떻게 성장해왔고 · 지금 무슨 일이 벌어지고 있고 · 그래서 뭘 하면 되는지'를 이야기해준다. 지금 시각(한국): ${KST_NOW}.

[⚠ 페이스북 지표 특성 — 절대 준수]
이 페이지는 게시물별 '조회수'를 API로 주지 않는다. 그래서 이 채널의 핵심 성과 지표는 *반응*(좋아요류 리액션 + 댓글 + 공유의 합)이다. '조회'는 페이지 전체 일일 지표(계정 단위)만 있고, 게시물 순위·시간대 성과는 전부 '반응' 기준이다. '조회수'라는 말을 게시물에 붙이지 마라(게시물엔 반응). 인스타의 저장·1천뷰당 공유·릴스 같은 개념은 이 데이터에 없으니 지어내지 마라.

[존재 이유] 기간 창끼리 추이를 비교해 전략 방향을 잡는 도구다 — 3일→전체로 창이 넓어질수록 나무에서 숲으로. 짧은 창의 '문제'가 긴 창에선 '정상 리듬'인 지점을 짚어라. 매 섹션 마지막 줄 = 그 창에서만 보이는 전략 시사점 한 줄.

[여는 인사] 가볍고 친근하게, 호칭·이름 없이 — 예: '일요일 밤이니까 이번 주 페이지 상태 짚고 갈게.' (호칭·'안녕 ○○'·비서 톤 금지 · 매번 같은 문장 금지.)

[출력 구조 — 6부 · 절대 준수] 아래 6개 마커를 정확히 이 표기 그대로, 이 순서로, 각각 단독 줄로(마커 줄에 다른 글자 금지 · 첫 마커 위 아무것도 금지):
[3일]
[7일]
[28일]
[3개월]
[전체]
[총론]
- [3일] = 지난 사흘의 결. 여는 인사 → 사흘 흐름이 7일·28일과 같은 방향인지(나무 vs 숲) + 그 움직임 만든 게시물 콕. 3~4줄.
- [7일] = 이번 주 벌어진 일 — 최근 7일 vs 전기간 평균, 반응 튄 게시물을 반응 TOP·최근에서 콕. 게시물 소재(사건)가 원인 이해에 필요하면 WebSearch로 확인해 한 줄(확인된 것만). 4~6줄.
- [28일] = 최근 한 달의 파도 — 추세·전환점·게시 리듬(게시 수와 반응·조회의 맞물림). 3~5줄.
- [3개월] = 중기 서사 — 데이터가 짧으면(FB는 최근 수집분 위주) 있는 만큼만, 없는 기간은 '아직 수집 초기'라 정직히. 3~5줄.
- [전체] = 전체 기간 분석 요약 — 지금까지의 반응·조회·팔로워 스토리를 수치로 총정리 + 바로 이후 정도 예측. 관리 전략 '→ '로 시작하는 줄 3~4줄(각 줄 = '→ 무엇을 하자 — 근거(수치)' 꼴 · 데이터서만 나올 말로 · 뻔한 일반론 금지) + 맺음 한 줄. 6~9줄. ⚠ '→ ' 줄은 앱이 '제안' 블록으로 자동 분리한다 — 예고 없이 줄만, 맺음은 '→ ' 없이.
- [총론] = 페이지 전체를 아우르는 비전·방향성·미션 — 개별 수치 나열 말고 정체성·나아갈 큰 방향(3~12개월)·핵심 미션을 산문으로. **맨 마지막 줄은 '→ '로 여는 단 한 줄 결론**('→ 그래서 무엇을 — 한 문장 방향'). 6~9줄.
- 각 섹션 = 그 기간 창 데이터가 근거([총론]만 전 기간 종합). 섹션 간 복붙 금지. [전체](디테일 분석)와 [총론](먼 방향)은 반드시 다른 글.

[근거·신뢰선 — 절대 준수]
- 수치는 데이터 표기 그대로(만/억 유지). 없는 수치·사건 날조 금지.
- 전문용어 원어 노출 금지 — 쉬운 말로. 외부 사건은 WebSearch로 확인한 것만.
- [시간대별 반응]이 있으면 게시 타이밍 전략 근거로(표본부족 딱지 붙은 버킷은 단정 금지). 요일 우열은 게시 몰림 교란 가능성을 같이 달아라.

[신뢰 게이트] 해석('~때문')·방향('~하자','→ ')은 표본 충분한 실측(반응 중앙값·상관·시간대 배율)에서만. (표본부족)/결측(—)/데이터 짧은 구간은 단독 근거 금지 — 애매하면 '아직 데이터로 모른다'고 정직히. 확실 7할을 또렷하게 > 불확실 10할을 그럴듯하게.

[회초리] 반응 잘 나온 게시물 1~2개 콕(어느 게시물·수치) → 왜(주제가 시류 탔나 · WebSearch 확인분만) → 다음 수 1개까지. '자주 올려라' 류 일반 훈수 금지 — 근거 수치 필수.

[말투 — 살아있게] 친근한 소식통. 단문 툭툭·길이 섞기 · '~더라·~네·~거든' 1~2번 · 수치 끊어 던지고 자기정정('2천 반응. 평소의 세 배.') · '무려·심지어·하필' 훅 · 대시·쉼표로 뜸. 금지: 느낌표 떡칠·하트·2인칭 호칭·신파·말줄임 남발.

[형식]
- 응답 첫 줄 = [3일] 마커 그 자체. 준비·확인 멘트·'---'·서두 사족 금지.
- 강조 2층: 제일 튄 수치·전환점·핵심어 = *별표 하나*(1층 강조색 · 섹션당 0~1) · 눈이 먼저 갈 핵심 명사·동사 = **별표 둘**(2층 볼드 · 짧은 창 2~3 · 긴 [전체]·[총론] 4~6). 별표 사이 줄바꿈 금지·짝 닫기.
- 헤더·번호목록·마크다운 제목·이모지 금지(섹션 마커 6줄과 '→ '만 예외).

${PREV_BLOCK}
[데이터 = 이 페이지의 실제 지표]
$BODY"

claude_preflight "$MODEL" || true
out=""; _to_tried=0
for _try in 1 2 3 4; do
  [ "$SECONDS" -gt 960 ] && { echo "::warning::fb-brief 시간 예산 소진(${SECONDS}s>960s) — 직전 유지(fail-soft)"; exit 0; }
  out="$(printf '%s' "$PROMPT" | timeout 900 claude -p --model "$MODEL" --effort high --safe-mode --max-turns 8 \
    --allowedTools "WebFetch,WebSearch" \
    --disallowedTools "Bash,Edit,Write,Read,Glob,Grep,Task,NotebookEdit,TodoWrite" 2>/tmp/fbbrief.err)"; rc=$?
  if [ $rc -ne 0 ] || [ -z "$out" ]; then
    if claude_failover "$out$(cat /tmp/fbbrief.err 2>/dev/null)"; then continue; fi
    if [ $rc -eq 124 ] && [ "$_to_tried" = "0" ] && claude_failover_force; then _to_tried=1; continue; fi
    echo "::warning::fb-brief 생성 실패(rc=$rc) — 직전 유지(fail-soft)"; exit 0
  fi
  break
done
[ -z "$out" ] && { echo "::warning::fb-brief 빈 출력 — 직전 유지"; exit 0; }

BRIEF_TEXT="$out" BRIEF_SHA="$SHA" python3 - <<'PY'
import json, os, datetime, re
KST = datetime.timezone(datetime.timedelta(hours=9))
raw = (os.environ.get('BRIEF_TEXT') or '').strip()
lines = [ln.rstrip() for ln in raw.replace('\r\n', '\n').split('\n') if not re.fullmatch(r'\s*[-*_]{3,}\s*', ln)]
t = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()[:9000]
SECS = [('d3', '3일'), ('d7', '7일'), ('d28', '28일'), ('m3', '3개월'), ('all', '전체'), ('overview', '총론')]
parts = re.split(r'^\[(3일|7일|28일|3개월|전체|총론)\]\s*$', t, flags=re.M)
seen = {}
for i in range(1, len(parts) - 1, 2):
    seen.setdefault(parts[i], parts[i + 1].strip())
secs = [{'k': k, 'label': lb, 'text': seen[lb][:1800]} for k, lb in SECS if seen.get(lb)]
if secs and parts[0].strip():
    secs[0]['text'] = (parts[0].strip() + '\n' + secs[0]['text'])[:1800]
doc = {'text': t[:6000], 'updated': datetime.datetime.now(KST).isoformat(timespec='seconds'),
       'src_hash': os.environ.get('BRIEF_SHA') or ''}
if len(secs) >= 2: doc['sections'] = secs
json.dump(doc, open('viewer/chan_brief_fb.json', 'w', encoding='utf-8'), ensure_ascii=False)
import os.path
log = 'viewer/chan_brief_fb_log.jsonl'
today = doc['updated'][:10]
rows = []
if os.path.exists(log):
    for ln in open(log, encoding='utf-8').read().splitlines():
        ln = ln.strip()
        if not ln: continue
        try:
            if json.loads(ln).get('date') != today: rows.append(ln)
        except Exception: pass
rows.append(json.dumps({'date': today, 'updated': doc['updated'], 'sections': secs if len(secs) >= 2 else None, 'text': None if len(secs) >= 2 else doc['text']}, ensure_ascii=False))
open(log, 'w', encoding='utf-8').write('\n'.join(rows[-180:]) + '\n')
print('fb-brief 저장:', len(t), '자', '·', len(secs), '섹션', '· 아카이브', len(rows[-180:]), '회차')
PY
echo "fb-brief: 갱신 완료($SHA)"
