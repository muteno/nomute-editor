#!/usr/bin/env bash
# 채널 요약(메뉴4) AI 브리프 — 인스타 채널 지표(insta_data.json)를 보고 '성장 서사 + 지금 상황 + 관리 전략'을 짚어주는 브리핑(운영자 260714 "초등학생도 아 이 채널 이렇게 성장해왔네·이래야겠네 전략이 뿅뿅").
# ⚠️ SNS 트렌드 브리프(sns_brief.sh·viewer/sns_brief.json)와 완전 별개 축 — 골격만 미러(운영자 "트렌드 요약 참고만·덮어씌우지 말고") · 출력 = viewer/chan_brief.json.
# 페르소나 = "채널을 같이 키우는 친한 그로스 애널리스트 · 호칭·이름 없이 친근 인사(KST) · 성장 서사 → 급변 원인 콕 → 데이터 근거 실행 전략 · 쉬운 말 · 수치 신뢰선 사수"(sns_brief v8 톤 계승).
# 구성 = 기간 5부(운영자 260714 "1년 전반부 총론만 나옴 → 구분 요약" · 2차 확정 = 3일/7일/28일/3개월/전체 총론) — 출력 = sections[{k,label,text}] + text(전문 = 하위호환·마커 파싱 실패 시 유일 렌더).
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
# 팔로워 활동 시간대(운영자 260714 "시간대는 총론 반영 가능") — 관객 쪽 데이터 = 게시 스케줄 교란 무관 · 수기 폴백이면 출처 명시
if d.get('online_peak_kst'):
    _pk = ' · '.join(d['online_peak_kst']) if isinstance(d['online_peak_kst'], list) else str(d['online_peak_kst'])
    _src = str(d.get('online_src') or '')
    L.append(f"[팔로워 접속 피크(KST)] {_pk}" + (f" — 출처: 운영자 인사이트 실측({_src[7:-1]})" if _src.startswith('manual(') else ''))
    _oh = d.get('online_hours_kst')
    if _oh:
        try:
            _hs = ' · '.join(f"{h}시 {v}" for h, v in sorted(_oh.items(), key=lambda x: int(x[0])))
            L.append(f"[팔로워 활동 시간 분포(KST · 상대 높이 = 피크 100)] {_hs}" + (f" — {d['online_note']}" if d.get('online_note') else ''))
        except Exception:
            pass
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
    L.append('[최근 30일 일일 계정 조회(만)·게시 수·새 팔로우(— = 미수집)]')
    for r in series[-30:]:
        L.append(f"{str(r.get('date',''))[5:]} 조회 {fv(r.get('views')) if r.get('views') is not None else '—'} · 게시 {r.get('posts') if r.get('posts') is not None else 0} · 팔로우 {('+' + format(r['follows'], ',')) if isinstance(r.get('follows'), int) and r['follows'] > 0 else '—'}")
# 게시-팔로워 인과 실측(insta_signals 산출 — 회초리의 '왜냐면' 근거 · 운영자 260715 Q02)
tmg = d.get('timing') or {}
if tmg:
    L.append(f"[게시-팔로워 인과 실측(일별 {tmg.get('n_days')}일 · {tmg.get('from')}~{tmg.get('to')})] "
             f"팔로워 증가는 게시 행위(당일 상관 {tmg.get('corr_posts_follows')})가 아니라 당일 조회수(상관 {tmg.get('corr_views_follows')})를 따름 · 다음날까지 {tmg.get('corr_views_follows_next')} = 게시 후 24~48시간 창 · "
             f"안 올린 날(표본 {tmg.get('rest_days_n')}일)의 증가 = 직전 3일 평균의 {round((tmg.get('rest_rel_med_ex_viral') or 0) * 100)}%(지연 바이럴 1일 제외 중앙 — 쉬면 다음날부터 꺼진다) · 올린 날 하루 증가 중앙 {tmg.get('post_day_med')}명 · "
             f"게시물 1개당 팔로워: {' · '.join(f'{k} {v}명' for k, v in (tmg.get('follows_per_post_by_era') or {}).items())} · {tmg.get('note','')}")
