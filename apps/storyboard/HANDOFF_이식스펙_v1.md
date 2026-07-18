# HANDOFF — AI 스토리보드→영상 파이프라인 이식 스펙 v1

작성: 2026-07-14 · 대상: 깃 저장소에서 구현할 Claude Code 세션(또는 개발자)
목적: Cowork에서 검증한 "스킬 5종 + 힉스필드 MCP" 파이프라인을 Claude Agent SDK 기반 웹앱으로 이식

---

## 0. 한 줄 요약

사용자가 **모델(오퍼스/페이블)을 고르고 → 이야기를 설명하면 → 에이전트가 스킬로 스토리보드 초안을 짜고 → 사용자가 보강하고 → 힉스필드 MCP로 시트 이미지·영상까지 생성**하는 웹앱. 엔진은 Claude Agent SDK, 콘티 지식은 `.claude/skills/` 5종, 생성은 힉스필드 원격 MCP.

## 0-1. 검증 상태 요약 (읽고 시작할 것)

| 항목 | 상태 | 근거 |
|---|---|---|
| Agent SDK가 `.claude/skills/` 스킬 로딩 | ✅ 공식 문서 확인 | code.claude.com/docs/en/agent-sdk/skills |
| 원격 MCP(HTTP/SSE + OAuth 토큰) 연결 | ✅ 공식 문서 확인 | platform.claude.com/docs/en/agent-sdk/mcp |
| 모델 세션별 선택 (`claude-opus-4-8` / `claude-fable-5`) | ✅ 공식 문서 확인 | platform.claude.com/docs/en/about-claude/models/overview |
| **구독 OAuth를 SDK 앱에서 사용** | ❌ **금지** (2026-01 서버 차단, 2026-02 문서화) | support.claude.com 문서 + GitHub 이슈 #42106 |
| Pro/Max 플랜의 SDK 전용 월간 크레딧 존재 | ✅ 공식 support 문서 | support.claude.com/en/articles/15036540 |
| 힉스필드 MCP에서 Seedance 2.0 사용 가능 | ✅ 이 세션 실측 | models_explore 응답 |
| 생성 비용 (아래 §7 표) | ✅ 이 세션 실측 (get_cost) | 2026-07-14 기준 |
| SDK 크레딧의 정확한 인증 연동 방식 | ⚠️ 미확정 — 구현 전 support 문서 재확인 | — |
| 힉스필드 MCP URL/등록 절차 (커넥터 외부용) | ⚠️ 미확정 — 힉스필드 개발자 문서 확인 필요 | — |

---

## 1. 목표 유저 플로우 (6단계)

```
[1] 로그인/인증
      └ Claude: API 키 기반 (구독 OAuth 불가 — §3)
      └ 힉스필드: OAuth → access token 확보 (앱이 플로우 수행)
[2] 모델 선택
      └ claude-opus-4-8  (정석 연출, 저비용)
      └ claude-fable-5   (연출 훅 강함, 고비용)
[3] 만들려는 이야기 설명
      └ 자유 텍스트 + (선택) 캐릭터 레퍼런스 이미지 업로드
[4] 스토리보드 초안 확인
      └ 4a. 텍스트 콘티 먼저 (0크레딧) — 컷 리스트·ACTION/CAMERA/DIALOGUE
      └ 4b. 승인 시 시트 이미지 렌더 (gpt_image_2, 크레딧 소모)
[5] 초안 보강 (반복)
      └ 세션 유지(resume) + "해당 컷만 좁혀 재생성" 원칙
[6] 힉스필드 커넥터로 제작
      └ Element 락 → 컷 분해(START/END) → Seedance 2.0 영상 생성
```

설계 원칙: **텍스트 초안 → 이미지 → 영상 순서로 비용이 커지므로, 각 단계에 사용자 승인 게이트를 둔다.** 영상 생성 직전에는 `get_cost:true` 프리플라이트로 예상 크레딧을 보여주고 확인받는다.

---

## 2. 아키텍처

