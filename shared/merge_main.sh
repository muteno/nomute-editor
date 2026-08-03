#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# merge_main.sh — CLAUDE.md [7-5] 자동 머지 절차 실행기(운영자 260803 "7-5 ㄱㄱ" 승인)
#
# ▷ 왜: 세션마다 ②~⑤를 손루프로 짜다 실측 사고 2종이 났다(260803 · PR #3498):
#     ① ⑤(main 푸시)가 ④(브랜치 동기)를 앞서 GitHub이 표식 PR을 merged 대신 closed로 닫음
#     ② 성공 판정을 push 출력 문자열("main -> main")로 해서 실제 성공("HEAD -> main")을
#        재패배로 오판 — 이미 이긴 뒤 4라운드를 헛돌았다
#   → 절차를 파일 하나로 굳힌다. 성공 판정 = 출력 파싱이 아니라 **fetch 후 origin/main==HEAD 사후 대조**.
#
# ▷ 순서( = [7-5] 그대로 · ①커밋은 세션 몫):
#   prep : ② git fetch origin main → ③ rebase(충돌 = abort·멈춤 [7-4/7-7]) → ③-b 게이트 재실행
#          (check_refs · 리베이스 자동병합 되돌림 검문 = 260802 사고 재발방지 · Q번호 경합은
#          --fix-qnum 자동 + amend + 커밋 메시지 Q 동기) → ④ 브랜치 --force-with-lease 푸시
#          → ④-b 안내 출력(표식 PR 비-draft = MCP 축이라 세션이 연다 · [7-6])
#   land : 라운드 루프 — ②→(main 이동 시 ③·③-b)→ **④ 브랜치 선착 → ⑤ main 후착 순차 2발**
#          → 사후 대조 성공 판정. (260803 2차 개정 · #3538 실측 = 구 --atomic 동시 도착이 PR head·
#          base를 같은 SHA로 동시 기록 → GitHub이 "변경 0"으로 closed 처리 = 점등 실패 변종.
#          점등은 head 먼저·base 나중 순서에서만 성립[260802 #3474~#3495 실측] · ⑤ = --no-verify로
#          경합 창 압축 = push_pair 주석 · main plain push 불변.)
#          → ⑥ 점등 사후 대조(운영자 260803 승인 · 3차): 표식 PR merged를 API 실측(GITHUB_TOKEN/GH_TOKEN)
#            — CLOSED 확정만 **rc=7**(머지 자체는 성공 · 보고에 「main 머지 완료 · 점등 실패」 강제),
#            토큰 없음·API 불가·PR 미발견·open 지연 = fail-soft rc=0 + MCP pull_request_read 재대조 지시
#            (성공을 실패로 오판해 헛도는 ⓑ축 재발 금지 · [7-6ⓒ] 표시보다 머지 우선).
#   go   : prep + land 연속.
#
# ▷ 안전 레일: main에 force 계열 절대 없음(⑤ = plain push 고정) · 리베이스 충돌 = 즉시 abort·rc=2
#   · 더티 트리 = 거부 · main/detached에서 실행 = 거부 · 비교 기준 = 항상 origin/main([7-7] 로컬 ref 불신)
#   · amend는 HEAD가 origin/main 밖일 때만 · pre-push 훅(check_refs)은 그대로 = 이중 방어 유지.
# ▷ UI 표면(viewer html) 변경이면 커밋 전 smoke_all rc=0은 종전대로 세션 몫(pre-commit 축) — --smoke로
#   prep에서 1회 실행 가능(land 루프엔 안 넣는다 = [7-5] ③-b 명시 게이트는 check_refs).
# 사용: bash shared/merge_main.sh prep|land|go [--rounds=8] [--smoke]
# ═══════════════════════════════════════════════════════════════════════════════
set -u -o pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 9
MODE="${1:-go}"; shift || true
ROUNDS=8; SMOKE=0
for a in "$@"; do case "$a" in --rounds=*) ROUNDS="${a#*=}";; --smoke) SMOKE=1;; esac; done
QFILE="docs/요구사항_큐.md"
say() { echo "[merge_main] $*"; }
die() { echo "[merge_main] ⛔ $*" >&2; exit "${2:-1}"; }

