#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""인스타 직결 수집 — Meta Instagram API(Instagram Login 경로) · LLM 0콜 · stdlib only(설치 0).

게이트: IG_ACCESS_TOKEN 미등록 = no-op exit 0 (시크릿 게이트 스캐폴드 관례 = thumb_gen GEMINI 계승).
산출: apps/insta/data/{insights_daily.jsonl(append·일별 계정지표) · media_latest.json(최근 25개+개별 인사이트)
      · audience.json(인구통계·활동시간대) · token_meta.json(토큰 해시꼬리+최초 관측일 — 원문 저장 절대 금지)}
정본 = apps/insta/00_지침_컨설턴트_인스타_v1.md §1-2·§2-0 · 세팅/재발급 = docs/인스타_직결_세팅.md
주의: 지표명은 Meta가 개폐함(예: impressions→views 이관) → insights()가 묶음 실패 시 낱개 폴백으로
      살아있는 지표만 수집하고 죽은 지표는 dropped에 기록(전건 실패 방지 · 미래 개폐 자가 적응).
스탬프 = KST(§표기표준 d) · API 원본 타임스탬프(UTC)는 원문 보존.
"""
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TOK = os.environ.get('IG_ACCESS_TOKEN', '').strip()
UID = os.environ.get('IG_USER_ID', '').strip() or 'me'
BASE = os.environ.get('IG_API_BASE', 'https://graph.instagram.com').rstrip('/')
OUT = 'apps/insta/data'
KST = ZoneInfo('Asia/Seoul')


def now_kst():
    return datetime.datetime.now(KST).isoformat(timespec='seconds')


def api(path, **params):
    """1콜 → (json|None, err|None). 네트워크 op 타임아웃 20s(§인프라 b — 무한 행 금지)."""
    q = {**params, 'access_token': TOK}
    url = f'{BASE}/{path}?' + urllib.parse.urlencode(q)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode('utf-8', 'replace'))
        except Exception:
            body = {}
        err = (body.get('error') or {})
        return None, f"{e.code}/{err.get('code')}: {err.get('message', 'HTTP error')}"
    except Exception as e:
        return None, str(e)


def parse_ins(j):
    """insights 응답 → {지표명: 값}. total_value·시계열 values 양식 모두 원형 보존."""
    out = {}
    for it in (j or {}).get('data', []):
        name = it.get('name')
        if not name:
            continue
        if 'total_value' in it:
            tv = it['total_value']
            out[name] = tv.get('breakdowns') or tv.get('value')
        elif it.get('values'):
            vals = it['values']
            out[name] = vals if len(vals) > 1 else vals[0].get('value')
    return out


def insights(path, metrics, **params):
    """지표 묶음 조회 — 묶음 실패 시 낱개 폴백. 반환 = (수집분, 드랍 목록)."""
    j, err = api(path, metric=','.join(metrics), **params)
    if j is not None:
        return parse_ins(j), []
    got, dropped = {}, []
    for m in metrics:
        j1, e1 = api(path, metric=m, **params)
        if j1 is None:
            dropped.append(f'{m} ({e1})')
        else:
            got.update(parse_ins(j1))
    return got, dropped


def main():
    if not TOK:
        print('no-op — IG_ACCESS_TOKEN 미등록(직결 세팅 전 스캐폴드 · 라이브 무영향). 세팅 = docs/인스타_직결_세팅.md')
        return 0
    os.makedirs(OUT, exist_ok=True)

    prof, err = api(UID, fields='id,username,name,account_type,followers_count,follows_count,media_count')
    if prof is None:
        print(f'::error::프로필 조회 실패 — {err} · 토큰 만료(60일)/권한 의심 → docs/인스타_직결_세팅.md §6 재발급')
        return 1
    uid = prof.get('id') or UID

    acc, drop1 = insights(
        f'{uid}/insights',
        ['views', 'reach', 'profile_views', 'accounts_engaged', 'total_interactions',
         'likes', 'comments', 'shares', 'saves', 'replies'],
        period='day', metric_type='total_value')
    fc, _ = insights(f'{uid}/insights', ['follower_count'], period='day')
    onl, _ = insights(f'{uid}/insights', ['online_followers'], period='lifetime')

    demo, drop2 = {}, []
    for br in ('age,gender', 'country', 'city'):
        d, dr = insights(f'{uid}/insights', ['follower_demographics'], period='lifetime',
                         metric_type='total_value', timeframe='this_month', breakdown=br)
        if d.get('follower_demographics') is not None:
            demo[br] = d['follower_demographics']
        drop2 += dr

    media, merr = api(f'{uid}/media',
                      fields='id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count',
                      limit='25')
    items = []
    for m in (media or {}).get('data', []):
        mm = dict(m)
        if isinstance(mm.get('caption'), str):
            mm['caption'] = mm['caption'][:120]
        base = ['views', 'reach', 'likes', 'comments', 'saved', 'shares', 'total_interactions']
        if m.get('media_product_type') == 'REELS':
            base += ['ig_reels_avg_watch_time', 'ig_reels_video_view_total_time']
        mi, _ = insights(f"{m['id']}/insights", base)
        mm['insights'] = mi
        items.append(mm)

    stamp = now_kst()
    dropped = drop1 + drop2
    with open(f'{OUT}/insights_daily.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'fetched_kst': stamp, 'profile': prof, 'account_day': acc,
                            'follower_count_series': fc.get('follower_count'),
                            'dropped': dropped}, ensure_ascii=False) + '\n')
    with open(f'{OUT}/media_latest.json', 'w', encoding='utf-8') as f:
        json.dump({'fetched_kst': stamp, 'media_error': merr, 'media': items}, f, ensure_ascii=False, indent=1)
    with open(f'{OUT}/audience.json', 'w', encoding='utf-8') as f:
        json.dump({'fetched_kst': stamp, 'follower_demographics': demo,
                   'online_followers': onl.get('online_followers')}, f, ensure_ascii=False, indent=1)

    # 토큰 나이 경보 — 장수명 토큰 60일 만료 · 50일부터 warning (원문 대신 sha256 꼬리만 저장)
    meta_p = f'{OUT}/token_meta.json'
    tid = hashlib.sha256(TOK.encode()).hexdigest()[:12]
    try:
        meta = json.load(open(meta_p, encoding='utf-8'))
    except Exception:
        meta = {}
    if meta.get('token_hash') != tid:
        meta = {'token_hash': tid, 'first_seen_kst': stamp}
        with open(meta_p, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False)
    else:
        age = (datetime.datetime.now(KST) - datetime.datetime.fromisoformat(meta['first_seen_kst'])).days
        if age >= 50:
            print(f'::warning::IG 토큰 관측 {age}일 경과(만료 60일) — 세팅 가이드 §6 재발급 권장')

    print(f"OK — @{prof.get('username')} 팔로워 {prof.get('followers_count')} · "
          f"계정지표 {len(acc)}종 · 미디어 {len(items)}건 · 드랍 {len(dropped)}종{' · ' + '; '.join(dropped[:3]) if dropped else ''}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
