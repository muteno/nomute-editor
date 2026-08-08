#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""채널 요약 지식 라이브러리 — 브리핑 아카이브를 '다음 회차의 참고 지식'으로 굽는다
(운영자 260808 "매번 판단이 그때그때 참고 지식이 없어서 새로 시작하는 것 같다 · 채널 요약의 라이브러리가 있으면 좋을듯 · 쌓이면 경쟁력").

⚠ 신설 사유 = **아카이브는 이미 쌓이는데 아무도 안 읽고 있었다.**
  실측 260808 = `viewer/chan_brief_log.jsonl` 24회차(3.5주)·215KB가 git 추적으로 살아 있는데,
  다음 회차 프롬프트에 들어가는 건 `chan_brief.sh`의 PREV_TXT = **직전 1회차 text 앞 1500자**뿐이었다.
  현 브리프 전문이 4,187자라 **64%가 잘리고 컷 지점이 [28일] 중간** = [3개월]·[전체]·[총론]이 통째로 증발.
  총론 = 채널 정체성·비전·미션 = 가장 오래 가는 판단인데 **매 회차 백지에서 다시 썼다.**
  그 결과가 실측 2종:
    ⓐ 정체성 표현이 8일 8변(08-01 "가장 먼저 가장 짧게 옮기는 곳" → 08-02 "퍼나르는 속보" →
       08-03 "속보 반사신경" → 08-04 "속보 번역기" → 08-05 "퍼나르기 속보 채널" → 08-06 없음 →
       08-07 "말을 얹지 않아서 퍼지는 뉴스 채널" → 08-08 "해석 없는 1차 기록소") = 같은 채널을 매일 다른 이름으로 부른다.
    ⓑ 하루 만의 정반대 제안(08-06 "업로드 시계를 21~22시로" → 08-07 "오후 2~6시로 당기자" → 08-08 다시 "21~22시")
       = 어제 뭐라 했는지 모르니 뒤집는다. 운영자에겐 '축적'이 아니라 '리셋'으로 보인다.
  기존 축은 전부 다른 것을 본다 — `algo_ledger`/`algo_insight` = **수치 패턴**(트렌드 일치·선행시차·초기속도),
  아카이브 로그 = **저장만**(뷰어 미노출·소비처 0) → 「과거 회차의 *판단*이 다음 판단에 들어가는가」는 축 자체가 없었다.
  이 레포가 반복해 겪은 「쌓이는데 아무도 안 읽는 죽은 원장」(brk_misfire·thumb_votes가 막으려던 바로 그 축)의 재발이다.

분업 = **파이썬이 추출·집계·대조 전부(LLM 0콜·네트워크 0·stdlib only)** · 모델은 이 블록을 읽고 판단만.
⚠ 파이썬은 「모순이다」라고 단정하지 않는다 — 축 분류는 사전 기반이라 오탐 가능이 구조적이므로,
  「같은 축에서 이런 제안들이 나왔다」까지만 사실로 제시하고 판정은 데이터를 쥔 모델에게 넘긴다([1] 정직).
  값이 안 뽑히는 제안은 **갈림 판정 대상에서 제외**(반복 카운트에만 참여) = 안전측 실패.

스코프 = ig(`viewer/chan_brief_log.jsonl`) · fb(`viewer/chan_brief_fb_log.jsonl`) — 두 로그는 같은 스키마
(`{date, updated, sections:[{k,label,text}], text}`)라 빌더 1개가 양쪽을 굽는다(사본 0 = 미러 드리프트 차단).

사용 = `python3 apps/insta/brief_lib.py --scope ig` → stdout에 프롬프트 주입 블록(없으면 빈 출력·rc0)
       `--json` = 기계 JSON · `--max-runs N` = 읽을 최근 회차 상한.
전 경로 fail-soft(rc0 · 라이브러리 실패가 브리프를 못 죽인다 = 실패 시 빈 블록 → 종전 동작).
CONTRACT: check_brief_lib
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

LOGS = {
    'ig': 'viewer/chan_brief_log.jsonl',
    'fb': 'viewer/chan_brief_fb_log.jsonl',
}
SCOPE_NM = {'ig': '인스타', 'fb': '페이스북'}

