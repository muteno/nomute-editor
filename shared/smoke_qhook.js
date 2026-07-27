#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_qhook.js — 커밋 훅 Q경합 체인 상비 스모크 (운영자 260727 한 수 채택 Q912 후속)
//
// 왜 = 260727 하루에 이 체인(경합 감지 → --fix-qnum 재부여 → 머지 커밋 보류 → 스냅샷 신선도 고지)을
//   네 번 고쳤는데, 검증은 매번 손이었다(임시 브랜치 + 임계값 임시 하향). 그 과정에서 픽스처를 두 번 틀렸다
//   (옛 커밋 기반 → 훅 파일 머지 충돌 / 임계 복원을 실증 커밋 기준으로 해 '신선' 케이스가 무효).
//   손 실증은 이렇게 조용히 틀린다 → 기계로 옮긴다.
//
// 무엇을 보나(2부):
//   [A 계약] 훅이 grep으로 잡는 **문구**가 진짜 check_refs.py 안에 살아있나(문구가 바뀌면 훅이 조용히 무력화된다
//            = 이 체인의 유일한 결합점이자 최대 사각). 정규식 2종: '원장 Q번호 신규 중복' · '스냅샷이 N분 전'.
//   [B 분기] **스크래치 레포**(임시 디렉터리 · 진짜 레포 무접촉)에 훅 2개를 복사하고 check_refs 스텁을 놓아
//            훅의 분기·종료코드·고지를 6경로로 실행 판정한다.
//
// 스코프 정직 고지: [B]는 **훅의 분기 계약**만 본다 — check_refs 본체의 판정(중복 계수·박제 무접촉·재부여 번호)은
//   그 파이썬 게이트 자신의 몫이라 여기서 재현하지 않는다(스텁). 대신 [A]가 둘 사이의 문구 계약을 못 박아,
//   "스텁은 통과하는데 실물은 깨진" 드리프트를 차단한다.
//
// 원커맨드:  node shared/smoke_qhook.js      (종료코드 0 = 전부 PASS)
// 네트워크·크로미엄 불필요(가장 가벼운 상비 스모크) · 진짜 레포의 원장·브랜치·인덱스 무접촉.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync, spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const results = [];
const t = (name, cond, detail) => results.push({ name, ok: !!cond, detail: detail || '' });

// ── [A 계약] 훅 ↔ check_refs 문구 결합점 ────────────────────────────────────────
const hook = fs.readFileSync(path.join(ROOT, '.githooks', 'pre-commit'), 'utf8');
const py = fs.readFileSync(path.join(ROOT, 'shared', 'check_refs.py'), 'utf8');
const mergeHook = fs.readFileSync(path.join(ROOT, '.githooks', 'pre-merge-commit'), 'utf8');

t('A1 훅이 잡는 경합 문구가 check_refs에 실존', hook.includes('원장 Q번호 신규 중복') && py.includes('원장 Q번호 신규 중복'),
  '문구 = 원장 Q번호 신규 중복');
// 훅 정규식 '스냅샷이 [0-9]*분 전' ↔ 파이썬 포맷 '스냅샷이 %d분 전'
t('A2 훅이 잡는 신선도 문구가 check_refs에 실존', /스냅샷이 \[0-9\]\*분 전/.test(hook) && /스냅샷이 %d분 전/.test(py),
  '훅 grep ↔ py 포맷 쌍');
