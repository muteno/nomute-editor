#!/usr/bin/env python3
"""css_hoist.py — 「여러 뷰어에 값이 똑같은 인라인 CSS 사본」을 nm-shared.css 단일정본으로 승격한다.

▷ 왜 도구인가 = 260807 실측. 공용 CSS 사본 승격을 3회 시도해 3회 다 화면이 깨졌고, 매번 세션이
  승격 스크립트를 **새로 짰다**. 그게 3번 터진 직접 원인이다(주석 오독 → 페이지 붕괴 / `</style>`
  삼킴 → 무증상 문서 붕괴 / 대상 집합 변경 → 캐스케이드 전역 재배치). 절차를 파일로 굳힌다.

▷ 계약 = **안전하지 않으면 자동 롤백**. 승격 → `css_hoist_verify.js` 5축 판정 → rc≠0이면 원상복구.
  세션이 "됐다"고 선언할 여지를 없앤다([1] 정직의 기계화).

▷ 사용:
    python3 shared/css_hoist.py --family='.go'          # 드라이런(대상만 보여준다)
    python3 shared/css_hoist.py --family='.go' --apply  # 승격 + 검증 + 실패 시 자동 롤백
    python3 shared/css_hoist.py --scan                  # 남은 사본 가족 목록

▷ 대상 조건(전부 충족):
    ① 3파일 이상에 등장  ② 값(선언 집합)이 **전건 동일**  ③ 셀렉터가 --family 접두로 시작
    ④ `<noscript>` 밖  ← 「JS가 죽었을 때만」의 **조건부 정본**이라 공용 SSOT로 올리면 정상 상태에서도
       적용된다(260807 실사고 = 스크롤바 폴백 부활 → 260726 "스크롤 없애" 계약 위반).

⚠ 캐스케이드는 규칙을 옮기는 순간 전역 재배치된다 → **가족 단위로 하나씩** 돌려라. 한꺼번에 넣으면
  상호작용이 폭발해 매 회차 새 불일치가 난다(실측).

⚠⚠ **이 도구의 PASS는 최종 판정이 아니다 — 승격 뒤 반드시 `bash shared/smoke_all.sh` 를 돌려라.**
  판정기는 각 뷰어를 **직접** 열 뿐 **상태를 만들지 않는다**(스튜디오 모달을 열지 않고, 탭을 옮기지 않고,
  데이터를 시드하지 않는다) → 그 상태에서만 렌더되는 부품은 **요소가 아예 없어서 대조 대상이 안 된다**.
  260807 실사고 = `.topdock` 승격이 AI생성 판 도크의 페이드 스커트를 깼는데(sh auto·그라데 불일치)
  이 판정기는 두 번(요소 축 · 의사요소 축 추가 후) 다 통과시켰고 `smoke_parity` C11이 잡았다.
  → 상태 의존 표면(도크·모달·탭 전환 후 화면)을 건드리는 가족은 이 도구만으로 승인하지 마라.
"""
import argparse, collections, glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER = os.path.join(ROOT, 'viewer')
SSOT = os.path.join(VIEWER, 'nm-shared.css')
VERIFY = os.path.join(ROOT, 'shared', 'css_hoist_verify.js')
LINK = '<link rel="stylesheet" href="nm-shared.css"><!-- 뷰어 공용 부품 CSS SSOT(값 사본 금지 · 운영자 260807) -->'


def mask_comments(css):
    """주석을 **길이 보존 공백**으로 치환 — 인덱스가 원본과 1:1이라 제거 범위가 안 어긋난다.
    ⚠ 260807 실패 = 마스킹 없이 파싱해 `/* … */\\n  *` 가 통째로 셀렉터가 되고 페이지가 붕괴했다."""
    return re.sub(r'/\*.*?\*/', lambda m: ' ' * len(m.group(0)), css, flags=re.S)


