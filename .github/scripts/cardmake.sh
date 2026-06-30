#!/usr/bin/env bash
# 카드뉴스 일괄 제작: 대상 queue/*.md → Claude 헤드리스 Step 4(카드 MD) → cards/<기사>/cards.md
# → 슛/edit 렌더 = 직영 gen_cards(Actions서 Gemini 장면 직접생성 + card_news 로컬 합성 + R2/git) — 외부 Drive/Apps Script/Cloud Run 0(260621 운영자).
# → 기사별 즉시 커밋·push(분석물 보존 최우선 — Pages가 그때그때 뷰어 갱신).
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PROMPT_FILE="prompts/card-make.md"
MODEL="claude-opus-4-8"
TARGET="${1:-all}"
MODE="${2:-full}"            # full=클로드+렌더 / text=텍스트만(자동 카드플랜·제미나이0) / shoot=렌더만(텍스트 재사용)
MAX_BATCH="${MAX_BATCH:-3}"  # all 배치 상한 — 무상한 Opus 폭증 차단(나머지는 다음 회차가 처리·중복skip이 페이징)

# 🔒 제미나이 이중잠금 Lock B — text(자동 카드플랜) 모드는 유료 생성경로에 절대 안 닿는다.
#   GDRIVE_SA_JSON(레거시 Drive 발사) + GEMINI_API_KEY(직영 gen_cards 발사) 둘 다 unset → 자동 카드 = 제미나이 0.
#   (Lock A = 자동 워크플로 YAML에 두 env 부재. 둘 다라야 실수로도 제미나이 미발사.)
[ "$MODE" = text ] && unset GDRIVE_SA_JSON GEMINI_API_KEY

# 지침 SSOT 강제 주입 — 요약과 동일한 단일 헬퍼(주입 로직 갈라짐 방지). card 프로필.
source "$ROOT/shared/inject_guidelines.sh"
source "$ROOT/shared/claude_transient.sh"  # is_transient() SSOT — 카드 claude콜 일시 과부하(5xx/Overloaded) 인라인 재시도용
source "$ROOT/shared/claude_meter.sh"      # claude_meter() SSOT — claude -p 토큰 사용량 계측(metrics shard · 옛 동작 호환)
INLINE_TRIES="${INLINE_TRIES:-3}"   # 카드 claude -p 일시 과부하 인라인 재시도(15s·30s 백오프) — 버스트 카드 유실 차단(analyze·ask와 동일·260622)
GVER="$(guidelines_version card)"
GBLOCK="$(guidelines_block card)"
echo "지침 버전(card): ${GVER} / MODE=${MODE}"

git config user.name  "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

push_main() {
  # news-analyze와 동일 전략: -X theirs(이 run의 산출물 우선), 충돌 시 abort 후 재시도
  for i in 0 1 2 3 4; do
    [ "$i" -gt 0 ] && sleep $((2**i))
    git pull --rebase -X theirs origin main && git push origin HEAD:main && return 0
    git rebase --abort 2>/dev/null || true
  done
  return 1
}

commit_push() {
  git add cards
  git add metrics 2>/dev/null || true   # 토큰 계측 shard(claude_meter) 동반 커밋 — 있을 때만(shoot 등 미터 부재 시 무해)
  # messages.json = claude 시스템성 실패/복구 알림(프로필 점등) — gitignore·미추적이라 shoot 모드선 부재.
  # 한 줄에 묶으면 부재 시 git add 전체가 fatal(=커밋 통째 누락) → 있을 때만 따로 add(슛 경로 커밋 보장).
  [ -f viewer/messages.json ] && git add viewer/messages.json
  git diff --cached --quiet && return 0
  git commit -m "$1"
  push_main || { echo "::error::push 실패: $1"; return 1; }
}

