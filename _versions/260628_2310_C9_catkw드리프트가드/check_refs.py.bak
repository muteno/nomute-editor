#!/usr/bin/env python3
"""노뮤트 플랫폼 — 참조·버전 정합 점검 (수정 모드 ③ 커밋 전 실행).

v1.15.2류 사본 드리프트(파일 rename 후 참조 미갱신·파일명↔내부 버전 불일치)를
사람 눈 대신 기계로 잡는다. 통과 = exit 0 / 실패 = exit 1 + 목록.

검사 2종:
  1) 경로 참조 실존 — md 문서(라우터·SKILL·앱 지침·메모리·README)의 백틱 참조 중
     레포 경로 꼴(`apps/...`·`shared/...`·`.claude/...`·`_산출/...` + 확장자,
     또는 앱 문서 안의 `NN_*.md` 상대 참조)이 실제로 존재하는지.
     (글롭 `*`·플레이스홀더 `{}`·`<>`·공백 포함 표기는 검사 제외 = 오탐 방지.)
  2) 파일명↔내부 버전 일치 — apps/ 의 `*_v<버전>.md` 파일명 버전 토큰이
     1행 헤더의 버전 토큰과 정확히 같은지 (예: 00_지침_v2.5.md ↔ "... v2.5").

사용: python3 shared/check_refs.py   (레포 어디서 실행해도 됨)
"""

import os
import re
import sys
import glob
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 검사 대상 md (백업 폴더 _versions 제외)
SCAN_GLOBS = ('*.md', 'apps/**/*.md', '.claude/skills/**/*.md')
# 루트 기준 경로 참조로 보는 접두사 + 확장자
PATH_PREFIX = re.compile(r'^(?:apps|shared|\.claude|_산출)/')
PATH_EXT = re.compile(r'\.(?:md|py|sh|png)$')
# 앱 문서 내부의 형제 파일 참조 (NN_으로 시작하는 .md — 예: 01_지침_*.md 실명 참조)
SIBLING = re.compile(r'^\d{2}_[^/]+\.md$')
# 백틱 스팬 / 버전 토큰
BACKTICK = re.compile(r'`([^`\n]+)`')
VTOKEN = re.compile(r'v\d+(?:\.\d+)*')
# 검사 제외(플레이스홀더·글롭·예시)
SKIP_CHARS = set('*{}<>… ')


def md_files():
    seen = []
    for g in SCAN_GLOBS:
        for p in glob.glob(os.path.join(ROOT, g), recursive=True):
            if os.path.relpath(p, ROOT).startswith('_versions'):
                continue
            seen.append(p)
    return sorted(set(seen))


def check_paths():
    fails = []
    for md in md_files():
        rel_md = os.path.relpath(md, ROOT)
        if rel_md.startswith('_versions'):
            continue
        try:
            text = open(md, encoding='utf-8').read()
        except OSError:
            continue
        for span in BACKTICK.findall(text):
            cand = span.strip().lstrip('./')
            if not cand or any(c in SKIP_CHARS for c in cand):
                continue
            if PATH_PREFIX.match(cand) and PATH_EXT.search(cand):
                if not os.path.exists(os.path.join(ROOT, cand)):
                    fails.append('%s → `%s` 없음 (루트 기준)' % (rel_md, cand))
            elif SIBLING.match(cand):
                if not os.path.exists(os.path.join(os.path.dirname(md), cand)):
                    fails.append('%s → `%s` 없음 (같은 폴더 기준)' % (rel_md, cand))
    return fails


def check_versions():
    fails = []
    for p in glob.glob(os.path.join(ROOT, 'apps', '**', '*_v*.md'), recursive=True):
        rel = os.path.relpath(p, ROOT)
        name_tok = VTOKEN.findall(os.path.basename(p))
        if not name_tok:
            continue
        try:
            head = open(p, encoding='utf-8').readline()
        except OSError:
            continue
        head_toks = VTOKEN.findall(head)
        if name_tok[-1] not in head_toks:
            fails.append('%s → 파일명 %s ≠ 1행 헤더 %s' %
                         (rel, name_tok[-1], (head_toks or ['버전 없음'])))
    return fails