MAX_RUNS = 30          # 읽을 최근 회차 상한(프롬프트 비대 가드 — 로그 캡은 180회차)
OUT_WIN = 7            # ⑤ 성패 대조 창(제안일 전 7일 vs 후 7일)
OUT_MIN_N = 3          # ⑤ 창당 최소 게시물(미만 = [표본부족] — 없는 결론을 지어내지 않는다)
OUT_SHOW = 5           # ⑤ 표시 제안 수
RIPE_H = 48            # ⑤ 성과 비교에 넣을 최소 나이(h) — 조회는 며칠에 걸쳐 쌓인다(나이 편향 차단)
LEDGER_GLOB = 'apps/insta/data/algo_runs/*.jsonl'   # 회차 원장(게시물 절대값 · 기록자 = insta-fetch 단독)
IDENT_SHOW = 10        # ① 정체성 궤적 표시 회차
REPEAT_MIN = 2         # ② 반복 제안 하한(1회 = 일시 관측이라 '굳은 축'이 아니다)
REPEAT_SHOW = 8        # ② 표시 개수
SPLIT_WIN = 7          # ③ 갈림 판정 창(최근 N회차 — 더 넓히면 낡은 방침 변경까지 모순으로 읽는다)
SPLIT_SHOW = 3         # ③ 표시 축 수
SPLIT_LINES = 4        # ③ 축당 표시 줄 수
PREV_CHARS = 3000      # ④ 직전 전문 상한(구판 1500 → 전 섹션이 들어가는 크기 = 이 모듈의 존재 이유)


# ── 축 사전 — 제안 줄이 '무엇에 대한 제안인가' ────────────────────────────────
# ⚠ 확실한 것만 담는다. 못 잡으면 축 없음(= 반복·갈림 판정 밖) = 안전측 실패.
# ⚠ 판정은 **첫 매치가 아니라 최다 매치**다 — 첫 매치 우선으로 두면 사전 순서가 곧 답이 되어
#   「문화 소재를 주 1회 고정」·「질문형 제목을 주 2회」가 둘 다 [게시 빈도]로 묶여 **거짓 갈림**이 난다(260808 첫 실행 실측).
#   동점이면 판정을 포기(None)한다 — 억지로 한 축에 밀어넣는 것보다 빠지는 쪽이 싸다([1] 정직).
AXES = [
    ('업로드 시간대', ('시간대', '시계', '피크', '업로드 시간', '몇 시', '시에 올', '시에 걸', '시에 물', '오후', '오전', '저녁', '심야')),
    ('게시 포맷',     ('릴스', '피드', '카루셀', '캐러셀', '슬라이드')),
    ('게시 빈도',     ('하루', '주 1', '주 2', '주 3', '배급', '게시 수', '무게시', '쉬는 날', '연속 게시')),
    ('소재 주제',     ('문화', '정치', '사회', '스포츠', '연예', '경제', '국제', '소재를', '주제를')),
    ('제목·네이밍',   ('제목', '네이밍', '질문형', '평서', '캡션', '카피')),
    ('시리즈·기획',   ('시리즈', '연재', '고정 코너', '정기', '기획')),
]

_RE_RANGE = re.compile(r'(\d{1,2})\s*[~–—-]\s*(\d{1,2})\s*시')
_RE_HOUR = re.compile(r'(\d{1,2})\s*시')
_RE_AFTN = re.compile(r'오후\s*(\d{1,2})')
_FMT_WORDS = ('릴스', '피드', '카루셀', '캐러셀')
_TOPIC_WORDS = ('문화', '정치', '사회', '스포츠', '연예', '경제', '국제')
_NAME_WORDS = ('질문형', '평서', '이모지', '숫자형')
_RE_PERDAY = re.compile(r'하루\s*(\d+)\s*장')
_RE_PERWEEK = re.compile(r'주\s*(\d+)\s*(?:회|장|번)')


def _hours(s):
    """제안 줄에서 시각 집합 추출 — '오후 2~6시' 같은 표현도 24시간제로 정규화.

    ⚠ 범위 매치를 **먼저 소비하고 그 자리를 지운 뒤** 단독 시각을 훑는다 — 순서를 뒤집으면
      '오후 2~6시'의 `6시`가 단독 시각으로 재매치돼 값이 `6-18시`로 망가진다(260808 첫 실행 실측).
    """
    pm = bool(_RE_AFTN.search(s)) or ('저녁' in s) or ('밤' in s)
    hs, rest = set(), s
    for m in list(_RE_RANGE.finditer(s)):
        try:
            a, b = int(m.group(1)), int(m.group(2))
        except ValueError:
            continue
        if pm and a < 12 and b < 12:                     # '오후 2~6시' → 14~18시
            a, b = a + 12, b + 12
        hs.update({a, b})
        rest = rest.replace(m.group(0), ' ', 1)          # 소비분 제거 = 단독 매치 오염 차단
    for m in _RE_AFTN.finditer(rest):                    # '오후 N'(범위 밖 단독) → N+12
        try:
            h = int(m.group(1))
        except ValueError:
            continue
        hs.add(h + 12 if h < 12 else h)
    for m in _RE_HOUR.finditer(rest):
        try:
            h = int(m.group(1))
        except ValueError:
            continue
        hs.add(h + 12 if (pm and h < 12) else h)
    return {h for h in hs if 0 <= h <= 24}


