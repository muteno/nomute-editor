#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""알고리즘 인사이트 일괄 집계 — 회차 원장(algo_runs)이 40줄+ 쌓이면 ISO주 1회 자동으로 패턴 표를 굽는다
(운영자 260802 "100개 이상 쌓이면 일괄 요약 → 뭐가 잘 뜨는지" · 평의회 260802 R6 계약).

분업 = 파이썬이 조인·보간·매칭·집계·표본 게이트 전부(수치는 여기서만 나옴) · LLM은 이 표를 서사화만(별건 —
LLM이 숫자를 생성하는 경로 0). 기존 집계 재발명 금지 — 게시시각·요일·포맷·주제 lift는 insta_signals(axes)가
정본이므로 여기선 안 만든다. 여기 질의는 **원장 없이는 불가능한 것만**:
  Q1 트렌드 일치×성과 — 게시 전후 창의 실검·급상승·커뮤니티와 캡션이 겹친 게시물 vs 아닌 것(소스별 lift)
  Q2 선행시차 — 트렌드 최초 관측(원장 등장·first_seen) 대비 게시까지 걸린 시간 버킷별 성과
  Q3 초기 속도곡선 — 나이-조회 점열 선형보간 v@24h/@72h → "24h에 얼마면 뜬 것"의 임계표
  Q7 놓친 트렌드 — 고강도 트렌드 중 ±24h 매칭 게시물 0건 목록(기회비용 후보)