BR="$(git symbolic-ref --quiet --short HEAD)" || die "detached HEAD — 작업 브랜치에서 실행하라" 4
[ "$BR" = "main" ] && die "main 브랜치에서 직접 실행 금지 — 작업 브랜치에서([7-5] ①)" 4
git diff --quiet && git diff --cached --quiet || die "더티 트리 — 먼저 커밋하라([7-5] ① = 세션 몫)" 4

LAST_GREEN_SHA=""   # 이 SHA로 게이트 통과함(같은 SHA 재게이트 생략 = 멱등 · 리베이스로 SHA 갈리면 반드시 재실행)

fetch_main() { git fetch origin main -q || die "fetch 실패 — 네트워크 확인" 5; }

rebase_main() {   # ③ — 충돌 = [7-4/7-7] 멈춤 조건(스크립트가 절대 자의 해소하지 않는다)
  git merge-base --is-ancestor origin/main HEAD && return 0   # 이미 최신 base = 리베이스 불필요
  say "③ rebase onto origin/main($(git rev-parse --short origin/main))"
  if ! git rebase origin/main >/dev/null 2>&1; then
    git rebase --abort >/dev/null 2>&1
    die "리베이스 충돌 — [7-4] 멈춰 묻는다(자동 해소 금지). 충돌 파일 확인 후 수동 해소." 2
  fi
}

fix_qnum() {   # 원장 Q번호 경합 자동 재부여 + 커밋 메시지 Q 동기(260803 실측 = 경합 2회로 수동 amend 왕복)
  git merge-base --is-ancestor HEAD origin/main && die "HEAD가 이미 origin/main 안 — amend 불가 상태(수동 확인)" 3
  python3 shared/check_refs.py --fix-qnum >/dev/null 2>&1
  git status --porcelain | grep -q . || return 1   # 고칠 게 없었다 = 내 신규 행 경합이 아님(박제 중복 등) → 호출자 판정
  local pair old new msg
  pair="$(git diff -U0 -- "$QFILE" | grep -oE '^[-+]- ✅ Q[0-9]+' | grep -oE 'Q[0-9]+' | head -2)"
  old="$(echo "$pair" | sed -n 1p)"; new="$(echo "$pair" | sed -n 2p)"
  msg="$(git log -1 --pretty=%B)"
  if [ -n "$old" ] && [ -n "$new" ] && [ "$old" != "$new" ]; then
    say "③-b Q번호 경합 → $old→$new 재부여 + 커밋 메시지 동기"
    msg="$(echo "$msg" | sed "s/\b$old\b/$new/g")"
  else say "③-b --fix-qnum 산출 편입(원장 외 면책 승계 포함)"; fi
  git add -A   # 시작 시 클린 트리 보장이라 지금 변경 = 전부 --fix-qnum 산출
  git commit --amend -q -m "$msg" || die "amend 실패" 3
}

gate() {   # ③-b — 리베이스 뒤 게이트 재실행([7-5] 명시 순서 · pre-push 훅은 별도 이중 방어)
  [ "$(git rev-parse HEAD)" = "$LAST_GREEN_SHA" ] && { say "③-b 게이트 스킵(동일 SHA 기통과 = 리베이스 없음)"; return 0; }
  say "③-b check_refs 재실행…"
  local log; log="$(mktemp)"
  if ! python3 shared/check_refs.py >"$log" 2>&1; then
    if grep -q "원장 Q번호 신규 중복" "$log"; then
      fix_qnum || { grep -E "^❌" "$log" | head -3 >&2; die "Q중복이 내 신규 행이 아님(기존 박제 중복 축) — 수동 확인" 3; }
      if ! python3 shared/check_refs.py >"$log" 2>&1; then grep -E "^❌" "$log" | head -3 >&2; die "Q재부여 후에도 게이트 rc≠0 — [7-7] 멈춤" 3; fi
    else grep -E "^❌" "$log" | head -3 >&2; die "게이트 rc≠0 — [7-7] 멈춤(리베이스 되돌림/신규 위반 확인)" 3; fi
  fi
  LAST_GREEN_SHA="$(git rev-parse HEAD)"; rm -f "$log"
}

