// nm-sync.js — 스튜디오 동기화 생명선 SSOT(운영자 260803 4차 "다른 스튜디오 탭에도 전부 상속 · 활성화 전환 시 갱신+동기화 자동")
// 상속 대상 = 이미지 스튜디오(thumb·tr) + 영상 스튜디오(edit·sb·k·song·vd) 전 탭 — <script src="nm-sync.js"> 한 줄이 계약(§3-5 레일 무조건 상속과 동축).
// 세 가지 일(전부 복귀·열림 시점 = "사용자가 뭐 입력하기 전에"):
//   ① 데이터 재동기 — 페이지가 노출한 window.nmRefresh(#toolRf 헤더 새로고침 훅 정본 · 260731)를 비활성→활성 전환 순간 자동 호출.
//   ② 로그인 만료 자가치유 — /manifest.json 프로브(redirect:'manual' · 정적 파일 = 서버 연산 0)로 Access 만료(opaqueredirect·401·403) 확정 시
//      최상위 '/?nosw=1' 자동 재진입(SW 우회 → 로그인 화면 · sw.js nm-auth-stale와 같은 착지 · iframe 내 로그인은 frame-ancestors로 백지라 반드시 top).
//      회선 사망(fetch reject) = 재진입 무익 → window.nmSyncWarn 훅(있으면 — thumb #status 경고줄)로만 알림.
//   ③ 신규 배포 자동 탑재 — 자기 문서 HEAD의 ETag/Last-Modified를 부팅값과 대조, 달라졌으면(=이 툴 파일이 재배포됨) 한가할 때 location.reload().
//      한가 판정 = 입력 포커스 없음 + window.nmSyncBusy?.() 아님(페이지별 훅 · thumb = 진행 중 잡). 바쁘면 다음 복귀로 이월(강제 이탈 0).
//      → 운영자 질문 "이게 되면 신규 개발분 반영(수동 재열기)도 없어도 되는가?" = 예(스튜디오 툴 한정 · index 셸은 기존 SW 토스트 계약 유지).
// 부하 = 복귀당 정적 요청 2건(manifest 프로브 + 자기 HEAD · 합계 수 KB)뿐 · 5s 코얼레싱 가드로 vis/focus/pageshow 연타 흡수 = 비활성화 타이밍 조정 불요.
// 가드 3중: 열림·복귀 15s 창(입력 중 강제 이탈 방지) · sessionStorage 3분(재진입 루프 차단) · 리로드는 버전 실변경+한가 시만.
(function () {
  'use strict';
  let visTs = Date.now();          // 마지막 열림·복귀 시각 — 자가치유 발동 창(15s)의 기준
  let lastKick = 0;                // 복귀 처리 코얼레싱(visibilitychange+focus+pageshow 동시 발화 = 1회 처리)
  let probing = false, bootTag = null, tagInflight = false;
  const TAG = r => (r && (r.headers.get('etag') || r.headers.get('last-modified'))) || '';   // 배포 감지 앵커 — Pages 정적 서빙 ETag(내용 바뀌면 반드시 변함)
  async function selfTag() {   // 자기 문서 HEAD — 부팅 기준값 채집·복귀 대조 공용(경로 = 쿼리 제거 자기 자신 · v=Date.now() 버스트와 무관하게 같은 파일)
    try { const r = await fetch(location.pathname, { method: 'HEAD', cache: 'no-store' }); return r.ok ? TAG(r) : null; } catch (_) { return null; }
  }
  const busy = () => {   // 리로드 한가 판정 — 입력 중(활성 포커스가 입력칸)이거나 페이지가 바쁨을 선언하면 미룸
    try { if (typeof window.nmSyncBusy === 'function' && window.nmSyncBusy()) return true; } catch (_) {}
    const a = document.activeElement; return !!(a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA' || a.isContentEditable));
  };
  async function probeNow() {   // ② 로그인 만료 판별 + 자동 재진입(thumb 3차 인라인의 SSOT 승격 — 프로브만 정적 manifest로 교체 = 서버 연산 0)
    if (probing) return; probing = true;
    try {
      const r = await fetch('/manifest.json?_=' + Date.now(), { redirect: 'manual', cache: 'no-store' });
      if (r.type === 'opaqueredirect' || r.status === 401 || r.status === 403 || (r.status >= 300 && r.status < 400)) {   // 3xx 명시 = 인터셉트 환경(스모크) 겸용
        let last = 0; try { last = +sessionStorage.getItem('nm_sync_heal') || 0; } catch (_) {}
        if (Date.now() - visTs < 15e3 && Date.now() - last > 180e3) {
          try { sessionStorage.setItem('nm_sync_heal', String(Date.now())); } catch (_) {}
          console.log('[nm-sync] 자가치유 — 로그인 만료 감지 · 최상위 재진입(?nosw=1)');   // 계측(CLAUDE.md [관측])
          try { window.top.location.href = '/?nosw=1'; } catch (_) { location.reload(); }
          return;
        }
        try { if (typeof window.nmSyncWarn === 'function') window.nmSyncWarn('auth'); } catch (_) {}   // 가드에 걸림 = 페이지 경고줄 폴백
      } else if (!r.ok && r.status) { try { if (typeof window.nmSyncWarn === 'function') window.nmSyncWarn('srv'); } catch (_) {} }
    } catch (_) { try { if (typeof window.nmSyncWarn === 'function') window.nmSyncWarn('net'); } catch (_) {} /* 회선 사망 = 재진입 무익 */ }
    finally { probing = false; }
  }
  async function verCheck() {   // ③ 신규 배포 자동 탑재 — 부팅 ETag 대비 변경 + 한가하면 즉시 새 코드 리로드(운영자 260803 "신규 개발분 반영도 없어도 되는가" = 예 축)
    if (tagInflight || bootTag == null) return; tagInflight = true;
    try {
      const now = await selfTag();
      if (now && bootTag && now !== bootTag) {
        if (busy()) { console.log('[nm-sync] 새 배포 감지 — 작업 중이라 이월(다음 복귀 때 재시도)'); return; }
        console.log('[nm-sync] 새 배포 감지 — 자동 리로드로 신규 코드 탑재');   // 계측 — 조용한 리로드 금지
        location.reload();
      }
    } finally { tagInflight = false; }
  }
  function resumeNow() {   // ①+②+③ — 비활성→활성 전환의 단일 진입점(테스트 훅 겸용)
    const t = Date.now(); if (t - lastKick < 5e3) return; lastKick = t;   // 5s 코얼레싱 = vis/focus/pageshow 동시 발화 1회 처리(부하 제로화)
    visTs = t;
    try { if (typeof window.nmRefresh === 'function') window.nmRefresh(); } catch (_) {}   // ① 동기화 내용 자동 반영(서버 인덱스 재fetch — 각 툴 정본 훅)
    probeNow();                                                                            // ② 로그인 만료면 여기서 자동 재진입
    verCheck();                                                                            // ③ 새 코드 있으면(한가 시) 자동 탑재
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) resumeNow(); });
  window.addEventListener('focus', () => resumeNow());
  window.addEventListener('pageshow', e => { if (e.persisted) { lastKick = 0; resumeNow(); } });   // iOS PWA bfcache 복귀 = vis 미발화 경로 · 가드 해제 = 확실 재처리
  selfTag().then(t => { bootTag = t; });   // 부팅 기준값(실패 = null → 버전 감지 비활성 · 프로브·재동기는 무영향)
  probeNow();   // 열림 즉시 확인(운영자 260803 "창이 열릴 때 그거부터 확인") — focus 미발화 열림(iframe 백그라운드 로드)도 로그인 만료면 바로 재진입 · 데이터 재fetch는 각 페이지 부팅 로직 몫(중복 0)
  window.nmSync = { probeNow, resumeNow, verCheck };   // 페이지 위임(thumb 생명선 카운터)·테스트 훅
})();