정직 게이트: 원장 40줄 미만 = 스킵(rc0) · 버킷 n<5 = [표본부족] 억제(insta_signals MIN_N 하우스 표준) ·
게시물 40개 미만 = 헤더에 「조기 리포트 · 결론 유보」 배지. 발동 = insta-fetch 브리프 레인에서 KST ISO주가
바뀌었을 때 1회(운영자 절차 0 — "100개 도달 트리거"는 도달 후 죽은 코드라 기각) · ALGO_INSIGHT_FORCE=1 = 즉시.
산출 = apps/insta/data/algo_insight.json(기계) + algo_insight.md(사람 — 최신 1본 덮어쓰기 · 원장에서 재생성 가능).
fail-soft rc0 · stdlib only · 네트워크 0 · LLM 0콜(기계 보증 = shared/check_refs.py::check_algo_ledger).
"""
import datetime
import json
import os
import re
import statistics
import sys
import unicodedata

KST = datetime.timezone(datetime.timedelta(hours=9))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DIR = os.path.join(ROOT, 'apps', 'insta', 'data', 'algo_runs')
OUT_J = os.path.join(ROOT, 'apps', 'insta', 'data', 'algo_insight.json')
OUT_M = os.path.join(ROOT, 'apps', 'insta', 'data', 'algo_insight.md')
MIN_ROWS = 40      # 원장 최소 줄수(미달 = 스킵 · ~5줄/일이라 8일께 자연 개시)
MIN_N = 5          # 버킷 최소 표본(insta_signals 하우스 표준)
MATURE_H = 168     # '최종 성과'로 인정하는 최소 나이(7일)
GAP_MAX_H = 12     # 보간 괄호 간극 상한(초과 = 결측)


def _iter_rows():
    try:
        names = sorted(f for f in os.listdir(DIR) if re.fullmatch(r'\d{4}-\d{2}\.jsonl', f))
    except FileNotFoundError:
        return
    for name in names:
        with open(os.path.join(DIR, name), encoding='utf-8') as f:
            for ln in f:
                if not ln.strip():
                    continue
                try:
                    yield json.loads(ln)
                except Exception:
                    continue


def _ts(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00').replace('+0000', '+00:00'))
    except Exception:
        return None


def _norm(s):
    s = unicodedata.normalize('NFKC', s or '').lower()
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def _grams(s, n=2):
    s = _norm(s)
    return {s[i:i + n] for i in range(len(s) - n + 1)} if len(s) >= n else set()


def _jac(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 2) if xs else None


def _interp(series, tau):
    """(age_h, v) 점열 → v(tau) 선형보간. 괄호 간극 > GAP_MAX_H = 결측(정직)."""
    pts = sorted((a, v) for a, v in series if isinstance(a, (int, float)) and isinstance(v, (int, float)))
    lo = hi = None
    for a, v in pts:
        if a <= tau:
            lo = (a, v)
        if a >= tau and hi is None:
            hi = (a, v)
    if lo and abs(lo[0] - tau) < 0.5:
        return lo[1]
    if not lo or not hi:
        return None
    if hi[0] - lo[0] > GAP_MAX_H:
        return None
    if hi[0] == lo[0]:
        return lo[1]
    return lo[1] + (hi[1] - lo[1]) * (tau - lo[0]) / (hi[0] - lo[0])


def build(rows):
    now = datetime.datetime.now(KST)
    # ── 런 → 게시물 붕괴: id별 (age,views/shares/saved) 점열 + 메타(최초 관측이 캡션·라벨 원천) ──
    series, meta = {}, {}
    trend_first = {}     # norm(q) → {'ts','q','src'} 원장 전체 최초 관측(실검 first_seen 리셋 오염 교정 축)
    trend_rows = []      # (row_ts, [(q, src, strength)]) — 매칭 창 탐색용
    for r in rows:
        rts = _ts(r.get('ts'))
        items = []
        tr = r.get('tr') or {}
        for x in (tr.get('gt') or []):
            items.append((x.get('q'), 'gt', x.get('v'), x.get('st') or x.get('fs')))
        for x in (tr.get('gtp') or []):
            items.append((x.get('q'), 'gt', x.get('v'), x.get('st')))
        for x in (tr.get('sig') or []):
            items.append((x.get('q'), 'sig', None, x.get('fs')))
        for x in (tr.get('soc') or []):
            items.append((x.get('t'), 'soc', x.get('b'), None))
        clean = []
        for q, src, strength, born in items:
            nq = _norm(q)
            if len(nq) < 4:
                continue
            clean.append((q, nq, src, strength))
            bt = _ts(born) or rts
            if nq not in trend_first or (bt and trend_first[nq]['ts'] and bt < trend_first[nq]['ts']):
                trend_first[nq] = {'ts': bt, 'q': q, 'src': src}
        if rts:
            trend_rows.append((rts, clean))
        for p in ((r.get('ig') or {}).get('posts') or []):
            pid = p.get('id')
            if not pid:
                continue
            ins = p.get('ins') or {}
            series.setdefault(pid, []).append(
                (p.get('age_h'), ins.get('views'), ins.get('shares'), ins.get('saved'), ins.get('reach')))
            m = meta.setdefault(pid, {})
            for k in ('cap', 'kw', 'cat', 'st', 'fmt', 'era', 'pl', 'ts_post', 'prod'):
                if m.get(k) in (None, [], '') and p.get(k) not in (None, [], ''):
                    m[k] = p.get(k)

    posts = []
    for pid, pts in series.items():
        m = meta[pid]
        pt = _ts(m.get('ts_post'))
        vv = [(a, v) for a, v, *_ in pts]
        last = max((x for x in pts if isinstance(x[0], (int, float))), key=lambda x: x[0], default=None)
        final_v = last[1] if last else None
        final_age = last[0] if last else None
        v24 = _interp(vv, 24)
        v72 = _interp(vv, 72)
        sh = last[2] if last else None
        share_pm = round(sh / final_v * 1000, 2) if (isinstance(sh, (int, float)) and final_v) else None
        # ── 매칭(분석 시점 계산 — 원장엔 안 구움): 게시 -24h ~ +6h 창의 트렌드와 캡션 대조 ──
        matched, msrc = [], set()
        if pt:
            ncap = _norm(m.get('cap'))
            gcap = _grams(m.get('cap'))
            for rts, items in trend_rows:
                if not (pt - datetime.timedelta(hours=24) <= rts <= pt + datetime.timedelta(hours=6)):
                    continue
                for q, nq, src, _s in items:
                    if nq in ncap or (src == 'soc' and _jac(_grams(q), gcap) >= 0.5):
                        if q not in matched:
                            matched.append(q)
                        msrc.add(src)
        lead_h = None
        if matched and pt:
            firsts = [trend_first[_norm(q)]['ts'] for q in matched if _norm(q) in trend_first and trend_first[_norm(q)]['ts']]
            if firsts:
                lead_h = round((pt - min(firsts)).total_seconds() / 3600, 1)
        posts.append({'id': pid, 'cap': (m.get('cap') or '')[:60], 'cat': m.get('cat'), 'st': m.get('st'),
                      'fmt': m.get('fmt') or m.get('prod'), 'ts_post': m.get('ts_post'), 'n_obs': len(pts),
                      'final_v': final_v, 'final_age_h': final_age, 'v24': round(v24) if v24 else None,
                      'v72': round(v72) if v72 else None, 'share_pm': share_pm,
                      'matched': matched[:5], 'msrc': sorted(msrc), 'lead_h': lead_h})

    mature = [p for p in posts if (p.get('final_age_h') or 0) >= MATURE_H and p.get('final_v')]
    ch_med = _med([p['final_v'] for p in mature])

    def lift(a, b):
        return round(a / b, 2) if (a and b) else None

    # Q1 — 트렌드 일치 × 성과(소스별 분해)
    q1 = {}
    for key, grp in (('matched', [p for p in mature if p['matched']]),
                     ('unmatched', [p for p in mature if not p['matched']])):
        q1[key] = {'n': len(grp), 'views_med': _med([p['final_v'] for p in grp]),
                   'share_pm_med': _med([p['share_pm'] for p in grp])}
    q1['low_sample'] = min(q1['matched']['n'], q1['unmatched']['n']) < MIN_N
    q1['views_lift'] = None if q1['low_sample'] else lift(q1['matched']['views_med'], q1['unmatched']['views_med'])
    for src in ('gt', 'sig', 'soc'):
        grp = [p for p in mature if src in p['msrc']]
        q1[src] = {'n': len(grp), 'views_med': _med([p['final_v'] for p in grp]) if len(grp) >= MIN_N else None,
                   'low_sample': len(grp) < MIN_N}

    # Q2 — 선행시차 버킷(트렌드 최초 관측 → 게시)
    q2 = []
    for lo, hi, lb in ((-9999, 0, '선행 게시(트렌드 전)'), (0, 3, '0~3h'), (3, 6, '3~6h'), (6, 12, '6~12h'),
                       (12, 24, '12~24h'), (24, 9999, '24h+')):
        grp = [p for p in mature if isinstance(p.get('lead_h'), (int, float)) and lo <= p['lead_h'] < hi]
        q2.append({'bucket': lb, 'n': len(grp),
                   'views_med': _med([p['final_v'] for p in grp]) if len(grp) >= MIN_N else None,
                   'low_sample': len(grp) < MIN_N})

    # Q3 — 초기 속도 임계(24h 4분위 → 최종이 채널 중앙 넘을 확률)
    q3 = {'note': 'v@24h 사분위별 P(최종 조회 ≥ 채널 중앙값)', 'rows': [], 'low_sample': True}
    have = [p for p in mature if p.get('v24')]
    if len(have) >= MIN_N * 2 and ch_med:
        qs = statistics.quantiles([p['v24'] for p in have], n=4)
        q3['low_sample'] = False
        q3['quartile_edges'] = [round(x) for x in qs]
        for i, lb in enumerate(('Q1(하위)', 'Q2', 'Q3', 'Q4(상위)')):
            lo = qs[i - 1] if i else -1
            hi = qs[i] if i < 3 else float('inf')
            grp = [p for p in have if lo < p['v24'] <= hi]
            hit = [p for p in grp if p['final_v'] >= ch_med]
            q3['rows'].append({'q': lb, 'n': len(grp),
                               'p_hit': round(len(hit) / len(grp), 2) if grp else None})

    # Q7 — 놓친 고강도 트렌드(±24h 매칭 게시물 0)
    def _vol(v):
        try:
            return int(re.sub(r'[^0-9]', '', str(v)) or 0)
        except Exception:
            return 0
    hot = {}
    for rts, items in trend_rows:
        for q, nq, src, strength in items:
            s = _vol(strength) if src == 'gt' else (float(strength or 0) * 1000 if src == 'soc' else 500)
            if src == 'gt' and s < 20000 and _vol(strength) < 200:
                continue
            if src == 'soc' and float(strength or 0) < 10:
                continue
            cur = hot.get(nq)
            if not cur or s > cur['s']:
                hot[nq] = {'q': q, 'src': src, 's': s, 'ts': rts.isoformat(timespec='minutes')}
    matched_nq = {_norm(q) for p in posts for q in p['matched']}
    q7 = sorted((h for nq, h in hot.items() if nq not in matched_nq), key=lambda h: -h['s'])[:10]
    for h in q7:
        h.pop('s', None)

    early = len(mature) < 40
    doc = {'v': 1, 'iso_week': '%d-W%02d' % datetime.date.today().isocalendar()[:2],
           'generated_kst': now.isoformat(timespec='seconds'),
           'n_rows': len(rows), 'n_posts': len(posts), 'n_mature': len(mature),
           'span': [rows[0].get('ts') if rows else None, rows[-1].get('ts') if rows else None],
           'channel_final_med': ch_med, 'early': early,
           'q1_trend_match': q1, 'q2_lead_lag': q2, 'q3_velocity': q3, 'q7_missed': q7,
           'posts': sorted(posts, key=lambda p: -(p.get('final_v') or 0))[:60]}
    return doc


def render_md(d):
    L = ['# 알고리즘 인사이트 — 회차 원장 일괄 집계', '']
    L.append('- 생성: %s · 원장 %d줄 · 게시물 %d개(성숙 %d) · 기간 %s ~ %s' % (
        d['generated_kst'][:16], d['n_rows'], d['n_posts'], d['n_mature'],
        str(d['span'][0])[:10], str(d['span'][1])[:10]))
    if d['early']:
        L.append('- ⚠️ **조기 리포트 · 결론 유보** — 성숙 게시물 40개 미만. 방향 참고만, 단정 금지.')
    L.append('- 수치 없는 칸 = [표본부족](버킷 n<%d) — 지어내지 않는다.' % MIN_N)
    q1 = d['q1_trend_match']
    L += ['', '## Q1 트렌드 일치 × 성과(최종 조회 중앙값)', '',
          '| 군 | n | 조회 중앙 | 1천뷰당 공유 중앙 |', '|---|---|---|---|']
    for k, lb in (('matched', '트렌드 일치'), ('unmatched', '비일치')):
        g = q1[k]
        L.append('| %s | %d | %s | %s |' % (lb, g['n'], g['views_med'] or '[표본부족]', g['share_pm_med'] or '—'))
    if q1.get('views_lift'):
        L.append('')
        L.append('→ 일치군 조회 lift = ×%s' % q1['views_lift'])
    L += ['', '## Q2 트렌드 최초 관측 → 게시까지 시차별 성과', '', '| 시차 | n | 조회 중앙 |', '|---|---|---|']
    for b in d['q2_lead_lag']:
        L.append('| %s | %d | %s |' % (b['bucket'], b['n'], b['views_med'] or '[표본부족]'))
    q3 = d['q3_velocity']
    L += ['', '## Q3 초기 속도 임계 — ' + q3['note'], '']
    if q3['low_sample']:
        L.append('[표본부족] — v@24h 보간 가능 게시물이 아직 적다(회차가 쌓이면 자동 채워짐).')
    else:
        L += ['| v@24h 분위 | n | P(채널 중앙 돌파) |', '|---|---|---|']
        for r in q3['rows']:
            L.append('| %s | %d | %s |' % (r['q'], r['n'], r['p_hit'] if r['p_hit'] is not None else '—'))
    L += ['', '## Q7 놓친 고강도 트렌드(±24h 매칭 게시물 0 — 기회비용 후보)', '']
    if not d['q7_missed']:
        L.append('(없음)')
    for h in d['q7_missed']:
        L.append('- [%s] %s (%s)' % (h['src'], h['q'], h['ts']))
    L += ['', '---', '_결정론 집계(algo_insight.py) — LLM 수치 생성 0 · 원장에서 언제든 재생성 가능_', '']
    return '\n'.join(L)


def main():
    rows = list(_iter_rows())
    if len(rows) < MIN_ROWS:
        print('algo-insight: 원장 %d줄 < %d — 스킵(쌓이면 자동 개시)' % (len(rows), MIN_ROWS))
        return 0
    week = '%d-W%02d' % datetime.date.today().isocalendar()[:2]
    if os.environ.get('ALGO_INSIGHT_FORCE') != '1':
        try:
            if json.load(open(OUT_J, encoding='utf-8')).get('iso_week') == week:
                print('algo-insight: 이번 주(%s) 집계 완료분 존재 — 스킵' % week)
                return 0
        except Exception:
            pass
    doc = build(rows)
    json.dump(doc, open(OUT_J, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(OUT_M, 'w', encoding='utf-8').write(render_md(doc))
    print('algo-insight: 집계 완료 — 게시물 %d(성숙 %d) · %s' % (doc['n_posts'], doc['n_mature'], os.path.basename(OUT_M)))
    return 0


if __name__ == '__main__':
    try:
        rc = main()
    except BaseException as e:   # fail-soft — 파이프라인 비차단
        print('::warning::algo-insight 실패(fail-soft) —', repr(e))
        rc = 0
    sys.exit(rc)
