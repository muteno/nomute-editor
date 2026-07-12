#!/usr/bin/env python3
"""account_failover.py — 활성 계정(vars.ACTIVE_ACCOUNT) 자동 승격(sticky failover).

문제(운영자 실증): 런타임 폴오버(shared/claude_transient.sh·claude_py.py)는 *프로세스 안에서만*
살아서, 활성 계정이 주간 한도로 며칠 막혀 있어도 매 워크플로 런이 그 죽은 계정부터 다시 시작한다
→ 매 런·매 호출이 쿼터 감지 왕복 1회를 낭비(로그 노이즈·배치 첫 항목 폴오버 소진).

해결: 활성 계정이 '이번 런에 쿼터로 폴오버'된 사실을 누적 카운트해서, 임계(기본 2)에 도달하면
vars.ACTIVE_ACCOUNT 를 계정 체인의 다음 계정으로 전진(PATCH). 4계정 순환이라, 막혔던 계정이
주간 리셋되면 순환하다 자연 복귀한다(원복 로직 0). 다음 런부터는 살아있는 계정에서 시작 = 손해 종료.

⚠️ no-op 안전장치(라이브 무해 = §파이프라인 '라이브 플래그 기본 OFF'):
  · GH_VARS_TOKEN(Variables 쓰기 PAT) 미설정 → 아무것도 안 함(exit 0). 운영자가 PAT 넣는 순간 켜짐.
  · 신호 파일(NOMUTE_QUOTA_SIGNAL · 기본 $GITHUB_WORKSPACE/.nomute_active_quota) 없음
    = 이번 런에 활성 계정이 쿼터로 안 막힘 → hits 안 건드림(exit 0).
  · 모든 예외 = 삼키고 exit 0 (승격 실패가 파이프라인을 절대 안 깸).

상태 저장 = GitHub Actions repo Variables(레포 파일 커밋 0):
  · ACTIVE_ACCOUNT     = 활성 계정명(체인의 어디서 시작하는지)
  · ACTIVE_QUOTA_HITS  = 활성 계정 쿼터 히트 누적(임계 도달 시 0 리셋 · 승격 후에도 0)

카운트 시맨틱 = '연속'이 아니라 '누적'(런 단위). 신호 없는 런(활성 계정 성공 or 미호출)은 hits를
안 건드린다 → '한동안 길게 막힘'이면 빠르게 임계 도달·승격(목적), 가끔 막히는 계정은 천천히 승격.

Variables API(fine-grained PAT · Repository permissions → Variables: Read and write):
  GET   /repos/{owner}/{repo}/actions/variables/{name}
  PATCH /repos/{owner}/{repo}/actions/variables/{name}   body {"name","value"}
  POST  /repos/{owner}/{repo}/actions/variables          body {"name","value"}   (없을 때 생성)
표준 라이브러리(urllib)만 — 러너에 requests 없어도 동작. 정본 문서 = docs/oauth_계정_자동승격_이식가이드.md.
"""
import json
import os
import sys
import urllib.error
import urllib.request

# 계정 체인 SSOT = 워크플로 env 매핑(MUTENO→NOMUTEFB→EMS1130G→MUTENONA)과 동일 순서·순환.
#   ⚠️ 체인을 바꾸면 워크플로들의 CLAUDE_CODE_OAUTH_TOKEN_ALT* 조건식도 같이 바꿔야 정합(양쪽 동기).
CHAIN = ["MUTENO", "NOMUTEFB", "EMS1130G", "MUTENONA"]
THRESHOLD = int(os.environ.get("PROMOTE_THRESHOLD", "2") or "2")   # 활성 계정 쿼터 몇 회 누적 시 승격(운영자 = 2)
API = "https://api.github.com"


def _repo():
    return os.environ.get("GITHUB_REPOSITORY", "muteno/nomute-editor")


def _req(method, path, token, body=None):
    url = "%s/repos/%s/actions/variables%s" % (API, _repo(), path)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "nomute-account-failover")
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode()
        return resp.status, (json.loads(raw) if raw.strip() else {})


def _get_var(name, token):
    try:
        _st, obj = _req("GET", "/" + name, token)
        return obj.get("value")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _set_var(name, value, token):
    """있으면 PATCH, 없으면(404) POST 로 생성."""
    try:
        _req("PATCH", "/" + name, token, {"name": name, "value": str(value)})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            _req("POST", "", token, {"name": name, "value": str(value)})
        else:
            raise


def _del_var(name, token):
    """변수 삭제(self-test 정리용)."""
    _req("DELETE", "/" + name, token)