# 팔로워 표본(계정 인구통계 + 운영자 자가 보고 · 운영자 260715 Q03)
smp = d.get('audience_sample') or {}
if smp:
    _pcs = []
    if smp.get('age_gender_top'): _pcs.append('성·연령 상위: ' + ' · '.join(f"{x['k']} {x['pct']}%" for x in smp['age_gender_top']) + ' (U=성별미공개)')
    if smp.get('country_top'): _pcs.append('국가: ' + ' · '.join(f"{x['k']} {x['pct']}%" for x in smp['country_top']))
    if smp.get('city_top'): _pcs.append('도시: ' + ' · '.join(f"{x['k'].split(',')[0]} {x['pct']}%" for x in smp['city_top']))
    L.append('[팔로워 표본(계정 전체 · API 실측)] ' + ' / '.join(_pcs))
    if smp.get('operator_note'):
        L.append('[팔로워 표본 — 운영자 자가 보고(데이터 아님 · 취급 주의)] ' + smp['operator_note'])
# 알고리즘 협착 — 운영자 가설 + 주제 간 실측(운영자 260715 Q05)
echo = d.get('echo') or {}
if echo.get('note'):
    ln = '[알고리즘 협착 — 운영자 가설(단정 금지)] ' + echo['note']
    ev = echo.get('evidence') or {}
    if ev:
        ln += f" || 이번 데이터 실측: 정치 1천뷰당 좋아요 {pm(ev.get('pol_like_pm_med'))}(전 주제 {ev.get('pol_like_rank')}위) · 조회 중앙 {fv(ev.get('pol_views_med'))} = 사회({fv(ev.get('soc_views_med'))})의 {ev.get('pol_vs_soc_views_pct')}%"
    L.append(ln)
# ── 기간 창별 실측(운영자 260714 "7일·14일·28일·3개월·전체 총론 구분 요약") — 각 기간 섹션의 수치 근거(표시용 합산만 · 신호 원본 = insta_signals §4-7 분업 유지) ──
if series:
    import datetime as _dt
    _anchor = max(_dt.date.fromisoformat(r['date']) for r in series if r.get('date'))
    _allv = [r['views'] for r in series if r.get('views') is not None]
    _base = (sum(_allv) / len(_allv)) if _allv else 0
    pall = d.get('posts') or []
    L.append('[기간 창별 실측(창 = 최신일서 거슬러) — 기간 섹션 요약의 근거]')
    for _days, _lb in ((3, '3일'), (7, '7일'), (28, '28일'), (90, '3개월')):   # 3일 신설·14일 제거(운영자 260714 2차 "3일, 7일, 28일, 3개월, 전체")
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
# 게시 요일 분포 + 교란 딱지(운영자 260714 "토일월에 쉬어서 그때 많이 올림 — 요일 성과는 그 영향이 커") — 요일 우열 단정을 데이터로 차단
_pall = d.get('posts') or []
if _pall:
    import datetime as _dt2
    _dc = {}
    for x in _pall:
        try:
            _w = ['월', '화', '수', '목', '금', '토', '일'][_dt2.datetime.fromisoformat(str(x.get('iso')).replace('Z', '+00:00')).weekday()]
            _dc[_w] = _dc.get(_w, 0) + 1
        except Exception:
            pass
    if _dc:
        L.append('[게시 요일 분포(표본 ' + str(sum(_dc.values())) + '개) — ⚠운영자 휴무일(토·일·월)에 게시 몰림: 요일별 성과 차이는 게시량 영향이 커서 요일 우열 단정 금지] '
                 + ' · '.join(f"{k} {_dc.get(k, 0)}" for k in ('월', '화', '수', '목', '금', '토', '일')))
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
    def tag(x):
        """반응 지문(fp = 채널 중앙 2배↑ 지배 반응축 — 그 게시물에 반응한 표본의 대리 지표)·확장문(exp) 딱지."""
        t = ''
        if x.get('fp'): t += f" · 지문 {x['fp']}"
        if x.get('exp'): t += ' · 🚪확장문'
        return t
    L.append('[TOP 게시물(점수순 12) — 지문 = 반응한 표본의 결(공유형=지인에 퍼나름·저장형=모아둠·댓글형=참전·좋아요형=가볍게 호응) · 🚪확장문 = 주력 주제 밖에서 평소 2배↑ 터짐+저장 강세 = 기존 팔로워 밖 새 표본 유입 신호]')
    for i, x in enumerate(posts[:12]):
        L.append(f"{i+1}위 [{x.get('iso','')} {x.get('format','')}·{x.get('style','')}·{x.get('cat','')}·{x.get('era','')}] {str(x.get('name') or '(무캡션)')[:60]} · 조회 {fv(x.get('views'))} · 1천뷰당 공유 {pm(x.get('share_pm'))}·저장 {pm(x.get('save_pm'))}{tag(x)}")
    L.append('[최근 게시물(최신 10)]')
    for x in sorted(posts, key=lambda x: str(x.get('iso') or ''), reverse=True)[:10]:
        L.append(f"[{x.get('iso','')} {x.get('format','')}·{x.get('style','')}·{x.get('cat','')}] {str(x.get('name') or '(무캡션)')[:60]} · 조회 {fv(x.get('views'))} · 1천뷰당 공유 {pm(x.get('share_pm'))}{tag(x)}")
    _exps = [x for x in posts if x.get('exp')]
    if _exps:
        L.append('[🚪확장문 게시물(최신 8) — 채널이 커지는 문 후보]')
        for x in sorted(_exps, key=lambda x: str(x.get('iso') or ''), reverse=True)[:8]:
            L.append(f"[{x.get('iso','')} {x.get('cat','')}] {str(x.get('name') or '(무캡션)')[:60]} · 조회 {fv(x.get('views'))}{tag(x)}")
