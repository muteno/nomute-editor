#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""알고리즘 인사이트 회차 원장 — AI 채널요약 회차마다 {요약 전문 · 요약이 쓴 데이터 · 그 시점 대세 키워드}를 1줄로 누적
(운영자 260802 "매 진행 시 메모 · 데이터 누락없이 · 당시 실검+커뮤니티 키워드 동봉 → 100+ 쌓이면 알고리즘 패턴").

설계 = 평의회 260802(오퍼스4+페이블4 · effort max) 합의안:
  · 원장 = apps/insta/data/algo_runs/YYYY-MM.jsonl (KST 월샤딩 · append-only · IG+FB 한 런 = 한 줄 = "한 곳")
  · 기록자 = insta-fetch 잡 단독(전 워크플로 실측 — apps/insta/data 착지는 insta-fetch.yml 하나 · concurrency 직렬)
    → git_land reset 재적층의 "남의 append 삼킴" 사고 클래스 원천 회피. 맨끝 git_land가 apps/insta/data
    디렉터리째 착지하므로 워크플로 인자 수정 0.
  · Δ·트렌드 매칭·era 재라벨은 **굽지 않는다**(회차 간격이 크론 드롭으로 3~9h 요동 = 구운 Δ는 거짓 수치 ·
    매칭 알고리즘은 분석기에서 교체 가능해야 전 역사 재계산 가능) — 절대값+타임스탬프만 저장.
  · posts = media_latest 25개 전량 verbatim(선별 = 생존편향을 원장에 재생산 · 결측은 null 보존, 0 둔갑 금지).
  · posts_db.jsonl(kw·cl) 의존 금지 — 2026-07-13 동결 실측. 키워드는 캡션 첫 줄 결정론 토큰화로 파생
    (cap 원문 동봉 = 토크나이저가 바뀌어도 언제든 재추출 가능한 유일한 미래보증).
  · account_day = KST 하루 누적 카운터(실측 00:03→23:34 사이 단조 증가) → day_date·day_h 딱지 없인 비교 금지.
  · 트렌드 = gtrends top25 + **pool 전량(24h 롤링창 = 런이 하루 1회만 성공해도 그날 급상승 결측 0)** +
    실검 10(kid = AI 재작성 churn 대비 추적키) + X 14(보관 전용) + 커뮤니티 25. staleness(age_min·sha8) 명기.
    제외 = youtube(rh 캡 포화)·tiktok(블롭)·bsky·reddit·hackernews(영어권·인과 경로 없음) 등.
  · ctx = 브리프가 실제로 본 집계(insta_data의 avg·eras·fmt·topics·timing·axes…)를 브리프 재생성 회차에만
    동봉(스킵 회차 = ctx_ref로 직전 참조). DIG 텍스트는 저장 안 함 — fv() 만/억 반올림 손실본이고
    ctx(반올림 전 원값)+src_hash+prompt_ver가 상위호환.
  · 멱등 2중키 = dk(내용 해시 · 무변화 재실행 흡수) + run_id/att(Actions Re-run 방어) · fsync 원자 append.
  · 서킷브레이커 = 샤드 8MB 초과 시 append 중단(::warning · 실측 월 ~5.3MB = 헤드룸 51%).
  · fail-soft = 어떤 예외도 rc 0(::warning만) — 수집·브리프 커밋 비차단. 네트워크 0 · LLM 0콜 · stdlib only
    (기계 보증 = shared/check_refs.py::check_algo_ledger).

스키마 v:1 필드 사전(로더는 미지 필드 무시 · 의미 변경/개명 = v++ · 과거 줄 재작성 절대 금지):
  v run_id att ev ts dk ms
  ig.brief{updated src_hash prompt_ver n_chars sections|unchanged} ig.acct{followers media_count follows
    day(verbatim) day_date day_h dropped} ig.posts[{id pl ts_post age_h prod mt cap kw st cat era fmt score fp exp
    ins(verbatim: views reach likes comments saved shares total_interactions ig_reels_avg_watch_time …)}]
  ig.ctx{avg eras fmt topics timing axes n_posts posts_view_avg online daily3 echo}|null ig.ctx_ref
  fb.brief{...} fb.acct{followers day(verbatim) totals} fb.posts(verbatim)
  tr.src{sns{upd age_min sha8 n} soc{upd sha8 amin_h n}} tr.gt tr.gtp tr.sig tr.xt tr.soc
