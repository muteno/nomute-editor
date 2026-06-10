#!/usr/bin/env python3
"""노뮤트 — 세션 사고(thinking) 판독기 (읽기 전용).

"의도 파악이 왜 오래 걸리나"를 느낌이 아니라 기록으로 판독한다:
세션 대화로그(jsonl)에서 턴별 사고 글자수·소요 시간·도구 호출을 뽑아 리포트.
모델마다 사고 스타일·예산이 달라서, 리포트에 모델 ID를 박아 모델 간 비교도 된다.

사용 (작업 세션 끝에 그 세션 안에서):
  python3 shared/profile_session.py            # 요약 리포트(턴별 표 + 사고 많은 턴 미리보기)
  python3 shared/profile_session.py --full     # + 사고 전문을 /mnt/user-data/outputs/사고기록_*.md 로 저장
  python3 shared/profile_session.py <jsonl경로> # 특정 세션 파일 지정(기본 = 최신 세션)

읽는 것: ~/.claude/projects/**/*.jsonl (attach.py와 동일 위치). 사고가 로그에 안 남는
모델/설정이면 시간 갭만으로 리포트하고 그 사실을 명시한다.
"""

import glob
import json
import os
import sys
from datetime import datetime


def latest_jsonl():
    cands = glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl'))
    if not cands:
        return None
    return max(cands, key=os.path.getmtime)


def ts(s):
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None


def load_events(path):
    evs = []
    for line in open(path, encoding='utf-8'):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get('isSidechain'):
            continue  # 서브에이전트 흐름은 본 타임라인에서 제외
        t = o.get('type')
        when = ts(o.get('timestamp', '')) if o.get('timestamp') else None
        if t == 'user':
            m = o.get('message') or {}
            c = m.get('content')
            blocks = c if isinstance(c, list) else []
            is_tool = any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in blocks)
            if is_tool:
                evs.append({'kind': 'tool_result', 'when': when})
            else:
                if isinstance(c, str):
                    text = c
                else:
                    text = ' '.join(b.get('text', '') for b in blocks
                                    if isinstance(b, dict) and b.get('type') == 'text')
                evs.append({'kind': 'human', 'when': when, 'text': text.strip()})
        elif t == 'assistant':
            m = o.get('message') or {}
            think, out, tools = [], 0, []
            for b in (m.get('content') or []):
                if not isinstance(b, dict):
                    continue
                bt = b.get('type')
                if bt == 'thinking':
                    think.append(b.get('thinking', ''))
                elif bt == 'text':
                    out += len(b.get('text', ''))
                elif bt == 'tool_use':
                    tools.append(b.get('name', '?'))
            n_blocks = sum(1 for b in (m.get('content') or [])
                           if isinstance(b, dict) and b.get('type') == 'thinking')
            evs.append({'kind': 'assistant', 'when': when, 'model': m.get('model', '?'),
                        'think': think, 'think_blocks': n_blocks, 'out_chars': out, 'tools': tools})
    return evs


def build_turns(evs):
    turns, cur = [], None
    for e in evs:
        if e['kind'] == 'human':
            if cur:
                turns.append(cur)
            cur = {'start': e['when'], 'input': (e.get('text') or '')[:60] or '(빈 입력)',
                   'end': e['when'], 'think_chars': 0, 'think_blocks': 0, 'think_texts': [],
                   'out_chars': 0, 'tools': [], 'msgs': 0, 'max_gap': 0.0, 'models': set()}
            prev = e['when']
        elif cur and e['kind'] in ('assistant', 'tool_result'):
            if e['when']:
                if cur['end'] and e['when'] > cur['end']:
                    cur['end'] = e['when']
                if prev and e['when'] > prev:
                    gap = (e['when'] - prev).total_seconds()
                    # 사고+생성 갭은 assistant 이벤트 직전 갭으로 잡힘
                    if e['kind'] == 'assistant' and gap > cur['max_gap']:
                        cur['max_gap'] = gap
                prev = e['when']
            if e['kind'] == 'assistant':
                cur['msgs'] += 1
                cur['models'].add(e['model'])
                cur['out_chars'] += e['out_chars']
                cur['tools'] += e['tools']
                cur['think_blocks'] += e.get('think_blocks', 0)
                for th in e['think']:
                    cur['think_chars'] += len(th)
                    if th.strip():
                        cur['think_texts'].append(th)
    if cur:
        turns.append(cur)
    return turns