body = '\n'.join(L)
PVER = 'chanbrief-v9.1-260715-echo'   # v9.1 = 알고리즘 협착 가설+실측(운영자 260715 Q05) · v9 = 회초리·표본(운영자 260715 Q02·Q03 — 인과 실측·팔로워 표본·반응 지문·확장문)   # 프롬프트 버전 — 바뀌면 해시 불일치 = 다음 run 강제 재생성 · v8 = 총론 분리(운영자 260714 "총론=비전·방향성·미션 큰 그림 3~12개월 / 전체=전체 기간 분석 디테일" — [전체 총론] 1부 → [전체]+[총론] 2부 = 6부) · v7 = 강조 2층 · v6 = 시간대·요일교란 · v5 = 존재이유+연재+아카이브 · v4 = 3일신설 · v3 = 5부 · v2 = 프리앰블금지
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

# ── 직전 브리핑 동봉(운영자 260714 3차 "날짜별로 달리 나오는 인사이트 모으면 뭔가 나올수도" — 연재 축) : 덮어쓰기 전 현 chan_brief.json = 직전 회차 → 프롬프트 참고 블록(반복 말고 이어서·비교) ──
PREV_TXT="$(python3 - <<'PY' 2>/dev/null || true
import json
try:
    d = json.load(open('viewer/chan_brief.json'))
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
[직전 브리핑($(printf '%s\n' "$PREV_TXT" | head -1)) — 참고: 반복 말고 이어서. 그때 짚은 흐름이 이어지는지 꺾였는지 비교해 연재처럼 읽히게(단, 직전 표현 복붙 금지)]
$(printf '%s\n' "$PREV_TXT" | tail -n +2)
"
fi

PROMPT="너는 이 인스타 뉴스 채널(@no_mute)을 운영자와 같이 키우는 친한 그로스 애널리스트다. 아래는 이 채널의 실제 지표 데이터다. 지표 나열이 아니라, 이걸 읽고 '이 채널이 어떻게 성장해왔고 · 지금 무슨 일이 벌어지고 있고 · 그래서 뭘 하면 되는지'를 이야기해준다. 지금 시각(한국): ${KST_NOW}.

[존재 이유 — 운영자가 이걸 읽는 목적]
이슈 터졌나 감시하는 게 아니다. *기간 창끼리 추이를 비교해 전략 방향을 잡는* 도구다 — 3일→전체로 창이 넓어질수록 나무에서 숲으로 시야가 바뀌는 맛이 핵심. 짧은 창에서 '문제'로 보이던 게 긴 창에선 '정상 리듬'이거나 그 반대인 지점을 명시적으로 짚어라. 매 섹션의 마지막 줄 = 그 창에서만 보이는 전략적 시사점 한 줄(이 창을 열어보는 이유가 되는 문장).

