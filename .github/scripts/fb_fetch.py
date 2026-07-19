#!/usr/bin/env python3
# 노뮤트 페이스북 페이지 직결 수집(1-2) — Meta Graph API · LLM 0콜 · 시크릿 미등록 = no-op 스캐폴드
# (운영자 260718 Q155 "채널 요약 1-1 인스타 / 1-2 페이스북" · insta_fetch.py 자매 — 등록 절차 = docs/페이스북_직결_세팅.md · 구 Q148 표기 = 원장 재부여 전 스테일 앵커 정정[페이블 검증단])
# 출력 = viewer/fb_data.json — **insta_data.json 스키마 미러**(profile/account_day/daily_series/posts/thumbs)라
# 뷰어 renderChan이 소스 무관 공용 동작(결측 유닛 = 자동 미표시 · 뷰어 분기 코드 0).
# 게이트: FB_PAGE_TOKEN(시크릿) 없으면 스킵(rc 0) · FB_PAGE_ID = 자동 해석(260718 1값 온보딩 — 유저 토큰 = me/accounts
#        페이지 토큰 자동 교체 · 페이지 토큰 = me 직독 · 변수 등록 시 그 값 고정) — FB_PAGE_TOKEN 부재 + IG_ACCESS_TOKEN 존재 시
#        겸용 프로브(me/accounts 페이지 토큰 자동 수급 · 페북 로그인 경로 토큰만 성립 · 실패 = 종전 no-op) · 프로필 실패 = 직전 파일 유지(fail-soft) ·
# 인사이트 메트릭별 독립 fail-soft(Graph 메트릭 개폐가 잦아 하나 죽어도 나머지 수집).
import json, os, sys, urllib.request, urllib.error, urllib.parse, datetime, statistics

TOK = os.environ.get('FB_PAGE_TOKEN', '').strip()
PID = os.environ.get('FB_PAGE_ID', '').strip()
IGTOK = os.environ.get('IG_ACCESS_TOKEN', '').strip()   # 겸용 프로브 폴백(운영자 260718 "인스타 API가 메타였는데 못 끌어와?" — 세팅 문서 §0)
OUT = 'viewer/fb_data.json'
G = 'https://graph.facebook.com/v21.0'
KST = datetime.timezone(datetime.timedelta(hours=9))   # 시각 = KST 강제(CLAUDE.md [12] · naive now 금지)


def api(path, tok=None, **params):
    params['access_token'] = tok or TOK
    try:
        with urllib.request.urlopen(f"{G}/{path}?{urllib.parse.urlencode(params)}", timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        # Graph 에러 본문을 예외 메시지에 승격(260719 — "HTTP 400"만으론 권한 누락 vs 지표 폐지 진단 불가 · insta_fetch 관용구 미러)
        try:
            err = (json.loads(e.read().decode('utf-8', 'replace')).get('error') or {})
            raise RuntimeError(f"{e.code}/{err.get('code')}: {err.get('message', 'HTTP error')[:200]}") from None
        except RuntimeError:
            raise
        except Exception:
            raise RuntimeError(f'{e.code}: HTTP error(본문 파싱 불가)') from None


def main():
    global TOK, PID
    if not TOK and IGTOK:
        # IG 토큰 겸용 프로브(운영자 260718) — 기존 인스타 직결 토큰이 '페이스북 로그인' 경로 토큰이면
        # me/accounts가 페이지 토큰을 돌려줘 추가 등록 0으로 자동 연동. 현 세팅 문서(인스타_직결_세팅.md 1행)는
        # 'Instagram Login' 경로 = graph.facebook.com에서 거부가 정상 → 종전 no-op 유지 · 아래 로그 = 판별 증거(토큰 원문 미출력).
        try:
            pages = api('me/accounts', IGTOK, fields='id,name,access_token').get('data') or []
            hit = next((p for p in pages if (not PID or p.get('id') == PID) and p.get('access_token')), None)
            if hit:
                TOK, PID = hit['access_token'], hit['id']
                print(f"fb-fetch: IG 토큰 = 메타(페북 로그인) 겸용 판정 — 페이지 '{hit.get('name')}'({PID}) 자동 연동")
            else:
                print('fb-fetch: IG 토큰 유효하나 페이지 0개(페이지 권한 없음) — 전용 페이지 토큰 필요(세팅 문서 §1~3)')
        except Exception as e:
            print(f'fb-fetch: IG 토큰 겸용 불가 = 인스타 전용(Instagram Login) 판정 — {e}')
    if TOK and not PID:
        # 1값 온보딩(운영자 260718 "끌어와서 지속 반영") — FB_PAGE_TOKEN만 등록해도 페이지 ID 자동 해석:
        # ⓐ 유저 토큰(pages 권한)이면 me/accounts가 페이지 목록+페이지 토큰을 반환 → 페이지 토큰으로 자동 교체
        # ⓑ 페이지 토큰이면 me = 페이지 자신 → id 직독. 둘 다 실패 = 종전 no-op(fail-soft · 토큰 원문 미출력).
        try:
            pages = api('me/accounts', fields='id,name,access_token').get('data') or []
            hit = next((p for p in pages if p.get('access_token')), None)
            if hit:
                TOK, PID = hit['access_token'], hit['id']
                print(f"fb-fetch: 유저 토큰 판정 — 페이지 '{hit.get('name')}'({PID}) 토큰 자동 교체")
        except Exception:
            pass
        if not PID:
            try:
                me = api('me', fields='id,name')
                PID = me.get('id') or ''
                if PID:
                    print(f"fb-fetch: 페이지 토큰 판정 — 페이지 '{me.get('name')}'({PID}) 자동 인식")
            except Exception as e:
                print(f'fb-fetch: 토큰 유효성 실패(만료·권한 확인 필요) — {e}')
    if not TOK or not PID:
        print('fb-fetch: 시크릿 미등록(FB_PAGE_TOKEN 필수 · FB_PAGE_ID = 자동/선택) — no-op 스캐폴드 스킵'); return 0
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