def selftest():
    """GH_VARS_TOKEN 이 Variables 를 실제로 읽고/쓰고/지울 수 있는지 실측(PAT 권한 확인).
    ⚠️ 활성 계정(ACTIVE_ACCOUNT)·카운터(ACTIVE_QUOTA_HITS)는 안 건드린다 — 전용 probe 변수만 왕복.
    통과 = rc0 / 권한·설정 문제 = rc1(승격 main 과 달리 fail-soft 아님 = 테스트라 실패를 드러냄)."""
    token = (os.environ.get("GH_VARS_TOKEN") or "").strip()
    if not token:
        print("❌ GH_VARS_TOKEN 미설정 — Secrets 탭에 등록됐는지 확인(이름 철자 GH_VARS_TOKEN).")
        return 1
    active = (os.environ.get("ACTIVE_ACCOUNT") or "MUTENO").strip()
    print("현재 활성 계정(ACTIVE_ACCOUNT) = %s · 체인 = %s" % (active, "→".join(CHAIN)))
    probe = "ACCOUNT_FAILOVER_SELFTEST"
    try:
        _set_var(probe, "probe-write-ok", token)
        print("  ✅ 쓰기(POST/PATCH) 성공 — %s 생성/갱신" % probe)
        v = _get_var(probe, token)
        print("  ✅ 읽기(GET) 성공 — 값 = %r" % v)
        _del_var(probe, token)
        print("  ✅ 삭제(DELETE) 성공 — %s 정리" % probe)
        hits = _get_var("ACTIVE_QUOTA_HITS", token)
        print("  ℹ️ 현재 ACTIVE_QUOTA_HITS = %r (없으면 아직 승격 카운트 0)" % hits)
        print("🎉 PAT 실측 통과 — Variables read/write/delete 전부 정상. 승격 준비 완료(ACTIVE_ACCOUNT 무손상).")
        return 0
    except urllib.error.HTTPError as e:
        print("  ❌ 실패 — HTTP %s %s" % (e.code, getattr(e, "reason", "")))
        if e.code in (403, 404):
            print("     → PAT 에 'Variables: Read and write' 권한이 없거나 이 레포 접근이 없음. 토큰 권한을 확인해.")
        return 1
    except Exception as e:   # noqa: BLE001
        print("  ❌ 실패 — %s" % e)
        return 1


def main():
    token = (os.environ.get("GH_VARS_TOKEN") or "").strip()
    if not token:
        print("  ⏭️  GH_VARS_TOKEN 미설정 — 활성 계정 자동 승격 비활성(no-op · 라이브 무해).")
        return 0

    sig = os.environ.get("NOMUTE_QUOTA_SIGNAL") or os.path.join(
        os.environ.get("GITHUB_WORKSPACE", "."), ".nomute_active_quota")
    if not os.path.exists(sig):
        return 0   # 이번 런에 활성 계정이 쿼터로 안 막힘 = 조용히 종료(hits 불변)

    active = (os.environ.get("ACTIVE_ACCOUNT") or "MUTENO").strip()
    if active not in CHAIN:
        print("  ⚠️  활성 계정 '%s' 이 체인에 없음 — 승격 생략(체인=%s)." % (active, "→".join(CHAIN)))
        return 0

    try:
        hits_raw = _get_var("ACTIVE_QUOTA_HITS", token)
        hits = int(hits_raw) if (hits_raw or "").strip().isdigit() else 0
    except Exception as e:   # noqa: BLE001
        print("  ⚠️  ACTIVE_QUOTA_HITS 조회 실패(%s) — 승격 생략." % e)
        return 0

    hits += 1
    if hits < THRESHOLD:
        try:
            _set_var("ACTIVE_QUOTA_HITS", hits, token)
        except Exception as e:   # noqa: BLE001
            print("  ⚠️  hits 기록 실패(%s) — 다음 런 재시도." % e)
        print("  📉 활성 계정 '%s' 쿼터 누적 %d/%d회 — 아직 승격 안 함." % (active, hits, THRESHOLD))
        return 0

    # 임계 도달 → 체인 다음 계정으로 전진(순환) + hits 리셋
    nxt = CHAIN[(CHAIN.index(active) + 1) % len(CHAIN)]
    try:
        _set_var("ACTIVE_ACCOUNT", nxt, token)
        _set_var("ACTIVE_QUOTA_HITS", 0, token)
        print("  🔀 활성 계정 자동 승격: %s → %s (쿼터 %d회 누적 · 다음 런부터 %s 로 시작)." % (active, nxt, hits, nxt))
    except Exception as e:   # noqa: BLE001
        print("  ⚠️  활성 계정 승격 실패(%s) — hits 유지·다음 런 재시도." % e)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())   # PAT 실측(실패 = rc1 노출)
    try:
        sys.exit(main())
    except Exception as e:   # noqa: BLE001  최후 방어 — 승격은 파이프라인을 절대 안 깬다
        print("  ⚠️  account_failover 예외(무시하고 통과): %s" % e)
        sys.exit(0)