def style_spans(src):
    """<style> 본문 구간 — ⚠ `<noscript>` 안은 제외(조건부 정본)."""
    ns = [(m.start(), m.end()) for m in re.finditer(r'<noscript[^>]*>.*?</noscript>', src, re.S)]
    out = []
    for m in re.finditer(r'<style[^>]*>(.*?)</style>', src, re.S):
        a, b = m.start(1), m.end(1)
        if any(a >= s0 and b <= e0 for s0, e0 in ns):
            continue
        out.append((a, b))
    return out


def top_rules(css, base=0):
    """최상위 규칙 [(sel, body, start, end)] — @블록·중첩 제외 · 셀렉터 오염분 스킵."""
    raw, css = css, mask_comments(css)
    out, i, buf, n = [], 0, '', len(css)
    while i < n:
        c = css[i]
        if c == '{':
            sel_start = i - len(buf)
            sel, buf = buf.strip(), ''
            i += 1; body_start, d = i, 1
            while i < n and d:
                if css[i] == '{': d += 1
                elif css[i] == '}':
                    d -= 1
                    if d == 0: break
                i += 1
            body, end = raw[body_start:i], i + 1
            sel = ' '.join(sel.split())
            if (sel and not sel.startswith('@') and '{' not in body
                    and '/*' not in sel and '*/' not in sel and ';' not in sel):
                out.append((sel, body, base + sel_start, base + end))
            i = end; continue
        elif c == '}':
            buf = ''
        else:
            buf += c
        i += 1
    return out


def decls(body):
    b = re.sub(r'/\*.*?\*/', ' ', body or '', flags=re.S)
    return tuple(sorted(d.strip() for d in b.split(';') if d.strip()))


def collect():
    per = {}
    for p in sorted(glob.glob(os.path.join(VIEWER, '*.html'))):
        src = open(p, encoding='utf-8').read()
        rs = []
        for s, e in style_spans(src):
            rs += top_rules(src[s:e], s)
        per[p] = (src, rs)
    return per


def candidates(per, family=None):
    idx, bodies = collections.defaultdict(dict), {}
    for p, (src, rs) in per.items():
        for sel, body, s, e in rs:
            d = decls(body)
            if len(d) < 2:
                continue
            idx[sel][p] = hashlib.md5('|'.join(d).encode()).hexdigest()[:8]
            bodies.setdefault((sel, idx[sel][p]), body)
    ssot = open(SSOT, encoding='utf-8').read() if os.path.exists(SSOT) else ''
    out = {}
    for sel, files in idx.items():
        if len(files) < 3 or len(set(files.values())) != 1:
            continue
        if family and not sel.startswith(family):
            continue
        if re.search(r'(?m)^' + re.escape(sel) + r' \{', ssot):
            continue                                   # 이미 승격됨
        out[sel] = (list(files.values())[0], sorted(files), bodies[(sel, list(files.values())[0])])
    return out


def style_balance(root):
    return {os.path.basename(p): open(p, encoding='utf-8').read().count('</style>')
            for p in sorted(glob.glob(os.path.join(root, '*.html')))}


