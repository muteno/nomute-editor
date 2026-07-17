#!/usr/bin/env python3
# claude_sync.py — CLAUDE.md의 SYNC-COMMON 마커 구간을 타 레포 CLAUDE.md 같은 구간에 PR로 전파.
# 원칙: 마커 안만 교체(레포 고유 절·【레포 바인딩】 무접촉) · 직접 push 없음(항상 PR) ·
#       마커 없는 레포 = 경고 후 스킵(최초 이식은 수동 1회 — CLAUDE.md 이식 노트 참조) ·
#       소스 커밋당 결정적 브랜치명(claude-sync/g<sha7>) = 중복 발사 멱등.
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


def span(text):
    i, j = text.find(START), text.find(END)
    if i < 0 or j < 0 or j < i:
        return None
    return text[i : j + len(END)]


def main():
    with open("CLAUDE.md", encoding="utf-8") as f:
        block = span(f.read())
    if not block:
        print("::error::원본 CLAUDE.md에 SYNC-COMMON 마커가 없다 — 전파 중단")
        return 1

    fails = []
    for repo in TARGETS:
        s, meta = gh("GET", f"/repos/{repo}")
        if s != 200:
            print(f"::warning::{repo}: 레포 조회 실패({s}) — 스킵")
            fails.append(repo)
            continue
        base = meta["default_branch"]

        s, cur = gh("GET", f"/repos/{repo}/contents/CLAUDE.md?ref={base}")
        if s != 200:
            print(f"::warning::{repo}: CLAUDE.md 없음({s}) — 마커 최초 이식 필요, 스킵")
            fails.append(repo)
            continue
        text = base64.b64decode(cur["content"]).decode("utf-8")
        old = span(text)
        if old is None:
            print(f"::warning::{repo}: SYNC-COMMON 마커 없음/훼손 — 최초 이식 필요, 스킵")
            fails.append(repo)
            continue
        if old == block:
            print(f"{repo}: 이미 동일 — 스킵")
            continue

        branch = f"claude-sync/g{SRC_SHA}"
        s, ref = gh("GET", f"/repos/{repo}/git/ref/heads/{base}")
        if s != 200:
            print(f"::warning::{repo}: base ref 조회 실패({s}) — 스킵")
            fails.append(repo)
            continue
        s, _ = gh("POST", f"/repos/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": ref["object"]["sha"]})
        if s == 422:
            print(f"{repo}: 브랜치 {branch} 이미 존재(이 소스 커밋은 기제안) — 스킵")
            continue
        if s != 201:
            print(f"::warning::{repo}: 브랜치 생성 실패({s}) — 스킵")
            fails.append(repo)
            continue

        new = text.replace(old, block, 1)
        s, _ = gh(
            "PUT",
            f"/repos/{repo}/contents/CLAUDE.md",
            {
                "message": f"chore: CLAUDE.md 공통 골격 동기화 (nomute-editor@{SRC_SHA})",
                "content": base64.b64encode(new.encode()).decode(),
                "sha": cur["sha"],
                "branch": branch,
            },
        )
        if s not in (200, 201):
            print(f"::warning::{repo}: 파일 커밋 실패({s}) — 스킵")
            fails.append(repo)
            continue

        s, pr = gh(
            "POST",
            f"/repos/{repo}/pulls",
            {
                "title": f"🔁 CLAUDE.md 공통 골격 동기화 — nomute-editor@{SRC_SHA}",
                "head": branch,
                "base": base,
                "body": (
                    f"자동 전파 PR — 원본 = muteno/nomute-editor@{SRC_SHA} CLAUDE.md의 SYNC-COMMON 마커 구간.\n\n"
                    "- 마커 안만 교체한다(레포 고유 절·【레포 바인딩】 무접촉).\n"
                    "- 내용 이견이 있으면 이 PR을 고치지 말 것 — muteno/nomute-editor CLAUDE.md에서 고쳐 재전파(여기서 고치면 다음 전파가 덮는다).\n"
                    "- 생성 주체 = nomute-editor `.github/workflows/claude-sync.yml`."
                ),
            },
        )
        if s == 201:
            print(f"{repo}: PR #{pr['number']} 생성 ✅ {pr.get('html_url','')}")
        else:
            print(f"::warning::{repo}: PR 생성 실패({s}) {pr.get('message','')}")
            fails.append(repo)

    if fails:
        print(f"::warning::미전파 = {', '.join(fails)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
