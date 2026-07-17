#!/usr/bin/env python3
# claude_sync.py — CLAUDE.md의 SYNC-COMMON 마커 구간을 타 레포 CLAUDE.md 같은 구간에 PR로 전파.
# 원칙: 마커 안만 교체(레포 고유 절·【레포 바인딩】 무접촉) · 직접 push 없음(항상 PR) ·
#       마커 없는/훼손(개수≠1) 레포 = 경고 후 스킵(최초 이식은 수동 1회 — CLAUDE.md 이식 노트 참조) ·
#       레포당 고정 브랜치(claude-sync/common)를 매 실행 base로 강제 갱신 + 열린 PR 1개 롤링 유지
#       (평의회 260717: 브랜치 잔존 재시도 덫·중복 PR 누적·stale sha 해소) ·
#       실패 1건이라도 있으면 rc=1(빨간 빌드 — 침묵 실패 금지 · 401/403 = PAT 만료/권한 의심).
import base64
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
TOKEN = os.environ["GH_TOKEN"]
TARGETS = os.environ.get("TARGETS", "").split()
SRC_SHA = os.environ.get("GITHUB_SHA", "manual")[:7]
START = "<!-- SYNC-COMMON-START -->"
END = "<!-- SYNC-COMMON-END -->"
BRANCH = "claude-sync/common"


def gh(method, path, body=None):
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "claude-sync",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}
    except Exception as e:  # URLError·타임아웃 — 레포별 격리(전체 팬아웃 중단 금지)
        return 0, {"message": str(e)}


def span(text):
    if text.count(START) != 1 or text.count(END) != 1:
        return None  # 부재·중복·코드펜스 인용 = 전부 훼손 취급
    i, j = text.find(START), text.find(END)
    if j < i:
        return None
    return text[i : j + len(END)]


def sync_one(repo, block):
    s, meta = gh("GET", f"/repos/{repo}")
    if s in (401, 403):
        print(f"::error::{repo}: 인증 실패({s}) — SYNC_PAT 만료/권한 의심. 재발급: https://github.com/settings/personal-access-tokens")
        return False
    if s != 200:
        print(f"::warning::{repo}: 레포 조회 실패({s}) {meta.get('message','')} — 스킵")
        return False
    owner, base = repo.split("/")[0], meta["default_branch"]

    s, cur = gh("GET", f"/repos/{repo}/contents/CLAUDE.md?ref={base}")
    if s != 200:
        print(f"::warning::{repo}: CLAUDE.md 없음({s}) — 마커 최초 이식 필요, 스킵")
        return False
    text = base64.b64decode(cur["content"]).decode("utf-8")
    old = span(text)
    if old is None:
        print(f"::warning::{repo}: SYNC-COMMON 마커 부재/중복/훼손 — 최초 이식(정확 1쌍) 필요, 스킵")
        return False
    if old == block or old.replace("\r\n", "\n") == block:
        print(f"{repo}: 이미 동일 — 스킵")
        return True

    # 고정 브랜치를 base 최신 head로 강제 갱신(없으면 생성) — 재시도 덫·stale sha 제거
    s, ref = gh("GET", f"/repos/{repo}/git/ref/heads/{base}")
    if s != 200:
        print(f"::warning::{repo}: base ref 조회 실패({s}) — 스킵")
        return False
    head_sha = ref["object"]["sha"]
    s, _ = gh("PATCH", f"/repos/{repo}/git/refs/heads/{BRANCH}", {"sha": head_sha, "force": True})
    if s == 404:
        s, _ = gh("POST", f"/repos/{repo}/git/refs", {"ref": f"refs/heads/{BRANCH}", "sha": head_sha})
        if s != 201:
            print(f"::warning::{repo}: 브랜치 생성 실패({s}) — 스킵")
            return False
    elif s != 200:
        print(f"::warning::{repo}: 브랜치 갱신 실패({s}) — 스킵")
        return False

    new = text.replace(old, block, 1)
    s, _ = gh(
        "PUT",
        f"/repos/{repo}/contents/CLAUDE.md",
        {
            "message": f"chore: CLAUDE.md 공통 골격 동기화 (nomute-editor@{SRC_SHA})",
            "content": base64.b64encode(new.encode()).decode(),
            "sha": cur["sha"],
            "branch": BRANCH,
        },
    )
    if s not in (200, 201):
        print(f"::warning::{repo}: 파일 커밋 실패({s}) — 스킵")
        return False

    # 열린 롤링 PR이 없을 때만 생성(있으면 방금 force-push로 내용이 이미 갱신됨)
    s, prs = gh("GET", f"/repos/{repo}/pulls?state=open&head={owner}:{BRANCH}")
    if s == 200 and isinstance(prs, list) and prs:
        print(f"{repo}: 기존 PR #{prs[0]['number']} 갱신 ✅ {prs[0].get('html_url','')}")
        return True
    s, pr = gh(
        "POST",
        f"/repos/{repo}/pulls",
        {
            "title": "🔁 CLAUDE.md 공통 골격 동기화 (자동 전파)",
            "head": BRANCH,
            "base": base,
            "body": (
                f"자동 전파 PR — 원본 = muteno/nomute-editor CLAUDE.md의 SYNC-COMMON 마커 구간(최신 반영 커밋 = @{SRC_SHA}).\n\n"
                "- 마커 안만 교체한다(레포 고유 절·【레포 바인딩】 무접촉).\n"
                "- 정본이 다시 바뀌면 이 PR이 자동 갱신된다(레포당 롤링 PR 1개).\n"
                "- 내용 이견이 있으면 이 PR을 고치지 말 것 — muteno/nomute-editor CLAUDE.md에서 고쳐 재전파(여기서 고치면 다음 전파가 덮는다).\n"
                "- 생성 주체 = nomute-editor `.github/workflows/claude-sync.yml`."
            ),
        },
    )
    if s == 201:
        print(f"{repo}: PR #{pr['number']} 생성 ✅ {pr.get('html_url','')}")
        return True
    print(f"::warning::{repo}: PR 생성 실패({s}) {pr.get('message','')}")
    return False


def main():
    with open("CLAUDE.md", encoding="utf-8") as f:
        block = span(f.read())
    if not block:
        print("::error::원본 CLAUDE.md의 SYNC-COMMON 마커가 정확히 1쌍이 아니다 — 전파 중단")
        return 1

    fails = []
    for repo in TARGETS:
        try:
            if not sync_one(repo, block):
                fails.append(repo)
        except Exception as e:
            print(f"::warning::{repo}: 예외 {e} — 스킵")
            fails.append(repo)

    if fails:
        print(f"::error::미전파 = {', '.join(fails)} — 위 경고 확인(인증이면 SYNC_PAT 재발급, 마커 훼손이면 해당 레포 수동 1회 복구)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
