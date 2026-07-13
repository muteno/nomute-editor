#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report_render.py — 지시 원장(TSV) → 인덱싱 20열 × N행 자기완결 HTML 기계 렌더 (실행 계약 4 · §작업표준 e-2 · 운영자 260713).

왜 존재하나(산술 정본): 20열×50행을 LLM이 자유 산문으로 쓰면 출력만 6~30분 = 10분 결론 룰과 산술 충돌(평의회 F1 실측).
∴ 표의 직렬화는 이 스크립트가 하고, LLM은 원장 TSV의 의도·해석 열만 채운다(행당 수십 토큰 = 10분 안 공존).

20열 스키마 정본(순서 = 사고 순서 · 열 1~7 의도 티어는 착수 전 원장의 복사 — 사후 역산 금지):
  1 행ID·축      : 분해 축(의도/증상/원인/수정/검증/리스크/대리결정)+일련번호
  2 지시 원문     : 운영자 문장 그대로(가공 0) — 하위 행은 `#N 상속` 허용
  3 표면 파싱     : 곧이곧대로 직역하면 뭘 하라는 건지
  4 추정 목적(왜) : 지시 뒤의 진짜 목적(§작업표준 a 3단의 1단) — 공란 = FAIL
  5 목적 근거     : 4를 뒷받침하는 인용·출처(과거 지시·작업이력·실측) — 추측이면 `추측` 딱지
  6 기각 해석·대안: 다른 뜻일 가능성 + 버린 이유 / 안 택한 해법
  7 영향 범위     : 목적대로 풀면 건드려야 할 전체(콕 집어 땜질 방지)
  8 선택 방법     : 택한 구현 방향 1줄
  9 대상          : 파일:줄·심볼(코드) / 토큰:컴포넌트(디자인) / 지시:화면(다수지시)
  10 전           : 변경 전 실측 값·상태
  11 후           : 변경 후 실측 값·상태
  12 대리 결정    : 묻지 않고 정한 것{선택지·고른 근거} — 없으면 `—`
  13 승인 4문     : 가)기틀 나)SSOT 다)비가역 라)과금 해당 여부 / `—`
  14 리스크·완화  : 품질저하 리스크 + 등급 + 완화 가드
  15 검증 방법    : 어떻게 확인했나(check_refs·read-back·헤드리스·실클릭)
  16 검증 결과    : 수치로(rc=0·N/N·px 실측) — 서술형 `됐다` 금지
  17 증빙 앵커    : diff·커밋·스크린샷·리포트 앵커
  18 롤백 1줄     : 실행 가능한 복구 명령(git revert <sha> 등)
  19 처분·커밋    : 완료/대기(사유)/STOP/분할 + 커밋·PR 번호
  20 목적 충족?   : 4열의 목적을 실제로 달성했는지 자기판정(표면만 = `미달` 강제 표기)