[여는 인사]
가볍고 친근하게, 호칭·이름 없이 열어라 — 예: '일요일 밤이니까 이번 주 채널 상태 짚고 갈게.' (이름 부르기·'안녕 ○○'·'사장님' 류 호칭 전면 금지 · 딱딱한 비서 톤 금지 · 매번 똑같은 문장은 피하기.)

[출력 구조 — 6부(기간 5창 + 총론) · 절대 준수]
아래 6개 섹션 마커를 정확히 이 표기 그대로, 이 순서로, 각각 단독 줄로 쓴다(마커 줄에 다른 글자 금지 · 첫 마커 위에 아무것도 쓰지 마라):
[3일]
[7일]
[28일]
[3개월]
[전체]
[총론]
- [3일] = 지난 사흘의 결. 여는 인사 한 줄로 시작 → 사흘 흐름이 7일·28일 추세와 같은 방향인지 어긋나는지(나무 vs 숲 대조)를 짚고, 그 움직임을 만든 게시물을 콕. 3~4줄.
- [7일] = 이번 주 벌어진 일 — 최근 7일이 전 기간 평균 대비 어떤지, 뭐가 튀었는지, 원인 게시물을 TOP·최근 게시물에서 콕. 게시물 소재(사건)가 원인 이해에 필요하면 WebSearch로 그 사건을 확인해 한 줄로(확인된 것만). 4~6줄.
- [28일] = 최근 한 달의 파도 — 추세·전환점·게시 리듬(게시 수와 조회의 맞물림). 3~5줄.
- [3개월] = 중기 서사 — 성장 3기·운영자 관측 변곡 이벤트와 맞물려 채널이 지금 어디쯤인지. 4~6줄.
- [전체] = **전체 기간에 대한 분석 요약(총론 아님 · 운영자 260714 '전체는 기간 분석에 집중·디테일하게')** — 처음부터 지금까지 무슨 일이 있었는지 성장 스토리를 수치로 총정리(초등학생도 '아, 이렇게 커왔구나') + '지금까지의 내용' 느낌 + *바로 이후 정도*까지의 예측(먼 미래 방향은 여기 쓰지 마라 = 총론 역할). 관리 전략 '→ '로 시작하는 줄 3~4줄(각 줄 = '→ 무엇을 하자 — 근거(수치)' 꼴 · 예: '→ 릴스 비중을 더 올리자 — 릴스가 피드보다 1천뷰당 공유가 ×1.7 높다.' · 뻔한 일반론 금지 — 데이터서만 나올 말로) + 맺음 한 줄. 7~10줄. ⚠ '→ ' 줄들은 앱이 '클로신의 제안' 블록으로 자동 분리 표시한다 — '전략은 이렇다:' 류 예고 없이 줄만, 맺음은 '→ ' 없이.
- [총론] = **채널 전체를 아우르는 비전·방향성·미션(운영자 260714 '짧게 3개월 길게 12개월·먼 날들까지·큰 그림·회초리 아닌 나침반')** — 개별 기간 수치를 나열하지 말고, 모든 기간 분석을 관통해 '이 채널이 무엇이고 어디로 가야 하는가'를 제시하라: 정체성(무슨 채널로 자리잡았나)·나아갈 큰 방향(3~12개월 반년~1년 시야)·핵심 미션. 산문 서술(여긴 큰 그림·방향이라 '→ ' 전략 줄 쓰지 마라 = 문장으로 방향을 그려라). '전체'가 지금까지의 디테일 분석이라면, 총론은 그 위에서 멀리 보는 나침반이다. 5~8줄.
- 각 섹션 = 그 기간 창 데이터([기간 창별 실측]·일일 흐름·TOP·최근 게시물)가 근거([총론]만 전 기간 종합). 섹션 간 같은 문장 복붙 금지 — 창이 넓어질수록 시야도 넓어지게, 앞 창과의 시야 차이(같은 데이터가 달리 읽히는 지점)를 살려라. ⚠ [전체](디테일 분석)와 [총론](먼 방향·비전)은 반드시 다른 글 — 총론에 수치 분석을, 전체에 먼 미래 비전을 넣지 마라.