# ── 디자인시스템 토큰 게이트 (분신술 D5 · 260620) ──────────────────────────────
# 값 SSOT = viewer/index.html :root. 신규/수정 CSS는 raw hex/blur/accent-rgba 대신 var() 토큰을 써야 한다(§🎨).
# WARN-only(커밋 차단 안 함) = 점진 강제: 기존은 봐주되 raw가 *늘면* 커밋 전(수정 모드 ③)에 눈에 띈다.
# raw를 토큰으로 줄였으면 baseline도 그만큼 낮춰 재발 방지(드리프트는 늘 때만 잡힘).
# baseline = `:root` SSOT 블록 제외한 현재 raw 카운트(=드리프트는 *늘 때만* 잡힘). 260620 실측.
_DESIGN_BASELINE = {
    'viewer/index.html': {'accent_raw': 109, 'blur': 128, 'hex': 161},   # STAGE1 조임(분신술10·260628): accent 122→109·hex 167→161 = 헐렁 baseline 실측까지(raw 되살아나는 구멍 차단). //   # blur126→128 = 뉴스요약 사진첨부(.askattach) 글래스 backdrop var(--blur-s) +2(토큰·raw 아님·혼자 flat이라 '따로놀던' 것 형제 .iobtn/.sbtn과 통일·운영자 260628) // accent_raw 105→123 요약본 스포티파이→노뮤트 / mkbtn 글래스 +1 / blur90→92 요약본 제목복사 글래스 / 92→90 #editdlg backdrop 제거(main 260621) / +2 요약헤더 .dlbox 글래스 알약 var(--blur-m)(260621) / 124→122 대기열 .qgo·.qb-succ accent rgba→var(--accent-rgb) 토큰화(260622) / blur 92→100 = 당겨서새로고침 #ptr 글래스 var(--blur-s) +2(토큰·raw 아님) + 기존 누적분 흡수(260623) / 100→102 = 수정중 .rev-hint 글래스 var(--blur-s) 복원(260623) / 102→104 = 뉴스요약 .askclip 하단걸침 2A 글래스 var(--blur-s) +2(토큰·복붙버튼 일괄통일·260625) / blur 104→106 = 수집함 병합박스(.mergebox) 글래스 backdrop var(--blur-m) +2(토큰·raw 아님·병합기능·260625) / blur 106→110·hex 168→167 = 병합 바 중립칩 재설계(초록알약 1표면→글래스 칩+별도 X+기준칩 3표면 var(--blur-s)·토큰·raw 아님) + #0c0c0c 제거(빈 mb-n display:none)(260625) / blur 110→112 = 병합 해제 확인 팝오버(.unmerge-go) 글래스 backdrop var(--blur-s) +2(토큰·raw 아님·260626) / blur 112→114 = 라디얼 제작메뉴 자막생성 도구 탭(.tooltab) 글래스 backdrop var(--blur-m) +2(토큰·raw 아님·thumb .tab 계승·260626) / blur 114→116 = 수정/요약 전송버튼(.asksend) 글래스 통일 backdrop var(--blur-s) +2(토큰·raw 아님·.mkbtn 정본 계승·머지시 main 114 기준 +2·260627) / blur 116→120 = 입력칸 복사/붙여넣기/지우개·되돌리기(.iobtn·.iobtn-edge) 이미지 제작 attachCopyPaste 이식 backdrop var(--blur-s)·var(--blur-m) +4(토큰·raw 아님·#revText·#crevText·260627) / blur 120→122 = 뉴스요약 최소화 선택 picker(.min-pick) 글래스 backdrop var(--blur-l) +2(토큰·raw 아님·260627) / blur 122→124 = main 실측 124 lag 흡수(선존 +2) · 필터 오버레이(.filterpop) token var(--blur-l) +2 와 옛 토글(.tk) raw 8px −2 상쇄 = 순증 0(raw→token 교체·옛 카테고리 칩바→필터 버튼 오버레이·260628) / blur124→126 = 붙여넣기 폴백 모달(.pastefb::backdrop) var(--blur-s) +2(토큰·raw 아님·통일 기틀·260628)
    'viewer/thumb.html': {'accent_raw': 0, 'blur': 43, 'hex': 34},   # STAGE1: hex 35→34 실측조임.   # blur39→41 = 빠른메뉴 코어 위 '-' 최소화(#rfab .rmin) 글래스 backdrop blur+webkit = 형제 .rc 코어 외형 계승(blur14 saturate1.3·thumb엔 blur토큰 없어 raw·창 최소화 엄지존·260627). accent rgba 토큰화 완료(--accent-rgb·260621). blur41→43 = 이미지 슬롯(.covimg) 글래스모피즘 backdrop blur+webkit(플레이트 색 제거·픽토 accent 50% · thumb엔 blur토큰 없어 raw·260626). blur43→39 = .covimg 글래스 제거(전경 완전 제거→픽토만·−2) + 상단 3탭 글자화(.tab 글래스 제거·−2)(운영자 260626). blur/hex는 thumb 독자팔레트라 잔존(후속). hex…→28 = .go.err 미입력 빨강(#ff7a7a·#ff5d5d) · hex28→27 = 흰 체크 #fff 제거. hex29→30 = 개별 변형 다운로드(.jvar-dl.dlbtn) 도형제거·픽토그램 흰색 #fff = 좌측 라벨(.jvar #fff)과 색 일치 목적(--fg #e9eaec≠#fff라 토큰화 불가·의도적 raw·260626). hex27→29 = 썸네일 통합 오버레이 포맷색(.ovfmt.post 시안 #1fd6ee · .ovfmt.reels 레몬 #e7ff2e · 후속 토큰화·260624). hex31→29 = /3 저작권 단일토글 전환으로 중복 .cpfmt 시안/레몬 hex 2개 제거(.ovfmt 계승=중복 회수 · §🎨 "raw 줄이면 baseline도 낮춰라" · 분신술7·8·260625). blur32→34 = 저작권 복사칩(.cref-kw 글래스) · blur34→36 = 축약 체크 = 수집함 확인토글(.sc-tg.ack) 글래스 박스 계승(backdrop blur·−→✓ 모프·accent는 var(--accent-rgb) 토큰·260622). blur36→38 = #rfab .rc 빠른메뉴 코어를 수정 연필 FAB(.rev-fab) 글래스 외형 계승(backdrop blur+webkit·thumb엔 blur토큰 없어 raw·260622). blur38→40 = 통합모드 OPA 롤러(260624) → blur40→38 = OPA 롤러 제거·섹션 헤더 인라인 조절 전환(글래스 팝업 폐지·blur 2개 감소·260624). blur38→39 = 축약어 등록 다이얼로그(.abdlg) cfm 글래스 계승(thumb엔 blur토큰 없어 raw·260624). blur39→41 = .iobtn-edge G1 글래스모피즘 backdrop blur13+saturate(복붙버튼 통일·thumb엔 blur토큰 없어 raw·260625). blur41→43·hex30→35 = 붙여넣기 폴백 모달(.pastefb dialog) 신설 — backdrop blur(4px) webkit+표준 +2(thumb엔 blur토큰 없어 raw) + 박스 배경 그라데이션·메시지/입력/버튼 색(#14160f·#0c0f0c·#cfd2d7·#e8eaed = 기존 모달 배경·보조텍스트 패턴 복제·적합 토큰 부재) +5(통일 기틀·readText 막힌 환경 폴백·운영자 260628).
    # ▼ 도구 3파일 게이트 편입(분신술 9·10 P0 — 옛 사각지대: 닫기/최소화 버그가 난 파일군이 무방비였음). accent_raw=0 = ly/k 토큰화 완료(--accent-rgb·260628), 늘면 즉시 잡힘. comp 7은 후속 토큰화 대상.
    'viewer/ly.html': {'accent_raw': 0, 'blur': 14, 'hex': 16},   # blur12→14·hex14→16 = 붙여넣기 폴백 모달(.pastefb) 신설 — backdrop blur(4px) webkit+표준 +2(ly엔 blur토큰 없어 raw) + 박스 배경 그라데이션 #14160f·#0c0f0c +2(기존 모달 배경 패턴·통일 기틀·운영자 260628)
    'viewer/k.html': {'accent_raw': 0, 'blur': 12, 'hex': 7},
    'viewer/comp.html': {'accent_raw': 0, 'blur': 2, 'hex': 5},   # STAGE1: --accent-rgb 추가·raw 7곳 토큰화 → accent_raw 7→0(픽셀0·k/ly 패턴·260628).
}
_ROOT_BLOCK = re.compile(r':root\s*\{.*?\}', re.S)