def axis_of(line):
    """제안 줄 → 축 이름(못 잡으면 None) — **최다 매치** 판정 · 동점이면 포기.

    ⚠ 판정 대상은 제안절(' — ' 앞)뿐이다 — 근거절엔 다른 축의 수치가 인용되므로
      전문을 훑으면 축이 근거에 끌려간다(예: 포맷 제안의 근거에 '피크 21시'가 붙는다).
    """
    head = re.split(r'\s—\s', line, 1)[0]
    best, bn, tie = None, 0, False
    for name, keys in AXES:
        n = sum(1 for k in keys if k in head)
        if name == '업로드 시간대' and _hours(head):
            n += 1                                       # 시각 표기 자체가 이 축의 강한 증거
        if n > bn:
            best, bn, tie = name, n, False
        elif n == bn and n > 0:
            tie = True
    return None if (bn == 0 or tie) else best


def value_of(axis, line):
    """제안 줄 → 그 축에서 가리키는 '방향값'(못 뽑으면 None = 갈림 판정 제외)."""
    if axis == '업로드 시간대':
        hs = _hours(line)
        # 근거절(— 뒤)의 '피크가 21·22·20시' 인용까지 삼키면 전 회차가 같은 값이 된다 → 제안절(— 앞)만 본다
        head = re.split(r'\s—\s', line, 1)[0]
        hh = _hours(head) or hs
        if not hh:
            return None
        return '%d-%d시' % (min(hh), max(hh))
    if axis == '게시 포맷':
        head = re.split(r'\s—\s', line, 1)[0]
        hit = [w for w in _FMT_WORDS if w in head]
        return '·'.join(hit) if hit else None
    if axis == '게시 빈도':
        head = re.split(r'\s—\s', line, 1)[0]
        m = _RE_PERDAY.search(head)
        if m:
            return '하루 %s장' % m.group(1)
        m = _RE_PERWEEK.search(head)
        if m:
            return '주 %s회' % m.group(1)
        return None
    if axis == '소재 주제':
        head = re.split(r'\s—\s', line, 1)[0]
        hit = [w for w in _TOPIC_WORDS if w in head]
        return '·'.join(hit) if hit else None
    if axis == '제목·네이밍':
        head = re.split(r'\s—\s', line, 1)[0]
        hit = [w for w in _NAME_WORDS if w in head]
        return '·'.join(hit) if hit else None
    return None


def _norm_key(line):
    """반복 판정 키 — 제안절(— 앞)에서 조사·수식 흔들림을 걷어낸 뼈대.

    ⚠ 24자로 자르면 서로 다른 제안이 한 키로 뭉친다(260808 첫 실행 실측 = 총론 결론들이
      전부 '그래서무엇을…' 접두를 공유해 **×15 거짓 반복**이 났다) → 40자 + 축 결합.
    """
    head = re.split(r'\s—\s', line, 1)[0]
    head = head.lstrip('→ ').strip()
    # 정도부사 제거 — '릴스 비중을 **더** 올리자'와 '**다시** 올리자'는 같은 제안인데 글자로는 갈린다(260808 실측)
    head = re.sub(r'(더|다시|좀|계속|또|조금|확실히|반드시|무조건|이제|아예)', '', head)
    head = re.sub(r'[^0-9A-Za-z가-힣]+', '', head)
    return (axis_of(line) or '기타') + '|' + head[:40]


# ── 로그 읽기 ────────────────────────────────────────────────────────────────
def load_rows(path, max_runs=MAX_RUNS):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8') as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue                       # 손상 줄 = 건너뛴다(fail-soft)
    rows.sort(key=lambda r: str(r.get('date') or ''))
    return rows[-max_runs:]


# ── ⑤ 회차 원장 조인 — 「그 제안, 그 뒤 어떻게 됐나」 ──────────────────────────
# ⚠ 이 층만 `algo_runs` 원장(게시물 절대값)을 읽는다. 브리핑 로그는 「무슨 말을 했나」만 알고
#   「그래서 그게 맞았나」는 모르기 때문 — 그 조인이 없으면 라이브러리는 일기장이지 지식본이 아니다.
def load_posts(root=ROOT):
    """원장 전 샤드에서 게시물 풀 구성(id 유일) — **필드별 최신 비결측** 채택.

    ⚠ 통짜 최신 레코드로 덮으면 안 된다 — 260808 실측 = 같은 게시물이 회차마다 다시 실리는데
      분류 필드(fmt·st·cat)가 **뒤 회차에서 None으로 비어 오는 경우가 있어**(실측 2건) 통짜 덮어쓰기는
      멀쩡히 관측됐던 값을 지운다. 지워진 값은 「분류 결측」과 구분이 안 돼 비중 통계를 그대로 거짓말시킨다.
    """
    import glob as _g
    pool = {}
    for f in sorted(_g.glob(os.path.join(root, LEDGER_GLOB))):
        try:
            fh = open(f, encoding='utf-8')
        except Exception:
            continue
        with fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                for p in ((r.get('ig') or {}).get('posts') or []):
                    pid = p.get('id')
                    if not pid:
                        continue
                    cur = pool.setdefault(pid, {})
                    for k, v in p.items():
                        if v is not None and v != '':
                            cur[k] = v                 # 비결측만 갱신 = 관측된 값이 안 지워진다
    return list(pool.values())