t('A3 머지 훅이 pre-commit에 --merge 전달', /pre-commit" --merge/.test(mergeHook), 'exec … --merge');
t('A4 보류 분기·고지가 두 종료 경로 모두에 배선', (hook.match(/stale_tail\s*$/gm) || []).length >= 2 && hook.includes('⏸ 머지 커밋 보류'),
  'stale_tail 호출 ' + ((hook.match(/^\s*stale_tail\s*$/gm) || []).length) + '회');

// ── [B 분기] 스크래치 레포에서 훅 6경로 실행 ────────────────────────────────────
const STUB = `#!/usr/bin/env python3
# check_refs 스텁 — 훅 분기 검증 전용(진짜 판정 아님). 환경변수로 상황을 만든다.
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, 'docs', '요구사항_큐.md')
FLAG = os.path.join(ROOT, '.qdup')            # 존재 = 원장 Q번호 신규 중복 상태
if '--fix-qnum' in sys.argv:
    if os.environ.get('QSMOKE_STALE') == '1':
        print('⚠️ --fix-qnum 주의 — origin/main 스냅샷이 42분 전 것이다. 그 사이 남이 민 행은 여기 없다.')
        print('   → git fetch origin main 먼저 하고 다시 돌려라.')
    if os.environ.get('QSMOKE_FIXCHANGES', '1') == '1':
        with open(LEDGER, 'a', encoding='utf-8') as f:
            f.write('- ✅ Q999(재부여됨)· 스텁\\n')
    if os.path.exists(FLAG):
        os.remove(FLAG)                        # 재부여로 경합 해소
    print('🔧 --fix-qnum 재부여 Q1 → Q999 (origin/main에 없는 = 이 브랜치 신규 행만)')
    sys.exit(0)
if os.environ.get('QSMOKE_OTHERFAIL') == '1':
    print('❌ 경로 참조 깨짐(Q경합이 아닌 다른 게이트 실패)')
    sys.exit(1)
if os.path.exists(FLAG):
    print('❌ 원장 Q번호 신규 중복(동시 세션 번호 경합): Q1 ×2(면책 1)')
    sys.exit(1)
print('✅ 원장 Q번호 유일성 — 신규 중복 0')
sys.exit(0)
`;

const git = (cwd, args) => execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'nm-qhook-'));
let fail = 0;
try {
  fs.mkdirSync(path.join(tmp, '.githooks'), { recursive: true });
  fs.mkdirSync(path.join(tmp, 'shared'), { recursive: true });
  fs.mkdirSync(path.join(tmp, 'docs'), { recursive: true });
  for (const h of ['pre-commit', 'pre-merge-commit']) {           // 훅 = 진짜 파일 그대로(사본 아님 = 드리프트 0)
    fs.copyFileSync(path.join(ROOT, '.githooks', h), path.join(tmp, '.githooks', h));
    fs.chmodSync(path.join(tmp, '.githooks', h), 0o755);
  }
  fs.writeFileSync(path.join(tmp, 'shared', 'check_refs.py'), STUB);
  fs.writeFileSync(path.join(tmp, 'docs', '요구사항_큐.md'), '- ✅ Q1(스텁)· 기준 행\n');
  git(tmp, ['init', '-q', '-b', 'main']);
  git(tmp, ['config', 'user.email', 'smoke@nomute']);
  git(tmp, ['config', 'user.name', 'smoke']);
  git(tmp, ['config', 'core.hooksPath', '.githooks']);
  git(tmp, ['add', '-A']);
  git(tmp, ['commit', '-q', '--no-verify', '-m', 'base']);

  // 훅 직접 실행(= git이 부르는 것과 같은 진입점) · 상황 = 환경변수 + .qdup 플래그
  const run = (opts) => {
    const flag = path.join(tmp, '.qdup');
    if (opts.dup) fs.writeFileSync(flag, '');
    else if (fs.existsSync(flag)) fs.unlinkSync(flag);
    const r = spawnSync('sh', [path.join(tmp, '.githooks', opts.merge ? 'pre-merge-commit' : 'pre-commit')], {
      cwd: tmp, encoding: 'utf8',
      env: Object.assign({}, process.env, {
        QSMOKE_STALE: opts.stale ? '1' : '0',
        QSMOKE_OTHERFAIL: opts.otherFail ? '1' : '0',
        QSMOKE_FIXCHANGES: opts.fixChanges === false ? '0' : '1',
      }),
    });
    const out = (r.stdout || '') + (r.stderr || '');
    const lines = out.trim().split('\n');
    return { rc: r.status, out, last: lines[lines.length - 1] || '' };
  };
  const TAIL = '마지막 고지';

  const b1 = run({ dup: false });
  t('B1 무경합 = 즉시 통과(자동수정·고지 0)', b1.rc === 0 && !b1.out.includes('🔧') && !b1.out.includes(TAIL), 'rc=' + b1.rc);

  const b2 = run({ dup: false, otherFail: true });
  t('B2 Q경합 아닌 실패 = 자동수정 미발동·즉시 차단', b2.rc === 1 && !b2.out.includes('🔧'), 'rc=' + b2.rc);

  const b3 = run({ dup: true, stale: false });
  t('B3 경합+신선 = 재부여 후 통과·꼬리 없음', b3.rc === 0 && b3.out.includes('🔧') && !b3.out.includes(TAIL), 'rc=' + b3.rc);

  const b4 = run({ dup: true, stale: true });
  t('B4 경합+낡음 = 통과 + 꼬리가 **마지막 줄**', b4.rc === 0 && b4.last.includes(TAIL), 'rc=' + b4.rc + ' · last=' + b4.last.slice(0, 40));

  const b5 = run({ dup: true, stale: true, merge: true });
  t('B5 머지+재부여 발생 = 보류(rc=1) + 꼬리 마지막 줄',
    b5.rc === 1 && b5.out.includes('⏸ 머지 커밋 보류') && b5.last.includes(TAIL), 'rc=' + b5.rc);

  const b6 = run({ dup: true, stale: false, merge: true, fixChanges: false });
  t('B6 머지지만 원장 무변경 = 보류 안 함(평시 머지 무영향)', b6.rc === 0 && !b6.out.includes('⏸'), 'rc=' + b6.rc);
} catch (e) {
  t('B0 스크래치 레포 구동', false, String(e.message).slice(0, 160));
} finally {
  try { fs.rmSync(tmp, { recursive: true, force: true }); } catch (_) {}
}

for (const r of results) {
  if (!r.ok) fail++;
  console.log((r.ok ? 'PASS' : 'FAIL') + ' | ' + r.name + (r.detail ? ' | ' + r.detail : ''));
}
console.log('── smoke_qhook ' + (fail ? 'FAIL ' + fail + '건' : results.length + '/' + results.length + ' 전부 PASS') + ' (스크래치 정리됨 · 진짜 레포 무접촉)');
process.exit(fail ? 1 : 0);
