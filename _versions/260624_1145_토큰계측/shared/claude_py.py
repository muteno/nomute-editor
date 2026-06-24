"""claude_py — 파이썬 claude -p 호출 + 계정 사용량 한도(쿼터) 시 대체 계정 자동 전환(account failover).

bash 쪽 SSOT(shared/claude_transient.sh: is_quota/claude_failover)의 파이썬판.
breaking_judge.py·gate_judge.py 공용 단일 출처 = 폴오버 로직 드리프트 차단(260622).

run_claude(args, prompt): subprocess.run 으로 claude -p 실행. 출력이 쿼터 한도면
CLAUDE_CODE_OAUTH_TOKEN_ALT(활성의 반대 계정)로 1회 전환 후 재시도.
  - 인증죽음(401)·5xx 과부하는 전환 안 함(전환 무의미 — bash is_quota 와 동일 경계).
  - 1회만 스왑(둘 다 한도면 더 못 피함 → 호출부가 기존대로 다음 런 재시도).
"""
import os
import re
import subprocess

# 쿼터·레이트리밋(429)만 — 5xx 과부하·인증죽음 제외(claude_transient.sh is_quota 와 동일 정규식)
_QUOTA = re.compile(r'usage limit|rate.?limit|rate_limit|429|too many requests|quota|limit reached|resets? (at|in)', re.I)
_swapped = False   # 프로세스 1회만 전환


def is_quota(text):
    head = "\n".join((text or "").splitlines()[:8])   # 앞 8줄만(본문 인용 오탐 억제)
    return bool(_QUOTA.search(head))


def run_claude(args, prompt, timeout=300):
    """claude -p 실행 → (CompletedProcess|None, returncode, stderr). 쿼터면 대체 계정 1회 전환·재시도."""
    global _swapped
    p = None
    for _ in range(2):
        try:
            p = subprocess.run(args, input=prompt, capture_output=True, text=True, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            return None, 1, f"{type(e).__name__}: {e}"
        if p.returncode == 0 and (p.stdout or "").strip():
            return p, p.returncode, p.stderr
        alt = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN_ALT")
        if alt and not _swapped and is_quota((p.stdout or "") + (p.stderr or "")):
            os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = alt
            _swapped = True
            print("  🔄 계정 사용량 한도 감지 — 대체 계정 토큰으로 전환 후 재시도(account failover)", flush=True)
            continue
        return p, p.returncode, p.stderr
    return p, p.returncode, (p.stderr if p else "")
