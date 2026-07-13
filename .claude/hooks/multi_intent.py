#!/usr/bin/env python3
"""multi_intent.py — T0 클럭 주입 + 다중 지시 기계 캡처 (UserPromptSubmit · 실행 계약 1·2 · 운영자 260713).

두 가지 일:
1) 매 프롬프트에 수신 시각(T0)·데드라인(+10분)을 주입 — 모델은 벽시계가 없어 경과를 못 느낀다(실행 계약 1의 기계 다리).
2) 다중 지시(명령 어미 2개+ / 나열 마커 2개+ / 명령형 3줄+)를 감지하면 원문 세그먼트를
   `docs/요구사항_큐.md`에 ⬜로 기계 append — 모델 협조 없이 원문이 파일에 박힘 = 누락 물리 차단(§작업표준 e-1).

설계 계약(§검증·O1/O9 평의회 수렴):
- exit 2(프롬프트 차단) 절대 금지 — 항상 exit 0 + stdout 주입만(오차단 0 철학 = bg_gate 계승).
- 오탐 비용 최소화: 감지돼도 비용 = 큐에 ⬜ 몇 줄 + 주입 1문단뿐(모델이 즉시 ✅로 닫으면 끝).
- 미탐이 진짜 손해(운영자 통증 = 30% 누락)라 임계는 공격적, 차단은 없음.
- 명칭 = `지시 복창`(작업이력 원장과 혼동 방지 · O9).
"""
import json
import sys
import os
import re
import datetime


def kst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


# 한국어 반말 명령 어미(문장 경계) — 운영자 말투 실측 기반
CMD_END = re.compile(
    r'(해줘|해라|하라|해봐|해주고|해주면|하셈|하자|바꿔|고쳐|만들어|만들고|추가해|삭제해|지워|없애|'
    r'빼|넣어|수정해|반영해|확인해|정리해|옮겨|줄여|늘려|통일해|맞춰|살펴|검토해|점검해|처리해|적용해|'
    r'알려줘|알려주고|보여줘|보여주고|가져와|찾아|줘|박아|올려|내려|열어|닫아|묶어|나눠|소환해|돌려|테스트해)'
    r'\s*[.!?~…)\]]*\s*$', re.M)
ENUM = re.compile(r'(?m)^\s*(\d+[.)]|[①-⑳]|[-*·•])\s+')
JOIN = re.compile(r'(그리고|그담에?|그\s*다음|또한?|추가로|아울러|이어서)\b')


def detect(prompt):
    # 감지는 명령 어미·나열 마커로, 캡처는 문단 단위(운영자 정정 260713 — 문장 쪼개기 = 맥락 파편화)
    text = re.sub(r'```.*?```', '', prompt, flags=re.S)
    text = re.sub(r'^\s*>.*$', '', text, flags=re.M)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cmd_lines = [ln for ln in lines if CMD_END.search(ln)]
    cmd_hits = len(CMD_END.findall(text))
    enum_hits = len(ENUM.findall(text))
    multi = (cmd_hits >= 2) or (enum_hits >= 2 and cmd_hits >= 1) or (len(cmd_lines) >= 3)
    paras = [re.sub(r'\s*\n\s*', ' ⏎ ', p.strip()) for p in re.split(r'\n\s*\n', text) if p.strip()]
    return multi, paras


def append_ledger(root, sid, segs, stamp):
    path = os.path.join(root, 'docs', '요구사항_큐.md')
    if not os.path.exists(path):
        return False
    rows = '\n'.join('- ⬜ Q%02d· %s' % (i + 1, s[:500]) for i, s in enumerate(segs[:12]))
    block = ('\n### 🧵 [%s %s] 훅 기계 캡처(문단 단위) — 원문 손대지 말고 [해석]·[계획] 붙여라 · '
             '보고 말미 Q&A 원장([Q.NN]→[A.NN])의 Q 재료(§작업표준 e-3)\n%s\n') % (sid, stamp, rows)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(block)
    return True


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    prompt = (data.get('prompt') or '')
    sid = (data.get('session_id') or 'nosid')[:8]
    root = os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd()
    now = kst_now()
    t0 = now.strftime('%H:%M:%S')
    dl = (now + datetime.timedelta(minutes=10)).strftime('%H:%M:%S')
    out = ['[⏱ T0=%s KST · 데드라인(+10분)=%s — 실행 계약 1 · 연속 교정이면 최초 T0 유지]' % (t0, dl)]

    try:
        if len(prompt) >= 40 and not prompt.rstrip().endswith('?'):
            multi, segs = detect(prompt)
            if multi:
                captured = append_ledger(root, sid, segs, now.strftime('%m/%d %H:%M'))
                where = 'docs/요구사항_큐.md 말미에 Q번호로 기계 등재됨(⬜)' if captured else '큐 파일 부재 — 직접 등재하라'
                out.append(
                    '[📒 지시 원장 — 문단 %d개 감지 · 실행 계약 2] 원문은 %s. '
                    '착수 전 각 ⬜에 [해석](왜 시켰나·표면 아님 목적)·[계획]을 채우고, 종료 시 ⬜→✅ 1:1 매트릭스 '
                    '+ 보고 말미 Q&A 원장([Q.NN] 원문→[A.NN] 모델명·노력도·시각·→결론 = §작업표준 e-3·전 문단 커버). '
                    '하나도 흘리지 마라 — 못 끝낸 건 ⬜로 남긴다("다음에" 금지).'
                    % (len(segs), where))
    except Exception:
        pass  # 캡처 실패 = 무의견(클럭 주입은 유지)

    print('\n'.join(out))
    sys.exit(0)


if __name__ == '__main__':
    main()
