#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# lock.py — 컴포넌트 작업 락(운영자 260802 "머지하셈" 승인분 · 병렬 세션 재작업 방지)
#
# 왜: 260802 하루에만 **같은 컴포넌트(미리보기 코너 레일)를 두 세션이 동시에 갈아엎는 사고가 3번**
#     났다(창 안 우상단 → 창 밖 우측 → 2단). 뒤에 온 쪽은 매번 리베이스 충돌을 만나 통째로 재작업했다.
#     충돌 자체는 못 막는다(각 세션은 서로를 모른다) — 막을 수 있는 건 **"착수 30초 만에 알아채는 것"**이다.
#     그래서 락은 *잠그지 않는다*. 「지금 이 파일을 누가·언제부터 잡고 있다」를 파일로 남기고,
#     커밋 게이트(check_refs `check_component_lock`)가 그걸 눈앞에 띄운다(WARN·비차단).
#
# 왜 비차단인가: 하드 차단은 락 해제를 잊은 세션 하나가 레포 전체를 얼린다(락 파일이 곧 사고원).
#     대신 **TTL 자동 만료**(기본 90분)로 유령 락이 스스로 사라진다.
#
# 사용:
#   python3 shared/lock.py take "코너 옵션 레일" viewer/thumb.html viewer/tr.html   # 착수 선언
#   python3 shared/lock.py list                                                    # 살아있는 락
#   python3 shared/lock.py release "코너 옵션 레일"                                 # 완료 후 반납
#   python3 shared/lock.py take … --ttl 180                                        # 긴 작업
# 세션 식별 = 환경변수 NM_SESSION(없으면 'unknown-<pid>') · 자기 락은 게이트가 「내 락」으로 구분해 조용.
# ═══════════════════════════════════════════════════════════════════════════════
import os
import re
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCKDIR = os.path.join(ROOT, 'docs', 'locks')
KST = datetime.timezone(datetime.timedelta(hours=9))
DEFAULT_TTL = 90


def _slug(name):
    s = re.sub(r'[^\w가-힣]+', '-', name.strip()).strip('-')
    return s or 'lock'


def session_id():
    return os.environ.get('NM_SESSION') or ('unknown-%d' % os.getpid())


def parse(path):
    """락 파일 → dict(name·session·since·ttl·files) · 형식 깨지면 None(게이트는 조용히 건너뛴다)."""
    try:
        txt = open(path, encoding='utf-8').read()
    except OSError:
        return None
    g = lambda k: (re.search(r'^- %s:\s*(.+)$' % k, txt, re.M) or [None, None])[1]
    name = (re.search(r'^# (.+)$', txt, re.M) or [None, os.path.basename(path)])[1]
    since, ttl = g('since'), g('ttl-min')
    if not since:
        return None
    try:
        t0 = datetime.datetime.fromisoformat(since.strip())
    except ValueError:
        return None
    files = re.findall(r'^\s*-\s+([\w./\-*]+\.[\w*]+)\s*$', txt.split('- files:')[-1], re.M) if '- files:' in txt else []
    return {'path': path, 'name': name.strip(), 'session': (g('session') or '?').strip(),
            'since': t0, 'ttl': int(ttl or DEFAULT_TTL), 'files': files}


def live(now=None):
    """만료 안 된 락만 — TTL 초과분은 유령이라 무시(해제 잊은 세션이 레포를 얼리지 않게)."""
    now = now or datetime.datetime.now(KST)
    out = []
    if not os.path.isdir(LOCKDIR):
        return out
    for fn in sorted(os.listdir(LOCKDIR)):
        if not fn.endswith('.md'):
            continue
        lk = parse(os.path.join(LOCKDIR, fn))
        if lk and (now - lk['since']).total_seconds() / 60 < lk['ttl']:
            out.append(lk)
    return out


def take(name, files, ttl=DEFAULT_TTL):
    os.makedirs(LOCKDIR, exist_ok=True)
    p = os.path.join(LOCKDIR, _slug(name) + '.md')
    now = datetime.datetime.now(KST).replace(microsecond=0)
    body = ('# %s\n- session: %s\n- since: %s\n- ttl-min: %d\n- files:\n%s\n'
            % (name, session_id(), now.isoformat(), ttl,
               '\n'.join('  - ' + f for f in files) or '  - (미지정)'))
    open(p, 'w', encoding='utf-8').write(body)
    print('🔒 락 확보 — %s (%d파일 · %d분) → %s' % (name, len(files), ttl, os.path.relpath(p, ROOT)))
    return 0


def release(name):
    p = os.path.join(LOCKDIR, _slug(name) + '.md')
    if os.path.exists(p):
        os.remove(p)
        print('🔓 락 반납 — %s' % name)
    else:
        print('· 락 없음(이미 반납·만료) — %s' % name)
    return 0


def main(argv):
    if len(argv) < 2 or argv[1] in ('-h', '--help'):
        print(__doc__ or 'usage: lock.py take|list|release')
        print('usage: lock.py take <이름> <파일…> [--ttl 분] | list | release <이름>')
        return 0
    cmd = argv[1]
    if cmd == 'list':
        ls = live()
        if not ls:
            print('· 살아있는 락 0')
        for lk in ls:
            age = int((datetime.datetime.now(KST) - lk['since']).total_seconds() / 60)
            print('🔒 %s — %s (%d분 전 · 남은 %d분) · %s'
                  % (lk['name'], lk['session'], age, lk['ttl'] - age, ', '.join(lk['files']) or '(파일 미지정)'))
        return 0
    if cmd == 'release':
        return release(argv[2]) if len(argv) > 2 else 1
    if cmd == 'take':
        args = argv[2:]
        ttl = DEFAULT_TTL
        if '--ttl' in args:
            i = args.index('--ttl'); ttl = int(args[i + 1]); del args[i:i + 2]
        return take(args[0], args[1:], ttl) if args else 1
    print('❌ 모르는 명령: %s' % cmd)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