# viewer :root 정의 토큰 중 var() 한 번도 안 쓰는 것 = 죽은 토큰 후보. 단 디자인시스템 어휘는
# 점진 이관(기존 raw→토큰) 중이라 '미리 선언·아직 미배선'이 의도된 게 다수(§🎨). → 현 미배선
# 집합을 baseline 으로 고정하고 그 *밖*의 새 미배선만 경고(드리프트는 늘 때만 = 새 죽은토큰 차단). 260621.
_FWD_UNUSED = {
    '--accent-2', '--amber-rgb', '--blur-backdrop', '--blur-l', '--blur-m', '--blur-s',
    '--blur-xl', '--btn', '--btn-xs', '--danger-rgb', '--dur-fast', '--ease', '--fg-2',
    '--fs-body', '--fs-display', '--fs-h1', '--fs-h2', '--fs-h3', '--fs-label', '--fs-xs',
    '--fw-b', '--fw-x', '--lh-base', '--on-arm', '--r-l', '--r-m', '--r-pill', '--sp-1', '--sp-2',
    '--sp-3', '--sp-4', '--warn',
    '--press-pico',   # 픽토온리 눌림 = thumb/ly/k의 rmin/file가 씀(index엔 .55 픽토 버튼 없음) = forward-declared(260628)
}
# --on-arm(arm 채움 위 글자색) = .revsend.confirm 채움 그라데 → 표준 플랫 arm 전환(260622)으로 현재 미배선.
# 정의는 보존(--arm/--arm-rgb 짝 · 향후 채움형 arm 컴포넌트용 어휘) → forward-unused 처리(§🎨).

