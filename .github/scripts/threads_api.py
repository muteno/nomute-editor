#!/usr/bin/env python3
# 루시 스레드 발행·답글 API 계층 — Meta Threads API(graph.threads.net) · stdlib only · 시크릿 미등록 = no-op(rc 0)
# (운영자 260726 "새계정 + 루시 + 자동 댓글 + AI지식 후가공 + 밤 전용" · fb_fetch.py 자매 — 등록 절차 = docs/스레드_직결_세팅.md)
#
# ⚠ 기존 "스레드 = 러너 수집 불가" 판정(작업이력 5468행 · curation-algorithm 99행)은 **웹 스크래핑 축 한정**이다.
#   본 파일은 토큰 인증 공식 API라 데이터센터 IP 차단과 무관 = Actions 러너에서 정상 가동(260726 실측 조사).
#
# 상태 = viewer/threads_state.json(커밋 영속) — **재답글 스팸 차단의 핵심**. 러너는 실행마다 기억이 없어서
#   상태 없이 짜면 매 실행 같은 답글을 재수집해 같은 사람에게 반복 답글 → 스팸 판정·계정 정지(가상인물 자동화
#   정지 선례와 동일 결). 답글 id·상대 username·발행 원문 url을 영속 기록해 3중으로 막는다.
#
# 하위 명령(sh가 호출 · 각 명령 독립 rc):
#   me              내 계정 id·username 해석(빈값 = 자문자답 루프 방지 하드 중단)
#   digest          AI 지식 다이제스트 stdout(원료 = viewer/sns_trends.json hackernews·aivid · 기발행 url 제외)
#   post <파일>     본문 파일 → 컨테이너 생성 → 대기 → publish → 상태 기록
#   replies         답글 대상 후보 JSON stdout(내 답글·기답글·1인1일 캡·상한 전부 적용 후)
#   reply <id> <파일>  해당 답글에 답글 발행 → 상태 기록
import json, os, sys, time, urllib.request, urllib.error, urllib.parse, datetime, re

TOK = os.environ.get('THREADS_ACCESS_TOKEN', '').strip()
G = 'https://graph.threads.net/v1.0'
STATE = 'viewer/threads_state.json'
TRENDS = 'viewer/sns_trends.json'
KST = datetime.timezone(datetime.timedelta(hours=9))   # 시각 = KST 강제(CLAUDE.md §D4 · naive now 금지)
DRY = os.environ.get('LUCY_DRY_RUN', '').strip() == '1'

# 발행 한도 = Meta 공식(글 250/24h · 답글 1,000/24h)의 극히 일부만 쓴다. 자동 계정 정지 사유 1순위가 빈도라
# 자체 상한을 코드에 박는다(운영자 260726 한 수 "밤에만 · 저빈도 고정" 채택분).
REPLY_CAP_RUN = int(os.environ.get('LUCY_REPLY_CAP', '8'))      # 1회 실행당 답글 상한
REPLY_GAP_SEC = float(os.environ.get('LUCY_REPLY_GAP', '5'))    # 답글 간 간격(초)
SCAN_POSTS = 5                                                  # 답글 스윕 대상 = 내 최근 글 N개
SCAN_REPLIES = 25                                               # 글당 훑을 답글 수
PUBLISH_WAIT = float(os.environ.get('LUCY_PUBLISH_WAIT', '30'))  # 컨테이너 → publish 대기(Meta 권장 ~30초)
MAX_LEN = 500                                                   # 스레드 본문 상한


def _now():
    return datetime.datetime.now(KST)


def api(path, tok=None, method='GET', **params):
    """Graph 호출 — 에러 본문을 예외 메시지로 승격(fb_fetch.py api() 관용구 미러 ·
    "HTTP 400"만으론 권한 누락 vs 토큰 만료 진단 불가)."""
    params['access_token'] = tok or TOK
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f'{G}/{path}'
    try:
        if method == 'POST':
            req = urllib.request.Request(url, data=qs.encode(), method='POST')
        else:
            req = urllib.request.Request(f'{url}?{qs}')
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = (json.loads(e.read().decode('utf-8', 'replace')).get('error') or {})
            code = err.get('code')
            msg = err.get('message', 'HTTP error')[:200]
            # 190 = 토큰 만료/무효. 조용한 실패로 묻으면 계정이 며칠째 죽은 걸 아무도 모른다 → 명시 승격.
            if code == 190:
                raise RuntimeError(f'토큰 만료·무효(code 190) — 시크릿 THREADS_ACCESS_TOKEN 재발급 필요: {msg}') from None
            raise RuntimeError(f'{e.code}/{code}: {msg}') from None
        except RuntimeError:
            raise
        except Exception:
            raise RuntimeError(f'{e.code}: HTTP error(본문 파싱 불가)') from None