사용: python3 shared/report_render.py <원장.tsv> --label <라벨> [--expect-50] [--outdir docs/reports]
TSV = 탭 구분 · 1행 = 헤더(무시·자리표시) · 셀 안 개행은 `\\n` 리터럴로.
검증(FAIL = 산출 없이 exit 1): ①열 수 20 미달 ②4열(목적) 공란 행 ③2열 공란인데 상속 표기도 없는 행.
패딩 감사(경고·말미 블록에 자동 기재): 인접 행 3셀 이상 동일 = 복붙 의심 · {5,9,16}열 전부 공란 = 앵커 없는 행.
파일명 = {YYYYMMDD}_{HHMMSS}_{라벨}_v{N}.html (KST · 같은 라벨 기존 v 최대+1 = 덮어쓰기 금지 · §작업표준 f).
Q↔커밋 자동 링크(§작업표준 e-3 · 운영자 260713): 커밋 메시지에 `[Qnn]` 태그를 달면 렌더 시 git log(최근 300)를
스캔해 행ID(1열)에 같은 Qnn이 있는 행의 19열(처분·커밋)에 sha를 자동 병기 — 운영자 문단→결과물 왕복 1클릭.
한계(정직) = Q번호는 작업 블록 로컬(날짜 무관 재사용)이라 최근 로그 범위에서만 유효.
"""
import sys
import os
import re
import html
import glob
import datetime

COLS = ['행ID·축', '지시 원문', '표면 파싱', '추정 목적(왜)', '목적 근거', '기각 해석·대안',
        '영향 범위', '선택 방법', '대상', '전', '후', '대리 결정', '승인 4문', '리스크·완화',
        '검증 방법', '검증 결과', '증빙 앵커', '롤백 1줄', '처분·커밋', '목적 충족?']
INTENT_IDX = [1, 2, 3, 4, 5, 6]  # 0-based: 지시원문~영향범위 = 의도 티어


def kst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def load(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f if l.strip()]
    for i, l in enumerate(lines):
        cells = l.split('\t')
        if i == 0 and ('행ID' in cells[0] or cells[0].startswith('#')):
            continue  # 헤더/주석
        cells = (cells + [''] * 20)[:20]
        rows.append([c.replace('\\n', '\n').strip() for c in cells])
    return rows


def validate(rows):
    fails = []
    for i, r in enumerate(rows, 1):
        if not r[3]:
            fails.append('행 %d: 4열(추정 목적) 공란 — 의도 티어는 착수 전 원장의 복사여야 한다' % i)
        if not r[1]:
            fails.append('행 %d: 2열(지시 원문) 공란 — 원문 인용 또는 `#N 상속` 표기 필수' % i)
    return fails


def audit(rows):
    notes = []
    for i in range(1, len(rows)):
        same = sum(1 for a, b in zip(rows[i - 1], rows[i]) if a and a == b)
        if same >= 3:
            notes.append('행 %d↔%d: 동일 셀 %d개 — 복붙 패딩 의심' % (i, i + 1, same))
    for i, r in enumerate(rows, 1):
        if not (r[4] or r[8] or r[15]):
            notes.append('행 %d: 실측 앵커(근거/대상/검증결과) 전무 — 패딩 의심' % i)
    miss = sum(1 for r in rows if '미달' in r[19])
    notes.append('목적 미달 자기판정 행: %d' % miss)
    return notes


def git_qmap(limit=300):
    """git log에서 `[Qnn]` 태그 커밋을 수집 → {'Q01': ['sha', ...]} (실패 = 빈 dict · 비차단)."""
    import subprocess
    try:
        out = subprocess.run(['git', 'log', '-%d' % limit, '--format=%h\x01%s'],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return {}
    m = {}
    for line in out.splitlines():
        sha, _, subj = line.partition('\x01')
        for q in re.findall(r'\[Q(\d{1,3})\]', subj):
            m.setdefault('Q%02d' % int(q), []).append(sha)
    return m


def link_commits(rows):
    """행ID(1열)의 Qnn ↔ 커밋 [Qnn] 태그 자동 매칭 — 19열(처분·커밋)에 sha 병기. 매칭 행 수 반환."""
    qmap = git_qmap()
    if not qmap:
        return 0
    n = 0
    for r in rows:
        shas = []
        for q in re.findall(r'Q\d{1,3}', r[0]):
            key = 'Q%02d' % int(q[1:])
            shas += [s for s in qmap.get(key, []) if s not in shas and s not in r[18]]
        if shas:
            r[18] = (r[18] + ' · ' if r[18] else '') + 'git:' + ','.join(shas)
            n += 1
    return n


def next_ver(outdir, label):
    vs = [int(m.group(1)) for p in glob.glob(os.path.join(outdir, '*_%s_v*.html' % label))
          if (m := re.search(r'_v(\d+)\.html$', p))]
    return (max(vs) + 1) if vs else 1


def render(rows, label, ts, audit_notes, expect50):
    def esc(s):
        return html.escape(s).replace('\n', '<br>')
    kpi = {}
    for r in rows:
        d = (r[18].split('/')[0].split('·')[0].strip() or '—')[:6]
        kpi[d] = kpi.get(d, 0) + 1
    kpis = ' · '.join('%s %d' % (k, v) for k, v in sorted(kpi.items(), key=lambda x: -x[1]))
    warn50 = ('' if (not expect50 or len(rows) >= 50) else
              '<p class="warn">⚠ 행 %d &lt; 50 — 다수 지시·기틀 변경이면 원자 분해가 덜 됐다(§작업표준 e-2).</p>' % len(rows))
    body_rows = []
    for i, r in enumerate(rows, 1):
        tds = []
        for j, c in enumerate(r):
            cls = ' class="it"' if j in INTENT_IDX or j == 0 else (' class="ok"' if j == 19 and '충족' in c else '')
            tds.append('<td%s>%s</td>' % (cls, esc(c)))
        body_rows.append('<tr><td class="n">%d</td>%s</tr>' % (i, ''.join(tds)))
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark">
<title>%(label)s — 20열 원장 렌더 v</title><style>
:root{color-scheme:dark}*{box-sizing:border-box;margin:0}
body{background:#0b0d0e;color:#eef7f0;font:14px/1.55 "Apple SD Gothic Neo","Pretendard","Noto Sans KR","Malgun Gothic",system-ui,sans-serif;padding:18px}
h1{font-size:19px;margin-bottom:4px}.sub{color:#9aa39d;font-size:12px;margin-bottom:14px}
.kpi{display:inline-block;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:11px;padding:8px 12px;font-size:12px;margin:0 8px 14px 0;font-variant-numeric:tabular-nums}
.tbl-wrap{overflow-x:auto;border:1px solid rgba(255,255,255,.1);border-radius:11px}
table{border-collapse:collapse;min-width:2400px;font-size:12px}
th{position:sticky;top:0;background:#14171a;color:#9aa39d;font-weight:700;text-align:left;padding:8px 9px;border-bottom:1px solid rgba(255,255,255,.14);white-space:nowrap}
td{padding:7px 9px;border-bottom:1px solid rgba(255,255,255,.06);vertical-align:top;max-width:340px}
td.n{color:#9aa39d;font-variant-numeric:tabular-nums}
td.it{background:rgba(0,238,210,.035)}
tr:hover td{background:rgba(255,255,255,.03)}
.warn{color:#FFE13D;font-size:12px;margin:10px 0}
.audit{margin-top:16px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:11px;padding:12px;font-size:12px}
.audit h2{font-size:13px;margin-bottom:6px;color:#9aa39d}
.foot{color:#9aa39d;font-size:11px;margin-top:14px}
</style></head><body>
<h1>%(label)s — 지시 원장 20열 렌더</h1>
<p class="sub">%(ts)s KST · 총 %(n)d행 · 열 1~7 = 의도 티어(민트 배경 = 착수 전 원장 복사분) · 기계 렌더 = shared/report_render.py(자유 산문 재생성 금지)</p>
<span class="kpi">처분: %(kpis)s</span>%(warn50)s
<div class="tbl-wrap"><table><thead><tr><th>#</th>%(head)s</tr></thead><tbody>
%(rows)s
</tbody></table></div>
<div class="audit"><h2>패딩·정합 자기감사(기계)</h2>%(audit)s</div>
<p class="foot">일회성 스냅샷(viewer 동기화 의무 없음 · check_refs 비대상) · 정본 스키마 = shared/report_render.py 헤더 · 실행 계약 4</p>
</body></html>''' % {
        'label': html.escape(label), 'ts': ts, 'n': len(rows), 'kpis': kpis or '—',
        'warn50': warn50,
        'head': ''.join('<th>%s</th>' % html.escape(c) for c in COLS),
        'rows': '\n'.join(body_rows),
        'audit': '<br>'.join(html.escape(a) for a in audit_notes) or '이상 없음',
    }


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    tsv = argv[1]
    label = '보고서'
    outdir = 'docs/reports'
    expect50 = '--expect-50' in argv
    if '--label' in argv:
        label = argv[argv.index('--label') + 1]
    if '--outdir' in argv:
        outdir = argv[argv.index('--outdir') + 1]
    rows = load(tsv)
    if not rows:
        print('❌ 원장 비어 있음: %s' % tsv)
        return 1
    fails = validate(rows)
    if fails:
        print('❌ 렌더 FAIL — 의도 티어 미기입(착수 게이트 위반 · 실행 계약 2):')
        for f in fails[:20]:
            print('  -', f)
        return 1
    linked = link_commits(rows)
    now = kst_now()
    ver = next_ver(outdir, label)
    name = '%s_%s_%s_v%d.html' % (now.strftime('%Y%m%d'), now.strftime('%H%M%S'), label, ver)
    path = os.path.join(outdir, name)
    notes = audit(rows) + ['Q태그 커밋 자동 매칭: %d행 (§작업표준 e-3 [Qnn] 규약)' % linked]
    doc = render(rows, label, now.strftime('%Y-%m-%d %H:%M:%S'), notes, expect50)
    os.makedirs(outdir, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(doc)
    print('✅ 렌더 완료: %s (%d행 × 20열)' % (path, len(rows)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