```
┌─ 웹 프론트 ─────────────────────────────┐
│ 모델 토글 · 스토리 입력 · 초안 뷰어(텍스트/시트) │
│ 컷 단위 수정 UI · 비용 확인 모달 · 결과 갤러리   │
└──────────────┬──────────────────────────┘
               │ HTTP/WebSocket (스트리밍)
┌──────────────▼──────────────────────────┐
│ 백엔드: Claude Agent SDK                  │
│  · model: 사용자 선택값                    │
│  · settingSources: ["project"]           │
│  · .claude/skills/ ← 스킬 5종             │
│  · mcpServers: 힉스필드 (type:url + token) │
│  · resumeSession / forkSession (보강 루프) │
│  · includePartialMessages (스트리밍)       │
└──────────────┬──────────────────────────┘
               │ 원격 MCP (Streamable HTTP)
┌──────────────▼──────────────────────────┐
│ 힉스필드: gpt_image_2 · Element · Seedance │
└──────────────────────────────────────────┘
```

- 1 대화 = 1 SDK 세션. 보강 루프는 `resumeSession(id)`로 컨텍스트 유지, 갈래 실험은 `forkSession`.
- 권한: `permissionMode` + `allowedTools`로 MCP 생성 도구를 사전 허용하되, **generate_video는 canUseTool 훅으로 사용자 승인 게이트**를 거는 걸 권장 (크레딧 보호).

---

## 3. 인증 설계 — ⚠️ 원래 계획 변경 필수

**원래 계획**: "구독제 클로드 OAuth 계정"으로 로그인.
**검증 결과**: **불가.** 2026-01부터 소비자 플랜(Free/Pro/Max) OAuth 토큰은 Claude Code·Claude.ai 밖에서 서버 차단, 2026-02-19 공식 문서로 금지 명시. 최종 사용자가 각자 구독으로 로그인하는 BYOS(멀티유저)도 명시적 금지.
[출처: support.claude.com/en/articles/15036540, github.com/anthropics/claude-code/issues/42106]

**대체 레인 (택1 또는 병행):**

| 레인 | 대상 | 방식 | 비고 |
|---|---|---|---|
| A (권장·개인 도구) | 앱 소유자 본인만 사용 | console.anthropic.com API 키를 백엔드 시크릿으로 보관 | Pro/Max 구독자는 SDK 전용 월간 크레딧 제공 ($20 Pro / $100 Max 5x / $200 Max 20x) — 연동 방식은 구현 전 support 문서 재확인 ⚠️ |
| B (멀티유저) | 여러 사용자 배포 시 | 각 사용자가 자기 API 키 등록 (BYOK) | 키는 서버측 암호화 저장, 프론트 노출 금지 |
| C (서비스형) | 운영자가 과금 부담 | 소유자 키 단일 사용 + 앱 자체 계정/쿼터 관리 | 남용 방지 rate limit 필수 |

**힉스필드 인증 (별도)**: 원격 MCP는 `authorization_token`을 설정에 넣는 방식 — **OAuth 플로우는 앱이 직접 수행해서 토큰을 획득**해야 함 (SDK가 자동 처리 안 함). 힉스필드가 외부 앱용 MCP 엔드포인트/토큰 발급을 어떻게 제공하는지 개발자 문서 확인 필요 ⚠️. 확인 경로가 막히면 차선: 웹앱은 프롬프트 번들까지 생성하고, 생성 실행은 힉스필드 UI 복붙.

```json
// .mcp.json 또는 SDK mcpServers 옵션 (형식은 공식 문서 확인됨)
{
  "mcpServers": {
    "higgsfield": {
      "type": "url",
      "url": "<힉스필드 MCP 엔드포인트>",
      "authorization_token": "<OAuth로 획득한 액세스 토큰>"
    }
  }
}
```

---

## 4. 모델 선택 (오퍼스 vs 페이블)

SDK 옵션 `model`에 세션별로 지정. 두 모델 모두 현행 제공 확인.

