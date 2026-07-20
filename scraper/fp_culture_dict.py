#!/usr/bin/env python3
# 문화 선별 사전 생성기 (지문 축 · Q285 · 운영자 260720 "문화 퉁치기 금지 — 내 문화 게시물 첫 문장 키워드로 추림")
# ─────────────────────────────────────────────────────────────────────
# 원리: 운영자가 실제 발행한 문화·연예 게시물의 제목(l1)·첫줄(l2) 어휘를 시간가중으로 누적해
#       "운영자가 추리는 문화의 결" 사전을 만든다. 문화 후보 뉴스는 이 사전 매칭 점수로 추림/거름.
#       시간가중 = 0.5^(게시물 나이일/HALF_D) — 새 게시물이 쌓일수록 사전이 따라 변함(운영자 260720
#       "첫 문장 키워드는 시간이 지날수록 올라가는 게시물에 따라 달라진다") → 재실행 = 재계산이 갱신 방식.
# 입력: apps/insta/data/posts_db.jsonl (전량 지문 DB · Q284) · 출력: apps/insta/data/fp_culture_dict.json
# 실행: python3 scraper/fp_culture_dict.py [--dry viewer/candidates.json]  (--dry = 오늘 후보 시운전)
# ⚠️ 수동 실행 전용 — 훅·pre-commit·크론 편입 금지(CLAUDE.md [15] smoke 규약과 동일 축).
#     뷰어 가점 배선은 별도 발주([9] 평의회 대상) — 이 스크립트는 사전 산출까지만.
import json, re, sys, datetime, collections, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, 'apps/insta/data/posts_db.jsonl')
OUT = os.path.join(ROOT, 'apps/insta/data/fp_culture_dict.json')
KST = datetime.timezone(datetime.timedelta(hours=9))
HALF_D = 90         # 시간가중 반감기(일) — 조정 가능
TOP_N = 220         # 사전 어휘 수 — 조정 가능
# 사회문제화 크로스오버(운영자 "사회 측면도 잘 터짐 · 사회문제 정도론 올라와야") — 문화인데 이 어휘 동반 = 보너스
CROSS_RE = re.compile(r'논란|공분|역풍|고소|고발|소송|법원|재판|구속|입건|유출|폭로|사과|퇴출|하차|파문|청원|신상|악플|혐의|갑질|미투|표절|난입')
STOP = set('있다 없다 됐다 했다 한다 있는 하는 그리고 이번 지난 오늘 내일 결국 다시 함께 위해 대한 관련 이유 무슨 어떤 그냥 진짜 정말 바로 지금 최근 이후 발표 확인 사람 남성 여성 대해 게시 영상 사진 출처 광고 협찬 보기 클릭 하지만 그런데 이제 아직 모두 가장 매우 하나 자신 우리 당신 여러분 생각 만에 만의 공개 공식 확정 기념 첫날 첫날부터 돌파 달성 우승 연승 완파 역대 사상'.split())   # 뒤 12개 = 형식·성과 나열어(운영자 260720 v1.1: "N년 만에·돌파·우승" 같은 형식어가 주제어처럼 점수 먹던 오염 제거 — 경기결과·흥행수치 나열형은 코퍼스에 없는 결이므로 사전 밖)

def tokens(txt):
    return [w for w in re.findall(r'[가-힣A-Za-z0-9]{2,}', txt or '') if w not in STOP and not w.isdigit()]

def build():
    now = datetime.datetime.now(KST)
    wdict = collections.Counter()
    n_posts = 0
    for line in open(DB, encoding='utf-8'):
        p = json.loads(line)
        is_cul = ('연예화제' in (p.get('cl') or [])) or (p.get('cat') == '문화')
        if not is_cul: continue
        try:
            age_d = (now - datetime.datetime.fromisoformat(p['ts'] + 'T00:00:00+09:00')).days
        except Exception:
            continue
        w = 0.5 ** (max(age_d, 0) / HALF_D)   # 최신 게시물일수록 사전 지배력↑
        n_posts += 1
        for t in set(tokens((p.get('l1') or '') + ' ' + (p.get('l2') or ''))):
            wdict[t] += w
    top = dict(sorted(wdict.items(), key=lambda x: -x[1])[:TOP_N])
    # v1.2 전역 인물·브랜드 층 — 문화 한정 사전이 카테고리를 넘는 운영자 결(트럼프 시상식·쿠팡 화재 등)을
    # 놓치던 구멍 봉합(260720 정답지 검증: 트럼프·쿠팡 지문 0점 → 전역층으로 회수). posts_db 전체 kw 시간가중.
    pw = collections.Counter()
    for line in open(DB, encoding='utf-8'):
        p = json.loads(line)
        try: age_d = (now - datetime.datetime.fromisoformat(p['ts'] + 'T00:00:00+09:00')).days
        except Exception: continue
        w = 0.5 ** (max(age_d, 0) / HALF_D)
        for k in (p.get('kw') or []): pw[k] += w
    out = {'generated_kst': now.strftime('%Y-%m-%d %H:%M'), 'half_days': HALF_D, 'n_posts': n_posts,
           'cross_bonus': 1.0, 'dict': {k: round(v, 3) for k, v in top.items()},
           'persons': {k: round(v, 3) for k, v in pw.most_common(60)}}
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=None, separators=(',', ':'))
    json.dump(out, open(os.path.join(ROOT, 'viewer/fp_dict.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=None, separators=(',', ':'))   # 뷰어 소비용 사본(fail-soft 대상 · Q286)
    print(f'사전 생성: 문화·연예 게시물 {n_posts}건 → 어휘 {len(top)}개 (반감기 {HALF_D}일) → {os.path.relpath(OUT, ROOT)}')
    return out

def score(title, d):
    ts = set(tokens(title))
    s = sum(d['dict'].get(t, 0) for t in ts)                              # ①문화결 어휘(시간가중)
    s += min(sum(d.get('persons', {}).get(t, 0) for t in ts) / 10, 2.0)   # ②전역 인물·브랜드(÷10 정규화·상한 2)
    if CROSS_RE.search(title or ''): s += d['cross_bonus']                # ③사회문제화 크로스
    return round(s, 2)

def dry(d, cand_path):
    cands = json.load(open(cand_path, encoding='utf-8'))
    rows = []
    for c in cands:
        if (c.get('cat') or '') != '문화': continue
        t = c.get('title') or ''
        rows.append((score(t, d), c.get('cross') or 0, c.get('grade'), t[:52]))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    print(f'\n== 시운전: 문화 후보 {len(rows)}건 — 선별 점수순 (제안 추림선 = 사회크로스 보너스 1.0 이상) ==')
    print('-- 추려짐(상위 12):')
    for s, cr, g, t in rows[:12]: print(f'  {s:>5} | cr{cr:>2} g{g if g is not None else "–"} | {t}')
    print('-- 걸러짐(하위 8):')
    for s, cr, g, t in rows[-8:]: print(f'  {s:>5} | cr{cr:>2} g{g if g is not None else "–"} | {t}')

if __name__ == '__main__':
    d = build()
    if '--dry' in sys.argv:
        dry(d, sys.argv[sys.argv.index('--dry') + 1])