def _new_dead_tokens(rel='viewer/index.html'):
    """viewer :root 정의 토큰 중 var() 미사용 & baseline 밖 = 새 죽은 토큰(접두사 오탐 가드)."""
    try:
        s = open(os.path.join(ROOT, rel), encoding='utf-8').read()
    except Exception:
        return []
    m = _ROOT_BLOCK.search(s)
    if not m:
        return []
    names = set(re.findall(r'(--[a-z0-9-]+)\s*:', m.group(0)))
    body = _ROOT_BLOCK.sub('', s, count=1)   # :root 정의부 제외 = 실사용만
    return [n for n in sorted(names)
            if n not in _FWD_UNUSED
            and not re.search(r'var\(\s*' + re.escape(n) + r'(?![\w-])', body)]

# ── viewer 인라인 JS 구문 게이트 (분신술 V2/V4 · 260620) ──────────────────────────
# 머지 가산·복붙 중복 등으로 viewer 인라인 <script>에 SyntaxError(예: let 재선언)가 들어가면
# 브라우저가 스크립트 전체를 평가 안 함 = 뷰어 전면 사망. node로 *구문만* 검사해 커밋 전 차단(하드 게이트).
# node 없으면 스킵(로컬·CI 환경차 흡수).
_SCRIPT_RE = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', re.S)

def check_viewer_js():
    node = shutil.which('node')
    if not node:
        print('⚠️ viewer JS 구문검사 스킵(node 없음)'); return 0
    rc = 0
    for rel in ('viewer/index.html', 'viewer/thumb.html', 'viewer/ly.html', 'viewer/k.html'):
        try:
            html = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        js = '\n;\n'.join(_SCRIPT_RE.findall(html))
        if not js.strip():
            continue
        tmp = None
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
                f.write(js); tmp = f.name
            r = subprocess.run([node, '--check', tmp], capture_output=True, text=True, timeout=30)
        finally:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        if r.returncode != 0:
            errs = [x for x in (r.stderr or '').splitlines() if 'Error' in x]
            print('❌ viewer JS 구문 오류 — %s: %s' % (rel, errs[0] if errs else 'syntax error'))
            rc = 1
        else:
            print('✅ viewer JS 구문 OK — %s' % rel)
    return rc

_ICON_DECL_RE = re.compile(r'^const ([A-Z0-9_]+_SVG) = ', re.M)
def check_icon_ssot():
    """공유 아이콘 SSOT 하드 게이트(운영자 260628 '하나 바꾸면 다 바뀜').
    nm-svg.js가 정의한 공유 아이콘을 뷰어가 다시 인라인 const로 선언하면(=섀도잉·드리프트 부활) rc=1.
    각 뷰어가 공유 아이콘을 *쓰면서* nm-svg.js를 로드 안 하면(런타임 ReferenceError) rc=1."""
    nm = os.path.join(ROOT, 'viewer/nm-svg.js')
    if not os.path.exists(nm):
        print('⚠️ nm-svg.js 없음 — 아이콘 SSOT 게이트 스킵'); return 0
    shared = set(_ICON_DECL_RE.findall(open(nm, encoding='utf-8').read()))
    if not shared:
        print('⚠️ nm-svg.js에 공유 상수 0 — 게이트 스킵'); return 0
    rc = 0
    for rel in ('viewer/index.html', 'viewer/thumb.html', 'viewer/ly.html', 'viewer/k.html'):
        try:
            html = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        loads = 'nm-svg.js' in html
        inlined = set(_ICON_DECL_RE.findall(html)) & shared
        if inlined:
            print('❌ 아이콘 SSOT 위반 — %s가 공유 아이콘을 인라인 재선언(섀도잉): %s → nm-svg.js만 두고 제거'
                  % (rel, ', '.join(sorted(inlined)))); rc = 1
        used = {c for c in shared if (c in html) and not loads}
        if used and not loads:
            print('❌ 아이콘 SSOT 위반 — %s가 공유 아이콘(%s)을 쓰는데 nm-svg.js 미로드 → <script src="nm-svg.js"> 추가'
                  % (rel, ', '.join(sorted(used))[:60])); rc = 1
    if rc == 0:
        print('✅ 아이콘 SSOT 정합 — 공유 아이콘 %d개 단일정본(nm-svg.js)·인라인 재선언 0' % len(shared))
    return rc