# ── 상태(영속) ───────────────────────────────────────────────────────────────
def load_state():
    try:
        d = json.load(open(STATE, encoding='utf-8'))
        if not isinstance(d, dict):
            raise ValueError
    except Exception:
        d = {}
    d.setdefault('posted', [])        # [{id, url, src, ts}] — 발행 이력(원문 url 재사용 차단)
    d.setdefault('replied', [])       # [reply_id] — 답글 단 대상(재답글 차단 1차)
    d.setdefault('replied_users', {})  # {username: 'YYYY-MM-DD'} — 1인 1일 1회(재답글 차단 2차)
    return d


def save_state(d):
    d['updated'] = _now().isoformat()
    # 무한 성장 방지 — 최근분만 유지(오래된 답글은 API 조회 범위 밖이라 재답글 위험이 사라진다)
    d['posted'] = d['posted'][-300:]
    d['replied'] = d['replied'][-2000:]
    cut = (_now() - datetime.timedelta(days=14)).strftime('%Y-%m-%d')
    d['replied_users'] = {k: v for k, v in d['replied_users'].items() if v >= cut}
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(d, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


# ── 위생(발행 직전 최종 방어) ────────────────────────────────────────────────
def sanitize(text):
    """LLM 산출 → 스레드 본문. 코드펜스·지문 별표 제거 후 문장 경계로 500자 컷.
    스레드엔 이탤릭이 없어서 지문 `*…*`가 그대로 별표로 노출된다(= 봇 티)."""
    t = (text or '').strip()
    t = re.sub(r'^```[a-zA-Z]*\n?|```$', '', t, flags=re.M).strip()
    t = re.sub(r'\*+', '', t)                      # 지문·볼드 별표 제거
    t = re.sub(r'\n{3,}', '\n\n', t).strip()
    if len(t) <= MAX_LEN:
        return t
    cut = t[:MAX_LEN]
    m = max(cut.rfind('。'), cut.rfind('.'), cut.rfind('!'), cut.rfind('?'), cut.rfind('\n'))
    return (cut[:m + 1] if m > MAX_LEN * 0.5 else cut).strip()


# ── 명령 ─────────────────────────────────────────────────────────────────────
def cmd_me():
    d = api('me', fields='id,username')
    uid, uname = str(d.get('id') or '').strip(), str(d.get('username') or '').strip()
    if not uid:
        print('threads: me 해석 실패 — 자기 필터가 무력화되면 자문자답 루프로 빠지므로 중단', file=sys.stderr)
        return 1
    print(json.dumps({'id': uid, 'username': uname}, ensure_ascii=False))
    return 0


def cmd_digest():
    """AI 지식 원료 다이제스트 — viewer/sns_trends.json(30분 크론 산출)을 **읽기만** 한다(D2-1 준수).
    hackernews = 해외 AI 원문 · aivid = 국내 AI 소식. 이미 발행에 쓴 url은 제외해 같은 소재 반복을 막는다."""
    try:
        d = json.load(open(TRENDS, encoding='utf-8'))
    except Exception as e:
        print(f'threads: 원료 없음({e}) — 다이제스트 빈손', file=sys.stderr)
        return 1
    st = load_state()
    used = {p.get('src') for p in st['posted'] if p.get('src')}
    L = []
    hn = [h for h in (d.get('hackernews') or []) if (h.get('url') or '') not in used]
    if hn:
        L.append('[해외 AI·기술 원문 — Hacker News 인기순]')
        for h in hn[:10]:
            L.append(f" - {str(h.get('title') or '')[:120]} · 점수 {h.get('score')} · 댓글 {h.get('cmts')} · {h.get('url') or ''}")
    av = [a for a in (d.get('aivid') or []) if (a.get('url') or f"yt:{a.get('id')}") not in used]
    if av:
        L.append('')
        L.append('[국내 AI 소식 — 유튜브 AI 레인]')
        for a in av[:8]:
            L.append(f" - {str(a.get('title') or '')[:120]} · 채널 {str(a.get('channel') or '')[:30]} · 조회 {a.get('views')}")
    if not L:
        print('threads: 새 소재 없음(전부 기발행) — 스킵', file=sys.stderr)
        return 1
    L.append('')
    L.append(f"[수집 시각] {d.get('updated') or '미상'} · [현재] {_now().strftime('%Y-%m-%d %H:%M KST')}")
    print('\n'.join(L))
    return 0


def _publish(text, reply_to_id=None):
    """컨테이너 생성 → 대기 → publish. Meta는 컨테이너 처리에 평균 ~30초를 권장한다 —
    짧게 잡으면 간헐 실패로 슬롯이 조용히 유실된다."""
    p = {'media_type': 'TEXT', 'text': text}
    if reply_to_id:
        p['reply_to_id'] = reply_to_id
    if DRY:
        print(f"[DRY_RUN] {'답글→' + reply_to_id if reply_to_id else '발행'} ({len(text)}자)\n{text}\n", file=sys.stderr)
        return {'id': 'dry-run'}
    c = api('me/threads', method='POST', **p)
    cid = str(c.get('id') or '')
    if not cid:
        raise RuntimeError(f'컨테이너 생성 실패: {c}')
    time.sleep(PUBLISH_WAIT)
    r = api('me/threads_publish', method='POST', creation_id=cid)
    if not r.get('id'):
        raise RuntimeError(f'publish 실패: {r}')
    return r


def cmd_post(path):
    text = sanitize(open(path, encoding='utf-8').read())
    if len(text) < 10:
        print('threads: 본문이 비었거나 너무 짧다 — 발행 중단(빈 글 방지)', file=sys.stderr)
        return 1
    src = os.environ.get('LUCY_SRC_URL', '').strip()
    r = _publish(text)
    st = load_state()
    st['posted'].append({'id': r.get('id'), 'src': src, 'ts': _now().isoformat(), 'len': len(text)})
    save_state(st)
    print(f"threads: 발행 OK — id {r.get('id')} · {len(text)}자" + (f' · 소재 {src}' if src else ''))
    return 0


def cmd_replies():
    """답글 후보 추출 — 4중 필터. 하나라도 빠지면 같은 사람에게 반복 답글 → 스팸 판정."""
    me = api('me', fields='id,username')
    my_id, my_name = str(me.get('id') or ''), str(me.get('username') or '')
    if not my_id:
        print('threads: 내 id 미해석 — 자기 필터 무력화 위험이라 중단', file=sys.stderr)
        return 1
    st = load_state()
    done = set(st['replied'])
    today = _now().strftime('%Y-%m-%d')
    out = []
    mine = (api('me/threads', fields='id,timestamp', limit=SCAN_POSTS).get('data') or [])
    for p in mine:
        pid = str(p.get('id') or '')
        if not pid:
            continue
        try:
            reps = (api(f'{pid}/replies', fields='id,text,username,timestamp', limit=SCAN_REPLIES).get('data') or [])
        except Exception as e:
            print(f'threads: {pid} 답글 조회 실패({e}) — 건너뜀', file=sys.stderr)
            continue
        for r in reps:
            rid = str(r.get('id') or '')
            un = str(r.get('username') or '')
            txt = str(r.get('text') or '').strip()
            if not rid or not txt:
                continue
            if rid in done:                          # ① 이미 답글 단 대상
                continue
            if my_name and un == my_name:            # ② 내 답글(자문자답 루프 차단)
                continue
            if st['replied_users'].get(un) == today:  # ③ 1인 1일 1회
                continue
            out.append({'reply_id': rid, 'root_id': pid, 'username': un, 'text': txt[:400]})
            if len(out) >= REPLY_CAP_RUN:            # ④ 1회 실행 상한
                break
        if len(out) >= REPLY_CAP_RUN:
            break
    print(json.dumps(out, ensure_ascii=False))
    return 0


def cmd_reply(reply_id, path):
    text = sanitize(open(path, encoding='utf-8').read())
    if len(text) < 2:
        print('threads: 답글 본문 비었음 — 중단', file=sys.stderr)
        return 1
    un = os.environ.get('LUCY_REPLY_USER', '').strip()
    r = _publish(text, reply_to_id=reply_id)
    st = load_state()
    st['replied'].append(reply_id)
    if un:
        st['replied_users'][un] = _now().strftime('%Y-%m-%d')
    save_state(st)
    print(f"threads: 답글 OK — {reply_id} → id {r.get('id')} · {len(text)}자")
    time.sleep(REPLY_GAP_SEC)
    return 0


def main():
    if not TOK:
        print('threads: 시크릿 미등록(THREADS_ACCESS_TOKEN) — no-op 스캐폴드 스킵')
        return 0
    a = sys.argv[1:]
    if not a:
        print('usage: threads_api.py {me|digest|post <파일>|replies|reply <id> <파일>}', file=sys.stderr)
        return 2
    try:
        if a[0] == 'me':
            return cmd_me()
        if a[0] == 'digest':
            return cmd_digest()
        if a[0] == 'post':
            return cmd_post(a[1])
        if a[0] == 'replies':
            return cmd_replies()
        if a[0] == 'reply':
            return cmd_reply(a[1], a[2])
    except RuntimeError as e:
        print(f'::error::threads: {e}', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'threads: 예기치 못한 실패({e}) — fail-soft', file=sys.stderr)
        return 1
    print(f'threads: 알 수 없는 명령 {a[0]}', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
