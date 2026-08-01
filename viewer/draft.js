/* 작성 중 입력 드래프트 보존 SSOT — 30분 만료 전역 통일(운영자 260801 "30분 만료를 전역에 유지").
   정본 원본 = viewer/thumb.html `nomute_thumb_draft`(DRAFT_MS 30분 · 260706 "약 5분+ 여유 상회·반나절 전
   잔재 오염은 차단")의 만료 패턴을 전 뷰어 공용으로 승격. 상수 복제 대신 이 파일이 유일한 30분 정의다.
   왜: AI 생성 주문칸(GENI_FREE_TXT)·k/sb 장면 입력은 만료가 없어 *한 달 전 테스트 문구*가 그대로 복원됐다
   (실측 260801 — 운영자 "예전에 적어 놓은 바나나가 그대로"). 드래프트의 용도 = 실수 이탈·페이지 킬 복구지
   영구 보관이 아니라 thumb과 같은 30분 창을 전 입력에 건다.
   API:
     · window.NM_DRAFT_MS            — 30분(ms). 자체 페이로드를 쓰는 곳(thumb 탭별 통)은 이 상수만 참조.
     · nmDraftSave(key, val)         — {v,ts} 봉투로 저장(val = 문자열·객체 무관). 빈 값 저장도 '의도'라 그대로 보존.
     · nmDraftLoad(key) → val | null — 30분 이내만 반환. 만료·파손 = 조용히 폐기 + 키 삭제.
   ⚠ 구 형식(ts 없는 raw 문자열·{wish} 객체)은 만료 취급 = 기존 잔재가 첫 로드에서 1회 자연 소멸(의도).
   비대상(입력물 아님 = 선호·설정 축이라 영속 유지): GENI_OPTS2 · k_form2 · sb_form · k_refimg 등 선택 스냅샷.
   ⚠ 파일명에 `nm-` 접두어를 안 붙인 이유 = 디자인기틀_SSOT §0-17 명명 규칙 — `nm-*.js`는 **디자인 SSOT 공유
   부품**(nm-svg 도형·nm-loader 로딩 표기) 탐지 키이고, 이 파일은 시각 산출 0인 **순수 동작 유틸**이라
   cscroll.js·upload.js와 같은 별개 축이다(§0-17 명문). */
(function (g) {
  'use strict';

  var MS = 30 * 60e3;   // 30분 — thumb DRAFT_MS 계승(값 창작 아님)
  g.NM_DRAFT_MS = MS;

  g.nmDraftSave = function (key, val) {
    try { localStorage.setItem(key, JSON.stringify({ v: val, ts: Date.now() })); } catch (e) {}   // 저장 실패(용량·프라이빗) = 조용히 포기(드래프트는 부가기능 · thumb 선례)
  };

  g.nmDraftLoad = function (key) {
    var d = null;
    try { d = JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) { d = null; }
    if (!d || typeof d !== 'object' || !(Date.now() - (d.ts || 0) <= MS)) {   // 없음·파손·구형식(ts 0)·만료 = 폐기
      try { localStorage.removeItem(key); } catch (e) {}
      return null;
    }
    return d.v;
  };
})(window);