| | `claude-opus-4-8` | `claude-fable-5` |
|---|---|---|
| 포지션 | Opus 티어 (2025-05 출시) | Mythos급 플래그십 (2026-06 출시) |
| API 단가 | ~$5 / $25 (입/출력 1M토큰) | ~$10 / $50 |
| 콘티 스타일 (자체 비교 자료 근거) | 정석 연속 아크 — 컷 END→다음 컷 START 인계, 안정적 가속 구조 | 연출 훅 — "시계 장치"(김·비·문 닫힘=카운트다운), 무음 피크→비트드롭, 이동 벡터 L→R 고정, 조명 방향 락 |

- 스타일 차이 근거는 저장소에 동봉할 `페이블5_오퍼스4.8_3탄_비디오프롬프트_전체.pdf` (4개 씬 × 2모델 프롬프트 원문). UI에 "같은 브리프로 A/B 생성" 토글을 넣으면 이 비교를 사용자가 재현 가능.
- 기본값 권장: 초안(텍스트 콘티)은 오퍼스로 싸게 여러 번, 최종 프롬프트 번들은 페이블로 — 비용/품질 절충.

---

## 5. 스킬 통합 (5종)

**배치**: 저장소 루트 기준 `.claude/skills/<스킬명>/SKILL.md` (+ assets/). SDK 옵션에 `settingSources: ["project"]` 필수 — 이게 없으면 스킬이 로드되지 않음. 스킬을 코드로 등록하는 API는 없음(파일시스템 전용). [공식 문서 확인]

| 순서 | 스킬 | 역할 | 산출물 |
|---|---|---|---|
| 1 | `master-sheet-v2` | 캐릭터/제품 클린 일관성 시트 (정면·3/4·측면·전신·표정) | 3:2 시트 이미지 — Element 락 소스 |
| 1' | `master-sheet-v1` | 풀 디테일 바이블 (의상 멀티세트·HEX·세계관) — 룩북 필요 시만 | 2:3 매거진 시트 |
| 2 | `storyboard-v1` | 한 편 전체 콘티 (15초=12컷, 크림 배경, ACTION/CAMERA/DIALOGUE) | 3:2 콘티 시트 |
| 3 | `storyboard-v2` | 핵심 컷 1개를 S1~S6로 정밀 분해 (START/END 프레임·SFX) | 3:2 다크 시트 |
| 4 | `seedance-continuity-builder` | Seedance 2.0용 최종 프롬프트 번들 (Continuity Bible·한/영 블록·카메라 그래머) | 텍스트 번들 |

**스킬 원본 위치**: 이 문서와 같은 폴더의 zip(`drive-download-20260713T141510Z-2-001.zip`) 안 `.skill` 파일 5개 = zip 아카이브. 압축 풀면 `<스킬명>/SKILL.md` 구조 그대로 나옴 → `.claude/skills/`에 복사.
(`seedance-continuity-builder (1).skill`은 폴더명에서 ` (1)` 제거할 것.)

**트리거 매핑 (에이전트 시스템 프롬프트에 명시 권장):**
- 이야기 설명 입력 → `storyboard-v1` (전체 콘티 초안)
- 캐릭터 확정 → `master-sheet-v2` (Element 락용)
- 사용자가 특정 컷 지목 "이 컷 디테일하게" → `storyboard-v2`
- "영상으로 뽑아줘" → `seedance-continuity-builder` → generate_video

---

## 6. 힉스필드 MCP — 도구 매핑 (이 세션 실측)

플로우 단계별로 실제 호출할 MCP 도구:

| 단계 | 도구 | 용도 · 실측 파라미터 |
|---|---|---|
| 레퍼런스 업로드 | `media_upload` → PUT → `media_confirm` | 이미지 업로드, media_id 획득 |
| 캐릭터 락 | `show_reference_elements` (action=create) | 마스터시트 정면컷으로 Element 생성. **프롬프트에 `<<<element_id>>>` 임베드하면 백엔드가 자동 주입** — 이게 MCP 경유 시 캐릭터 일관성 핵심 |
| 시트 렌더 | `generate_image` model=`gpt_image_2` | aspect_ratio 3:2(콘티·V2시트)/2:3(V1바이블), resolution 2k, quality high |
| 영상 생성 | `generate_video` model=`seedance_2_0` | duration 4~15s · 480p/720p/1080p/4k · mode std/fast · roles: `start_image`/`end_image`/`image_references`/`video_references`/`audio_references` · `generate_audio` bool · 비율 auto/16:9/9:16/4:3/3:4/1:1/21:9 |
| 결과 표시 | `job_display` (job id 1개씩) | 결과 위젯. 스킬 문서의 "자동 폴링·재폴링 금지"에 대응 |
| 비용 확인 | `generate_*`에 `get_cost:true` | 잡 제출 없이 견적만 — **영상 생성 전 필수 게이트** |
| 크레딧 | `balance` / `transactions` | 잔액·사용 내역 |
| 청구 대상 | `list_workspaces` / `select_workspace` | 팀 워크스페이스 과금 전환 |

**주의 — 참조 표기 규칙이 경로마다 다름:**
- 스킬 원문의 "@표기 금지, 자연어로"는 **Seedance UI 직접 붙여넣기** 기준.
- **MCP 경유**에서는 `<<<element_id>>>` 문법 사용 (백엔드가 `@element_name`으로 재작성). 두 경로를 코드에서 분기할 것.
- 실존 인물 얼굴 레퍼런스는 플랫폼이 자동 거부 — 업로드 전 프론트에서 경고.

**Seedance 2.0 체이닝 (15초 초과 영상):**
1. 세그먼트1 생성 (≤15s) → 성공 시드 기록
2. 결과 영상을 다음 세그먼트의 참조로, 동일 시드 유지, "연장" 방식 사용
3. storyboard-v2의 각 샷 START/END 프레임 = `start_image`/`end_image` 체이닝 소스

---

## 7. 비용 실측표 (2026-07-14, get_cost 기준)

| 작업 | 설정 | 크레딧 |
|---|---|---|
| 시트 이미지 (초안용) | gpt_image_2 · 1k · low | 0.5~1 |
| 시트 이미지 (정품 스펙) | gpt_image_2 · 2k · high | **7** |
| 영상 테스트 | seedance_2_0 · 4s · 480p · fast | **6** |
| 영상 스킬 기본 스펙 | seedance_2_0 · 15s · 720p · std | **67.5** |
| 풀 체인 1회 (시트+콘티+분해 각 2k + 15s 영상) | — | **≈ 88+** |

- 현재 계정 상태: **무료 플랜, 잔액 10크레딧** → 풀 체인 불가. 구현 테스트 전 충전/플랜 결정 필요.
- UI 설계 반영: 모든 생성 버튼 옆에 예상 크레딧 표시(get_cost), 15초·고해상은 확인 모달.
- Claude 측 비용은 별도 (API 토큰 과금, §4 단가).

---

## 8. 초안 확인 · 보강 루프 설계

1. **초안은 항상 텍스트 먼저** (0크레딧): 컷 리스트를 구조화 출력(JSON 권장 — cut_no, action, camera, dialogue, duration)으로 받아 프론트에서 표로 렌더.
2. 사용자 승인 → 시트 이미지 렌더 (1회 7크레딧이므로 초안 단계에선 1k·low로 가안 뽑는 옵션 제공).
3. 보강 요청은 `resumeSession`으로 같은 세션에 전달. **스킬 원칙: 전체 재생성 지양, 지목된 컷/셀만 좁혀 재생성.**
4. A/B 실험 (오퍼스판 vs 페이블판): `forkSession`으로 같은 브리프에서 분기.
5. 스트리밍: `includePartialMessages: true`로 초안 생성 과정을 실시간 표시.
6. 상태 저장: 세션 id ↔ 프로젝트(스토리) 매핑을 앱 DB에 보관 — 다음 접속 때 이어서 보강.

---

## 9. 스킬 하드 룰 (에이전트가 어겨선 안 되는 것 — 원문 추출)