status_json() {  # $1=dir $2=state [$3=버전 오버라이드(shoot=기존 버전 보존)]
  # rev = 이 카드가 만들어진 시점의 요약(queue) 수정회차 — 뷰어 stale 감지용(요약이 더 revise되면 a.rev>cards.rev).
  # gen_cards가 남긴 .r2_images.json(R2 공개URL 배열) 있으면 "images"로 합쳐 박는다(뷰어가 R2 직접서빙).
  local sjstem; sjstem="$(basename "$1")"
  local sjrev; sjrev="$(grep -m1 '^rev:' "queue/$sjstem.md" 2>/dev/null | grep -o '[0-9]\+' | head -1)"
  SJ_DIR="$1" SJ_STATE="$2" SJ_GVER="${3:-$GVER}" SJ_REV="${sjrev:-0}" python3 - <<'PY'
import os, json, datetime
d = os.environ["SJ_DIR"]
st = {"state": os.environ["SJ_STATE"],
      "updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
      "guidelines_version": os.environ["SJ_GVER"],
      "rev": int(os.environ["SJ_REV"] or 0)}
side = os.path.join(d, ".r2_images.json")
if os.path.isfile(side):
    try:
        imgs = json.load(open(side, encoding="utf-8"))
        if isinstance(imgs, list) and imgs:
            st["images"] = imgs
    except Exception:
        pass
json.dump(st, open(os.path.join(d, "status.json"), "w", encoding="utf-8"), ensure_ascii=False)
PY
}

# ── edit 모드: 단일 카드 변경(직영 gen_cards · Cloud Run/Drive/Apps Script 0) ──
# CARD_N(1-base)·EDIT_TEXT(*강조*)·EDIT_WISH = env. gen_cards가 내부 분기:
#  • 이미지 수정 희망 없음 + 장면 보존본 있음 → 로컬 합성(card_news · 제미나이 0 · 좋아한 장면 100% 보존)
#  • 이미지 수정 희망 있음 OR 장면 보존본 없음 → Gemini 장면 1장 재생성 + 로컬 합성
#  → R2 카드면 같은 키 덮어쓰기(.r2_images.json 불변·?v= 캐시버스트) / 아니면 로컬 _final · 버전(versions/card-NN) 보존 · cards.md 텍스트 갱신
if [ "$MODE" = edit ]; then
  stem="$(basename "$TARGET" .md)"
  [ -s "cards/$stem/cards.md" ] || { echo "::error::cards.md 없음: $stem"; exit 1; }
  [ -n "${CARD_N:-}" ]    || { echo "::error::CARD_N(카드 번호) 없음"; exit 1; }
  [ -n "${EDIT_TEXT:-}" ] || { echo "::error::EDIT_TEXT 없음"; exit 1; }
  echo "::group::카드 변경: $stem 카드$CARD_N"
  # 합성 폰트(Noto CJK) — card_news 로컬 합성 필수. 캐시 미적중 시만 설치(§🧰).
  fc-list 2>/dev/null | grep -qi "noto sans cjk" || { sudo apt-get update -qq && sudo apt-get install -y -qq fonts-noto-cjk; }
  # 첨부 사진(4:5) 경로 — card-make.yml inputs.scene → EDIT_SCENE_PATH. 있으면 검증 후 EDIT_SCENE로(=장면 직접지정·제미나이 0).
  #   누락(dispatch 레이스)이면 silent text-only 폴백을 막고 명시 실패(::error·exit) — 운영자가 사진 유실을 즉시 알게.
  EDIT_SCENE=""
  if [ -n "${EDIT_SCENE_PATH:-}" ]; then
    if [ -f "${EDIT_SCENE_PATH}" ]; then EDIT_SCENE="${EDIT_SCENE_PATH}"; echo "첨부 사진 장면 사용: ${EDIT_SCENE_PATH}";
    else echo "::error::첨부 사진 경로 없음(dispatch 레이스 추정): ${EDIT_SCENE_PATH}"; exit 1; fi
  fi
  # 이미지 재생성(체크 EDIT_SYNC=1 또는 수동 EDIT_WISH) = Claude가 지침대로 이미지 프롬프트 작성 → gen_cards가 그걸로 Gemini 재생성.
  #   (체크=캡션+맥락 / wish=캡션+맥락+수정희망. 둘 다 아니면 EDIT_PROMPT 빈 채 = gen_cards가 장면 보존·문구만 = 제미나이 0)
  #   ⚠️ 첨부 사진이 있으면(EDIT_SCENE) 사진이 곧 장면 → Claude 프롬프트·Gemini 둘 다 건너뜀(순수 합성·제미나이 0).
  #   ⚠️ 임의 프롬프팅 금지 — GBLOCK(card 지침)을 떠먹여 규약(텍스트-free·구도·GOVERNING·안전) 준수(운영자 요구 260621).
  EDIT_PROMPT=""
  if { [ "${EDIT_SYNC:-0}" = "1" ] || [ -n "${EDIT_WISH:-}" ]; } && [ -n "${GEMINI_API_KEY:-}" ] && [ -z "${EDIT_SCENE}" ]; then
    echo "이미지 프롬프트 작성(claude · 지침 준수)…"
    ap="${GBLOCK}

