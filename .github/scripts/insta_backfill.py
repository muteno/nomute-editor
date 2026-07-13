#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""인스타 전 게시물 백필 — 페이지네이션 + 인사이트 field expansion · LLM 0콜 · stdlib only.

배경(운영자 260713): 신호 분석이 media_latest(최근 25개)만 보던 것을 전체(982개+)로 확장 —
*어떤 콘텐츠가 반응 좋았나*의 표본을 계정 전 생애로. 게시물별 낱개 인사이트(982콜) 대신
목록 콜에 insights.metric(...) 확장을 실어 약 20~40콜로 수집(레이트리밋 안전).

산출: apps/insta/data/media_all.json {fetched_kst, n, media:[{id,timestamp,...,insights:{...}}]}
게이트: IG_ACCESS_TOKEN 미등록 = no-op exit 0. 발사 = insta-fetch.yml workflow_dispatch(backfill=true).
fail-soft: expansion 미지원/부분실패 = 그 페이지 insights 없이 수집(핵심 = timestamp·목록 확보 →
일일 게시수 소급은 인사이트 없이도 성립) · 페이지 실패 = 그 지점까지 저장.
주의: REELS 전용 지표(avg_watch_time)는 expansion에 안 실음(피드 글에서 페이지 통째 에러 위험).
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TOK = os.environ.get('IG_ACCESS_TOKEN', '').strip()
UID = os.environ.get('IG_USER_ID', '').strip() or 'me'
BASE = os.environ.get('IG_API_BASE', 'https://graph.instagram.com').rstrip('/')
OUT = 'apps/insta/data'
KST = ZoneInfo('Asia/Seoul')
MAX_PAGES = int(os.environ.get('BACKFILL_MAX_PAGES', '60'))   # 50개/페이지 × 60 = 3,000개 상한
PAGE_SLEEP = float(os.environ.get('BACKFILL_SLEEP', '1.0'))   # 콜 간 여유(레이트 보수)

FIELDS_BASE = 'id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count'
INS_METRICS = 'views,reach,likes,comments,saved,shares,total_interactions'


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode('utf-8', 'replace'))
        except Exception:
            body = {}
        return None, f"{e.code}: {(body.get('error') or {}).get('message', 'HTTP error')}"
    except Exception as e:
        return None, str(e)


def parse_ins_field(m):
    """media 노드의 insights 확장(data[{name,values/total_value}]) → {지표: 값}."""
    out = {}
    for it in ((m.get('insights') or {}).get('data') or []):
        name = it.get('name')
        if not name:
            continue
        if 'total_value' in it:
            out[name] = (it['total_value'] or {}).get('value')
        elif it.get('values'):
            out[name] = it['values'][0].get('value')
    return out


def main():
    if not TOK:
        print('no-op — IG_ACCESS_TOKEN 미등록(스캐폴드 관례)')
        return 0
    os.makedirs(OUT, exist_ok=True)

    prof, err = get(f'{BASE}/{UID}?' + urllib.parse.urlencode({'fields': 'id,media_count', 'access_token': TOK}))
    if prof is None:
        print(f'::error::프로필 조회 실패 — {err}')
        return 1
    uid = prof.get('id') or UID
    total = prof.get('media_count')

    items, pages, expansion_ok = [], 0, True
    fields = f'{FIELDS_BASE},insights.metric({INS_METRICS})'
    url = f'{BASE}/{uid}/media?' + urllib.parse.urlencode({'fields': fields, 'limit': '50', 'access_token': TOK})
    while url and pages < MAX_PAGES:
        j, err = get(url)
        if j is None and expansion_ok:
            # expansion 미지원 폴백 — 목록만이라도(타임스탬프 = 일일 게시수 소급의 핵심)
            print(f'::warning::insights 확장 실패({err}) → 목록 전용 폴백')
            expansion_ok = False
            fields = FIELDS_BASE
            url = f'{BASE}/{uid}/media?' + urllib.parse.urlencode({'fields': fields, 'limit': '50', 'access_token': TOK})
            continue
        if j is None:
            print(f'::warning::페이지 {pages + 1} 실패({err}) — 그 지점까지 저장')
            break
        for m in j.get('data', []):
            mm = {k: m.get(k) for k in FIELDS_BASE.split(',')}
            if isinstance(mm.get('caption'), str):
                mm['caption'] = mm['caption'][:120]
            ins = parse_ins_field(m)
            if ins:
                mm['insights'] = ins
            items.append(mm)
        pages += 1
        url = ((j.get('paging') or {}).get('next'))
        if url:
            time.sleep(PAGE_SLEEP)

    stamp = datetime.datetime.now(KST).isoformat(timespec='seconds')
    with open(f'{OUT}/media_all.json', 'w', encoding='utf-8') as f:
        json.dump({'fetched_kst': stamp, 'media_count_profile': total, 'n': len(items),
                   'insights_expansion': expansion_ok, 'pages': pages, 'media': items}, f, ensure_ascii=False)
    with_ins = sum(1 for m in items if m.get('insights'))
    print(f'OK — 전 게시물 {len(items)}/{total}개({pages}페이지) · 인사이트 동봉 {with_ins}개 · expansion={expansion_ok}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