def check_design():
    # accent_raw = 차단(rc=1) 승격(운영자 ③b·STAGE1·260628). 단일 정확패턴 `rgba(15,253,2`라 오탐 0,
    #   index 빼고 전부 0(thumb/ly/k/comp) → 새 raw 강조색 박기 구조적 차단. 봇 무영향(check-refs.yml=PR전용·봇은 데이터JSON만 직푸시·A7 실측).
    # hex/blur/죽은토큰 = WARN 유지(의도적 raw·토큰글래스 +2 누적이라 차단하면 정당작업 막힘).
    warns, hard = [], []
    for rel, base in _DESIGN_BASELINE.items():
        try:
            s = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        s = _ROOT_BLOCK.sub('', s, count=1)   # :root = 토큰 SSOT 정의 자리 → 카운트 제외(D5 화이트리스트)
        cnt = {'accent_raw': s.count('rgba(15,253,2'), 'blur': s.count('blur('),
               'hex': len(re.findall(r'#[0-9a-fA-F]{3,8}\b', s))}
        for k, b in base.items():
            if cnt[k] > b:
                msg = '%s: raw %s %d > baseline %d → var() 토큰으로(§🎨)' % (rel, k, cnt[k], b)
                (hard if k == 'accent_raw' else warns).append(msg)
    for n in _new_dead_tokens():   # 새로 추가됐는데 var() 미배선인 토큰(죽은 토큰) — 배선하거나 정의 삭제
        warns.append('viewer/index.html: 토큰 %s 정의됐으나 var() 미사용 → 배선하거나 정의 삭제(§🎨)' % n)
    if hard:
        print('❌ 디자인 토큰 게이트(차단) — raw 강조색(rgba(15,253,2)) 증가 = var(--accent-rgb) 토큰으로:')
        for w in hard:
            print('  -', w)
    if warns:
        print('⚠️ 디자인 토큰 게이트(비차단): raw 값 증가 감지 —')
        for w in warns:
            print('  -', w)
    if not hard and not warns:
        print('✅ 디자인 토큰 게이트 — raw 값 baseline 이내(신규 미토큰 없음).')
    return 1 if hard else 0   # accent_raw만 차단, hex/blur/죽은토큰은 WARN

# 주입 지침 소스에 '----- ... -----' 형태 본문 줄 금지 (R6 가드 · 260624).
# inject_guidelines.sh 의 guidelines_version() 은 해시 입력에서 경로헤더('^----- path -----$')를 제외해
#   파일 rename 에도 같은 버전을 내(불필요 재생성 방지). 그런데 *주입 지침 본문*에 같은 형태의 줄이 있으면
#   그 줄도 해시에서 빠져 → 그 줄만 편집해도 버전이 안 바뀜 = 조용한 드리프트(이 시스템이 막으려는 바로 그것).
#   현재 0건. 이 게이트로 미래에 그런 줄이 들어오는 걸 차단(분신술 8인 권고 260624).
_DIVIDER_RE = re.compile(r'^----- .+ -----\s*$')
_INJECT_GLOBS = ('apps/news/00_에디터_뉴스_운영.md', 'apps/news/01_지침_에디터_뉴스_*.md',
                 'apps/news/02_라이브러리_이미지_*.md', 'PROJECT_MEMORY.md')


def check_inject_dividers():
    fails = []
    for g in _INJECT_GLOBS:
        for path in glob.glob(os.path.join(ROOT, g)):
            try:
                with open(path, encoding='utf-8') as fh:
                    for n, line in enumerate(fh, 1):
                        if _DIVIDER_RE.match(line):
                            rel = os.path.relpath(path, ROOT)
                            fails.append("주입 지침 본문에 '----- ... -----' 줄(%s:%d) — R6 해시서 제외돼 드리프트 미탐 위험. 다른 표기로 바꿔라." % (rel, n))
            except Exception:
                continue
    return fails


def check_inject_markers():
    """주입 지침 파일의 <!-- INJECT-SKIP-START/END --> 마커 짝 균형(260624 단일화 가드).
    START 가 END 없이 열리면 awk 가 EOF까지 통째로 주입에서 누락 = 조용한 드리프트(이 시스템이 막는 것).
    파일별 START 수 == END 수 가 아니면 실패."""
    fails = []
    for g in _INJECT_GLOBS:
        for path in glob.glob(os.path.join(ROOT, g)):
            try:
                txt = open(path, encoding='utf-8').read()
            except Exception:
                continue
            s, e = txt.count('INJECT-SKIP-START'), txt.count('INJECT-SKIP-END')
            if s != e:
                fails.append("INJECT-SKIP 마커 불균형(%s: START %d ≠ END %d) — 미종결 마커는 그 뒤 주입 내용을 통째 누락시킴." % (os.path.relpath(path, ROOT), s, e))
    return fails