롤백 = repo variable ALGO_LEDGER=0(스텝 스킵 · 원장 잔존) 또는 insta-fetch.yml 스텝 블록 삭제. 데이터 삭제는 없다.
"""
import datetime
import hashlib
import json
import os
import re
import sys
import time

KST = datetime.timezone(datetime.timedelta(hours=9))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DIR = os.path.join(ROOT, 'apps', 'insta', 'data', 'algo_runs')
MAX_SHARD_MB = 12   # 실측 행 = 재생성 64KB·스킵 ~40KB(verbatim 완전성 = 운영자 "함축 금지") × 4~5런/일 → 월 ~7-9MB + 헤드룸
# 캡션 토큰화 스탑워드 — social_burst.py 미러 정신(뉴스·커뮤 제목 관용어) + 인스타 헤드 이모지 잔재
_STOP = {'속보', '단독', '종합', '전문', '공식', '오늘', '내일', '관련', '기자', '영상', '사진', '실시간', '현재', '근황',
         '논란', '소식', '이유', '결국', '충격', '경악', '레전드', '수준', '정도', '상황', '발언', '입장', '공개', '확인'}


def _now():
    return datetime.datetime.now(KST)


def _read_json(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _sha(obj, n=16):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:n]


def _tokenize(text, cap=6):
    """캡션 첫 줄 → 결정론 키워드(재현 가능 · LLM 0). cap 원문이 함께 저장되므로 언제든 재추출 가능."""
    toks = []
    for t in re.findall(r'[가-힣]{2,}|[A-Za-z]{2,}|[0-9]{2,}', text or ''):
        if t in _STOP or t in toks:
            continue
        toks.append(t)
        if len(toks) >= cap:
            break
    return toks


def _first_line(s):
    for ln in (s or '').split('\n'):
        ln = re.sub(r'^[^\w가-힣"\'…\[]+', '', ln.strip())
        if ln:
            return ln
    return ''


def _age_min(ts_str, now):
    try:
        t = datetime.datetime.fromisoformat(str(ts_str).replace('Z', '+00:00'))
        return round((now - t).total_seconds() / 60)
    except Exception:
        return None


def _prompt_ver(script_rel):
    try:
        m = re.search(r"^PVER = '([^']+)'", open(os.path.join(ROOT, script_rel), encoding='utf-8').read(), re.M)
        return m.group(1) if m else None
    except Exception:
        return None


def _tail_rows(max_bytes=262144, max_rows=200):
    """최신 샤드의 꼬리 행들(멱등키·직전 비교용) — 전체 파싱 금지(seek tail). 월 경계 = 파일명 내림차순 첫 유효 파일."""
    try:
        shards = sorted((f for f in os.listdir(DIR) if re.fullmatch(r'\d{4}-\d{2}\.jsonl', f)), reverse=True)
    except FileNotFoundError:
        return [], None
    for name in shards:
        p = os.path.join(DIR, name)
        try:
            size = os.path.getsize(p)
            with open(p, 'rb') as f:
                f.seek(max(0, size - max_bytes))
                chunk = f.read().decode('utf-8', 'replace')
            lines = [ln for ln in chunk.split('\n') if ln.strip()]
            if size > max_bytes and lines:
                lines = lines[1:]   # 경계 잘림 첫 줄 폐기
            rows = []
            for ln in lines[-max_rows:]:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    continue
            if rows:
                return rows, name
        except Exception:
            continue
    return [], None


def _brief_block(doc, prev_hash, script_rel, shard_first):
    """브리프 블록 — 전문 인라인. 직전 행과 src_hash 동일(스킵 회차)이면 sections 생략(unchanged:true)로 중복 절감.
    단 샤드 첫 행은 무조건 인라인(월 경계에서 참조 단절 방지)."""
    if not doc:
        return None
    b = {'updated': doc.get('updated'), 'src_hash': doc.get('src_hash'),
         'prompt_ver': _prompt_ver(script_rel), 'n_chars': len(doc.get('text') or '')}
    if doc.get('src_hash') and doc.get('src_hash') == prev_hash and not shard_first:
        b['unchanged'] = True
    else:
        b['sections'] = doc.get('sections') or [{'k': 'all', 'text': (doc.get('text') or '')[:6000]}]
    return b


def build_record(now):
    run_id = os.environ.get('GH_RUN') or os.environ.get('GITHUB_RUN_ID') or ('local-' + now.strftime('%y%m%d%H%M%S'))
    att = os.environ.get('GH_ATT') or os.environ.get('GITHUB_RUN_ATTEMPT') or '1'
    ev = os.environ.get('GH_EV') or os.environ.get('GITHUB_EVENT_NAME') or 'manual-seed'
    prev_rows, _ = _tail_rows()
    prev = prev_rows[-1] if prev_rows else {}
    shard = os.path.join(DIR, now.strftime('%Y-%m') + '.jsonl')
    shard_first = not os.path.exists(shard)
    prev_ig_hash = ((prev.get('ig') or {}).get('brief') or {}).get('src_hash')
    prev_fb_hash = ((prev.get('fb') or {}).get('brief') or {}).get('src_hash')

    sig = _read_json('viewer/insta_data.json') or {}
    med = _read_json('apps/insta/data/media_latest.json') or {}
    ig_brief = _read_json('viewer/chan_brief.json')
    fb_brief = _read_json('viewer/chan_brief_fb.json')
    fb_data = _read_json('viewer/fb_data.json') or {}
    sns = _read_json('viewer/sns_trends.json') or {}
    soc = _read_json('viewer/social_candidates.json') or []

    # ── IG 계정(수집 원장 최종행 = 이번 런 수집분) — account_day는 KST 하루 누적: day_date·day_h 없인 비교 금지 ──
    acct = None
    try:
        with open(os.path.join(ROOT, 'apps/insta/data/insights_daily.jsonl'), 'rb') as f:
            f.seek(max(0, os.path.getsize(f.name) - 65536))
            last = [ln for ln in f.read().decode('utf-8', 'replace').split('\n') if ln.strip()][-1]
        row = json.loads(last)
        prof = row.get('profile') or {}
        fk = row.get('fetched_kst') or ''
        day_h = None
        try:
            t = datetime.datetime.fromisoformat(fk)
            day_h = round(t.hour + t.minute / 60, 2)
        except Exception:
            pass
        acct = {'followers': prof.get('followers_count'), 'media_count': prof.get('media_count'),
                'follows': prof.get('follows_count'), 'fetched': fk, 'day_date': fk[:10], 'day_h': day_h,
                'day': row.get('account_day'), 'dropped': row.get('dropped')}
    except Exception:
        pass

    # ── IG 게시물 25 전량 verbatim + 라벨 조인(뷰어 소비본 posts = permalink 키) + 결정론 kw ──
    lab = {}
    for p in (sig.get('posts') or []):
        if p.get('permalink'):
            lab[p['permalink']] = p
    posts = []
    for m in (med.get('media') or []):
        cap = _first_line(m.get('caption'))[:120]
        age_h = None
        try:
            t = datetime.datetime.fromisoformat(str(m.get('timestamp')).replace('+0000', '+00:00'))
            age_h = round((now - t).total_seconds() / 3600, 2)
        except Exception:
            pass
        L = lab.get(m.get('permalink')) or {}
        posts.append({'id': m.get('id'), 'pl': m.get('permalink'), 'ts_post': m.get('timestamp'), 'age_h': age_h,
                      'prod': m.get('media_product_type'), 'mt': m.get('media_type'), 'cap': cap,
                      'kw': _tokenize(cap), 'st': L.get('style'), 'cat': L.get('cat'), 'era': L.get('era'),
                      'fmt': L.get('format'), 'score': L.get('score'), 'fp': L.get('fp'), 'exp': L.get('exp'),
                      'like': m.get('like_count'), 'cmt': m.get('comments_count'),
                      'ins': m.get('insights')})   # verbatim — 결측 키는 그대로 없음(0 둔갑 금지)

    ig_bb = _brief_block(ig_brief, prev_ig_hash, '.github/scripts/chan_brief.sh', shard_first)
    regenerated = bool(ig_bb) and not ig_bb.get('unchanged')

    # ── ctx = 브리프가 본 집계(반올림 전 원값) — 재생성 회차에만 · 스킵 회차 = 직전 참조 ──
    ctx = None
    ctx_ref = None
    if regenerated and sig:
        ctx = {'avg': sig.get('avg'), 'eras': sig.get('eras'), 'fmt': sig.get('fmt'), 'topics': sig.get('topics'),
               'timing': sig.get('timing'), 'axes': (sig.get('signals') or {}).get('axes'),
               'n_posts': (sig.get('signals') or {}).get('n_posts'), 'posts_view_avg': sig.get('posts_view_avg'),
               'online': sig.get('online_peak_kst'), 'daily3': (sig.get('daily_series') or [])[-3:],
               'echo': (sig.get('echo') or {}).get('evidence')}
    else:
        for r in reversed(prev_rows):
            if (r.get('ig') or {}).get('ctx'):
                ctx_ref = r.get('run_id')
                break

    # ── FB 자매(같은 줄 = "한 곳") — fb_data posts는 verbatim(views null 실측 = v1 분석은 IG 한정) ──
    fbp = fb_data.get('profile') or {}
    fb = {'brief': _brief_block(fb_brief, prev_fb_hash, '.github/scripts/fb_brief.sh', shard_first),
          'acct': {'followers': fbp.get('followers_count'), 'day': fb_data.get('account_day'),
                   'totals': fb_data.get('fb_totals')},
          'posts': fb_data.get('posts')}

    # ── 트렌드 스냅샷 — staleness 명기 · pool 전량(24h창 = 결측 0 축) ──
    def _gt(x, r):
        d = {'q': x.get('query'), 'r': r, 'v': x.get('vol') or x.get('traffic')}
        if x.get('started'):
            d['st'] = x['started']
        if x.get('first_seen'):
            d['fs'] = x['first_seen']
        if isinstance(x.get('rh'), list):
            d['nh'] = len(x['rh'])
        news = x.get('news') or []
        if news and isinstance(news, list) and news[0].get('title'):
            d['h'] = news[0]['title'][:60]
        return d
    gt = [_gt(x, i + 1) for i, x in enumerate(sns.get('gtrends') or [])]
    gtp = [{'q': x.get('q'), 'v': x.get('vol'), 'st': x.get('started')} for x in (sns.get('gtrends_pool') or [])]
    sigl = [{'q': x.get('query'), 'r': i + 1, 'kid': x.get('kid'), 'fs': x.get('first_seen'),
             'nh': len(x.get('rh') or []), 's': x.get('state')} for i, x in enumerate(sns.get('signal') or [])]
    xt = [{'q': x.get('query'), 'r': i + 1, 'fs': x.get('first_seen'), 'nh': len(x.get('rh') or [])}
          for i, x in enumerate(sns.get('xtrends') or [])]
    socl = [{'t': (x.get('title') or '')[:70], 'r': i + 1, 'b': x.get('burst'), 'a': x.get('age_h'),
             'sc': x.get('source_count'), 'p': x.get('posts')} for i, x in enumerate(soc or [])]
    tr = {'src': {'sns': {'upd': sns.get('updated'), 'age_min': _age_min(sns.get('updated'), now),
                          'sha8': _sha([x.get('q') for x in gt] + [x.get('q') for x in sigl], 8),
                          'n': {'gt': len(gt), 'gtp': len(gtp), 'sig': len(sigl), 'xt': len(xt)}},
                  'soc': {'upd': None,   # bare list 실측 — 모른다는 사실의 명시적 기록(amin_h·sha8로 사후 복원)
                          'sha8': _sha([x.get('t') for x in socl], 8),
                          'amin_h': min((x.get('a') for x in socl if isinstance(x.get('a'), (int, float))), default=None),
                          'n': len(socl)}},
          'gt': gt, 'gtp': gtp, 'sig': sigl, 'xt': xt, 'soc': socl}

    dk = _sha([(ig_bb or {}).get('src_hash'), (acct or {}).get('day'),
               sorted((p.get('id'), (p.get('ins') or {}).get('views'), (p.get('ins') or {}).get('shares'),
                       (p.get('ins') or {}).get('saved')) for p in posts),
               tr['src']['sns']['sha8'], tr['src']['soc']['sha8'], (fb.get('brief') or {}).get('src_hash')])

    rec = {'v': 1, 'run_id': str(run_id), 'att': str(att), 'ev': ev, 'ts': now.isoformat(timespec='seconds'),
           'dk': dk, 'ig': {'brief': ig_bb, 'acct': acct, 'posts': posts, 'ctx': ctx, 'ctx_ref': ctx_ref},
           'fb': fb, 'tr': tr}
    return rec, prev_rows, shard


def main():
    t0 = time.time()
    now = _now()
    rec, prev_rows, shard = build_record(now)
    prev = prev_rows[-1] if prev_rows else {}
    # 멱등 2중키 — ① 내용 무변화(dk) ② 같은 run 재실행(Actions Re-run)
    if prev.get('dk') == rec['dk']:
        print('algo-ledger: 무변화(dk 동일) — append 0')
        return 0
    if rec['ev'] != 'manual-seed':
        for r in prev_rows:
            if r.get('run_id') == rec['run_id'] and r.get('att') == rec['att']:
                print('algo-ledger: 같은 run 재실행 감지 — append 0')
                return 0
    os.makedirs(os.path.join(DIR), exist_ok=True)
    if os.path.exists(shard) and os.path.getsize(shard) > MAX_SHARD_MB * 1024 * 1024:
        print('::warning::algo-ledger: 샤드 %s %dMB 초과 — append 중단(운영자 조치 필요)' % (os.path.basename(shard), MAX_SHARD_MB))
        return 0
    rec['ms'] = round((time.time() - t0) * 1000)
    line = json.dumps(rec, ensure_ascii=False, separators=(',', ':'))   # 직렬화 실패 = 파일 무접촉
    with open(shard, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
        f.flush()
        os.fsync(f.fileno())
    # 매니페스트(운영자 진입점 — "몇 회차 쌓였나" 파일 하나로)
    try:
        total = 0
        for name in os.listdir(DIR):
            if re.fullmatch(r'\d{4}-\d{2}\.jsonl', name):
                with open(os.path.join(DIR, name), 'rb') as f:
                    total += sum(1 for ln in f if ln.strip())
        json.dump({'n_runs': total, 'last_ts': rec['ts'], 'last_run_id': rec['run_id'],
                   'shard': os.path.basename(shard), 'shard_bytes': os.path.getsize(shard),
                   'brief_regenerated': not (rec['ig'].get('brief') or {}).get('unchanged', False)},
                  open(os.path.join(DIR, '_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except Exception as e:
        print('::warning::algo-ledger: _index 갱신 실패(원장은 정상) —', e)
    if rec['ms'] > 5000:
        print('::warning::algo-ledger: 조립 %dms > 5000ms — 점검 필요' % rec['ms'])
    print('algo-ledger: 회차 append —', os.path.basename(shard), '·', len(line), 'B ·', rec['ms'], 'ms')
    return 0


if __name__ == '__main__':
    try:
        rc = main()
    except BaseException as e:   # fail-soft — 어떤 예외도 수집·브리프 커밋을 못 막는다
        print('::warning::algo-ledger 실패(fail-soft) —', repr(e))
        rc = 0
    sys.exit(rc)