def _pdate(p):
    t = p.get('ts_post')
    if not t:
        return None
    try:
        dt = __import__('datetime').datetime.fromisoformat(str(t).replace('Z', '+00:00'))
        return dt.astimezone(__import__('datetime').timezone(__import__('datetime').timedelta(hours=9)))
    except Exception:
        return None


def _med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _fv(v):
    """조회수 → 만 단위 한국식(chan_brief.sh fv() 표기 계승 — 프롬프트 안 표기 통일)."""
    if v is None:
        return '—'
    v = round(v)
    return '{:,}만'.format(round(v / 10000)) if v >= 10000 else '{:,}'.format(v)


# 축 → (원장 필드, 제안값 → 필드값 정규화) · 못 재는 축(시리즈·기획)은 아예 안 넣는다
_OUT_FIELD = {'게시 포맷': 'fmt', '제목·네이밍': 'st', '소재 주제': 'cat'}
_VAL_NORM = {'질문형': '질문', '평서': '평서', '이모지': '이모지브리핑', '숫자형': '숫자'}


def _share(posts, axis, val):
    """창 안에서 「제안이 가리킨 값」의 비중(%) — **분류 결측은 분모에서 뺀다**.

    ⚠ 결측을 0으로 세면 「릴스 비중이 떨어졌다」는 거짓 신호가 난다(260808 실측 = 34건 중 12건이
      원장에 분류값 자체가 없다). 분모는 「그 축이 실제로 분류된 게시물」뿐이고, 뺀 수는 호출부가 같이 낸다.
    """
    if axis == '업로드 시간대':
        m = re.match(r'(\d{1,2})-(\d{1,2})시', val or '')
        if not m:
            return None, 0
        lo, hi = int(m.group(1)), int(m.group(2))
        ds = [d for d in (_pdate(p) for p in posts) if d]
        if not ds:
            return None, 0
        hit = sum(1 for d in ds if lo <= d.hour <= hi)
        return round(hit / len(ds) * 100), len(ds)
    if axis == '게시 빈도':
        return None, 0                                   # 비중이 아니라 일평균 = 호출부가 따로 낸다
    fld = _OUT_FIELD.get(axis)
    if not fld:
        return None, 0
    want = {_VAL_NORM.get(x, x) for x in (val or '').split('·') if x}
    known = [p for p in posts if p.get(fld)]
    if not known:
        return None, 0
    hit = sum(1 for p in known if p.get(fld) in want)
    return round(hit / len(known) * 100), len(known)