def fmt_dur(t):
    return '%ds' % round(t) if t < 120 else '%dm%02ds' % (int(t // 60), round(t % 60))


def main():
    args = [a for a in sys.argv[1:]]
    full = '--full' in args
    paths = [a for a in args if not a.startswith('--')]
    path = paths[0] if paths else latest_jsonl()
    if not path or not os.path.exists(path):
        print('❌ 세션 jsonl을 못 찾음 (~/.claude/projects/*/*.jsonl) — 이 환경은 대화로그가 안 남는 접속일 수 있음.')
        return 1

    evs = load_events(path)
    turns = build_turns(evs)
    if not turns:
        print('❌ 판독할 턴이 없음:', path)
        return 1

    models = sorted({m for t in turns for m in t['models']})
    total_think = sum(t['think_chars'] for t in turns)
    total_blocks = sum(t['think_blocks'] for t in turns)
    print('🧠 세션 사고 판독 — %s' % os.path.basename(path))
    print('모델: %s / 턴 %d개 / 총 사고 %s자 (블록 %d개)' % (
        ', '.join(models) or '?', len(turns), format(total_think, ','), total_blocks))
    if total_think == 0 and total_blocks > 0:
        print('⚠️ 이 모델/설정은 사고 내용을 로그에 안 남김(서명만 기록) — 사고량은 "최장갭"(사고+생성 구간)으로 판독:')
        print('   최장갭이 큰데 출력자수가 작은 턴 = 보이지 않는 사고가 시간을 먹은 턴.')
    elif total_blocks == 0:
        print('⚠️ 사고 블록 자체가 없음(사고 꺼짐/미기록 설정) — 시간 갭으로만 판독.')
    print()
    print('턴 | 입력(앞부분) | 소요 | 사고자수 | 출력자수 | 도구 | 최장갭')
    print('---|---|---|---|---|---|---')
    for i, t in enumerate(turns, 1):
        dur = (t['end'] - t['start']).total_seconds() if t['start'] and t['end'] else 0
        print('%d | %s | %s | %s | %s | %d | %s' % (
            i, t['input'].replace('|', '/').replace('\n', ' ')[:40], fmt_dur(dur),
            format(t['think_chars'], ','), format(t['out_chars'], ','),
            len(t['tools']), fmt_dur(t['max_gap'])))
    print()

    heavy = sorted(range(len(turns)), key=lambda i: turns[i]['think_chars'], reverse=True)[:3]
    heavy = [i for i in heavy if turns[i]['think_chars'] > 0]
    if heavy:
        print('🔎 사고 많은 턴 미리보기 (각 첫 사고 블록 앞 200자):')
        for i in heavy:
            t = turns[i]
            head = t['think_texts'][0].strip().replace('\n', ' ')[:200] if t['think_texts'] else ''
            print('  · 턴 %d (%s자, 입력 "%s"): %s…' % (i + 1, format(t['think_chars'], ','), t['input'][:24], head))
        print()

    if full:
        outdir = '/mnt/user-data/outputs'
        os.makedirs(outdir, exist_ok=True)
        out = os.path.join(outdir, '사고기록_%s.md' % datetime.now().strftime('%y%m%d_%H%M'))
        with open(out, 'w', encoding='utf-8') as f:
            f.write('# 세션 사고 전문 — %s\n모델: %s\n\n' % (os.path.basename(path), ', '.join(models)))
            for i, t in enumerate(turns, 1):
                f.write('## 턴 %d — 입력: %s\n(사고 %s자 · 도구 %d회)\n\n' % (
                    i, t['input'], format(t['think_chars'], ','), len(t['tools'])))
                for j, th in enumerate(t['think_texts'], 1):
                    f.write('### 사고 %d\n%s\n\n' % (j, th.strip()))
        print('📄 사고 전문 저장: %s (이 파일을 에디터에게 보내면 판독해준다)' % out)
    else:
        print('(사고 전문이 필요하면: python3 shared/profile_session.py --full)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