[근거·신뢰선 — 절대 준수]
- 수치는 데이터에 적힌 표기 그대로(만/억 단위 유지). 데이터에 없는 수치·사건 날조 절대 금지.
- share_pm 같은 원어·전문용어를 그대로 노출하지 마라 — '1천뷰당 공유'처럼 쉬운 말로. 어려운 개념은 반 줄로 풀어서.
- 외부 사건은 WebSearch/WebFetch로 확인한 것만. 못 찾으면 사건 언급 없이 지표만 담백하게.
- [팔로워 접속 피크]·[팔로워 활동 시간 분포]가 데이터에 있으면 게시 타이밍 전략의 근거로 살려라 — 특히 [전체 총론] 전략 줄 후보(예: '→ 피크인 18~21시에 맞춰 올리자 — 팔로워 활동이 이 구간에 가장 높다'). 이건 관객이 언제 깨어 있느냐라 게시 습관과 무관한 데이터다.
- 반대로 요일 우열('무슨 요일이 잘 터진다')은 [게시 요일 분포]의 ⚠딱지대로 단정 금지 — 게시가 몰린 요일은 성과도 같이 부풀어 보인다. 요일 얘기가 필요하면 '게시가 몰려서 그렇게 보일 수 있다'는 유보를 같이 달아라. 시간대 이야기까지만 확언한다.

[회초리 — 잘한 건 콕 집고, 근거로만 때려라(운영자 260715)]
- 잘 터진 게시물 1~2개는 반드시: ① '이 부분이 터졌다' 콕(어느 게시물·수치) → ② 왜 터졌나 — 주제가 그 시기 흐름(사건·시류)을 탔는지 진단(외부 사건은 WebSearch로 확인된 것만·못 찾으면 지표만) → ③ 그 게시물의 '지문'으로 반응한 표본을 그려라(공유형 = 지인에게 퍼나르는 표본 · 저장형 = 모아두고 다시 보는 표본 · 댓글형 = 참전하는 표본) → ④ '~를 활용하면 더 좋겠다' 다음 수 1개까지. 칭찬으로 끝내지 말고 반드시 ④까지.
- '그냥 자주 올려라' 류 일반 훈수 전면 금지 — 모든 지적·권고에는 [게시-팔로워 인과 실측]이나 지표 수치가 근거로 붙어야 한다(핵심 실측: 팔로워는 게시 *행위*가 아니라 조회가 터진 날 는다 — 다만 안 올리면 터질 것도 없다. [게시-팔로워 인과 실측]의 상관·휴식일 vs 게시일 중앙값을 그대로 인용해 근거를 대라).
- 🚪확장문 딱지 게시물이 있으면 '지금 팔로워 밖에서 새 표본이 들어오는 문'으로 짚어라 — 특히 [3개월]·[총론]에서 채널이 커지는 방향의 근거로.
- [알고리즘 협착] 블록이 있으면 정치·편향 소재 다룰 때의 확산 페널티 근거로 써라 — 단 '가설+부분 실측'이니 단정하지 말고 '네가 관측했고 데이터도 그 방향(좋아요 최고·조회 최저권)' 꼴로. 대안 제시 = 확산형 소재(사회·양쪽이 갈리는 구도)와 협착형 소재(한쪽만 환호)의 구분을 게시물 콕 집어.
- [팔로워 표본 — 운영자 자가 보고]의 성향 메모는 운영자의 추정(데이터 아님): 다수 성향은 소재 감도 참고까지만 쓰고, 특정 성향 몰빵 권고·채널을 정치 성향 채널로 규정하는 표현은 금지. 성향이 섞인 표본 자체가 이 채널의 강점(명시적 표방 없이 시작·문화 혼합 출발)이니 그 균형을 지키는 방향으로 제안하라 — 성향 밖 표본이 반응한 게시물(🚪)이 바로 그 균형의 증거다.

[말투 — 살아있게(팬픽·웹소설 문체)]
친근한 소식통 톤. 단문으로 툭툭 끊되 길이 섞기 · 종결을 '~다'에 가두지 말고 '~더라(현장 톤)·~네(발견)·~거든(배경)'을 1~2번 · 수치는 끊어 던지고 자기정정으로 강조('97만 조회. 평소의 세 배.') · '무려·심지어·하필·그것도' 훅 · 대시(—)·쉼표로 뜸. 금지: 느낌표 떡칠·하트·2인칭 호칭(여러분/너)·신파·오글·말줄임(...) 남발.