def outcomes(props, posts):
    """제안별 전/후 창 대조 — 사실만 낸다(인과 단정 0).

    ⚠ 파이썬은 「그 제안이 먹혔다」라고 말하지 않는다 — 제안 뒤 실제로 어느 쪽으로 움직였는지와
      그때 성과가 얼마였는지까지만 사실로 내고, 인과 판정은 데이터를 쥔 모델 몫([1] 정직 · ③ 갈린 축과 같은 축).
    """
    import datetime as _dt
    dated = [(d.date(), p) for d, p in ((_pdate(p), p) for p in posts) if d]
    if not dated:
        return []
    last = max(d for d, _ in dated)          # 원장이 아는 마지막 발행일 = 관측 지평
    out = []
    for pr in props:
        if not pr.get('axis'):
            continue
        try:
            D = _dt.date.fromisoformat(pr['date'])
        except Exception:
            continue
        # ⚠ 창이 아직 안 찼으면 **평가 자체를 보류**한다(260808 첫 실행 실측 봉합) —
        #   후 창을 OUT_WIN 고정으로 나누면 실경과 2일을 7로 나눠 「일평균 1.71 → 0.43」 같은
        #   급감 신호를 만든다. 게시를 줄인 적이 없는데 줄인 것처럼 보이는 = 순수 거짓말.
        elapsed = (last - D).days
        if elapsed < OUT_WIN:
            out.append({'axis': pr['axis'], 'date': pr['date'], 'line': pr['line'],
                        'short': True, 'why': 'young', 'elapsed': max(elapsed, 0),
                        'nb': 0, 'na': 0})
            continue
        before = [p for d, p in dated if D - _dt.timedelta(days=OUT_WIN) <= d < D]
        after = [p for d, p in dated if D < d <= D + _dt.timedelta(days=OUT_WIN)]
        if len(before) < OUT_MIN_N or len(after) < OUT_MIN_N:
            out.append({'axis': pr['axis'], 'date': pr['date'], 'line': pr['line'],
                        'short': True, 'why': 'sample', 'nb': len(before), 'na': len(after)})
            continue
        e = {'axis': pr['axis'], 'date': pr['date'], 'line': pr['line'], 'short': False,
             'nb': len(before), 'na': len(after)}
        if pr['axis'] == '게시 빈도':
            e['move'] = ('일평균 게시', round(len(before) / OUT_WIN, 2), round(len(after) / OUT_WIN, 2), '개/일')
        elif pr.get('val'):
            sb, kb = _share(before, pr['axis'], pr['val'])
            sa, ka = _share(after, pr['axis'], pr['val'])
            if sb is None or sa is None:
                e['move'] = None
            else:
                e['move'] = ('%s 비중' % pr['val'], sb, sa, '%%(분류된 %d→%d건)' % (kb, ka))
        else:
            e['move'] = None
        # ⚠ 성과 비교는 **익은 게시물끼리만**(age_h ≥ RIPE_H) — 조회는 발행 후 며칠에 걸쳐 쌓이므로
        #   갓 올린 글을 성숙분과 나란히 세우면 「조회 중앙 56만 → 14만」처럼 **나이 차를 성과 하락으로**
        #   읽는다(260808 첫 실행 실측 = 후 창 게시물 age_h 10.5h). 표본이 모자라면 성과는 안 낸다.
        rb = [p for p in before if (p.get('age_h') or 0) >= RIPE_H]
        ra = [p for p in after if (p.get('age_h') or 0) >= RIPE_H]
        e['nrb'], e['nra'] = len(rb), len(ra)
        def spm(ps):
            xs = []
            for p in ps:
                i = p.get('ins') or {}
                v, s = i.get('views'), i.get('shares')
                if v and s is not None:
                    xs.append(s / v * 1000)
            return _med(xs)
        if len(rb) >= OUT_MIN_N and len(ra) >= OUT_MIN_N:
            e['vb'], e['va'] = _med([p.get('ins', {}).get('views') for p in rb]), _med([p.get('ins', {}).get('views') for p in ra])
            e['sb'], e['sa'] = spm(rb), spm(ra)
        else:
            e['vb'] = e['va'] = e['sb'] = e['sa'] = None
        out.append(e)
    out.sort(key=lambda x: x['date'], reverse=True)
    return out


def stalled(repeats, outs):
    """② 반복 × ⑤ 성패 교차 = **말은 여러 번 했는데 실제로는 안 옮겨진 축**
    (운영자 260808 3차 "아이디어 ㄱ").

    ⚠ 이 교차가 필요한 이유 = 260808 첫 실측이 드러낸 게 「제안이 틀렸다」가 아니라 「제안이 안 옮겨졌다」였다
      (07-30~31 제안 4건 전건 실행 ▼ · 그래서 ②에 「릴스 올리자 ×4회」가 쌓였다 = 논쟁이 아니라 미실행).
      ②만 보면 「확신이 굳은 축」으로 읽히고 ⑤만 보면 개별 제안의 전후일 뿐이라, 「반복 ∧ 미실행」은
      두 층을 곱해야만 보인다. 그리고 그게 다음 브리프가 **방침 대신 오늘 행동**을 내야 할 정확한 지점이다.

    술어 = 반복 2회+ ∧ 평가된 회차에서 실행이 **오르지 않음**(after ≤ before) ∧ 평가 표본 1건 이상.
    ⚠ 평가 못 한 제안(창 미충족·표본 미달)은 **여기 안 넣는다** — 안 옮겨진 건지 아직 모르는 건지 구분이 안 되고,
      모르는 걸 「안 했다」로 밀면 그 자체가 거짓 신호다([1] 정직 · ⑤ 보류 분리와 같은 축).
    """
    by = {}
    for o in outs:
        if o.get('short') or not o.get('move'):
            continue
        by.setdefault(_norm_key(o['line']), []).append(o)
    out = []
    for r in repeats:
        ev = by.get(_norm_key(r['line']))
        if not ev:
            continue
        flat = [o for o in ev if (o['move'][2] or 0) <= (o['move'][1] or 0)]
        if len(flat) == len(ev):                      # 평가된 전 회차에서 한 번도 안 올랐다
            last = sorted(ev, key=lambda x: x['date'])[-1]
            out.append({'axis': r['axis'], 'n': r['n'], 'line': r['line'],
                        'move': last['move'], 'date': last['date'], 'n_eval': len(ev)})
    out.sort(key=lambda x: -x['n'])
    return out


def sec_text(row, key):
    for s in (row.get('sections') or []):
        if s.get('k') == key:
            return s.get('text') or ''
    return ''