[작업] 아래 카드뉴스 카드 1장의 **이미지 프롬프트**만 다시 작성하라. 위 지침의 이미지 프롬프트 규약(텍스트-free 장면·구도·GOVERNING·안전 등)을 엄격히 따른다. 임의로 벗어나지 말 것.
[카드 캡션(장면이 이 내용을 표현 — 이미지에 글자로 넣지 않음)]: ${EDIT_TEXT}
[이미지 수정 희망(있으면 반영)]: ${EDIT_WISH:-(없음)}
[기사 맥락 다이제스트]:
$(cat "queue/$stem.md" 2>/dev/null)

[출력] 이미지 프롬프트 한 단락만(머리말·설명·따옴표·코드블록 없이). 장면 묘사 텍스트만."
    EDIT_PROMPT="$(printf '%s' "$ap" | METER_SRC=card-edit METER_REF="$stem" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
          --model "$MODEL" --effort max \
          --allowedTools "WebFetch,WebSearch" \
          --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,Read,Glob,Grep" \
          --max-turns 20 2>"/tmp/editprompt_${stem}.err")"
    if [ -z "${EDIT_PROMPT// }" ]; then
      echo "::warning::이미지 프롬프트 작성 실패 — 기존 카드 프롬프트로 폴백"; EDIT_PROMPT=""
    else
      echo "이미지 프롬프트 작성 완료(${#EDIT_PROMPT}자)"
    fi
  fi
  EDIT_TEXT="$EDIT_TEXT" EDIT_WISH="${EDIT_WISH:-}" EDIT_SYNC="${EDIT_SYNC:-0}" EDIT_PROMPT="$EDIT_PROMPT" EDIT_SCENE="$EDIT_SCENE" \
    python3 .github/scripts/gen_cards.py --stem "$stem" --edit-card "$CARD_N" \
    || { echo "::error::카드 변경 실패"; exit 1; }
  pv="$(grep -o '"guidelines_version":"[^"]*"' "cards/$stem/status.json" 2>/dev/null | cut -d'"' -f4)"
  status_json "cards/$stem" "done" "${pv:-$GVER}"
  commit_push "cards: $stem 카드$CARD_N 변경"
  echo "::endgroup::"
  exit 0
fi

# 대상 결정: all = cards/ 미존재(미제작) 큐 전체 / 그 외 = queue 파일명 1개
shopt -s nullglob
targets=()
if [ "$TARGET" = "all" ]; then
  # 최신(파일명 = YYMMDD-HHMM…) 먼저 — 방금 공유한 기사가 옛 백로그에 밀리지 않게(파일명 ASCII-safe).
  for q in $(ls -1 queue/*.md 2>/dev/null | sort -r); do
    stem="$(basename "$q" .md)"
    if [ ! -d "cards/$stem" ]; then targets+=("$q"); continue; fi
    # 지침 게이트 — 카드의 지침 버전이 현재와 다르면(갱신됨) 재생성 대상에 포함.
    cv="$(grep -o '"guidelines_version":"[^"]*"' "cards/$stem/status.json" 2>/dev/null | cut -d'"' -f4)"
    [ "$cv" = "$GVER" ] && continue   # 지침 동일 = 최신, 스킵
    # ⛔ done 보호(운영자 승인 260618) — 이미 '슛'해 이미지까지 만든 카드(done/fired_partial/렌더이미지·scenes 보존본)는
    #    지침이 바뀌어도 자동 재생성하지 않는다(이미지·운영자 편집 유실 방지). 반영은 운영자 재촬영(슛)으로.
    cst="$(grep -o '"state":"[^"]*"' "cards/$stem/status.json" 2>/dev/null | cut -d'"' -f4)"
    cimg="$(ls "cards/$stem"/*.jpg "cards/$stem"/*.png "cards/$stem"/scenes/*.jpg 2>/dev/null | head -1)"
    if [ "$cst" = "done" ] || [ "$cst" = "fired_partial" ] || [ -n "$cimg" ]; then
      echo "지침 변경됐으나 이미 촬영된 카드 — 보호·재생성 스킵: $stem (state=${cst:-?})"; continue
    fi
    echo "지침 변경 — 카드 재생성 대상: $stem (${cv:-없음}→${GVER})"; targets+=("$q")
  done
else
  base="$(basename "$TARGET")"
  if [[ ! "$base" =~ ^[A-Za-z0-9._-]+\.md$ ]] || [ ! -f "queue/$base" ]; then
    echo "::error::잘못된 대상: $TARGET"; exit 1
  fi
  targets=("queue/$base")
fi
# all 배치 상한 — 한 회차에 MAX_BATCH건만(나머지는 다음 회차가 처리, 중복skip이 자연 페이징).
if [ "$TARGET" = "all" ] && [ ${#targets[@]} -gt "$MAX_BATCH" ]; then
  echo "배치 상한 ${MAX_BATCH} — ${#targets[@]}건 중 ${MAX_BATCH}건만 이번 회차"
  targets=("${targets[@]:0:$MAX_BATCH}")
fi
if [ ${#targets[@]} -eq 0 ]; then
  echo "대상 없음(전부 제작됨)"; exit 0
fi

# 시작 상태 일괄 커밋 → 뷰어에 ⏳
for q in "${targets[@]}"; do
  stem="$(basename "$q" .md)"
  mkdir -p "cards/$stem"
  status_json "cards/$stem" "generating"
done
commit_push "cards: 제작 시작 ⏳ ${#targets[@]}건"

fail=0
for q in "${targets[@]}"; do
  stem="$(basename "$q" .md)"
  echo "::group::카드 제작: $stem"

  # shoot(렌더만) + 기존 cards.md 있으면 = 클로드 스킵(낭비·드리프트 0). 텍스트의 지침버전 보존(pv).
  if [ "$MODE" = shoot ] && [ -s "cards/$stem/cards.md" ]; then
    echo "슛(렌더만): 기존 cards.md 재사용 — 클로드 스킵"
    pv="$(grep -o '"guidelines_version":"[^"]*"' "cards/$stem/status.json" 2>/dev/null | cut -d'"' -f4)"
    [ -n "$pv" ] || pv="$GVER"
  else
    # 고정부(프롬프트 + 강제 주입 지침) → 가변부(다이제스트). stdin 전달 = ARG_MAX 회피
    # (카드 지침 통째 주입이 커서 명령행 인자로는 'Argument list too long' 126 — stdin은 무제한).
    # --disallowedTools + --max-turns = 헤드리스 무중단(파일쓰기/권한대기/툴 무한루프 차단, analyze.sh와 동일).
    # timeout 900(15분) = analyze 요약콜과 동일·뷰어 genStuck(15분 실패표시)와 정합(260619 1500→900↓:
    #   백엔드가 25분까지 슬롯 붙들어 15~25분이 낭비였음 — 프론트는 이미 15분에 실패라 운영자 재시도. 단발 Opus콜이라 15분이면 충분).
    fp="$(cat "$PROMPT_FILE")

${GBLOCK}

[큐레이션 다이제스트 — 이 기사로 카드뉴스 MD를 만든다]
$(cat "$q")"
    # 인라인 재시도 — API 일시 과부하(529 Overloaded/5xx)면 짧은 백오프로 즉시 재시도(analyze·ask와 동일·260622).
    #   성공(필수 헤더 존재)·CARDS_FAILED(막다른길)는 즉시 탈출. 과부하 신호일 때만 재시도(is_transient).
    # ── 폭주(runaway) 교정 재시도 (운영자 260630 · 원인 대응) ──
    #   모델이 양식을 무시하고 대용량 출력(카드헤더 없음)하면 = 폭주. 정상 기사는 미발동(성공 즉시 탈출)이고,
    #   폭주 때만 "사고과정 없이 첫 글자부터 카드 양식만·즉시 종료"를 강제하는 교정 프리픽스를 붙여 *1회* 재시도한다
    #   (정치 민감·모욕 메타포 기사서 6만+토큰 폭주 → 포맷검사 실패하던 근본 대응 · 비용 바운드=폭주 재시도 1회만 ·
    #    잡 timeout 120분 내 충분). 그래도 실패하면 아래 분류기가 'runaway'로 표면화.
    fp_base="$fp"; runaway_fixed=0
    STRICT_PREFIX="⚠️⚠️ [출력 규율 — 강제]: 직전 시도가 양식을 어겨 실패했다. 지금은 사고과정·서론·해설·자기검증을 일절 쓰지 말고, 응답 첫 글자부터 \`# {제목}\`으로 시작해 카드뉴스 MD 양식(\`### [카드 N]\`·\`**텍스트**\`·\`**이미지 프롬프트**\`·\`**검색어**\`)만 3~7장 출력하라. 마지막 카드 직후 즉시 멈춰라(블록·문장 반복 금지). 도저히 카드화 불가하면 첫 줄에 \`CARDS_FAILED: <사유>\`만 출력하라.

"
    inline_delay=15
    for attempt in $(seq 1 "$INLINE_TRIES"); do
      out="$(printf '%s' "$fp" | METER_SRC=card METER_REF="$stem" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
            --model "$MODEL" \
            --effort max \
            --allowedTools "WebFetch,WebSearch" \
            --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,Read,Glob,Grep" \
            --max-turns 40 \
            2> "/tmp/${stem}.err")"
      rc=$?
      if { [ $rc -eq 0 ] && [ -n "${out// }" ] && grep -qm1 '^### \[카드 1\]' <<<"$out"; } || grep -qm1 '^CARDS_FAILED' <<<"$out"; then
        break
      fi
      if claude_failover "$out$(cat "/tmp/${stem}.err" 2>/dev/null)"; then continue; fi   # 쿼터 한도 → 대체 계정 1단계씩 전환·재시도(서브1→서브2 · SSOT)
      if [ "$attempt" -lt "$INLINE_TRIES" ] && is_transient "$out$(cat "/tmp/${stem}.err" 2>/dev/null)"; then
        echo "  ⏳ API 일시 과부하 추정(인라인 ${attempt}/${INLINE_TRIES}, rc=$rc) — ${inline_delay}s 후 재시도"
        sleep "$inline_delay"; inline_delay=$((inline_delay * 2)); continue
      fi
      # 폭주 교정 — rc0·출력은 있는데 카드헤더 없음(=양식 위반/폭주) → 교정 프리픽스로 1회만 재시도.
      if [ "$runaway_fixed" -eq 0 ] && [ "$attempt" -lt "$INLINE_TRIES" ] && [ $rc -eq 0 ] && [ -n "${out// }" ]; then
        runaway_fixed=1
        echo "  ⚠️ 양식 위반/폭주 추정($(printf '%s' "$out" | wc -l | tr -d ' ')줄·카드헤더 없음) — 출력규율 강제 프리픽스로 교정 재시도(${attempt}/${INLINE_TRIES})"
        fp="${STRICT_PREFIX}${fp_base}"; continue
      fi
      break
    done

    # 실패 판정: 비정상 종료 / 빈 출력 / 실패 신호 / parsePrompts 필수 헤더 부재
    if [ $rc -ne 0 ] || [ -z "${out// }" ] || grep -qm1 '^CARDS_FAILED' <<<"$out" \
       || ! grep -qm1 '^### \[카드 1\]' <<<"$out" || ! grep -qm1 '^\*\*이미지 프롬프트\*\*' <<<"$out"; then
      # ── 실패 사유 분류(운영자 260630) — '모델 폭주(runaway)'를 일시·막다른길과 구별해 명시 ──
      #   증상: 카드헤더(### [카드 1]) 없는 대용량 출력 = 모델이 출력 상한까지 폭주(예: 정치 민감 기사서 6만+ 토큰)
      #   → 클릭 재시도로 안 풀림(같은 콘텐츠=같은 폭주). reason 첫 줄을 error.log에 박아 뷰어가 표면화(헛클릭 방지).
      ol=$(printf '%s' "$out" | wc -l | tr -d ' '); ob=$(printf '%s' "$out" | wc -c | tr -d ' ')
      if grep -qm1 '^CARDS_FAILED' <<<"$out"; then
        reason="$(grep -m1 '^CARDS_FAILED' <<<"$out" | cut -c1-200)"
      elif [ $rc -ne 0 ]; then
        reason="비정상 종료(exit $rc · $(head -c 120 "/tmp/${stem}.err" 2>/dev/null | tr '\n' ' '))"
      elif [ -z "${out// }" ]; then
        reason="빈 응답(모델 무출력)"
      elif ! grep -qm1 '^### \[카드 1\]' <<<"$out" && { [ "${ol:-0}" -gt 400 ] || [ "${ob:-0}" -gt 40000 ]; }; then
        reason="모델 출력 폭주(runaway · ${ol}줄/${ob}B · 카드헤더 미생성) — 출력규율 강제 교정 재시도도 실패. 전문 붙여넣기/다이제스트 수정 권장"
      else
        reason="카드 포맷 미생성(필수 헤더·라벨 부재 · ${ol}줄/${ob}B)"
      fi
      {
        echo "reason: $reason"
        echo "exit_code: $rc · out_lines: $ol · out_bytes: $ob"
        echo "---- stderr ----"; cat "/tmp/${stem}.err" 2>/dev/null
        echo "---- stdout(head 30) ----"; printf '%s\n' "$out" | head -n 30
        echo "---- stdout(tail 20) ----"; printf '%s\n' "$out" | tail -n 20
      } > "cards/$stem/error.log"
      echo "::warning::카드 실패 [$stem]: $reason"
      status_json "cards/$stem" "failed"
      commit_push "cards: $stem 제작 실패"
      fail=$((fail+1)); echo "::endgroup::"; continue
    fi

    # 모델 사족 방어 — 첫 '#' 줄(제목)부터 저장
    printf '%s\n' "$out" | sed -n '/^#/,$p' > "cards/$stem/cards.md"
    pv="$GVER"
  fi

  state="text_done"
  # ── 슛(렌더) 경로 = 직영(gen_cards)만 ── (레거시 Drive/Apps Script/Cloud Run 폴백 제거 · 운영자 260621)
  #   gen_cards = Actions 러너 안에서 Gemini 직접생성 + card_news 로컬합성 + R2(or git) — 외부 Drive/Cloud Run 0.
  #   exit코드: 0=done · 2=fired_partial(일부) · 그 외=failed. GEMINI_API_KEY 없으면 text_done 유지(이미지 미발사).
  if [ -n "${GEMINI_API_KEY:-}" ]; then
    python3 .github/scripts/gen_cards.py --stem "$stem"; rc=$?
    if   [ "$rc" -eq 0 ]; then state="done"
    elif [ "$rc" -eq 2 ]; then state="fired_partial"
    else state="failed"; fi
  else
    echo "GEMINI_API_KEY 없음 — 이미지 발사 생략(text_done 유지)"
  fi
  status_json "cards/$stem" "$state" "$pv"
  commit_push "cards: $stem ($state)"
  echo "::endgroup::"
done

# 전건 실패만 잡 실패로
[ $fail -eq ${#targets[@]} ] && exit 1 || exit 0
