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
    for cat, kws in CATS.items():
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
        'id': post.get('id'), 'date_kst': ts_kst.strftime('%m/%d %H시'), 'name': name[:60],
        'format': '릴스' if post.get('media_product_type') == 'REELS' else '피드',
        'style': naming_style(name, feats), 'feats': feats,
        'cat': category(name), 'cat_src': 'kw',
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
    """online_followers(UTC 시간대 히스토그램) → KST 피크 상위 3시간. 형식 방어적 파싱."""
    try:
        raw = audience.get('online_followers')
        if isinstance(raw, list):
            raw = raw[0].get('value') if raw else None
        if not isinstance(raw, dict):
            return None
        kst_hours = {}
        for h, c in raw.items():
            kst_hours[(int(h) + 9) % 24] = kst_hours.get((int(h) + 9) % 24, 0) + (c or 0)
        top = sorted(kst_hours.items(), key=lambda x: -x[1])[:3]
        return [f'{h}시(KST)' for h, _ in top]
    except Exception:
        return None


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
    }
    span = sorted(p['date_kst'] for p in posts)
    flags = ['율·속도 기반 = 누적 편향 완화(통제 실험 아님 · 관찰 신호)',
             f'n<{MIN_N} 버킷 = low_sample=true → 결론 금지·후속 표본 대기',
             '카테고리 = 키워드 휴리스틱(cat_src=kw) — 세션이 오분류 재라벨 가능']
    return {
        'generated_kst': datetime.datetime.now(KST).isoformat(timespec='seconds'),
        'source_fetched_kst': media_doc.get('fetched_kst'),
        'n_posts': len(posts), 'span': [span[0], span[-1]],
        'weights': W, 'global_median': {k: round(v, 3) for k, v in g_med.items()},
        'axes': axes,
        'posts': sorted(posts, key=lambda p: -p['score']),
        'audience_overlay': {'online_peak_kst': online_peak_kst(audience or {})},
        'flags': flags,
    }


def fmt_lift(b):
    lf = b['lift']
    tag = ' [표본부족]' if b['low_sample'] else ''
    return (f"{b['bucket']}: 공유율 ×{lf['share_pm']} · 저장율 ×{lf['save_pm']} · "
            f"조회속도 ×{lf['vpd']} (n={b['n']}){tag}")


def main():
    media = jload('media_latest.json')
    if not media:
        print('데이터 없음 — insta-fetch 수집분(apps/insta/data/media_latest.json)부터 필요')
        return 1
    sig = compute(media, jload('audience.json'))
    if 'error' in sig:
        print(sig['error'])
        return 1
    with open(os.path.join(DATA, 'signals.json'), 'w', encoding='utf-8') as f:
        json.dump(sig, f, ensure_ascii=False, indent=1)
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
