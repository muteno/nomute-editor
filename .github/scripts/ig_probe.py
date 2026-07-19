#!/usr/bin/env python3
# 인스타 인사이트 경로 비교 프로브(운영자 260719 "지금 토큰으로 인스타 인사이트 뽑은 거랑 기존이랑 비교") — READ-ONLY 진단.
# 신경로 = FB_PAGE_TOKEN(페북 로그인 유저 토큰 · graph.facebook.com · 페이지→instagram_business_account 경유)
# 구경로 = IG_ACCESS_TOKEN(인스타그램 로그인 · graph.instagram.com · 현행 insta-fetch 파이프라인 축)
# 같은 지표 후보를 양쪽에 쏘고 생존/사망을 로그로 판정 — 파일 산출·커밋 없음(rc 항상 0 · 롤백 = 파일 삭제).
# 파라미터 사다리: ①period=day+metric_type=total_value ②period=day ③period=lifetime (현대 IG 지표가 요구 형태별로 갈려서).
import json, os, urllib.request, urllib.error, urllib.parse

FBTOK = os.environ.get('FB_PAGE_TOKEN', '').strip()
IGTOK = os.environ.get('IG_ACCESS_TOKEN', '').strip()
GFB = 'https://graph.facebook.com/v21.0'
GIG = 'https://graph.instagram.com'

METS = ['views', 'reach', 'impressions', 'profile_views', 'accounts_engaged', 'total_interactions',
        'likes', 'comments', 'shares', 'saves', 'replies', 'follows_and_unfollows',
        'website_clicks', 'profile_links_taps', 'online_followers', 'follower_count']
LADDER = [{'period': 'day', 'metric_type': 'total_value'}, {'period': 'day'}, {'period': 'lifetime'}]


def call(base, path, tok, **params):
    params['access_token'] = tok
    try:
        with urllib.request.urlopen(f"{base}/{path}?{urllib.parse.urlencode(params)}", timeout=20) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        try:
            err = (json.loads(e.read().decode('utf-8', 'replace')).get('error') or {})
            return None, f"{e.code}/{err.get('code')}: {str(err.get('message', ''))[:110]}"
        except Exception:
            return None, f'{e.code}: HTTP'
    except Exception as e:
        return None, str(e)[:110]


def probe(base, uid, tok, label):
    print(f'── {label} ──')
    alive, dead = [], []
    for m in METS:
        verdict = None
        for pr in LADDER:
            j, err = call(base, f'{uid}/insights', tok, metric=m, **pr)
            if j is not None:
                verdict = f"생존({'+'.join(f'{k}={v}' for k, v in pr.items())})"
                break
            last = err
        if verdict:
            alive.append(m); print(f'  ✅ {m} — {verdict}')
        else:
            dead.append(m); print(f'  ❌ {m} — {last}')
    print(f'  요약: 생존 {len(alive)} = {",".join(alive) or "없음"} · 사망 {len(dead)}')
    return alive


def main():
    new_alive = old_alive = None
    if FBTOK:
        acc, err = call(GFB, 'me/accounts', FBTOK, fields='id,name,access_token,instagram_business_account{id,username}')
        page = (acc or {}).get('data', [{}])[0] if acc else {}
        iba = (page.get('instagram_business_account') or {})
        if iba.get('id'):
            print(f"신경로: 페이지 '{page.get('name')}' → 인스타 비즈니스 계정 @{iba.get('username')}({iba.get('id')})")
            new_alive = probe(GFB, iba['id'], page.get('access_token') or FBTOK, '신경로(페북 로그인 토큰 · graph.facebook.com)')
        else:
            print(f'신경로: 인스타 비즈니스 계정 미연동/조회 불가 — {err or acc}')
    else:
        print('신경로: FB_PAGE_TOKEN 미등록')
    if IGTOK:
        me, err = call(GIG, 'me', IGTOK, fields='user_id,username')
        print(f"구경로: @{(me or {}).get('username')} ({(me or {}).get('user_id')})" if me else f'구경로 프로필 실패 — {err}')
        old_alive = probe(GIG, 'me', IGTOK, '구경로(인스타그램 로그인 토큰 · graph.instagram.com · 현행 파이프라인)')
    else:
        print('구경로: IG_ACCESS_TOKEN 미등록')
    if new_alive is not None and old_alive is not None:
        only_new = [m for m in new_alive if m not in old_alive]
        only_old = [m for m in old_alive if m not in new_alive]
        print('── 비교 ──')
        print(f'  신경로 단독 생존: {",".join(only_new) or "없음"}')
        print(f'  구경로 단독 생존: {",".join(only_old) or "없음"}')
        print(f'  양쪽 공통 생존: {",".join(m for m in new_alive if m in old_alive) or "없음"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
