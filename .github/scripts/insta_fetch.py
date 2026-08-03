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
import re
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


_SHORTCODE_RE = re.compile(r'instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)')


def _public_cover(permalink):
    """인스타 **공개** 커버 경로로 커버 회수(운영자 260803 "빈칸을 최대한 없애는 방향") — '' = 못 얻음.
    `/p/<shortcode>/media/?size=l`은 로그인 없이 커버 CDN URL로 302 리다이렉트한다(실측 260803: 정상 릴스
    10건 전부 실제 이미지 · 커버 자산이 없는 2건만 `static.cdninstagram.com/rsrc.php/null.jpg` 플레이스홀더).
    Graph가 thumbnail_url을 무성 생략해도 이 경로엔 남아있는 회차가 있어 **독립 소스**로서 값이 있다.
    비인증·토큰 무관 · 결손 릴스에만 1콜 · 타임아웃 10s · 어떤 실패도 '' (fail-soft = 종전 동작)."""
    mo = _SHORTCODE_RE.search(permalink or '')
    if not mo:
        return ''
    url = f'https://www.instagram.com/p/{mo.group(1)}/media/?size=l'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; nomute-editor/1.0)'})
        with urllib.request.urlopen(req, timeout=10) as r:
            final = r.geturl()
            ctype = (r.headers.get('Content-Type') or '')
        if 'null.jpg' in final or not ctype.startswith('image/'):
            return ''   # 플레이스홀더·비이미지 = 자산 부재
        return final
    except Exception:
        return ''


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
    """지표 묶음 조회 — 묶음 실패 OR 묶음 성공이어도 응답 누락분은 낱개 폴백. 반환 = (수집분, 드랍 목록).
    ⚠ Meta는 metric_type별 미지원 지표를 200 응답에서 '무성 생략'한다(260717 실측: 계정 time_series가
    reach만 주고 views·profile_views 등은 조용히 빠뜨림 → 종전 로직은 묶음 200이면 dropped 0으로 통과 →
    daily_series views가 5일간 None인데 아무 경보 없이 방치됨). 교정 = 요청했는데 응답에 없는 지표는 낱개
    재시도(솔로로는 될 수도) → 그래도 없으면 dropped에 명시 = 조용한 누락을 가시 경보로. (미래 개폐 자가 적응.)"""
    j, err = api(path, metric=','.join(metrics), **params)
    got = parse_ins(j) if j is not None else {}
    dropped = []
    for m in [x for x in metrics if x not in got]:   # 묶음에 빠진 지표(실패 = 전부 · 부분 = 누락분)만 낱개 재시도
        j1, e1 = api(path, metric=m, **params)
        g1 = parse_ins(j1) if j1 is not None else {}
        if m in g1:
            got.update(g1)
        else:
            dropped.append(f'{m} ({e1 or "200-응답미포함"})')
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
    # 팔로우/취소 분해(운영자 260719 Q171 — 뷰어 '팔로워 증감' 카드 취소 라인 데이터원) — follows_and_unfollows
    # = total_value 전용(일별 시계열 미지원)이라 어제 00:00~오늘 00:00 KST 1창을 명시해 달력일 확정 귀속.
    # FOLLOWER 값 = follower_count 결측일 보강 겸용(병합은 선점자 우선 = 기존 수집 무접촉) · 실패 = dropped 가시 경보.
    day0 = datetime.datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    fu, drop4 = insights(f'{uid}/insights', ['follows_and_unfollows'],
                         period='day', metric_type='total_value', breakdown='follow_type',
                         since=str(int((day0 - datetime.timedelta(days=1)).timestamp())),
                         until=str(int(day0.timestamp())))
    onl, _ = insights(f'{uid}/insights', ['online_followers'], period='lifetime')
    # 일별 버킷(time_series · 운영자 260713 일일 추이) — since/until 명시 = 진짜 달력일 배열.
    # 지난 3일 창 = 결측일 자가치유 · 미지원 지표 = insights() 낱개 폴백이 dropped 기록 = fail-soft(기존 수집 무접촉).
    now_ep = int(datetime.datetime.now(KST).timestamp())
    ts, drop3 = insights(
        f'{uid}/insights',
        ['views', 'reach', 'profile_views', 'accounts_engaged', 'total_interactions'],
        period='day', metric_type='time_series', since=str(now_ep - 3 * 86400), until=str(now_ep))

    demo, drop2 = {}, []
    for br in ('age,gender', 'country', 'city'):
        d, dr = insights(f'{uid}/insights', ['follower_demographics'], period='lifetime',
                         metric_type='total_value', timeframe='this_month', breakdown=br)
        if d.get('follower_demographics') is not None:
            demo[br] = d['follower_demographics']
        drop2 += dr

    media, merr = api(f'{uid}/media',
                      fields='id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count,media_url,thumbnail_url',
                      limit='25')
    items = []
    for m in (media or {}).get('data', []):
        mm = dict(m)
        if isinstance(mm.get('caption'), str):
            mm['caption'] = mm['caption'][:120]
        # 릴스 커버 회수(운영자 260718) — /media 목록 응답이 일부 릴스의 thumbnail_url을 무성 생략(실측 2/25).
        # 누락 시 media_url은 mp4 스트림뿐이라 뷰어 <img>가 깨져 '최근 게시물' 타일이 조용히 사라짐 →
        # 미디어 노드 직접 재조회로 커버 복구(빠진 것만 · 대개 0~2콜) · 그래도 없으면 무접촉(fail-soft).
        if not mm.get('thumbnail_url') and (m.get('media_type') == 'VIDEO' or m.get('media_product_type') == 'REELS'):
            tj, _terr = api(m['id'], fields='thumbnail_url')
            if tj and tj.get('thumbnail_url'):
                mm['thumbnail_url'] = tj['thumbnail_url']
            else:
                # 2차 = **인스타 공개 커버 경로**(운영자 260803 "빈칸을 최대한 없애는 방향") — Graph가 둘 다 빈손인
                # 릴스도 공개 permalink 경로엔 커버가 살아있는 경우가 있다(260803 실측 = 결손 아닌 릴스 10건 전부
                # 이 경로로 정상 CDN 이미지 · 자산 자체가 없는 2건만 null.jpg). 토큰 불요·결손건만 1콜(평시 0~2).
                # 채택 조건 = 리다이렉트 종착이 **CDN 이미지**(null.jpg 플레이스홀더 = 자산 부재 = 버림).
                pub = _public_cover(m.get('permalink'))
                if pub:
                    mm['thumbnail_url'] = pub
        base = ['views', 'reach', 'likes', 'comments', 'saved', 'shares', 'total_interactions']
        if m.get('media_product_type') == 'REELS':
            base += ['ig_reels_avg_watch_time', 'ig_reels_video_view_total_time']
        mi, _ = insights(f"{m['id']}/insights", base)
        mm['insights'] = mi
        items.append(mm)

    stamp = now_kst()
    dropped = drop1 + drop2 + drop3 + drop4
    with open(f'{OUT}/insights_daily.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'fetched_kst': stamp, 'profile': prof, 'account_day': acc,
                            'follower_count_series': fc.get('follower_count'),
                            'follows_split': {'date': (day0 - datetime.timedelta(days=1)).date().isoformat(),
                                              'raw': fu.get('follows_and_unfollows')},
                            'account_daily': ts,
                            'dropped': dropped}, ensure_ascii=False) + '\n')
    with open(f'{OUT}/media_latest.json', 'w', encoding='utf-8') as f:
        json.dump({'fetched_kst': stamp, 'media_error': merr, 'media': items}, f, ensure_ascii=False, indent=1)
    with open(f'{OUT}/audience.json', 'w', encoding='utf-8') as f:
        json.dump({'fetched_kst': stamp, 'follower_demographics': demo,
                   'online_followers': onl.get('online_followers')}, f, ensure_ascii=False, indent=1)

    # 접속 실측 원장(운영자 260803 "내 팔로워 접속 실측 붙이면 매우 좋을듯" — 뷰어 실측 곡선·요일 축적의 원천) —
    # online_followers 일버킷(시각 = PT 로컬 · 판정 260803 insta_signals._pt_kst_shift — 원문 그대로 보존, KST 변환 = 분석기 몫)을 날짜 키로 병합 누적. audience.json은 매 런 덮어써 최신 ~2일뿐이라
    # 누적 없인 요일별 실측이 영영 불가. 원문 보존(KST 변환 = 분석기 몫) · 같은 날 재수집 = 최신 덮음 · 400일 컷(비대 방지) · 실패 = 종전 산출 무피해.
    try:
        led_p = f'{OUT}/online_ledger.json'
        try:
            led = json.load(open(led_p, encoding='utf-8'))
            assert isinstance(led, dict)
        except Exception:
            led = {}
        raw_onl = onl.get('online_followers')
        for b in (raw_onl if isinstance(raw_onl, list) else []):
            v, et = (b or {}).get('value'), ((b or {}).get('end_time') or '')[:10]
            if isinstance(v, dict) and v and len(et) == 10:
                led[et] = v
        if led:
            for k in sorted(led)[:-400]:
                led.pop(k, None)
            with open(led_p, 'w', encoding='utf-8') as f:
                json.dump(led, f, ensure_ascii=False)
    except Exception as e:
        print(f'online_ledger 적재 실패(비치명 · 곡선은 audience 스냅샷 폴백): {e}')

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