push_branch() {   # ④ 단독(prep용) — 리베이스로 SHA 갈리므로 lease 상시
  git push --force-with-lease="refs/heads/$BR" -u origin "refs/heads/$BR:refs/heads/$BR" \
    || die "브랜치 푸시 실패(lease 어긋남 = 원격 브랜치가 예상 밖 — 수동 확인)" 5
}

landed() { fetch_main; [ "$(git rev-parse origin/main)" = "$(git rev-parse HEAD)" ]; }   # 성공 판정 정본 = 사후 대조(출력 파싱 금지)

verify_light() {   # ⑥ 점등 원시 대조(운영자 260803 "그렇게 해줘" 승인) — 표식 PR merged 실측 · 출력 = 판정 토큰 한 줄
  local tok="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
  [ -z "$tok" ] && { echo NOTOK; return 0; }
  local slug; slug="$(git remote get-url origin | sed -E 's#\.git$##; s#.*[:/]([^/]+/[^/]+)$#\1#')"
  GH_SLUG="$slug" GH_BR="$BR" GH_TOK="$tok" python3 - <<'PY' 2>/dev/null || echo ERR
import json, os, urllib.request
slug, br, tok = os.environ['GH_SLUG'], os.environ['GH_BR'], os.environ['GH_TOK']
def api(p):
    r = urllib.request.Request('https://api.github.com' + p, headers={'Authorization': 'Bearer ' + tok, 'Accept': 'application/vnd.github+json', 'User-Agent': 'merge-main-light'})
    with urllib.request.urlopen(r, timeout=10) as f: return json.load(f)
try:
    prs = api('/repos/%s/pulls?head=%s:%s&state=all&sort=updated&direction=desc&per_page=3' % (slug, slug.split('/')[0], br))
    if not prs: print('NOPR')
    else:
        p = prs[0]
        print(('MERGED' if p.get('merged_at') else ('OPEN' if p.get('state') == 'open' else 'CLOSED')), p.get('number'))
except Exception:
    print('ERR')
PY
}

light_check() {   # ⑥ 점등 사후 대조 — 머지 성공 «뒤»에만 호출. CLOSED 확정만 rc=7(머지 자체는 성공 = 보고 문구 강제),
  #   나머지(토큰 없음·API 불가·PR 미발견·open 지연)는 fail-soft rc=0([7-6ⓒ] 표시보다 머지 우선 ·
  #   성공을 실패로 오판해 헛도는 축 재발 금지 = ⓑ 교훈 · MCP 세션은 pull_request_read로 재대조).
  local L; L="$(verify_light)"
  case "$L" in
    MERGED*) say "⑥ 점등 확인 ✓ — 표식 PR #${L#* } merged";;
    CLOSED*) say "⚠️ ⑥ 점등 실패 실측 — 표식 PR #${L#* } closed(비머지 · #3538 축 신변종?). 머지는 성공 — 보고 6-1에 「main 머지 완료 · 점등 실패」로 못박고 변종 기록"; return 7;;
    OPEN*)   say "⚠️ ⑥ 표식 PR #${L#* } 아직 open(GitHub 전파 지연 가능) — 세션이 MCP pull_request_read로 재대조하라";;
    NOPR)    say "⑥ 표식 PR 미발견 — [7-6ⓔ] 표시 없음 = PR 생성 실패 축(머지는 성공) · 세션이 PR 유무 확인";;
    *)       say "⑥ 점등 자동 대조 불가(${L:-무응답} = 토큰 없음/API 불가) → 세션 몫 = MCP pull_request_read로 merged=true 확인(false면 보고에 점등 실패 못박기)";;
  esac
  return 0
}

