#!/usr/bin/env python3
# 노뮤트 페이스북 페이지 직결 수집(1-2) — Meta Graph API · LLM 0콜 · 시크릿 미등록 = no-op 스캐폴드
# (운영자 260718 Q155 "채널 요약 1-1 인스타 / 1-2 페이스북" · insta_fetch.py 자매 — 등록 절차 = docs/페이스북_직결_세팅.md · 구 Q148 표기 = 원장 재부여 전 스테일 앵커 정정[페이블 검증단])
# 출력 = viewer/fb_data.json — **insta_data.json 스키마 미러**(profile/account_day/daily_series/posts/thumbs)라
# 뷰어 renderChan이 소스 무관 공용 동작(결측 유닛 = 자동 미표시 · 뷰어 분기 코드 0).
# 게이트: FB_PAGE_TOKEN(시크릿)+FB_PAGE_ID(변수) 없으면 스킵(rc 0) · 프로필 실패 = 직전 파일 유지(fail-soft) ·
# 인사이트 메트릭별 독립 fail-soft(Graph 메트릭 개폐가 잦아 하나 죽어도 나머지 수집).
import json, os, sys, urllib.request, urllib.parse, datetime, statistics

TOK = os.environ.get('FB_PAGE_TOKEN', '').strip()
PID = os.environ.get('FB_PAGE_ID', '').strip()
OUT = 'viewer/fb_data.json'
G = 'https://graph.facebook.com/v21.0'
KST = datetime.timezone(datetime.timedelta(hours=9))   # 시각 = KST 강제(CLAUDE.md [12] · naive now 금지)


def api(path, **params):
    params['access_token'] = TOK
    with urllib.request.urlopen(f"{G}/{path}?{urllib.parse.urlencode(params)}", timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    if not TOK or not PID:
        print('fb-fetch: 시크릿 미등록(FB_PAGE_TOKEN/FB_PAGE_ID) — no-op 스캐폴드 스킵'); return 0
    now = datetime.datetime.now(KST)
    d = {'generated_kst': now.isoformat(timespec='seconds'), 'src': 'facebook'}
    try:
        p = api(PID, fields='name,username,fan_count,followers_count,link')
        d['profile'] = {'id': p.get('id'), 'username': p.get('username'), 'name': p.get('name'),
                        'followers_count': p.get('followers_count') or p.get('fan_count'), 'media_count': None}
    except Exception as e:
        print('::warning::fb-fetch 프로필 실패 — 직전 유지:', e); return 0
    series, a = {}, {}
    since = (now - datetime.timedelta(days=30)).date().isoformat()
    MET = {'page_impressions': 'views', 'page_impressions_unique': 'reach', 'page_fan_adds': 'follows'}
    for m, k in MET.items():
        try:
            for row in api(f'{PID}/insights', metric=m, period='day', since=since, until=now.date().isoformat()).get('data', []):
                for v in row.get('values', []):
                    dt = str(v.get('end_time', ''))[:10]
                    if dt: series.setdefault(dt, {})[k] = v.get('value')
            days = sorted(dt for dt in series if k in series[dt])
            if days: a[k] = series[days[-1]][k]
        except Exception as e:
            print(f'fb-fetch: 인사이트 {m} 스킵({e})')
    d['account_day'] = {'views': a.get('views'), 'reach': a.get('reach')}
    posts, thumbs = [], []
    try:
        for x in api(f'{PID}/posts', fields='message,permalink_url,created_time,full_picture', limit=10).get('data', []):
            nm = (x.get('message') or '(무캡션)').split('\n')[0][:60]
            posts.append({'name': nm, 'permalink': x.get('permalink_url'), 'iso': x.get('created_time'), 'views': None, 'share_pm': None})
            thumbs.append({'th': x.get('full_picture') or '', 'u': x.get('permalink_url'), 't': nm, 'r': False})
            dt = str(x.get('created_time', ''))[:10]
            series.setdefault(dt, {})['posts'] = (series.get(dt, {}).get('posts') or 0) + 1
    except Exception as e:
        print('fb-fetch: 게시물 스킵:', e)
    d['posts'], d['thumbs'] = posts, thumbs
    d['daily_series'] = [{'date': k, **v} for k, v in sorted(series.items())]
    # 집계 이식(운영자 260718 "집계 이식 ㄱ") — insta_signals.py avg 산식 미러(L410-413: mean 전체·최근7·ratio) ·
    # daily_series 실측 축(views/reach/follows/posts)만 = 확실한 데이터. per-post 지표가 필요한 topics/signals/eras/fmt는
    # Graph 미수집이라 이식 ㄴ(운영자 원칙 "데이터 일치하면 해주고 애매하면 시도 ㄴ") → 뷰어 평균 병기·결측 유닛 자동 미표시와 정합.
    srows = d['daily_series']
    avg = {}
    for k in ('views', 'reach', 'follows', 'posts'):
        vals = [(r.get(k) or 0) for r in srows] if k == 'posts' else [r[k] for r in srows if r.get(k) is not None]
        if len(vals) >= 2:
            a_all = statistics.mean(vals)
            a7 = statistics.mean(vals[-7:])
            avg[k] = {'avg_all': round(a_all, 2), 'avg_7d': round(a7, 2),
                      'ratio_7d': round(a7 / a_all, 2) if a_all else None, 'n_days': len(vals)}
    if avg:
        d['avg'] = avg
    json.dump(d, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"fb-fetch: OK — 팔로워 {d['profile'].get('followers_count')} · 시리즈 {len(series)}일 · 게시물 {len(posts)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