def check_sens_vocab():
    """민감 통제어휘 미러 정합 — 드리프트 하드 게이트(260625 분신술 10인).
    정본 SSOT = prompts/news-analysis.md `tags:` 줄 '동일 통제어휘:'. viewer SENS_PROTECT 집합 일치 + DRUG_RE(viewer↔build-viewer) 바이트 동일 강제.
    (이 게이트 부재가 5↔7 드리프트·'장면 검열 없음' stale의 구조적 원인 — 기계로 닫음.)"""
    def _rd(p):
        try:
            return open(os.path.join(ROOT, p), encoding='utf-8').read()
        except Exception:
            return ''
    rc = 0
    prompt, viewer, bv = _rd('prompts/news-analysis.md'), _rd('viewer/index.html'), _rd('build-viewer.mjs')
    seg = prompt.split('동일 통제어휘:', 1)[1].split('(', 1)[0] if '동일 통제어휘:' in prompt else ''
    ssot = set(re.findall(r'#[가-힣·]+', seg))
    mv = re.search(r"const SENS_PROTECT\s*=\s*\[([^\]]+)\]", viewer)
    sp = set(re.findall(r'#[가-힣·]+', mv.group(1))) if mv else set()
    if not ssot or not sp:
        print('⚠️ 민감 통제어휘 추출 실패 — prompts SSOT/viewer SENS_PROTECT 패턴 확인(게이트 무력)')
    elif ssot != sp:
        print('❌ 민감 통제어휘 불일치 — prompts SSOT %s ≠ viewer SENS_PROTECT %s' % (sorted(ssot), sorted(sp)))
        rc = 1
    az = _rd('.github/scripts/analyze.sh')
    def _drug(s, pat):
        m = re.search(pat, s)
        return frozenset(re.findall(r'[가-힣]+', m.group(1))) if m else None
    drug = {
        'viewer': _drug(viewer, r'DRUG_RE\s*=\s*/([^/\n]+)/'),
        'build-viewer': _drug(bv, r'DRUG_RE\s*=\s*/([^/\n]+)/'),
        'analyze.sh': _drug(az, r"grep -qE '([^']*펜타닐[^']*)'"),   # #마약 백스톱 shell 어휘
    }
    present = {k: v for k, v in drug.items() if v}
    if len(set(present.values())) > 1:
        print('❌ DRUG 어휘 불일치(따로 놀기) — ' + ' / '.join('%s:%s' % (k, sorted(v)) for k, v in present.items()))
        rc = 1
    if rc == 0 and ssot and sp:
        print('✅ 민감 통제어휘 미러 정합 — 통제어휘 %d개·SENS_PROTECT 일치·DRUG 어휘 %d곳 동일' % (len(ssot), len(present)))
    return rc


def check_curation_constants():
    """큐레이션 랭킹 상수(viewer) ↔ docs/curation-algorithm.md §★ 정본값 정합 하드게이트.
    #1135식 stale-PR 자기-revert·코드↔문서 드리프트를 CI가 즉시 차단(260628 13인 감사 C8).
    viewer 리터럴(CROSS_POW·FOLLOW_W·BREAKING_RANK_BOOST·GRADE_W grade0 floor)을 §★ 인용값과 대조."""
    rc = 0
    try:
        v = open(os.path.join(ROOT, 'viewer', 'index.html'), encoding='utf-8').read()
        d = open(os.path.join(ROOT, 'docs', 'curation-algorithm.md'), encoding='utf-8').read()
    except Exception as e:
        print('⚠️ check_curation_constants 스킵(파일):', e); return 0
    star = next((ln for ln in d.splitlines() if '누적 랭킹' in ln and 'cross^' in ln), '')
    if not star:
        print('⚠️ check_curation_constants 스킵(§★ 랭킹식 줄 못 찾음)'); return 0
    def vcode(pat):
        m = re.search(pat, v); return m.group(1) if m else None
    def vdoc(pat):
        m = re.search(pat, star); return m.group(1) if m else None
    checks = [
        ('CROSS_POW',           vcode(r'const CROSS_POW\s*=\s*([\d.]+)'),           vdoc(r'cross\^([\d.]+)')),
        ('FOLLOW_W',            vcode(r'const FOLLOW_W\s*=\s*([\d.]+)'),            vdoc(r'FW([\d.]+)')),
        ('BREAKING_RANK_BOOST', vcode(r'const BREAKING_RANK_BOOST\s*=\s*([\d.]+)'), vdoc(r'isBreaking\?([\d.]+)')),
        ('GRADE_W.grade0',      vcode(r'GRADE_W\s*=\s*\{\s*0:\s*([\d.]+)'),         vdoc(r'floor 0\.05→\*\*([\d.]+)')),
    ]
    bad = []
    for name, code_v, doc_v in checks:
        if code_v is None or doc_v is None:
            bad.append('%s: 추출실패(code=%s·doc=%s)' % (name, code_v, doc_v)); continue
        if float(code_v) != float(doc_v):
            bad.append('%s: viewer=%s ≠ §★문서=%s (코드↔문서 드리프트/자기-revert 의심)' % (name, code_v, doc_v))
    if bad:
        print('❌ 큐레이션 상수↔문서 정합 실패(C8 게이트):')
        for b in bad: print('  -', b)
        rc = 1
    else:
        print('✅ 큐레이션 상수↔문서 정합 — CROSS_POW·FOLLOW_W·BOOST·GRADE_W floor = §★ 일치.')
    return rc