[형식]
- 응답 첫 줄 = [3일] 마커 그 자체. 그 위에 '확인됐어/찾아봤어/이야기 풀게' 류 준비·확인 멘트, '---' 같은 구분선, 서두 사족 전면 금지(그건 네 사고 과정이지 브리핑이 아니다).
- 강조는 2층: 제일 크게 튄 수치·전환점 = *별표 하나*(1층 = 강조색·진짜 특별한 것만) · 그다음 어느정도 중요한 대목 = **별표 둘**(2층 = 볼드만·강조색 아님 · 문장에서 눈이 먼저 가야 할 핵심 명사·동사구). 각 섹션에 1층 0~1개·2층 1~3개 정도. 별표 사이 줄바꿈 금지 · 별표 짝 반드시 닫기.
- 헤더·번호목록·마크다운 제목·이모지 금지(섹션 마커 5줄과 전략 줄의 '→ '만 예외).

${PREV_BLOCK}
[데이터 = 이 채널의 실제 지표]
$BODY"

out=""; _to_tried=0   # _to_tried = 타임아웃(rc=124) 강제 계정 전환 1회 소진 플래그(analyze.sh 계승)
for _try in 1 2 3 4; do
  # 누적 벽시계 캡(평의회6 260714 · analyze.sh ANALYZE_JOB_DEADLINE 관용구 계승): 산술 최악 4×600s=40분 > 잡 timeout 20분 —
  # 15분 소진 후의 재시도는 성공해도 잡 하드킬로 수집 데이터 커밋까지 동반 유실될 운명이라, 브리프만 곱게 포기(fail-soft·직전 유지)하고 커밋 스텝을 살린다. 평상시 무영향(쿼터 실패 = 초 단위 반환).
  [ "$SECONDS" -gt 900 ] && { echo "::warning::chan-brief 시간 예산 소진(${SECONDS}s>900s) — 직전 brief 유지(fail-soft)"; exit 0; }
  out="$(printf '%s' "$PROMPT" | timeout 600 claude -p --model "$MODEL" --effort max --safe-mode --max-turns 8 \
    --allowedTools "WebFetch,WebSearch" \
    --disallowedTools "Bash,Edit,Write,Read,Glob,Grep,Task,NotebookEdit,TodoWrite" 2>/tmp/chanbrief.err)"; rc=$?
  if [ $rc -ne 0 ] || [ -z "$out" ]; then
    if claude_failover "$out$(cat /tmp/chanbrief.err 2>/dev/null)"; then continue; fi   # 쿼터 = 4계정 체인 1단씩(§📰-f)
    # 타임아웃(rc=124)은 출력이 비어 is_quota가 못 잡는 사각지대 → *딱 1회* 강제 계정 전환 후 재시도(analyze.sh:292 계승 · 운영자 260714 Q12 "막히면 대기 말고 바로 다른 계정 · 몇 번 돌리면 해결"). 서브2 지연(rc=124)에서 멈춰 서브3 미도달하던 것 봉합. 1회 제한 = 타임아웃 대개 입력바운드라 무한 전환은 시간·쿼터만 소진(평의회 260704).
    if [ $rc -eq 124 ] && [ "$_to_tried" = "0" ] && claude_failover_force; then _to_tried=1; continue; fi
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
SECS = [('d3', '3일'), ('d7', '7일'), ('d28', '28일'), ('m3', '3개월'), ('all', '전체'), ('overview', '총론')]   # v8 총론 분리(운영자 260714): all=전체기간 분석 / overview=비전·방향성·미션 큰그림 — 세그는 all까지, overview는 뷰어 (3)고정
parts = re.split(r'^\[(3일|7일|28일|3개월|전체|총론)\]\s*$', t, flags=re.M)
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
# 인사이트 아카이브(운영자 260714 3차 "모으면 뭔가 나올수도") — 일자별 회차 축적 = 추이 비교·패턴 채굴 원료 · 같은 날 재생성 = 최신으로 교체 · 캡 180회차(파일 비대 가드) · 뷰어 미노출(겉면 불변)
import os.path
log = 'viewer/chan_brief_log.jsonl'
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
print('chan-brief 저장:', len(t), '자', '·', len(secs), '섹션', '· 아카이브', len(rows[-180:]), '회차')
PY
echo "chan-brief: 갱신 완료($SHA)"