def apply(targets, per):
    """SSOT 뒤에 규칙을 덧붙이고 각 뷰어 인라인에서 제거 + link."""
    order = list(targets)
    with open(SSOT, 'a', encoding='utf-8') as fh:
        for sel in order:
            h, files, body = targets[sel]
            fh.write('%s {%s}   /* %d표면 공용: %s */\n'
                     % (sel, body.rstrip().rstrip(';') + (';' if body.strip() else ''),
                        len(files), ' '.join(os.path.basename(f).replace('.html', '') for f in files)))
    n = 0
    for p, (src, rs) in per.items():
        hits = [(sel, s, e) for sel, body, s, e in rs if sel in targets and p in targets[sel][1]]
        if not hits:
            continue
        for sel, s, e in sorted(hits, key=lambda x: -x[1]):
            ls = src.rfind('\n', 0, s) + 1
            if not src[ls:s].strip():
                s = ls
            le = src.find('\n', e)
            if le > 0:
                tail = src[e:le].strip()
                # ⚠ 꼬리가 **주석뿐일 때만** 줄 끝까지. 무조건 삼키면 같은 줄의 `</style>`을 먹는다
                #   (260807 실패 = buttons 0 · bodyH 0 · 콘솔 에러 0 = 무증상 문서 붕괴).
                if not tail or (tail.startswith('/*') and tail.endswith('*/')):
                    e = le + 1
            src = src[:s] + src[e:]
        if 'href="nm-shared.css"' not in src:
            m = (re.search(r'(?m)^(.*<link[^>]*href="nm-clip\.css"[^>]*>.*)$', src)
                 or re.search(r'(?m)^(.*<link[^>]*href="tokens\.css"[^>]*>.*)$', src)
                 or re.search(r'(?m)^(.*<link[^>]*rel="stylesheet"[^>]*>.*)$', src))
            if m:
                src = src[:m.end()] + '\n' + LINK + src[m.end():]
        open(p, 'w', encoding='utf-8').write(src)
        n += len(hits)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--family', help="승격할 셀렉터 접두(예: '.go')")
    ap.add_argument('--apply', action='store_true', help='실제 승격(미지정 = 드라이런)')
    ap.add_argument('--scan', action='store_true', help='남은 사본 가족 목록')
    a = ap.parse_args()

    per = collect()
    if a.scan or not a.family:
        cands = candidates(per)
        fam = collections.Counter()
        for sel, (h, files, body) in cands.items():
            fam[re.split(r'[ :.#>,\[]', sel.lstrip('.#'), 1)[0]] += len(files)
        print('남은 사본 가족(3파일+ 완전동값 · 미승격) — 총 %d종 / %d규칙'
              % (len(cands), sum(len(v[1]) for v in cands.values())))
        for k, v in fam.most_common(20):
            print('  %-24s %3d규칙' % (k[:24], v))
        return 0

    targets = candidates(per, a.family)
    if not targets:
        print("· 대상 없음 — '%s' 로 시작하는 미승격 완전동값 사본이 없다." % a.family)
        return 0
    print("· 대상 %d종 / %d규칙 (family='%s')" % (len(targets), sum(len(v[1]) for v in targets.values()), a.family))
    for sel, (h, files, body) in sorted(targets.items(), key=lambda x: -len(x[1][1]))[:12]:
        print('   %2d표면  %s' % (len(files), sel[:72]))
    if not a.apply:
        print('· 드라이런 — 실제 승격은 --apply')
        return 0

    backup = tempfile.mkdtemp(prefix='nm-hoist-')
    shutil.copytree(VIEWER, os.path.join(backup, 'viewer'))
    bal_before = style_balance(VIEWER)
    n = apply(targets, per)
    print('· 인라인 %d규칙 제거 → SSOT 참조' % n)

    # ⑤ <style> 태그 균형(정적) — 렌더 전에 먼저 본다(붕괴면 렌더 판정이 무의미)
    bal_after = style_balance(VIEWER)
    broke = [f for f in bal_before if bal_before[f] != bal_after.get(f)]
    ok = not broke
    if broke:
        print('❌ <style> 태그 균형 붕괴: ' + ', '.join(broke))
    else:
        sels = os.path.join(backup, 'sels.json')
        json.dump(sorted(targets), open(sels, 'w'), ensure_ascii=False)
        rc = subprocess.call(['node', VERIFY, os.path.join(backup, 'viewer'), VIEWER, sels])
        ok = (rc == 0)

    if not ok:
        shutil.rmtree(VIEWER); shutil.copytree(os.path.join(backup, 'viewer'), VIEWER)
        print('↩︎ 자동 롤백 완료 — 이 가족은 표면 고유 경쟁 규칙이 있다(가족을 더 쪼개거나 인라인 유지).')
        return 1
    print('✅ 승격 확정 — %s (%d규칙) · 백업 %s' % (a.family, n, backup))
    print('   다음 = check_shared_canon 의 _SHARED_SELS 에 승격 셀렉터를 등재하고 커밋해라.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
