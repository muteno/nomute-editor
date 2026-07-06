#!/usr/bin/env bash
# 카드뉴스 일괄 제작: 대상 queue/*.md → Claude 헤드리스 Step 4(카드 MD) → cards/<기사>/cards.md
# → 슛/edit 렌더 = 직영 gen_cards(Actions서 Gemini 장면 직접생성 + card_news 로컬 합성 + R2/git) — 외부 Drive/Apps Script/Cloud Run 0(260621 운영자).
# → 기사별 즉시 커밋·push(분석물 보존 최우선 — Pages가 그때그때 뷰어 갱신).
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PROMPT_FILE="prompts/card-make.md"
source "$ROOT/shared/model_env.sh"   # 모델 단일 원천(PIPE_MODEL — 7스크립트 하드코딩 1점화 · 260702)
MODEL="$PIPE_MODEL"
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

# ⚠️ status.json 쓰기 = json.dump(기본 separator) → 콜론 뒤 공백 `"key": "val"`. 이걸 읽는 모든 grep은
#    반드시 `'"key":[[:space:]]*"…"'`(공백 허용)이라야 함 — 무공백 `'"key":"…"'`는 공백포맷을 영구 미스
#    (보호 게이트·지침버전 게이트 무력화·좀비 미수거 = 260620·260630 분신술 실증). 신규 읽기 grep도 이 규칙 따를 것.
status_json() {  # $1=dir $2=state [$3=버전 오버라이드(shoot=기존 버전 보존)]
  # rev = 이 카드가 만들어진 시점의 요약(queue) 수정회차 — 뷰어 stale 감지용(요약이 더 revise되면 a.rev>cards.rev).
  # gen_cards가 남긴 .r2_images.json(R2 공개URL 배열) 있으면 "images"로 합쳐 박는다(뷰어가 R2 직접서빙).
  local sjstem; sjstem="$(basename "$1")"
  local sjrev; sjrev="$(grep -m1 '^rev:' "queue/$sjstem.md" 2>/dev/null | grep -o '[0-9]\+' | head -1)"
  SJ_DIR="$1" SJ_STATE="$2" SJ_GVER="${3:-$GVER}" SJ_REV="${sjrev:-0}" SJ_RETRY="${SJ_RETRY:-0}" python3 - <<'PY'
import os, json, datetime
d = os.environ["SJ_DIR"]
st = {"state": os.environ["SJ_STATE"],
      "updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
      "guidelines_version": os.environ["SJ_GVER"],
      "rev": int(os.environ["SJ_REV"] or 0)}
_retry = int(os.environ.get("SJ_RETRY", "0") or 0)   # 자동 재시도 회차(>0이면 뷰어가 '재(N회)' 표식 · generating일 때만 유효)
if _retry > 0:
    st["retry"] = _retry
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
  pv="$(grep -o '"guidelines_version":[[:space:]]*"[^"]*"' "cards/$stem/status.json" 2>/dev/null | cut -d'"' -f4)"
  status_json "cards/$stem" "done" "${pv:-$GVER}"
  commit_push "cards: $stem 카드$CARD_N 변경"
  echo "::endgroup::"
  exit 0
fi

# 대상 결정: all = cards/ 미존재(미제작) 큐 전체 / 그 외 = queue 파일명 1개
shopt -s nullglob
targets=()
if [ "$TARGET" = "all" ]; then
  # 지침 변경 재생성 지평선(14인 평의회 ⑧ SYS-03 · 260702) — 지침 1자 수정 = text_done 백로그 전량(230+건)
  #   재생성 폭탄이던 것을 최근 N일(기본 14일)로 캡. 옛 기사는 운영자가 그 기사를 쓸 때(단일 지정·shoot·edit =
  #   무게이트) 갱신. env CARD_REGEN_SINCE=YYMMDD 로 오버라이드(0이면 지평선 OFF = 구 동작).
  CARD_REGEN_SINCE="${CARD_REGEN_SINCE:-$(TZ='Asia/Seoul' date -d '14 days ago' +%y%m%d 2>/dev/null || echo 0)}"
  # 최신(파일명 = YYMMDD-HHMM…) 먼저 — 방금 공유한 기사가 옛 백로그에 밀리지 않게(파일명 ASCII-safe).
  for q in $(ls -1 queue/*.md 2>/dev/null | sort -r); do
    stem="$(basename "$q" .md)"
    if [ ! -d "cards/$stem" ]; then targets+=("$q"); continue; fi
    # 지침 게이트 — 카드의 지침 버전이 현재와 다르면(갱신됨) 재생성 대상에 포함.
    cv="$(grep -o '"guidelines_version":[[:space:]]*"[^"]*"' "cards/$stem/status.json" 2>/dev/null | cut -d'"' -f4)"
    [ "$cv" = "$GVER" ] && continue   # 지침 동일 = 최신, 스킵
    # 재생성 지평선 — 이미 카드가 있는(cards.md 존재) 옛 기사는 지침이 stale이어도 자동 재생성 제외.
    sd="${stem%%-*}"
    if [ "$CARD_REGEN_SINCE" != "0" ] && [[ "$sd" =~ ^[0-9]{6}$ ]] && [ "$sd" -lt "$CARD_REGEN_SINCE" ] && [ -s "cards/$stem/cards.md" ]; then
      continue   # 지평선 이전 백로그 — 뷰어 stale 감지는 그대로 남음(운영자 수요 시 단일 재생성)
    fi
    # ⛔ done 보호(운영자 승인 260618) — 이미 '슛'해 이미지까지 만든 카드(done/fired_partial/렌더이미지·scenes 보존본)는
    #    지침이 바뀌어도 자동 재생성하지 않는다(이미지·운영자 편집 유실 방지). 반영은 운영자 재촬영(슛)으로.
    cst="$(grep -o '"state":[[:space:]]*"[^"]*"' "cards/$stem/status.json" 2>/dev/null | cut -d'"' -f4)"
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
    # 재촬영 경로 lint(비차단 · 9인 리뷰 ② 260702) — 레거시 카드의 규격 위반·비ASCII 혼입을 과금 렌더 전에 가시화(차단 안 함·재사용 유지)
    python3 .github/scripts/card_gate.py lint "cards/$stem/cards.md" >/dev/null 2>&1 \
      || echo "::warning::[$stem] 기존 cards.md 규격 위반 잔존(레거시) — 렌더는 진행하되 '텍스트만 수정'으로 교정 권장"
    pv="$(grep -o '"guidelines_version":[[:space:]]*"[^"]*"' "cards/$stem/status.json" 2>/dev/null | cut -d'"' -f4)"
    [ -n "$pv" ] || pv="$GVER"
  else
    # 고정부(프롬프트 + 강제 주입 지침) → 가변부(다이제스트). stdin 전달 = ARG_MAX 회피
    # (카드 지침 통째 주입이 커서 명령행 인자로는 'Argument list too long' 126 — stdin은 무제한).
    # --disallowedTools + --max-turns = 헤드리스 무중단(파일쓰기/권한대기/툴 무한루프 차단, analyze.sh와 동일).
    # timeout 900(15분) = analyze 요약콜과 동일·뷰어 genStuck(15분 실패표시)와 정합(260619 1500→900↓:
    #   백엔드가 25분까지 슬롯 붙들어 15~25분이 낭비였음 — 프론트는 이미 15분에 실패라 운영자 재시도. 단발 Opus콜이라 15분이면 충분).
    # thumb_dispatch 해설(라이브러리 조회·가변부 = GVER 무영향 · 14인 평의회 ⑦ LIB-05 · 260702) —
    #   analyze가 고른 연출 코드(AG/LGT/SG/DF)가 카드 LLM에겐 해독 불가 문자열로 전달되던 계승 회로 보수.
    #   thumb_gen._load_lib 재사용(SSOT) · 코드 미존재·파일 부재 = 빈 문자열(fail-soft·현 동작 유지).
    disp="$(grep -m1 '^thumb_dispatch:' "$q" 2>/dev/null | sed -E 's/^thumb_dispatch:[[:space:]]*"?//; s/"[[:space:]]*$//')"
    disp_note=""
    if [ -n "${disp// }" ]; then
      disp_note="$(DISP="$disp" python3 - 2>/dev/null <<'PY'
import os, sys
sys.path.insert(0, os.path.join(".github", "scripts"))
try:
    import thumb_gen as tg
    lib = tg._load_lib()
    out = []
    for code in os.environ.get("DISP", "").replace(",", " ").split():
        kw = lib.get(code.strip())
        if kw:
            out.append("%s = %s" % (code.strip(), kw))
    print("\n".join(out[:6]))
except Exception:
    pass
PY
)"
    fi
    if [ -n "${disp_note// }" ]; then
      disp_note="

[참고: thumb_dispatch 코드 해설 — analyze가 이 사건을 보고 고른 연출 코드의 라이브러리 정의다. §라이브러리 계승 규칙대로 조명 톤·정조만 비주얼 키노트로 상속하고, 앵글·샷 코드를 카드 N장에 복제하지 마라(카드 앵글은 카드마다 분산).]
${disp_note}"
    fi
    fp="$(cat "$PROMPT_FILE")

${GBLOCK}

[큐레이션 다이제스트 — 이 기사로 카드뉴스 MD를 만든다]
$(cat "$q")${disp_note}"
    # 인라인 재시도 — API 일시 과부하(529 Overloaded/5xx)면 짧은 백오프로 즉시 재시도(analyze·ask와 동일·260622).
    #   성공(필수 헤더 존재)·CARDS_FAILED(막다른길)는 즉시 탈출. 과부하 신호일 때만 재시도(is_transient).
    # ── 폭주(runaway) 교정 재시도 (운영자 260630 · 원인 대응) ──
    #   모델이 양식을 무시하고 대용량 출력(카드헤더 없음)하면 = 폭주. 정상 기사는 미발동(성공 즉시 탈출)이고,
    #   폭주 때만 "사고과정 없이 첫 글자부터 카드 양식만·즉시 종료"를 강제하는 교정 프리픽스를 붙여 *1회* 재시도한다
    #   (정치 민감·모욕 메타포 기사서 6만+토큰 폭주 → 포맷검사 실패하던 근본 대응 · 비용 바운드=폭주 재시도 1회만 ·
    #    잡 timeout 120분 내 충분). 그래도 실패하면 아래 분류기가 'runaway'로 표면화.
    fp_base="$fp"; runaway_fixed=0; timeout_retried=0
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
      # 생성 타임아웃(rc=124 = claude_meter 900s 상한 초과·무출력) 자동 재시도 1회 (운영자 260701).
      #   무거운 입력(전문 paste·재작성 + effort max·max-turns 40)이 15분을 넘겨 SIGTERM 종료되던 것 구제.
      #   is_transient(5xx/과부하 텍스트)엔 안 걸리는 순수 타임아웃/행이라 별도 처리 — 같은 입력이라도 API 상태·경로 편차로 2차 시도 성공 가능. 1회만(비용 바운드·잡 timeout 120분 내).
      if [ "$timeout_retried" -eq 0 ] && [ "$attempt" -lt "$INLINE_TRIES" ] && [ "$rc" -eq 124 ]; then
        timeout_retried=1
        echo "  ⏳ 생성 타임아웃(rc=124 · 900s 초과·무출력) — ${inline_delay}s 후 1회 재시도(${attempt}/${INLINE_TRIES})"
        SJ_RETRY=1 status_json "cards/$stem" "generating"; commit_push "cards: $stem 재시도 1회 ⏳"   # 뷰어 라이브 '재(1회)' 표식(generating 유지 · 성공/실패 시 최종 status_json이 retry 해제)
        sleep "$inline_delay"; continue
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

    # ── 규격 린트 + 교정 재시도 1회 (14인 평의회 ⑤⑧ SYS-02 · 260702) ──
    #   합성기 물리 제약(줄≤4·hangul≤18·weight≤19.5·빈줄0·별표짝)·비ASCII 혼입을 슛(=Gemini 과금) *전에* 검사.
    #   위반이면 위반 목록을 명시한 교정 프리픽스로 1회만 재생성(비용 바운드 — 폭주 교정과 동일 골격),
    #   재실패면 저장은 유지(비차단·::warning) — 렌더 단계 실패(과금 후)보다 언제나 싸다.
    printf '%s\n' "$out" | sed -n '/^#/,$p' > "/tmp/${stem}.cards.tmp"
    lint_out="$(python3 .github/scripts/card_gate.py lint "/tmp/${stem}.cards.tmp" 2>&1)"; lint_rc=$?
    if [ $lint_rc -ne 0 ]; then
      echo "  ⚠️ 규격 린트 위반 — 교정 재시도 1회"
      printf '%s\n' "$lint_out" | sed 's/^/    /'
      LINT_PREFIX="⚠️⚠️ [규격 교정 — 강제]: 직전 시도가 아래 합성기 규격을 위반했다. 위반 항목만 고쳐 같은 카드뉴스 MD 전체를 처음부터 다시 출력하라(내용·구성은 유지·규격만 교정 · 응답 첫 글자부터 \`# {제목}\`).
[위반 목록]
${lint_out}

"
      out2="$(printf '%s' "${LINT_PREFIX}${fp_base}" | METER_SRC=card METER_REF="$stem" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter 900 \
            --model "$MODEL" --effort max \
            --allowedTools "WebFetch,WebSearch" \
            --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,Read,Glob,Grep" \
            --max-turns 40 2>/dev/null)"
      if [ -n "${out2// }" ] && grep -qm1 '^### \[카드 1\]' <<<"$out2"; then
        printf '%s\n' "$out2" | sed -n '/^#/,$p' > "/tmp/${stem}.cards.retry"
        if python3 .github/scripts/card_gate.py lint "/tmp/${stem}.cards.retry" >/dev/null 2>&1; then
          echo "  ✓ 교정 재시도 통과 — 교정본 채택"
          cp "/tmp/${stem}.cards.retry" "/tmp/${stem}.cards.tmp"
        else
          echo "::warning::[$stem] 규격 교정 재시도도 위반 잔존 — 원본 저장(비차단·렌더 단계 방어에 위임)"
        fi
      else
        echo "::warning::[$stem] 규격 교정 재시도 무출력/양식 위반 — 원본 저장(비차단)"
      fi
    fi
    # prev 보존(재생성 A/B 비교 원본 · 14인 평의회 ⑪ LOOP-05) — 1세대만(덮어쓰기·뷰어 미노출)
    [ -s "cards/$stem/cards.md" ] && cp "cards/$stem/cards.md" "cards/$stem/cards.prev.md"
    mv "/tmp/${stem}.cards.tmp" "cards/$stem/cards.md"
    pv="$GVER"
    # 커버리지 소프트 경보(요약→카드 알맹이 증발 · 14인 평의회 ② SYS-01 · 비차단 · 248쌍 실측 기반 HS≥2 게이트)
    cov_out="$(python3 .github/scripts/card_gate.py coverage "$q" "cards/$stem/cards.md" 2>&1)"; cov_rc=$?
    printf '%s\n' "$cov_out" > "cards/$stem/coverage.log"
    [ $cov_rc -eq 2 ] && echo "::warning::[$stem] 요약→카드 알맹이 누락 의심(고신호 ≥2) — 슛 전에 '텍스트만 수정'으로 복원 검토: $(printf '%s' "$cov_out" | grep -m1 'COV 플래그')"
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