_INPUT_RE = re.compile(r'<input\b[^>]*>', re.I)
_AC_NEED = ('autocomplete', 'autocapitalize', 'autocorrect', 'spellcheck')

def check_autocomplete():
    """평문 텍스트 입력칸 = OS 자동완성 끔 4종 세트 하드 게이트(§🎨 · 운영자 260628).
    편집가능 <input type=text|search>가 autocomplete/autocapitalize/autocorrect/spellcheck 중 하나라도
    빠지면 rc=1 → 모바일 OS가 🔑비번·💳카드·📍주소 자동완성 바를 붙여 입력 번잡(운영자 실측 = 썸네일 '부제').
    제외: readonly/disabled/hidden(표시 전용 = 자동완성 대상 아님)·기타 type."""
    rc = 0
    for rel in ('viewer/index.html', 'viewer/thumb.html', 'viewer/ly.html', 'viewer/k.html', 'viewer/comp.html'):
        try:
            s = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        for m in _INPUT_RE.finditer(s):
            tag = m.group(0)
            tl = tag.lower()
            tm = re.search(r'type\s*=\s*["\']?(\w+)', tl)
            typ = tm.group(1) if tm else 'text'   # type 생략 = text
            if typ not in ('text', 'search'):
                continue
            if 'readonly' in tl or 'disabled' in tl:
                continue
            miss = [n for n in _AC_NEED if n not in tl]
            if miss:
                ln = s[:m.start()].count('\n') + 1
                print('❌ 자동완성 4종 누락 — %s:%d (%s 빠짐) → autocomplete/autocapitalize/autocorrect/spellcheck off 추가(§🎨)'
                      % (rel, ln, '·'.join(miss)))
                rc = 1
    if rc == 0:
        print('✅ 자동완성 게이트 — 편집가능 text/search 입력칸 전부 OS 자동완성 끔 4종 세트.')
    return rc


# render-text × (닫기/삭제 버튼이 SVG 아닌 문자 ×/✕ 사용) = 드리프트(§🎨 닫기=SVG X-path 단일 권장).
# 컴포넌트 컨텍스트(aria-label 닫기·삭제 류 또는 close/del/x 클래스)이고 *내용이 ×문자 하나뿐*일 때만 잡아
# 치수 텍스트('1080×1350')·JS 문자열 오탐 0. WARN(점진 통일 — thumb 등 병렬작업 파일이라 비차단).
_XSET = '×✕⨯╳✖'
_XEL_RE = re.compile(r'<(button|a|span|div|i)\b([^>]*)>\s*([' + _XSET + r'])\s*</\1>', re.I)
_XCTX_RE = re.compile(r'aria-label\s*=\s*["\'][^"\']*(닫기|닫음|삭제|취소|제거|지우)|class\s*=\s*["\'][^"\']*(tool-x|dlg-x|-x\b|close|abdel|del|btn-x)', re.I)

def check_x_char():
    warns = []
    for rel in ('viewer/index.html', 'viewer/thumb.html', 'viewer/ly.html', 'viewer/k.html', 'viewer/comp.html'):
        try:
            s = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        s2 = re.sub(r'<!--.*?-->', '', s, flags=re.S)   # 주석 제거(오탐 차단)
        for m in _XEL_RE.finditer(s2):
            if _XCTX_RE.search(m.group(2)):
                ln = s2[:m.start()].count('\n') + 1
                warns.append('%s:%d <%s> 닫기/삭제 = 문자 「%s」 → SVG X-path(§🎨 닫기=SVG 단일 권장)'
                             % (rel, ln, m.group(1), m.group(3)))
    if warns:
        print('⚠️ 닫기/삭제 × 문자 게이트(비차단) — SVG로 통일 권장:')
        for w in warns:
            print('  -', w)
    else:
        print('✅ 닫기/삭제 × 문자 게이트 — 문자 ×/✕ 닫기버튼 0(전부 SVG).')
    return 0   # WARN-only(병렬작업 파일 비차단)