push_pair() {   # ④ 선착 → ⑤ 후착 순차 2발(260803 2차 개정 · #3538 실측) · 판정은 항상 landed()
  # ⚠ 구 --atomic 동시 도착 = 리베이스 라운드에서 PR head·base가 **같은 SHA로 동시 기록** → GitHub이
  #   "변경 0"으로 closed 처리(#3538 = merged 점등 실패 변종 · #3498의 반대쪽 구멍). 점등이 성립하는 유일한
  #   순서 = 260802 실측 축(#3474~#3495) 그대로 — head가 새 SHA로 먼저 서 있고, base가 나중에 따라와야
  #   GitHub이 「head가 base에 흡수됨 = merged」로 판정한다. 그래서 atomic을 버리고 ④→⑤ 순서를 강제한다.
  # ⚠ ⑤ --no-verify = 같은 SHA가 이번 라운드 ③-b(check_refs) + ④의 pre-push 훅으로 **이중 기통과**한
  #   직후라 3번째 동일 게이트만 생략(④→⑤ 경합 창을 RTT급으로 압축 = 구 atomic의 「훅 1회」 취지 계승).
  #   main에 force 계열 없음은 불변(⑤ = plain push 고정) · ⑤ 패배 = landed() false → 다음 라운드 재시도.
  push_branch
  git push --no-verify origin "HEAD:refs/heads/main" >/dev/null 2>&1
  landed
}

case "$MODE" in
prep|go)
  say "① 커밋 확인 = $(git log -1 --oneline) (브랜치 $BR)"
  [ "$SMOKE" = 1 ] && { say "smoke_all 1회(--smoke)…"; bash shared/smoke_all.sh >/dev/null 2>&1 || die "smoke_all rc≠0 — UI 게이트 실패" 3; }
  fetch_main; rebase_main; gate
  say "④ 브랜치 푸시(--force-with-lease)"; push_branch
  say "④-b 표식 PR: 비-draft PR(base=main·head=$BR)이 없으면 지금 열어라(MCP create_pull_request · draft=false · [7-6] draft=폐기 · 이미 있으면 그대로). 생성 실패해도 land 진행(fail-soft ⓒ = 표시보다 머지 우선)."
  [ "$MODE" = "prep" ] && { say "다음 = 표식 PR 확인/생성 후 \`bash shared/merge_main.sh land\`"; exit 0; }
  ;&   # go = land로 계속
land)
  landed && { say "✅ 이미 main == HEAD($(git rev-parse --short HEAD)) — 머지 완료 상태"; light_check; exit $?; }
  for r in $(seq 1 "$ROUNDS"); do
    fetch_main; rebase_main; gate
    say "라운드 $r/$ROUNDS — ④ 브랜치 선착 → ⑤ main 후착(HEAD=$(git rev-parse --short HEAD))"
    if push_pair; then
      say "✅ main 머지 완료 · SHA=$(git rev-parse HEAD) — 보고 6-1·6-5에 이 해시로 못박아라([7-5])"
      light_check; exit $?
    fi
    say "라운드 $r 경합 패배(origin/main=$(git rev-parse --short origin/main)) → 재시도"
  done
  die "라운드 $ROUNDS회 소진 — [7-6-ⓔ] PR 열어둔 채 미완 상태로 멈춤. 재시도 = land 재실행(경합 완화 시) · 지속 시 운영자에게 보고" 6
  ;;
*) die "사용법: bash shared/merge_main.sh prep|land|go [--rounds=8] [--smoke]" 4 ;;
esac
