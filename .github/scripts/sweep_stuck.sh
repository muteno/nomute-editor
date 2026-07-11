#!/usr/bin/env bash
# 좀비 generating 스윕 SSOT — 잡 하드킬/크래시로 'generating'에 고착된 카드 status.json을 failed로 수거.
# 호출 = news-analyze·news-ask·news-revise 각 card 잡의 마지막 스텝(if: always() · concurrency group=card-make라
# 라이브 생성과 직렬 = genuine 림보만 수거). 구 3벌 인라인 printf가 status.json을 통째 덮어써
# ⓐ fails 유실(자동 재시도 3회 캡 리셋 = 무한 재시도 벡터) ⓑ guidelines_version 공백화(지침 게이트로 무상한
# 재편입 = Door2) 하던 것을 load-merge로 봉합(평의회 260711 ②⑧⑨ 수렴): 기존 필드 보존 + fails+1(좀비도 실패
# 1회로 집계 = 캡 지배) + 지침해시 보존(generating 일괄이 이미 도장해둔 값 = 추가 계산 0).
set -uo pipefail
git config user.name  "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
swept=0
for s in cards/*/status.json; do
  [ -f "$s" ] || continue
  grep -qE '"state":[[:space:]]*"generating"' "$s" || continue   # json.dump=콜론뒤 공백 → 공백 허용(무공백 grep은 영구 미스=좀비 미수거, 260620 분신술 실증)
  d="$(dirname "$s")"
  echo "좀비 generating → failed: $d"
  python3 - "$s" <<'PY'
import json, sys, datetime
p = sys.argv[1]
try:
    o = json.load(open(p, encoding="utf-8"))
except Exception:
    o = {}
o["state"] = "failed"
o["updated"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
o["fails"] = int(o.get("fails", 0) or 0) + 1   # 좀비(하드킬)도 실패 1회 — 자동 재시도 캡(CARD_FAIL_RETRY_MAX)이 스윕 경유에도 전역 강제
o.pop("retry", None)                            # 진행 표식 정리(최종 상태)
json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PY
  echo "잡 중단/크래시로 카드 생성 미완료(자동 스윕)" > "$d/error.log"
  swept=$((swept+1))
done
[ "$swept" -eq 0 ] && { echo "좀비 없음"; exit 0; }
git add cards
git commit -m "cards: 좀비 generating ${swept}건 → failed(스윕)" || exit 0
for i in 1 2 3 4; do
  git pull --rebase -X theirs origin main && git push origin HEAD:main && exit 0
  git rebase --abort 2>/dev/null || true; sleep $((2**i))
done
echo "::warning::스윕 push 실패"
