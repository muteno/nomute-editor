// 노뮤트 푸시 서비스워커 — 긴급(breaking) 속보 웹푸시 수신·표시. scope=/(루트·sw.js가 루트라 기본 scope).
// 발송 = .github/scripts/push_send.py(pywebpush) / 구독 = api/push. 정본 설명 = CLAUDE.md §🚨.
self.addEventListener('push', event => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch { d = { body: event.data && event.data.text() }; }
  const title = d.title || '🚨 긴급 속보';
  const opts = {
    body: d.body || '',
    icon: d.icon || '/assets/brand/icon-192.png',
    badge: d.badge || '/assets/brand/badge.png',   // 상태바 배지 = 흑백+투명 실루엣(N) — 불투명 컬러는 안드로이드가 흰 네모로 칠함
    tag: d.tag || 'nomute-breaking',          // 같은 tag = 교체(중복 알림 안 쌓임)
    data: { url: d.url || '/' },
    lang: 'ko',
  };
  event.waitUntil(self.registration.showNotification(title, opts));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const raw = (event.notification.data && event.notification.data.url) || '/';
  const target = new URL(raw, self.location.origin);   // 알림이 가리키는 화면(제작완료=/thumb.html#done · 긴급=/)
  event.waitUntil((async () => {
    const list = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    // 1) 이미 타깃 화면(경로+쿼리+해시 일치)에 있는 탭이면 그냥 포커스(불필요한 새로고침 방지).
    //    ⚠️ 쿼리(search)까지 비교해야 함 — 요약 딥링크(/?a=stem)는 쿼리가 유일 구별자라, 쿼리 무시 시
    //    루트(/)에 열린 탭이 '일치'로 오판돼 focus만 하고 navigate를 안 해 딥링크가 안 열렸음(분신술 2번 발견).
    for (const c of list) {
      try { const u = new URL(c.url); if (u.pathname === target.pathname && u.search === target.search && u.hash === target.hash && 'focus' in c) return c.focus(); } catch (_) {}
    }
    // 2) 열린 탭이 있으면 그 탭을 타깃으로 *이동*시켜 제작 화면을 보여줌(과거: 무조건 포커스만 → 옛 화면/모달에 머묾)
    for (const c of list) {
      if ('navigate' in c && 'focus' in c) {
        try { const nc = await c.navigate(target.href); return (nc || c).focus(); } catch (_) { /* navigate 불가 → 새 창 폴백 */ }
      }
    }
    // 3) 열린 탭 없음 → 새 창
    if (self.clients.openWindow) return self.clients.openWindow(target.href);
  })());
});

self.addEventListener('install', () => self.skipWaiting());           // 새 sw 즉시 활성
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