- 참조 표기: UI 경로=자연어("첨부와 동일"), MCP 경로=`<<<element_id>>>` (§6)
- 텍스트: 한국어+영어만, **일본어 문자 금지**, 워터마크·실존 브랜드 로고 금지
- 시트 규격: V1 콘티=밝은 크림 3:2 / V2 분해=다크 네이비 #0A0A12 3:2 / 마스터 V2=3:2 / 마스터 V1=2:3
- 컷 수 로직: 6~8s=6컷(2×3) · 10~12s=9컷(3×3) · **15s=12컷(3×4)** · 20~30s=16컷(4×4)
- 마지막 컷 = 제품+슬로건 키비주얼 (광고인 경우)
- 오디오: storyboard-v2는 NO BGM(나레이션+SFX만) / seedance-continuity-builder는 3레이어(스팅어·리듬비트·엔딩테일) 또는 무음악 모드 — 사용자에게 모드 선택 노출
- 카메라: 같은 앵글/구도 연속 반복 금지, 〈렌즈·앵글/구도·무브·광학〉 4요소
- 시드: 시리즈=고정, 단편=첫 성공 시드 기록
- 네거티브 프롬프트에 얼굴결함·조명드리프트·의상플리커·AI결함 세트 항상 포함
- Element 락은 멀티패널 시트 통째가 아니라 **깨끗한 정면 1컷**으로

---

## 10. 구현 마일스톤

- [ ] M1 스캐폴드: 저장소에 `.claude/skills/` 5종 배치, SDK 백엔드 부팅, settingSources·model 옵션 동작 확인
- [ ] M2 인증: API 키 백엔드 시크릿 + 힉스필드 OAuth 토큰 획득 플로우 (⚠️ 힉스필드 외부용 MCP 엔드포인트 확인 선행)
- [ ] M3 초안 루프: 스토리 입력→텍스트 콘티(JSON)→표 렌더→보강(resume) E2E
- [ ] M4 이미지: Element 생성 + gpt_image_2 시트 렌더 + get_cost 게이트
- [ ] M5 영상: storyboard-v2 START/END → seedance_2_0 (테스트는 4s·480p·fast=6크레딧)
- [ ] M6 통합 테스트: 저비용 설정 풀 플로우 1회 (크레딧 충전 필요, 현재 잔액 10)
- [ ] M7 마감: 비용 표시 UI, 실존 인물 얼굴 거부 안내, 세그먼트 체이닝(>15s)

## 11. 출처 · 파일 인벤토리

**공식 문서 (2026-07-14 검증):**
- 구독 플랜과 Agent SDK: support.claude.com/en/articles/15036540
- 스킬 in SDK: code.claude.com/docs/en/agent-sdk/skills
- 원격 MCP: platform.claude.com/docs/en/agent-sdk/mcp · platform.claude.com/docs/en/agents-and-tools/remote-mcp-servers
- 모델: platform.claude.com/docs/en/about-claude/models/overview
- 호스팅/스트리밍/세션: platform.claude.com/docs/en/agent-sdk/hosting · /streaming-vs-single-mode

**저장소에 동봉할 원본:**
- 스킬 5종: `master-sheet-v1.skill` `master-sheet-v2.skill` `storyboard-v1.skill` `storyboard-v2.skill` `seedance-continuity-builder (1).skill`
  - (260718 정리) 루트의 위 .skill 번들 5종 = `.claude/skills/` 설치 추적본과 중복이라 제거(운영자 승인 · 웹앱 감사 후속) — 정본 = `.claude/skills/<이름>/` · 재이식 시 그 디렉토리를 zip하면 동일.
- 모델 비교 근거: `페이블5_오퍼스4.8_3탄_비디오프롬프트_전체.pdf` + 비교 시트 PNG 10장
- 검증 샘플: 캐릭터 시트 3장·콘티 시트 3장·컷 이미지(1-1~9-3) — 기대 품질 기준선

**이 세션 실측 데이터**: §6 도구 스펙, §7 비용표 — 힉스필드 MCP 직접 호출 결과.