def check_tokens_link():
    """공유 구조토큰 tokens.css 배선 하드게이트(§🎨 STAGE3·분신술7·260628).
    4뷰어(thumb/ly/k/comp)가 viewer/tokens.css를 <link>로 로드하는지 검증 — 미링크면 신규 컴포넌트가
    var(--r-m 등) 구조토큰을 못 써 raw로 새거나(드리프트), 옛 링크가 깨지면 침묵(check_paths가 HTML <link>
    미검증)이라 여기서 잡는다. tokens.css 파일 부재면 게이트 무력(아직 미생성=스킵)."""
    if not os.path.exists(os.path.join(ROOT, 'viewer', 'tokens.css')):
        print('⚠️ tokens.css 없음 — 구조토큰 링크 게이트 스킵'); return 0
    rc = 0
    for rel in ('viewer/thumb.html', 'viewer/ly.html', 'viewer/k.html', 'viewer/comp.html'):
        try:
            html = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        if not re.search(r'<link[^>]+href=["\']tokens\.css["\']', html):
            print('❌ 구조토큰 링크 누락 — %s가 tokens.css를 <link> 안 함 → <head>에 <link rel=stylesheet href=tokens.css> 추가(§🎨 STAGE3)' % rel)
            rc = 1
    if rc == 0:
        print('✅ 구조토큰 링크 — 4뷰어 전부 tokens.css 로드.')
    return rc


def main():
    fails = check_paths() + check_versions() + check_inject_dividers() + check_inject_markers()
    rc = 0
    if fails:
        print('❌ check_refs 실패 %d건:' % len(fails))
        for f in fails:
            print('  -', f)
        rc = 1
    else:
        print('✅ check_refs 통과 — 경로 참조 실존·파일명↔내부 버전 일치.')
    # /k 라이브러리 SSOT↔유닛 정합(통합본에서 유닛 재생성 = 현재 유닛 동일?) — 드리프트 게이트
    try:
        import build_library
        if build_library.check() != 0:
            rc = 1
    except Exception as e:
        print('⚠️ build_library check 스킵:', e)
    try:
        if check_viewer_js() != 0:   # viewer 인라인 JS 구문(하드 게이트 — SyntaxError=뷰어 전면 사망)
            rc = 1
    except Exception as e:
        print('⚠️ check_viewer_js 스킵:', e)
    try:
        if check_icon_ssot() != 0:   # 공유 아이콘 SSOT(하드 게이트 — 인라인 재선언·미로드=드리프트 부활 차단·260628)
            rc = 1
    except Exception as e:
        print('⚠️ check_icon_ssot 스킵:', e)
    try:
        import build_design_mirror   # 디자인 거울 정합: 구성도/base.css = viewer :root (하드 게이트·§🎨 ⓐ)
        if build_design_mirror.check() != 0:
            rc = 1
    except Exception as e:
        print('⚠️ 디자인 거울 check 스킵:', e)
    try:
        if check_design() != 0:   # accent_raw 차단(rc=1·운영자 ③b STAGE1) · hex/blur/죽은토큰은 내부 WARN
            rc = 1
    except Exception as e:
        print('⚠️ check_design 스킵:', e)
    try:
        if check_sens_vocab() != 0:   # 민감 통제어휘 미러 정합(하드 게이트 — 5↔7 드리프트·DRUG_RE 따로놀기 차단·260625)
            rc = 1
    except Exception as e:
        print('⚠️ 민감 통제어휘 check 스킵:', e)
    try:
        if check_curation_constants() != 0:   # 큐레이션 랭킹 상수↔§★ 문서 정합(하드 게이트 — #1135식 자기-revert·드리프트 차단·260628 감사 C8)
            rc = 1
    except Exception as e:
        print('⚠️ check_curation_constants 스킵:', e)
    try:
        if check_autocomplete() != 0:   # 평문 텍스트칸 OS 자동완성 끔 4종(하드 게이트 — 자동완성 바 재발 차단·STAGE1b·260628)
            rc = 1
    except Exception as e:
        print('⚠️ check_autocomplete 스킵:', e)
    try:
        check_x_char()   # 닫기/삭제 × 문자 → SVG 권장(WARN-only·병렬작업 파일 비차단)
    except Exception as e:
        print('⚠️ check_x_char 스킵:', e)
    try:
        if check_tokens_link() != 0:   # 공유 구조토큰 tokens.css 4뷰어 링크(하드 게이트·§🎨 STAGE3·260628)
            rc = 1
    except Exception as e:
        print('⚠️ check_tokens_link 스킵:', e)
    return rc


if __name__ == '__main__':
    sys.exit(main())
