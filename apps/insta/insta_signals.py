#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""인스타 신호 엔진 — 직결 수집분(apps/insta/data)에서 *어느 축이 상대적으로 호응이 좋은가*를
정량 신호(signals.json)로 뽑는 분석 모듈 · LLM 0콜 · stdlib only(설치 0).

분업(정본 = apps/insta/00_지침 §4-7): 수치 계산 = 이 모듈(재현성·날조 방지) · 해석·전략 착지 = /insta 세션.
방법: 게시물별 절대 누적치 대신 {율 = 공유·저장·댓글·좋아요 per 1천뷰 · 속도 = views/경과일}을 만들고
      — lifetime 누적의 게시시점 편향 완화 — 축별 버킷 중앙값 ÷ 전체 중앙값 = 상대 lift,
      게시물 점수 = 강건 z(중앙값+MAD · 큐레이션 OUT 감쇠와 동일 하우스 표준)의 전략 가중합.
호출: python3 apps/insta/insta_signals.py  → apps/insta/data/signals.json 갱신 + 한국어 요약 stdout.
한계(정직): n<5 버킷 = [표본부족](결론 금지 플래그) · 카테고리 = 키워드 휴리스틱(category_src='kw' —
      세션이 재라벨 가능) · 율·속도는 편향 *완화*지 노출량 통제 실험(A/B)이 아님 = 관찰 신호.
