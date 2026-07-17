#!/usr/bin/env bash
# 봇 산출물을 붐비는 main에 '최신 재기점 재적층'으로 착지시키는 공용 커밋·푸시 헬퍼.
# 왜: 종전 관용구 `git pull --rebase -X ours origin main 2>/dev/null || true` + push 4회 재시도는
#     같은 파일을 다른 봇이 먼저 밀면 리베이스가 꼬여(HEAD=origin/main 무적용) 로컬이 뒤처진 채
#     4연속 fetch-first 거부 → push는 '성공'처럼 보여도 원격 내용 no-op만 밀고 우리 산출물이 증발.
#     (실측 260716 insta-fetch run 29539535483: 브리프 생성됨 → push 거부 4회 → 다음주기 재수집 →
#      chan_brief 7/14 정지 3일. 같은 관용구 12개 워크플로 공유 = systemic.)
# 방식: git 조작 전 산출물을 워킹트리에서 스냅샷 → 매 시도 {리베이스 잔여 청소 · fetch · reset --hard
#     origin/main(최신 기점) · 스냅샷 재적층 · commit · push}. 리베이스를 안 써서 꼬임 자체가 불가하고,
#     매 시도가 최신 main의 직계 자식 단일 커밋이라 경쟁에 져도 다음 시도서 재동기 → 결국 착지.
# ⚠ 전제(안전 조건): 인자 경로 = 이 워크플로가 '유일 기록자'여야 한다(타 워크플로가 같은 경로를
#     동시에 쓰면 reset 재적층이 그쪽 변경을 덮을 수 있음). insta 산출물(insta_data·chan_brief·apps/insta/data)·
#     sns 산출물 등은 각 파이프라인 단독 소유라 안전. 공유 원장(append-only)엔 쓰지 말 것.
# 사용: bash .github/scripts/git_land.sh "<커밋 메시지>" <경로 ...>
# rc: 항상 0(fail-soft — 커밋 스텝/후속 스텝 비차단) · 미착지 시 ::warning만.
set -u
MSG="${1:-chore: bot commit}"; shift || true
PATHS=("$@")
[ "${#PATHS[@]}" -gt 0 ] || { echo "git_land: 대상 경로 없음 — no-op"; exit 0; }
git config user.name "nomute-bot"
git config user.email "bot@users.noreply.github.com"

# 변동 선판정 — 없으면 조용히 종료(푸시 0)
git add -- "${PATHS[@]}" 2>/dev/null || true
if git diff --cached --quiet 2>/dev/null; then echo "git_land: 변동 없음 — 커밋 생략"; exit 0; fi

# ★ git 조작(fetch/reset --hard) 전에 산출물을 워킹트리에서 스냅샷 — reset가 덮기 전 원본 보존이 핵심.
SNAP="$(mktemp -d)"
for p in "${PATHS[@]}"; do
  [ -e "$p" ] || continue
  mkdir -p "$SNAP/$(dirname "$p")"
  cp -a "$p" "$SNAP/$p" 2>/dev/null || true
done

pushed=0
for i in 1 2 3 4 5 6; do
  git rebase --abort 2>/dev/null || true      # 잔여 리베이스/머지 상태 청소(멱등)
  git merge --abort 2>/dev/null || true
  if ! git fetch -q origin main 2>/dev/null; then echo "git_land: fetch 실패 — 재시도 $i"; sleep $((i * 2)); continue; fi
  git reset -q --hard origin/main 2>/dev/null || true   # 최신 원격 = 기점(이전 로컬 커밋 폐기 = 충돌 원천 제거)
  # 스냅샷을 최신 main 위에 재적층(경로가 dir이어도 안전하게 교체)
  for p in "${PATHS[@]}"; do
    [ -e "$SNAP/$p" ] || continue
    rm -rf "$p" 2>/dev/null || true
    mkdir -p "$(dirname "$p")"
    cp -a "$SNAP/$p" "$p" 2>/dev/null || true
  done
  git add -- "${PATHS[@]}" 2>/dev/null || true
  if git diff --cached --quiet 2>/dev/null; then echo "git_land: 최신 main과 동일 — 착지 불필요"; pushed=1; break; fi
  git commit -q -m "$MSG" 2>/dev/null || true
  if git push -q origin HEAD:main 2>/dev/null; then echo "git_land: 착지 성공(시도 $i)"; pushed=1; break; fi
  echo "git_land: push 경쟁 — 최신 main 재기점 재시도 $i"; sleep $((i * 2))
done
[ "$pushed" = 1 ] || echo "::warning::git_land: 착지 실패(6회 재기점 소진) — 다음 주기 재수집"
exit 0
