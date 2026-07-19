#!/usr/bin/env python3
"""PostToolUse 디자인 게이트(260702 · 260713 diff 게이트 증설) — Edit/Write 대상이 UI 파일이면 즉시 검사.
위반 = exit 2 → stderr가 모델에 피드백돼 같은 턴에서 자가수정(§디자인 계승 강제의 세션내 버전).
커밋 게이트보다 한 단계 엄격: '방금 편집한 파일'의 raw 증가 WARN도 여기선 차단(지금 고치는 게 제일 쌈).

260713 증설 — diff 신규 raw px 게이트(실행 계약 5 · 운영자 "9.5px 한 달째" 종전):
- 이 편집이 *추가한 줄*에서 font-size·radius·gap·padding·margin·blur() raw px를 검사(기존분 관용 = diff 기반).
- 총량 카운터가 아니라 diff라 remove-one/add-one 상쇄 위장에 면역. 차단 메시지에 가장 가까운 토큰을 자동 제안.
- 정당 raw 통로: `/* raw-ok: 사유 */` 같은 줄 주석 · 음수 margin(광학) · var()/env()/calc() · `--` 토큰 정의줄 ·
  백틱 포함 줄(JS 템플릿 = 자기완결) · 0 · letter-spacing(토큰 사다리 부재 = WARN만).
비UI 파일은 무간섭(exit 0·출력 0) — 일반 작업 마찰 없음."""
import json, sys, os, io, re, contextlib, subprocess

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
fp = (data.get('tool_input') or {}).get('file_path') or ''
root = os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd()
if not fp:
    sys.exit(0)
try:
    rel = os.path.relpath(os.path.abspath(fp), root).replace(os.sep, '/')
except ValueError:
    sys.exit(0)
if not re.match(r'^(viewer/.*\.(html|css)|구성도/.*\.(html|css))$', rel):
    sys.exit(0)

os.chdir(root)
sys.path.insert(0, os.path.join(root, 'shared'))
buf, rc = io.StringIO(), 0
with contextlib.redirect_stdout(buf):
    try:
        import check_refs
        for fn in ('check_design', 'check_icon_ssot', 'check_tokens_link',
                   'check_soremeori', 'check_autocomplete', 'check_viewer_js'):
            try:
                rc |= (getattr(check_refs, fn)() or 0)
            except Exception as e:
                print('%s 스킵(비차단): %s' % (fn, e))
        try:
            import build_design_mirror
            if hasattr(build_design_mirror, 'check'):
                rc |= (build_design_mirror.check() or 0)
        except Exception as e:
            print('mirror 검사 스킵(비차단): %s' % e)
    except Exception as e:
        print('check_refs 로드 실패(비차단): %s' % e)
out = buf.getvalue()
# 방금 편집한 파일의 raw 증가 WARN → 세션내 승격 차단(죽은토큰·× 문자 등 기존 WARN은 경고 유지)
esc = re.escape(rel)
if re.search(r'raw (hex|blur|accent_\w+) \d+ > baseline', out) and re.search(esc + r': raw ', out):
    rc = 1

# ── 260713 diff 게이트: 추가된 줄의 신규 raw px만 차단 ─────────────────────────
def _added_lines():
    try:
        d = subprocess.run(['git', 'diff', '-U0', '--', rel], capture_output=True,
                           text=True, timeout=10, cwd=root).stdout
        added = [l[1:] for l in d.splitlines() if l.startswith('+') and not l.startswith('+++')]
        if added:
            return added
    except Exception:
        pass
    ti = data.get('tool_input') or {}
    return (ti.get('new_string') or ti.get('content') or '').splitlines()


def _ladders():
    lad = {}
    try:
        s = open(os.path.join(root, 'viewer', 'index.html'), encoding='utf-8').read()
        m = re.search(r':root\s*\{([^}]*)\}', s)
        toks = dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', m.group(1))) if m else {}

        def px(*prefixes):
            o = []
            for k, v in toks.items():
                if any(k.startswith(p) for p in prefixes):
                    mm = re.match(r'\s*(\d+(?:\.\d+)?)px', v.strip())
                    if mm:
                        o.append((k, float(mm.group(1))))
            return o
        lad = {'font-size': px('--fs-'), 'border-radius': px('--r-'),
               'gap': px('--sp-'), 'padding': px('--sp-', '--trend-'), 'margin': px('--sp-', '--trend-'),
               'blur': px('--blur-')}   # --trend-indent(13px) 사다리 편입(260720 평의회 — raw 13px에 --sp-2(12) 오제안하던 것을 정확 제안으로 = CII "자동 제안" 문구 실체화)
    except Exception:
        pass
    return lad