"""
import datetime
import json
import os
import re
import statistics
import sys
from zoneinfo import ZoneInfo

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
KST = ZoneInfo('Asia/Seoul')

# 전략 가중(지침 §3-3 참여 우선순위의 사상 · [추정 · 운영자 튜닝 노브])
W = {'share_pm': 3.0, 'save_pm': 2.0, 'cmt_pm': 1.5, 'like_pm': 1.0, 'vpd': 1.5}
MIN_N = 5           # 이 미만 버킷 = [표본부족]
MIN_AGE_D = 0.25    # 신생글 속도 폭주 가드(최소 6시간로 나눔)

RATE_FIELDS = ('vpd', 'share_pm', 'save_pm', 'cmt_pm', 'like_pm')
CATS = {
    '정치': ['대통령', '국회', '여야', '의원', '장관', '민주', '국민의힘', '선거', '청문', '탄핵', '시장', '정부', '이준석'],
    '사회사건': ['사고', '화재', '실종', '사망', '구조', '경찰', '판사', '재판', '검찰', '체포', '붕괴', '돌진'],
    '스포츠': ['골', '경기', '감독', '선수', '응원', '월드컵', '축구', '야구', '16강', '결승', '홍명보', '구단', '홀란드'],
    '연예문화': ['배우', '아이돌', '드라마', '영화', '예능', '컴백', '열애', '연인', '소속사', 'PD', '편집'],
    '국제': ['트럼프', '미국', '일본', '중국', '멕시코', '노르웨이', '유럽', '러시아', 'CIA', 'FBI'],
    '테크경제': ['반도체', 'AI', '주가', '금리', '서버', '데이터', '조 원', '조원', '삼성전자'],
}
HOUR_BANDS = [(0, 6, '새벽0-6'), (6, 11, '오전6-11'), (11, 14, '점심11-14'),
              (14, 18, '오후14-18'), (18, 22, '저녁18-22'), (22, 24, '밤22-24')]

# 알고리즘 3기(운영자 관측 = insta_events.json과 짝 · 5/7 꺾임 · 7/11 회복) — 게시일(KST) 기준
def algo_era(d):
    if d <= '2026-05-07':
        return '부흥기(~5/7)'
    if d <= '2026-07-10':
        return '침체기(5/8~7/10)'
    return '회복기(7/11~)'


def _load_news_cat():
    """뉴스 주제 분류기(CAT_KW 222개 · scraper/to_candidates.py) 재사용 — 텍스트 파싱(모듈 실행 회피 ·
    단방향 의존 = 큐레이션 무접촉 · 운영자 260713 "이미 있는 주제 분류기 찾아서 보완"). 실패 = 빈 사전."""
    try:
        src = open(os.path.join(DATA, '..', '..', '..', 'scraper', 'to_candidates.py'), encoding='utf-8').read()
        m = re.search(r'CAT_KW\s*=\s*(\{.*?\n\})', src, re.S)
        return __import__('ast').literal_eval(m.group(1)) if m else {}
    except Exception:
        return {}


def _build_cats():
    """신 주제 사전 = 6버킷 확정(정치·사회·경제·국제·문화·테크 — 운영자 260713 · 스포츠/가십류 = 문화로 편성)."""
    base = {k: list(v) for k, v in _load_news_cat().items()}
    if not base:
        return CATS   # 뉴스 분류기 로드 실패 = 구 사전 폴백
    for old_k, new_k in (('정치', '정치'), ('사회사건', '사회'), ('연예문화', '문화'), ('국제', '국제'), ('테크경제', '테크')):
        if new_k in base:
            base[new_k] += [w for w in CATS.get(old_k, []) if w not in base[new_k]]
    if '문화' in base:   # 스포츠 버킷 폐지 → 키워드는 문화로 흡수(운영자 "스포츠는 다 문화로")
        base['문화'] += [w for w in CATS.get('스포츠', []) if w not in base['문화']]
    return base


CATS2 = _build_cats()
DOW = ['월', '화', '수', '목', '금', '토', '일']


def jload(name):
    try:
        with open(os.path.join(DATA, name), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def first_line(caption):
    return (caption or '').split('\n')[0].strip()


def naming_features(name):
    return {
        '이모지머리': bool(re.match(r'^[^\w\s\'"‘’“”]', name)) if name else False,
        '인용부호': bool(re.search(r'[\'"‘’“”]', name)),
        '질문형': '?' in name,
        '숫자포함': bool(re.search(r'\d', name)),
        '말줄임': ('…' in name) or ('...' in name),
    }


def naming_style(name, feats):
    # 우선순위 분류(중복은 naming_feature 축이 따로 잡음): 무캡션 > 인용서사 > 질문 > 이모지브리핑 > 평서
    if not name:
        return '무캡션(영상문구만)'
    if feats['인용부호']:
        return '인용·서사'
    if feats['질문형']:
        return '질문'
    if feats['이모지머리']:
        return '이모지브리핑'
    return '평서'


def category(name):
    best, hits = '기타', 0
    for cat, kws in CATS2.items():
        h = sum(1 for k in kws if k in name)
        if h > hits:
            best, hits = cat, h
    return best


def cap_len_band(n):
    if n == 0:
        return '0(무캡션)'
    if n <= 20:
        return '~20자'
    if n <= 35:
        return '21~35자'
    return '36자+'


_CAT_OVR = None   # 운영자 수동 라벨 오버라이드(data/cat_overrides.json = {media_id: 주제} · 라벨링 도구 회신 배선 — 없으면 no-op)


def cat_override(media_id, fallback):
    global _CAT_OVR
    if _CAT_OVR is None:
        _CAT_OVR = jload('cat_overrides.json') or {}
    return _CAT_OVR.get(str(media_id)) or fallback


def enrich(post, fetched):
    ins = post.get('insights') or {}
    views = ins.get('views') or 0
    ts = datetime.datetime.fromisoformat(post['timestamp'].replace('+0000', '+00:00'))
    ts_kst = ts.astimezone(KST)
    age_d = max((fetched - ts).total_seconds() / 86400, MIN_AGE_D)
    pm = lambda k: (ins.get(k) or 0) / views * 1000 if views else 0.0
    name = first_line(post.get('caption'))
    feats = naming_features(name)
    band = next(b for lo, hi, b in HOUR_BANDS if lo <= ts_kst.hour < hi)
    return {
        'id': post.get('id'), 'date_kst': ts_kst.strftime('%m/%d %H시'), 'iso': ts_kst.strftime('%Y-%m-%d'), 'name': name[:60],   # iso = 뷰어 심층 모달 최신순 정렬 키(연 경계 안전)
        'format': '릴스' if post.get('media_product_type') == 'REELS' else '피드',
        'style': naming_style(name, feats), 'feats': feats,
        'cat': cat_override(post.get('id'), category(name)), 'cat_src': 'kw+news+ovr',   # 뉴스 CAT_KW 계승 병합 + 운영자 수동 라벨 우선(260713)
        'era': algo_era(ts_kst.date().isoformat()),
        'hour_band': band, 'dow': DOW[ts_kst.weekday()], 'len_band': cap_len_band(len(name)),
        'views': views, 'vpd': views / age_d,
        'share_pm': pm('shares'), 'save_pm': pm('saved'), 'cmt_pm': pm('comments'), 'like_pm': pm('likes'),
        'watch_ms': ins.get('ig_reels_avg_watch_time'),
        'permalink': post.get('permalink'),
    }


def med(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else 0.0


def robust_z(vals):
    """중앙값+MAD 강건 z(하우스 표준 — 큐레이션 OUT 감쇠 동일 철학). MAD=0 → 전원 0."""
    m = med(vals)
    mad = med([abs(v - m) for v in vals])
    if mad == 0:
        return [0.0] * len(vals)
    return [(v - m) / (1.4826 * mad) for v in vals]


def bucket_lifts(posts, key_fn, g_med):
    groups = {}
    for p in posts:
        keys = key_fn(p)
        for k in (keys if isinstance(keys, list) else [keys]):
            groups.setdefault(k, []).append(p)
    out = []
    for k, grp in groups.items():
        lifts = {}
        for f in RATE_FIELDS:
            gm = g_med[f]
            bm = med([p[f] for p in grp])
            lifts[f] = round(bm / gm, 2) if gm else None
        top = max(grp, key=lambda p: p['score'])
        out.append({'bucket': k, 'n': len(grp), 'lift': lifts,
                    'low_sample': len(grp) < MIN_N,
                    'top': {'name': top['name'], 'score': top['score']}})
    out.sort(key=lambda b: -(b['lift'].get('share_pm') or 0))
    return out


def online_peak_kst(audience):
    """online_followers(UTC 시간대 히스토그램) → KST 피크 상위 3시간. 형식 방어적 파싱.
    API는 일 버킷 리스트로 회신 — 첫 버킷만 읽던 구버그를 전 버킷 합산으로 수리(빈 value 버킷 = 자연 무시)."""
    try:
        raw = audience.get('online_followers')
        if isinstance(raw, list):
            merged = {}
            for b in raw:
                v = (b or {}).get('value')
                if isinstance(v, dict):
                    for h, c in v.items():
                        merged[h] = merged.get(h, 0) + (c or 0)
            raw = merged or None
        if not isinstance(raw, dict) or not raw:
            return None
        kst_hours = {}
        for h, c in raw.items():
            kst_hours[(int(h) + 9) % 24] = kst_hours.get((int(h) + 9) % 24, 0) + (c or 0)
        top = sorted(kst_hours.items(), key=lambda x: -x[1])[:3]
        return [f'{h}시(KST)' for h, _ in top]
    except Exception:
        return None


def audience_overlay(audience):
    """접속 시간대 오버레이 — API(online_followers) 우선 · 공회신(260713~ 빈 value 실측)이면
    운영자 수기 실측(audience_manual.json = 인사이트 '팔로워 활동 시간' 스크린샷) 폴백. 출처 딱지 동봉 = 브리프가 근거를 밝힘."""
    peak = online_peak_kst(audience or {})
    if peak:
        return {'online_peak_kst': peak, 'online_src': 'api'}
    man = (audience or {}).get('manual') or {}
    hours = man.get('online_hours_kst')
    try:
        if isinstance(hours, dict) and hours:
            hs = sorted(((int(h), v or 0) for h, v in hours.items()), key=lambda x: x[0])
            top = sorted(hs, key=lambda x: -x[1])[:3]
            return {'online_peak_kst': [f'{h}시(KST)' for h, _ in top],
                    'online_src': f"manual({man.get('as_of') or ''})",
                    'online_hours_kst': {str(h): v for h, v in hs},
                    'online_note': str(man.get('note') or '')[:160]}
    except Exception:
        pass
    return {'online_peak_kst': peak}


def compute(media_doc, audience=None):
    fetched = datetime.datetime.fromisoformat(media_doc['fetched_kst'])
    posts = [enrich(p, fetched) for p in media_doc.get('media') or []]
    posts = [p for p in posts if p['views'] > 0]
    if len(posts) < 3:
        return {'error': f'게시물 표본 부족(n={len(posts)}) — 신호 계산 생략'}

    # 게시물 점수 = 율·속도 강건 z의 전략 가중합
    zs = {f: robust_z([p[f] for p in posts]) for f in RATE_FIELDS}
    for i, p in enumerate(posts):
        contrib = {f: round(W[f] * zs[f][i], 2) for f in RATE_FIELDS}
        p['score'] = round(sum(contrib.values()), 2)
        p['drivers'] = [k for k, _ in sorted(contrib.items(), key=lambda x: -x[1])[:2] if contrib[k] > 0]

    g_med = {f: med([p[f] for p in posts]) for f in RATE_FIELDS}
    axes = {
        'format': bucket_lifts(posts, lambda p: p['format'], g_med),
        'naming_style': bucket_lifts(posts, lambda p: p['style'], g_med),
        'naming_feature': bucket_lifts(posts, lambda p: [k for k, v in p['feats'].items() if v] or ['특징없음'], g_med),
        'category_kw': bucket_lifts(posts, lambda p: p['cat'], g_med),
        'hour_band': bucket_lifts(posts, lambda p: p['hour_band'], g_med),
        'dow': bucket_lifts(posts, lambda p: p['dow'], g_med),
        'caption_len': bucket_lifts(posts, lambda p: p['len_band'], g_med),
        'algo_era': bucket_lifts(posts, lambda p: p['era'], g_med),
    }
    def seg_summary(key_fn):
        segs = {}
        for p in posts:
            segs.setdefault(key_fn(p), []).append(p)
        out = {}
        for k, grp in segs.items():
            vs = [p['views'] for p in grp]
            out[k] = {'n': len(grp), 'views_avg': round(statistics.mean(vs)), 'views_med': round(statistics.median(vs)),
                      'share_pm_med': round(med([p['share_pm'] for p in grp]), 2),
                      'save_pm_med': round(med([p['save_pm'] for p in grp]), 2),
                      'cmt_pm_med': round(med([p['cmt_pm'] for p in grp]), 2),
                      'like_pm_med': round(med([p['like_pm'] for p in grp]), 2)}
        return out
    # 절대 요약 3종(운영자 260713 — 릴스 평균·포스트 평균 / 주제별 반응률 / 3기 대비)
    fmt_sum = seg_summary(lambda p: p['format'])
    topic_sum = seg_summary(lambda p: p['cat'])
    era_sum = seg_summary(lambda p: p['era'])
    # 반응 지문(fp) + 확장문 딱지(exp) — 회초리 브리프 재료(운영자 260715 Q02·Q03)
    # fp = 채널 중앙 대비 1.5배↑로 튄 지배 반응축(게시물 단위 표본의 대리 지표 — IG API는 게시물별 인구통계 미제공)
    # exp = 주력(볼륨 1위) 주제 밖 + 그 주제 평소 조회 중앙의 1.5배↑ + 저장 강세(채널 중앙 1.3배↑) = 기존 팔로워 밖 새 표본 유입 신호
    FP_LB = {'share_pm': '공유형', 'save_pm': '저장형', 'cmt_pm': '댓글형', 'like_pm': '좋아요형'}
    vol_top = max(topic_sum, key=lambda k: topic_sum[k]['n']) if topic_sum else None
    for p in posts:
        ratios = {f: p[f] / g_med[f] for f in FP_LB if g_med.get(f)}
        fdom = max(ratios, key=ratios.get) if ratios else None
        p['fp'] = FP_LB[fdom] if fdom and ratios[fdom] >= 2.0 else None   # 2배↑만 = 지문(탑 표본은 원래 1.5배쯤 튀어 변별력 없음 실측 260715)
        tmed = (topic_sum.get(p['cat']) or {}).get('views_med') or 0
        p['exp'] = bool(vol_top and p['cat'] not in (vol_top, '기타') and tmed and p['views'] >= 2.0 * tmed
                        and g_med.get('save_pm') and p['save_pm'] >= 1.5 * g_med['save_pm'])
    span = sorted(p['date_kst'] for p in posts)
    flags = ['시간대·요일 축 = 게시 몰림 편향 주의(운영자 자가 보고 260713: 휴식기에 몰아 올려 쏠림 — 인과 해석 금지)',
             '율·속도 기반 = 누적 편향 완화(통제 실험 아님 · 관찰 신호)',
             f'n<{MIN_N} 버킷 = low_sample=true → 결론 금지·후속 표본 대기',
             '카테고리 = 키워드 휴리스틱(cat_src=kw) — 세션이 오분류 재라벨 가능']
    return {
        'generated_kst': datetime.datetime.now(KST).isoformat(timespec='seconds'),
        'source_fetched_kst': media_doc.get('fetched_kst'),
        'n_posts': len(posts), 'span': [span[0], span[-1]],
        'weights': W, 'global_median': {k: round(v, 3) for k, v in g_med.items()},
        'axes': axes,
        'format_summary': fmt_sum, 'topic_summary': topic_sum, 'era_summary': era_sum,
        'posts': sorted(posts, key=lambda p: -p['score'])[:100],   # 저장 cap(전체 표본은 axes에 반영 · 비대 방지)
        'audience_overlay': audience_overlay(audience),
        'flags': flags,
    }


def fmt_lift(b):
    lf = b['lift']
    tag = ' [표본부족]' if b['low_sample'] else ''
    return (f"{b['bucket']}: 공유율 ×{lf['share_pm']} · 저장율 ×{lf['save_pm']} · "
            f"조회속도 ×{lf['vpd']} (n={b['n']}){tag}")


def _daily_timeseries(daily):
    """일일값 시계열 병합 → (daily_series, meta). 운영자 260713 일일 추이 배선.
    합성 = 과거 시드(insta_history.json — 대시보드 CSV 8개월 · insta_history_import.py 산출)
         ∪ 봇 수집(insights_daily.jsonl): follower_count_series → follows(일별 신규 팔로우) ·
           account_daily(time_series·있으면) → views/reach/profile_views/interactions ·
           media_count 인접일 차분 → posts(일일 게시수 · 연속한 날만 = gap 과대귀속 방지).
    규칙: 과거 시드 우선 · 봇은 빈 날짜만 채움(결정적) · 봇 time_series는 수집일 이전 날짜만(부분일 제외) ·
          결측 = 키 없음(gap 유지 = 차트가 선 끊어 정직 표시). 출력 = 날짜 오름차순 [{date, ...지표}]."""
    hist = jload('insta_history.json')
    merged = {}
    def put(d, k, v):
        if v is None or len(d) != 10:
            return
        merged.setdefault(d, {}).setdefault(k, v)   # 선점자 우선(과거 시드 → 봇 순서로 호출)
    for r in (hist.get('daily') or []):
        d = r.get('date') or ''
        for k in ('views', 'reach', 'profile_views', 'interactions', 'follows'):
            put(d, k, r.get(k))
    for row in daily:
        fd = (row.get('fetched_kst') or '')[:10]
        for p in (row.get('follower_count_series') or []):
            put((p.get('end_time') or '')[:10], 'follows', p.get('value'))
        ts = row.get('account_daily') or {}
        for k_api, k_out in (('views', 'views'), ('reach', 'reach'), ('profile_views', 'profile_views'),
                             ('total_interactions', 'interactions'), ('accounts_engaged', 'engaged')):
            arr = ts.get(k_api)
            if isinstance(arr, list):
                for p in arr:
                    et = (p.get('end_time') or '')[:10]
                    if et and et < fd:   # 수집일 당일 = 진행 중 부분값 → 제외
                        put(et, k_out, p.get('value'))
    # 일일 게시수 ① 정본 = 전 게시물 백필 타임스탬프 일별 집계(KST · 수집일 = 진행 중 → 제외)
    mall = jload('media_all.json')
    if mall and mall.get('media'):
        cnt = {}
        for m in mall['media']:
            ts = m.get('timestamp')
            if not ts:
                continue
            try:
                d = datetime.datetime.fromisoformat(ts.replace('+0000', '+00:00')).astimezone(KST).date().isoformat()
            except ValueError:
                continue
            cnt[d] = cnt.get(d, 0) + 1
        fetch_d = (mall.get('fetched_kst') or '')[:10]
        lo = min(merged) if merged else '0000-00-00'   # 지표 시계열 범위 안만(계정 초기 잔재로 축 안 늘림)
        for d in sorted(cnt):
            if lo <= d < fetch_d:
                put(d, 'posts', cnt[d])
        if cnt:   # 범위 내 게시 0일 = 명시적 0(백필 = 전수라 0이 사실 · 결측 아님)
            for d in list(merged):
                if d < fetch_d and 'posts' not in merged[d]:
                    merged[d]['posts'] = 0
    # ② 보충 = media_count 인접일 차분(백필 없을 때 · 연속한 날만)
    mc = {}
    for row in daily:
        d = (row.get('fetched_kst') or '')[:10]
        v = (row.get('profile') or {}).get('media_count')
        if len(d) == 10 and v is not None:
            mc[d] = v   # 나중 스냅샷이 덮음 = 그날 마지막
    md = sorted(mc)
    for i in range(1, len(md)):
        a, b = md[i - 1], md[i]
        try:
            gap = (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days
        except ValueError:
            continue
        if gap == 1:
            put(b, 'posts', max(mc[b] - mc[a], 0))
    series = [dict({'date': d}, **merged[d]) for d in sorted(merged)]
    meta = {'history': hist.get('metrics') or {}, 'history_cut': hist.get('cut_partial_day'),
            'note': '일별값 · 과거 = 대시보드 CSV 시드 · 이후 = 봇 수집 · 결측 = gap 유지',
            'events': (jload('insta_events.json') or {}).get('events') or []}   # 운영자 관측 변곡 마커(차트 세로선)
    return series, meta


def _avg_signals(series):
    """평균 신호(운영자 260713 — 실사용 핵심 ①): 지표별 {전 기간 일평균 · 최근 7일 평균 · 배율 · 표본일}.
    posts 포함 = *평균적으로 몇 개 올렸나* + *요즘이 평소 대비 어디냐*를 수치로."""
    out = {}
    for k in ('posts', 'views', 'reach', 'profile_views', 'interactions', 'follows'):
        vals = [r[k] for r in series if r.get(k) is not None]
        if len(vals) < 8:
            continue
        avg_all = statistics.mean(vals)
        avg_7 = statistics.mean(vals[-7:])
        out[k] = {'avg_all': round(avg_all, 2), 'avg_7d': round(avg_7, 2),
                  'ratio_7d': round(avg_7 / avg_all, 2) if avg_all else None, 'n_days': len(vals)}
    return out


def _corr(a, b):
    """피어슨 상관(표본 부족·분산 0 = None) — 게시-팔로워 인과 실측용."""
    if len(a) != len(b) or len(a) < 30:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** .5
    return round(sum((x - ma) * (y - mb) for x, y in zip(a, b)) / den, 2) if den else None


def _timing_stats(series):
    """게시-팔로워 인과 실측(운영자 260715 Q02 — 회초리 브리프의 '왜냐면' 근거).
    핵심 실측(260715 분석 보고서 계승): 팔로워는 게시 *행위*가 아니라 당일 *조회수*를 따른다."""
    rows = [r for r in series if isinstance(r.get('follows'), int) and isinstance(r.get('posts'), int)]
    while rows and rows[-1]['follows'] == 0:   # 말미 0 연속 = 봇 미수집 결측(placeholder) — 진짜 0과 구분 불가라 실측창에서 제외
        rows.pop()
    if len(rows) < 30:
        return None
    F = [r['follows'] for r in rows]
    P = [r['posts'] for r in rows]
    V = [r.get('views') or 0 for r in rows]
    rest = [r['follows'] for r in rows if r['posts'] == 0]
    postd = [r['follows'] for r in rows if r['posts'] > 0]
    # 휴식일 상대 지표(시대 교란 보정): 그날 증가 / 직전 3일 평균 — 절대 중앙값은 부흥기 휴식일이 끌어올려 오독 위험(실측 260715)
    rest_rel = []
    for i, r in enumerate(rows):
        if r['posts'] == 0 and i >= 3:
            prev = statistics.mean(x['follows'] for x in rows[i - 3:i])
            if prev > 0:
                rest_rel.append(r['follows'] / prev)
    era_fp = {}
    for r in rows:
        e = algo_era(r['date'])
        d = era_fp.setdefault(e, {'f': 0, 'p': 0})
        d['f'] += r['follows']; d['p'] += r['posts']
    return {
        'n_days': len(rows), 'from': rows[0]['date'], 'to': rows[-1]['date'],
        'corr_views_follows': _corr(V, F),          # 당일 조회↔팔로워 증가
        'corr_posts_follows': _corr(P, F),          # 당일 게시 수↔팔로워 증가
        'corr_views_follows_next': _corr(V[:-1], F[1:]),   # 조회 D일↔팔로워 D+1일(24~48h 시차)
        'rest_day_med': round(statistics.median(rest)) if rest else None,
        'post_day_med': round(statistics.median(postd)) if postd else None,
        'rest_days_n': len(rest),
        'rest_rel_med': round(statistics.median(rest_rel), 2) if rest_rel else None,   # 휴식일 증가 = 직전 3일 평균 대비 배율 중앙(1 미만 = 쉬면 꺼짐)
        'rest_rel_med_ex_viral': round(statistics.median([x for x in rest_rel if x < 3]), 2) if [x for x in rest_rel if x < 3] else None,
        'follows_per_post_by_era': {k: round(v['f'] / v['p']) for k, v in era_fp.items() if v['p']},
        'note': '휴식일 증가 사례는 직전 게시물 지연 바이럴(예: 7/11 무게시 +299 = 전일까지 릴스 재배급 조회 295만) — 휴식 자체가 증가 요인인 적 없음',
    }


def _audience_sample(aud):
    """팔로워 표본(계정 단위 인구통계 + 운영자 자가 보고 노트 · 운영자 260715 Q03).
    게시물 단위 인구통계는 IG API 미제공 — 게시물 표본은 posts의 fp(반응 지문)가 대리."""
    fd = (aud or {}).get('follower_demographics') or {}
    out = {}
    def top(axis, n):
        blk = fd.get(axis) or []
        res = (blk[0].get('results') or []) if blk else []
        tot = sum(r.get('value') or 0 for r in res)
        if not tot:
            return None
        return [{'k': '·'.join(r['dimension_values']), 'pct': round(r['value'] / tot * 100, 1)}
                for r in sorted(res, key=lambda r: -(r.get('value') or 0))[:n]]
    for axis, key, n in (('age,gender', 'age_gender_top', 5), ('country', 'country_top', 3), ('city', 'city_top', 3)):
        v = top(axis, n)
        if v:
            out[key] = v
    note = ((aud or {}).get('manual') or {}).get('operator_audience_note')
    if note:
        out['operator_note'] = note
    return out or None


def main():
    # 표본 = 전 게시물 백필(media_all · 운영자 260713 "기존꺼 파악") 우선 — 인사이트 유표본 30 미만 = 최근 25개 폴백
    mall = jload('media_all.json')
    media = None
    if mall and sum(1 for m in (mall.get('media') or []) if (m.get('insights') or {}).get('views')) >= 30:
        media = mall
    media = media or jload('media_latest.json')
    if not media:
        print('데이터 없음 — insta-fetch 수집분(apps/insta/data/media_latest.json)부터 필요')
        return 1
    aud = jload('audience.json') or {}
    man = jload('audience_manual.json')   # 운영자 수기 실측(API online_followers 공회신 폴백 — audience_overlay 참조)
    if man:
        aud['manual'] = man
    sig = compute(media, aud)
    if 'error' in sig:
        print(sig['error'])
        return 1
    with open(os.path.join(DATA, 'signals.json'), 'w', encoding='utf-8') as f:
        json.dump(sig, f, ensure_ascii=False, indent=1)
    # 뷰어 소비본(채널 요약 탭 · 운영자 260713) — 슬림 병합 1파일 = viewer/insta_data.json
    try:
        daily = [json.loads(l) for l in open(os.path.join(DATA, 'insights_daily.jsonl'), encoding='utf-8') if l.strip()]
        last = daily[-1] if daily else {}
        posts = [{k: p.get(k) for k in ('date_kst', 'iso', 'format', 'style', 'cat', 'era', 'name', 'views', 'score', 'share_pm', 'save_pm', 'fp', 'exp', 'permalink')} for p in sig['posts'][:100]]   # 100개+cat·era·iso = 심층 모달(게시물 탐색 — 정렬·포맷/주제 필터) 재료(운영자 260713 "앱 내에서 볼 경로")
        med = json.load(open(os.path.join(DATA, 'media_latest.json'), encoding='utf-8'))
        thumbs = [{'th': m.get('thumbnail_url') or m.get('media_url'), 'u': m.get('permalink'),
                   't': first_line(m.get('caption'))[:40]} for m in (med.get('media') or [])[:12]]
        vdoc = {'generated_kst': sig['generated_kst'], 'profile': last.get('profile'), 'account_day': last.get('account_day'),
                'signals': {'axes': sig['axes'], 'n_posts': sig['n_posts']}, 'posts': posts, 'thumbs': thumbs,
                **sig['audience_overlay']}   # online_peak_kst(+수기 폴백 시 online_src·online_hours_kst·online_note) — 뷰어 예약 필·chan_brief 다이제스트 공용
        # 일일 추이 배선(운영자 260713) — 과거 CSV 시드 ∪ 봇 수집 일별값을 뷰어까지 전달(차트는 후속·플레이그라운드)
        series_daily, daily_meta = _daily_timeseries(daily)
        vdoc['daily_series'] = series_daily
        vdoc['daily_meta'] = daily_meta
        vdoc['avg'] = _avg_signals(series_daily)   # 평균 게시량·평균 대비 현재(운영자 실사용 핵심)
        vdoc['fmt'] = sig.get('format_summary')    # 릴스·피드 절대 요약
        vdoc['topics'] = sig.get('topic_summary')  # 주제별 반응률(뉴스 분류기 계승)
        vdoc['eras'] = sig.get('era_summary')      # 알고리즘 3기 대비
        vdoc['timing'] = _timing_stats(series_daily)       # 게시-팔로워 인과 실측(회초리 근거 · 운영자 260715 Q02)
        vdoc['audience_sample'] = _audience_sample(aud)    # 팔로워 표본(인구통계+운영자 노트 · 운영자 260715 Q03)
        vp = os.path.abspath(os.path.join(DATA, '..', '..', '..', 'viewer', 'insta_data.json'))
        with open(vp, 'w', encoding='utf-8') as f:
            json.dump(vdoc, f, ensure_ascii=False, indent=1)
        print('뷰어 소비본 OK → viewer/insta_data.json')
    except Exception as e2:
        print(f'뷰어 소비본 실패(비치명 · 세션/뷰어는 구본 유지): {e2}')

    print(f"■ 인스타 신호 요약 — n={sig['n_posts']} · {sig['span'][0]}~{sig['span'][1]} · 기준 = 전체 중앙값 대비 상대 lift")
    label = {'format': '포맷', 'naming_style': '네이밍 스타일', 'naming_feature': '네이밍 특징(중복 허용)',
             'category_kw': '카테고리(kw)', 'hour_band': '업로드 시간대', 'dow': '요일', 'caption_len': '네이밍 길이'}
    for ax, lb in label.items():
        print(f'[{lb}]')
        for b in sig['axes'][ax]:
            print('  ' + fmt_lift(b))
    peak = sig['audience_overlay']['online_peak_kst']
    if peak:
        print(f"[팔로워 접속 피크] {' · '.join(peak)}")
    print('[게시물 점수 TOP5] (전략 가중 강건 z 합)')
    for p in sig['posts'][:5]:
        print(f"  {p['score']:+.1f} [{p['format']}/{p['style']}] {p['name'][:40]} — 드라이버: {','.join(p['drivers']) or '-'}")
    print('→ signals.json 갱신 완료(해석·전략 착지 = /insta 세션 몫 · 지침 §4-7)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
