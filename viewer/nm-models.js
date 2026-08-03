// 모델 표시명 SSOT — 노뮤트 전 표면의 정식 모델 표기 단일 사전(운영자 260803 4차 "모델명 항상 통일 — 어디는 Kling 3.0 Omni 어디는 클링 이러면 안됨" · 5차 "아이디어도 배선해줘" 승인).
// 규칙 = ① 화면에 모델을 이름으로 쓸 땐 이 사전 값만 쓴다(한글 음차·축약·소문자 변형 금지) ② 새 모델 = 여기 1줄 추가가 시작 ③ 강제 = check_refs `check_model_names`(음차·변형 래칫 + 리터럴 표면 동기).
// ⚠ functions/**(Pages Functions 서버)는 뷰어 정적 자산인 이 파일을 import 못 한다 — 서버 리터럴(api/sb.js DIRECTOR_NM)은 게이트가 이 사전과 문자 단위 동기 검증(어긋나면 커밋 차단).
// 로드 = nm-svg.js 관례(뷰어 head/본문 <script src="nm-models.js"> 1줄 · 동기 로드 = 아래 인라인 스크립트보다 항상 먼저).
window.NM_MODELS = {
  fable: 'Fable 5',            // 감독(연출 LLM) — 감성·서사 마감
  opus: 'Opus 5',              // 감독 — 잔잔·광고
  gpt: 'GPT 5.6 Sol',          // 감독 — 완급·액션(풀네임 = 설계확정 260714 문서·api DIRECTOR_NM 정본)
  kling: 'Kling 3.0 Omni',     // 비디오 엔진(콘티 촬영·프롬프팅 공통)
  veo: 'Veo 3.1',              // 비디오 엔진(프롬프팅 · 초안)
  seedance: 'Seedance 2.0',    // 비디오 엔진 — 버전 = 운영자 260803 5차 확정 "2.0이 맞고"(구 2.5 초안 표기 회수 · 2.5 승격 = 가용성 실측 후 여기 1줄)
  motion: '모션그래픽',          // 촬영 3레인(사내 렌더 — 외부 모델이 아니라 한글 고유명이 정식)
  gemini: 'Gemini 3.1 Flash',  // 이미지·레퍼런스 엔진(index GENI_ENG_ICO 동일 문자열)
  gpt_image: 'GPT Image 2.0',  // 이미지 엔진(index GENI_ENG_ICO 동일 문자열)
  suno: 'Suno',                // 음원 — 복붙 프롬프팅 레인
  lyria: 'Lyria 3'             // 음원 — 곡 생성 레인(구글 유료)
};