_LAD = _ladders()


def _snap(axis, v):
    lad = _LAD.get(axis) or []
    if not lad:
        return '(갱신) 정문 또는 `/* raw-ok: 사유 */`'
    k, tv = min(lad, key=lambda t: abs(t[1] - v))
    if tv == v:
        return '동값 토큰 있음 — var(%s)=%gpx로 참조(복붙 금지)' % (k, tv)
    return '근접 토큰 var(%s)=%gpx(Δ%.2g) 자동 계승 권장 · 부적합 = (갱신) 정문 또는 `/* raw-ok: 사유 */`' % (k, tv, abs(tv - v))


GATED = re.compile(r'(?P<prop>font-size|border-radius|(?:row-|column-)?gap|padding(?:-[a-z]+)?|margin(?:-[a-z]+)?)\s*:\s*(?P<val>[^;{}]*)')
PX = re.compile(r'(?<![\w.-])(\d+(?:\.\d+)?)px')
BLUR = re.compile(r'(?<!-)blur\(\s*(\d+(?:\.\d+)?)px')
LS = re.compile(r'letter-spacing\s*:\s*(?P<val>[^;{}]*)')

diff_hits, ls_warn = [], []
for ln in _added_lines():
    l = ln.strip()
    if (not l or 'raw-ok' in l or l.startswith('--') or '`' in l
            or l.startswith('/*') or l.startswith('*') or 'env(' in l or 'calc(' in l):
        continue
    for m in GATED.finditer(l):
        val = m.group('val')
        if 'var(' in val:
            continue
        prop = m.group('prop')
        axis = ('padding' if prop.startswith('padding') else 'margin' if prop.startswith('margin')
                else 'gap' if prop.endswith('gap') else prop)
        for pm in PX.finditer(val):
            v = float(pm.group(1))
            if v == 0:
                continue
            diff_hits.append('%s: 신규 raw `%s:%gpx` → %s' % (rel, axis, v, _snap(axis, v)))
    for bm in BLUR.finditer(l):
        diff_hits.append('%s: 신규 raw `blur(%spx)` → %s' % (rel, bm.group(1), _snap('blur', float(bm.group(1)))))
    for lm in LS.finditer(l):
        if 'var(' not in lm.group('val') and PX.search(lm.group('val')):
            ls_warn.append('%s: letter-spacing raw px 신규 — 토큰 사다리 없는 축(WARN·비차단), 형제 값 계승 확인: %s' % (rel, l[:80]))

if diff_hits:
    rc = 1
    out += '\n🚫 diff 게이트 — 이 편집이 새로 넣은 raw(기존분 무관·추가 줄만 검사):\n' + '\n'.join('  · ' + h for h in diff_hits[:12])
if ls_warn:
    out += '\n⚠ ' + '\n⚠ '.join(ls_warn[:4])
# ──────────────────────────────────────────────────────────────────────────────

if rc:
    sys.stderr.write(
        '🎨 디자인 게이트 위반 — 계승이 디폴트(디자인기틀_SSOT.md §0·실행 계약 5). raw 값 창작 금지 → viewer/index.html :root의 '
        'var() 토큰 사용(정확 토큰이 없어도 가장 가까운 토큰 자동 계승 = 안 물음). 컴포넌트는 docs/CII_컴포넌트계승인덱스.md 정본 셀렉터 계승. '
        '진짜 새 단이 필요하면 (갱신) 정문 = 기틀 승인 경로, 1회성 광학 보정은 같은 줄 `/* raw-ok: 사유 */`:\n' + out)
    sys.exit(2)
print(out.strip() or '✅ 디자인 게이트 통과')
sys.exit(0)