def arrows(row):
    """회차의 '→ ' 전략 줄 — (섹션 라벨, 줄) 목록."""
    out = []
    secs = row.get('sections') or []
    if not secs and row.get('text'):
        secs = [{'label': '전문', 'text': row['text']}]
    for s in secs:
        for ln in (s.get('text') or '').split('\n'):
            ln = ln.strip()
            if ln.startswith('→'):
                out.append((s.get('label') or '', ln))
    return out


def identity(row):
    """총론의 1층 강조(*…*) = 그 회차가 이 채널을 규정한 말.

    ⚠ 1층 강조는 프롬프트상 「튄 수치 **또는** 채널을 규정하는 핵심어」 둘 다 허용이라 수치가 섞여 들어온다
      (260808 실측 = FB 판에 «30대 중반에서 50대 초반이 절반 이상»이 정체성으로 잡혔다) →
      **숫자로 시작하는 강조는 수치 쪽**으로 보고 뺀다. 규정어가 숫자로 여는 경우는 드물어 손실이 작고,
      섞이면 「이 채널을 뭐라 불러왔나」 목록이 통계 나열로 오염돼 블록의 목적 자체가 죽는다.
    """
    t = sec_text(row, 'overview')
    if not t:
        return []
    out = []
    for m in re.findall(r'(?<!\*)\*([^*\n]{2,60})\*(?!\*)', t):
        m = m.strip()
        if not m or re.match(r'^[0-9]', m):
            continue
        out.append(m)
    return out


# ── 집계 ─────────────────────────────────────────────────────────────────────
def analyze(rows):
    """회차 목록 → (정체성 궤적, 총론 방향 궤적, 반복 제안, 갈린 축).

    ⚠ 총론의 '→ ' 줄과 [전체]의 '→ ' 줄은 **성격이 다르다** — 총론은 「반년~1년 방향 한 문장」이고
      전체는 「지금 실행할 전략」이다(chan_brief.sh 프롬프트 계약). 섞으면 방향 문장들이 서로
      반복·모순으로 잡혀 실행 전략 목록을 오염시킨다(260808 첫 실행 실측 = ×15 거짓 반복의 진범).
      → 총론 줄은 ②·③에서 빼고 ①-b 방향 궤적으로 따로 세운다.
    """
    ident, direction, props = [], [], []
    for r in rows:
        d = str(r.get('date') or '')[:10]
        for nm in identity(r):
            ident.append({'date': d, 'name': nm})
        for lb, ln in arrows(r):
            if lb == '총론':
                direction.append({'date': d, 'line': ln})
                continue
            ax = axis_of(ln)
            props.append({'date': d, 'sec': lb, 'line': ln,
                          'axis': ax, 'val': value_of(ax, ln) if ax else None,
                          'key': _norm_key(ln)})

    # ② 반복 제안 — 같은 뼈대가 몇 회차에 걸쳐 나왔나(회차 단위 집계 = 한 회차 중복은 1로)
    rep = {}
    for p in props:
        e = rep.setdefault(p['key'], {'line': p['line'], 'dates': set(), 'axis': p['axis']})
        e['dates'].add(p['date'])
        e['line'] = p['line']                          # 최신 표현으로 갱신
    repeats = sorted(({'line': v['line'], 'axis': v['axis'], 'n': len(v['dates']),
                       'dates': sorted(v['dates'])} for v in rep.values() if len(v['dates']) >= REPEAT_MIN),
                     key=lambda x: (-x['n'], x['dates'][-1]))

    # ③ 갈린 축 — 최근 창에서 같은 축인데 값이 2종 이상
    recent = {str(r.get('date') or '')[:10] for r in rows[-SPLIT_WIN:]}
    byax = {}
    for p in props:
        if not p['axis'] or not p['val'] or p['date'] not in recent:
            continue
        byax.setdefault(p['axis'], []).append(p)
    splits = []
    for ax, ps in byax.items():
        vals = {p['val'] for p in ps}
        if len(vals) < 2:
            continue
        ps = sorted(ps, key=lambda x: x['date'], reverse=True)
        splits.append({'axis': ax, 'vals': sorted(vals), 'items': ps[:SPLIT_LINES]})
    splits.sort(key=lambda s: (-len(s['vals']), -len(s['items'])))
    return ident, direction, repeats, splits, props


