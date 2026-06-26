"""claude_py — 파이썬 claude -p 호출 + 계정 사용량 한도(쿼터) 시 대체 계정 자동 전환(account failover)
              + 토큰 사용량 계측(metrics shard · shared/claude_meter.sh 파이썬판).

bash 쪽 SSOT(shared/claude_transient.sh: is_quota/claude_failover · shared/claude_meter.sh: 토큰 계측)의 파이썬판.
breaking_judge.py·gate_judge.py 공용 단일 출처 = 폴오버·계측 로직 드리프트 차단(260622·260624).

run_claude(args, prompt, source=None): subprocess.run 으로 claude -p 실행. 출력이 쿼터 한도면
대체 계정 토큰으로 1단계씩 전환(서브1=CLAUDE_CODE_OAUTH_TOKEN_ALT → 서브2=CLAUDE_CODE_OAUTH_TOKEN_ALT2 · 3계정 체인).
  - 인증죽음(401)·5xx 과부하는 전환 안 함(전환 무의미 — bash is_quota 와 동일 경계).
  - 최대 2회 스왑(서브1→서브2 · 셋 다 한도면 호출부가 기존대로 다음 런 재시도). ALT2 없으면 1회로 폴백(하위호환).
  - source 가 주어지면(예: "gate"·"breaking") --output-format json 으로 돌려 .result(=원래 텍스트)만
    p.stdout 으로 돌려주고, .usage 토큰을 metrics/usage/<run>-<job>-<attempt>.jsonl 에 1줄 기록.
    호출부는 p.stdout 을 예전과 똑같이 받는다(파싱 무변경). METER_OFF=1 또는 파싱 실패면 옛 동작으로 폴백.
"""
import datetime
import json
import os
import re
import subprocess
from pathlib import Path

# 쿼터·레이트리밋(429)만 — 5xx 과부하·인증죽음 제외(claude_transient.sh is_quota 와 동일 정규식)
_QUOTA = re.compile(r'usage limit|rate.?limit|rate_limit|429|too many requests|quota|limit reached|resets? (at|in)', re.I)
_swap_n = 0   # 프로세스 전환 횟수(0→1→2 · 3계정 체인: 서브1=ALT, 서브2=ALT2)
_KST = datetime.timezone(datetime.timedelta(hours=9))   # §📐 시각=KST


def is_quota(text):
    head = "\n".join((text or "").splitlines()[:8])   # 앞 8줄만(본문 인용 오탐 억제)
    return bool(_QUOTA.search(head))


def _arg_val(args, flag):
    """args 리스트에서 `--flag value` 의 value 추출(없으면 "")."""
    try:
        return args[args.index(flag) + 1]
    except (ValueError, IndexError):
        return ""


def _meter_record(source, args, obj, rc):
    """claude -p --output-format json 결과 obj 에서 토큰·비용을 뽑아 잡 단위 shard 에 1줄 append.
    실패는 조용히 삼킨다(분석물·판정 유실 0). bash claude_meter.sh 와 동일 스키마."""
    try:
        root = Path(__file__).resolve().parents[1]   # shared/ → repo root (CWD 무관)
        d = root / "metrics" / "usage"
        d.mkdir(parents=True, exist_ok=True)
        shard = d / f"{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.environ.get('GITHUB_JOB', 'local')}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}.jsonl"
        usage = obj.get("usage") or {}
        rec = {
            "ts": datetime.datetime.now(_KST).isoformat(timespec="seconds"),
            "src": source,
            "ref": os.environ.get("METER_REF", ""),
            "model": _arg_val(args, "--model"),
            "effort": _arg_val(args, "--effort"),
            "in": usage.get("input_tokens") or usage.get("inputTokens") or 0,
            "out": usage.get("output_tokens") or usage.get("outputTokens") or 0,
            "cache_r": usage.get("cache_read_input_tokens") or 0,
            "cache_w": usage.get("cache_creation_input_tokens") or 0,
            "cost": obj.get("total_cost_usd") or obj.get("cost_usd") or 0,
            "turns": obj.get("num_turns") or 0,
            "dur_ms": obj.get("duration_ms") or 0,
            "run": os.environ.get("GITHUB_RUN_ID", ""),
            "job": os.environ.get("GITHUB_JOB", "local"),
            "wf": os.environ.get("GITHUB_WORKFLOW", "local"),
            "rc": rc,
        }
        with open(shard, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass   # 계측 실패가 본 파이프라인을 절대 안 깨게


def _parse_metered(stdout):
    """--output-format json stdout → (텍스트, obj|None). 파싱 실패면 (raw, None) = 옛 동작 폴백."""
    try:
        obj = json.loads(stdout)
        if isinstance(obj, dict) and isinstance(obj.get("result"), str):
            return obj["result"], obj
    except Exception:  # noqa: BLE001
        pass
    return stdout, None


def run_claude(args, prompt, timeout=300, source=None):
    """claude -p 실행 → (CompletedProcess|None, returncode, stderr). 쿼터면 대체 계정 1단계씩 전환·재시도(서브1→서브2).
    source 지정 시 토큰 계측(--output-format json · metrics shard). p.stdout 은 항상 *텍스트*(=.result)."""
    global _swap_n
    metered = bool(source) and os.environ.get("METER_OFF", "0") != "1"
    if metered and "--output-format" not in args:
        try:   # '-p' 바로 뒤에 --output-format json 삽입(없으면 끝에 추가)
            i = args.index("-p")
            args = args[:i + 1] + ["--output-format", "json"] + args[i + 1:]
        except ValueError:
            args = args + ["--output-format", "json"]
    p = None
    for _ in range(3):   # 초기 + 서브1 + 서브2 (3계정 체인 = 최대 2회 폴오버)
        try:
            p = subprocess.run(args, input=prompt, capture_output=True, text=True, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            return None, 1, f"{type(e).__name__}: {e}"
        text, obj = _parse_metered(p.stdout) if metered else (p.stdout, None)
        if p.returncode == 0 and (text or "").strip():
            if metered and obj is not None:
                _meter_record(source, args, obj, p.returncode)
            p.stdout = text   # 호출부는 텍스트(.result)를 받는다(파싱 무변경)
            return p, p.returncode, p.stderr
        # 쿼터 한도면 다음 대체 계정으로 1단계 전환(서브1=ALT → 서브2=ALT2 · 체인 소진 시 폴오버 없음)
        if is_quota((text or "") + (p.stderr or "")):
            nxt = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN_ALT") if _swap_n == 0 else (
                os.environ.get("CLAUDE_CODE_OAUTH_TOKEN_ALT2") if _swap_n == 1 else None)
            if nxt:
                os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = nxt
                _swap_n += 1
                print("  🔄 계정 사용량 한도 — 서브%d 계정으로 전환 후 재시도(account failover %d/2)" % (_swap_n, _swap_n), flush=True)
                continue
        if metered:
            p.stdout = text   # 실패 경로도 텍스트(raw)로 — 호출부 실패판정 옛날과 동일
        return p, p.returncode, p.stderr
    if metered and p is not None:
        p.stdout, _ = _parse_metered(p.stdout)
    return p, p.returncode, (p.stderr if p else "")
