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
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) { if ('focus' in c) return c.focus(); }   // 이미 열린 탭 포커스
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});

self.addEventListener('install', () => self.skipWaiting());           // 새 sw 즉시 활성
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