# ── 블록 조립 ────────────────────────────────────────────────────────────────
def build_block(rows, scope):
    if len(rows) < 2:
        return ''                                       # 1회차 = 라이브러리가 아니다(종전 동작 유지)
    ident, direction, repeats, splits, props = analyze(rows)
    d0 = str(rows[0].get('date') or '')[:10]
    d1 = str(rows[-1].get('date') or '')[:10]
    nm = SCOPE_NM.get(scope, scope)
    L = []
    L.append(f"[누적 지식 라이브러리 — 이 {nm} 채널 브리핑 {len(rows)}회차({d0}~{d1})에서 *네가 직접 내린 판단*의 원장이다. "
             "백지에서 시작하지 마라: 아래는 이미 쌓인 지식이고, 오늘 할 일은 이걸 **이어받아 갱신**하는 것이다. "
             "새로 발견한 게 있으면 그것대로 쓰되, 이미 확립된 축은 매번 새로 지어내지 말고 계승하거나 '왜 바꾸는지'를 밝혀라.]")

    if ident:
        L.append('')
        L.append(f"[① 이 채널을 뭐라고 불러왔나 — 총론이 규정한 정체성(최근 {IDENT_SHOW}회차 · 최신 위)]")
        seen_d = []
        for e in reversed(ident):
            if len(seen_d) >= IDENT_SHOW:
                break
            seen_d.append(f"{e['date'][5:]} {e['name']}")
        L.extend(seen_d)
        uniq = len({e['name'] for e in ident})
        if uniq >= 3:
            L.append(f"⚠ {len(ident)}회 규정 중 표현이 {uniq}종으로 갈렸다 — 같은 채널을 매번 다른 이름으로 부르면 축적이 안 된다. "
                     "위 표현 중 가장 정확한 하나를 **이어받아 굳히거나**, 바꿀 거면 오늘 데이터의 어느 근거로 바꾸는지 총론에 밝혀라.")

    if direction:
        L.append('')
        L.append(f"[①-b 총론이 가리킨 방향(마지막 '→' 결론 · 최근 {IDENT_SHOW}회차 · 최신 위)]")
        for e in list(reversed(direction))[:IDENT_SHOW]:
            L.append(f"{e['date'][5:]} {e['line'][:120]}")
        L.append("→ 이건 반년~1년짜리 나침반이라 매 회차 새로 지어낼 물건이 아니다. 방향이 그대로면 **표현을 굳혀 이어받고**, "
                 "틀어야 하면 무엇이 바뀌어서 트는지 한 줄로 밝혀라.")

    if repeats:
        L.append('')
        L.append(f"[② 반복해서 내린 제안 = 확신이 굳은 축(같은 제안이 나온 회차 수 · {REPEAT_MIN}회 이상)]")
        for e in repeats[:REPEAT_SHOW]:
            ds = ','.join(x[5:] for x in e['dates'][-5:])
            more = '…' if len(e['dates']) > 5 else ''
            L.append(f"×{e['n']}회 [{e['axis'] or '기타'}] {e['line'][:110]}  (최근: {ds}{more})")
        L.append("→ 3회 이상 반복된 제안은 이미 여러 번 말한 것이다. 오늘 또 같은 말을 할 거면 그대로 복창하지 말고 "
                 "**실행됐는지 데이터로 확인**하거나, 아직 안 굳었으면 '왜 아직인지'를 짚어라. 새 제안은 이 목록과 겹치지 않는 자리에서 꺼내라.")

    if splits:
        L.append('')
        L.append(f"[③ ⚠ 회차마다 답이 갈린 축 — 최근 {SPLIT_WIN}회차 안에서 같은 축인데 방향이 달랐다]")
        for s in splits[:SPLIT_SHOW]:
            L.append(f"[{s['axis']}] 제시된 값: {' vs '.join(s['vals'])}")
            for p in s['items']:
                L.append(f"  {p['date'][5:]} {p['line'][:105]}")
        L.append("→ 같은 축인데 회차마다 다른 답을 냈다는 뜻이다(과거의 네가 어제 뭐라 했는지 모른 채 뒤집었을 수 있다). "
                 "오늘은 **어느 쪽인지 데이터로 결론을 내거나**, 조건이 갈리는 축이면 '무엇일 땐 A · 무엇일 땐 B'로 정리해라. "
                 "근거 없이 또 뒤집지 마라.")

    # ⑤ 제안 성패 대조(IG 전용 — 원장 게시물이 IG 축이다 · FB는 조인 원료 없음 = 자동 생략)
    if scope == 'ig':
        try:
            outs = outcomes(props, load_posts())
        except Exception:
            outs = []
        shown = [o for o in outs if not o['short']][:OUT_SHOW]
        if shown:
            L.append('')
            L.append(f"[⑤ 그 제안, 그 뒤 어떻게 됐나 — 회차 원장 실측(제안일 기준 전 {OUT_WIN}일 vs 후 {OUT_WIN}일)]")
            for o in shown:
                L.append(f"{o['date'][5:]} [{o['axis']}] {o['line'][:88]}")
                if o.get('move'):
                    lb, b, a, unit = o['move']
                    arrow = '▲' if (a or 0) > (b or 0) else ('▼' if (a or 0) < (b or 0) else '—')
                    L.append(f"   실행: {lb} {b} → {a} {unit} {arrow}")
                else:
                    L.append('   실행: 이 축은 원장으로 못 잰다(분류 결측 또는 측정 불가 축)')
                if o.get('vb') is not None:
                    L.append(f"   성과: 조회 중앙 {_fv(o['vb'])} → {_fv(o['va'])}"
                             f" · 1천뷰당 공유 {('%.1f' % o['sb']) if o['sb'] is not None else '—'}"
                             f" → {('%.1f' % o['sa']) if o['sa'] is not None else '—'}"
                             f"  (익은 게시물 {o['nrb']}→{o['nra']}건 · 발행 {RIPE_H}h 경과분만)")
                else:
                    L.append(f"   성과: 아직 못 잰다 — 후 창에 {RIPE_H}h 이상 익은 게시물이 {OUT_MIN_N}건 미만"
                             f"(익은 {o.get('nrb', 0)}→{o.get('nra', 0)}건). 조회는 며칠에 걸쳐 쌓이니 지금 비교하면 나이 차를 성과로 오독한다.")
            L.append("→ ⚠ 이건 **인과가 아니라 전후 실측**이다(그 사이 사건·시류가 같이 움직였다). "
                     "다만 **말만 하고 안 옮겨진 제안**(실행 수치가 그대로거나 반대로 간 것)은 오늘 다시 꺼낼 때 "
                     "'왜 안 됐는지'부터 짚어라 — 같은 말을 세 번째 반복하는 건 제안이 아니라 소음이다.")
            st = stalled(repeats, outs)
            if st:
                L.append('')
                L.append('[⑥ ⚠ 말은 반복했는데 한 번도 안 옮겨진 축 — 오늘은 방침 말고 **행동**으로 바꿔라]')
                for e in st[:3]:
                    lb, b, a, unit = e['move']
                    L.append(f"×{e['n']}회 말했고, 마지막 평가({e['date'][5:]})에서 {lb} {b} → {a} {unit.split('(')[0].strip()} = 안 올랐다")
                    L.append("   %s" % e['line'][:104])
                L.append("→ 이 축은 **제안이 틀린 게 아니라 실행이 안 된 것**이다. 같은 방침을 또 적으면 다섯 번째 반복일 뿐이다. "
                         "[전체]의 '→ ' 전략 줄 **하나는 반드시** 이 축을 '오늘 올릴 그 한 장을 어떻게'로 좁혀 써라 "
                         "— 예: '릴스 비중을 올리자'(방침·금지) 대신 '오늘 첫 장은 릴스 평서로'(행동·필수). "
                         "무엇을·언제·어떤 모양으로가 한 줄에 들어가야 한다.")

            young = [o for o in outs if o['short'] and o.get('why') == 'young']
            samp = [o for o in outs if o['short'] and o.get('why') == 'sample']
            if young:
                L.append(f"   (아직 {OUT_WIN}일이 안 지나 평가 보류 {len(young)}건 — 가장 최근 것은 제안 후 {max(o['elapsed'] for o in young)}일차)")
            if samp:
                L.append(f"   (창 게시물 {OUT_MIN_N}건 미만으로 평가 보류 {len(samp)}건)")

    prev = rows[-1]
    ptxt = (prev.get('text') or '').strip()
    if not ptxt:
        ptxt = '\n\n'.join(f"[{s.get('label')}]\n{s.get('text')}" for s in (prev.get('sections') or []) if s.get('text'))
    if ptxt:
        L.append('')
        L.append(f"[④ 직전 회차 전문({str(prev.get('date') or '')[:10]}) — 반복 말고 이어서. 그때 짚은 흐름이 이어지는지 꺾였는지 비교해 연재처럼 읽히게(직전 표현 복붙 금지)]")
        L.append(ptxt[:PREV_CHARS])
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scope', default='ig', choices=sorted(LOGS))
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--max-runs', type=int, default=MAX_RUNS)
    a = ap.parse_args()
    try:
        rows = load_rows(os.path.join(ROOT, LOGS[a.scope]), a.max_runs)
        if a.json:
            ident, direction, repeats, splits, props = analyze(rows) if len(rows) >= 2 else ([], [], [], [], [])
            json.dump({'scope': a.scope, 'runs': len(rows),
                       'identity': ident, 'direction': direction, 'repeats': repeats,
                       'outcomes': [{k: v for k, v in o.items() if k != 'line'} for o in (outcomes(props, load_posts()) if a.scope == 'ig' else [])],
                       'splits': [{'axis': s['axis'], 'vals': s['vals'],
                                   'items': [{'date': p['date'], 'line': p['line']} for p in s['items']]} for s in splits]},
                      sys.stdout, ensure_ascii=False)
            print()
        else:
            b = build_block(rows, a.scope)
            if b:
                print(b)
    except Exception as e:                                # fail-soft — 라이브러리가 브리프를 죽이지 않는다
        print('brief_lib: 실패(%s) — 빈 블록' % e, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
