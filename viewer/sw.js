// 노뮤트 서비스워커 — ① 긴급(breaking) 속보 웹푸시 수신·표시 ② HTML 셸 stale-while-revalidate 캐시.
// 발송 = .github/scripts/push_send.py(pywebpush) / 구독 = api/push. 정본 설명 = CLAUDE.md §🚨·§8-5.
//
// ── ② 셸 캐시(운영자 승인 260706 — OS 스플래시 노출 최단화 · 기틀검증 5인 260706) ──
// 뷰어 index 셸(/·/index.html) 최상위 내비게이션*만* 캐시-우선 + 백그라운드 재검증: 콜드부트 첫 페인트가
// 네트워크 대기 없이 즉시 = WebAPK 스플래시가 한 깜빡으로 줄어듦.
// ⚠️ 스코프 = index 두 경로 화이트리스트가 기틀(평의회 1·2·4·5 수렴): 도구 HTML(thumb/ly/k/comp/track)은
//    loadToolFrame의 `?v=Date.now()` 버스트 + _headers no-cache = '항상 최신' 계약이라 절대 캐시 대상 아님
//    (전 내비게이션 캐시였던 초안이 이 계약을 무력화 → REJECT·수정). 스코프 넓히기 = 기틀 변경(재검증 필수).
// 트레이드(운영자 수용): index 셸 = 인라인 앱 JS 포함 통째로 배포 후 첫 진입이 직전판(백그라운드 갱신 →
//    다음 진입 반영 · 당겨서 새로고침도 SWR = 즉시 새 셸 아님). 데이터 JSON(articles 등)·외부 JS·이미지는
//    fetch(비내비게이션)라 SW 불간섭 = 기사 내용 '항상 최신' 불변.
// 가드 3중: ⓐ res.type==='basic' && ok && !redirected만 캐시 = Cloudflare Access 로그인/리다이렉트 오염 차단
//          ⓑ ?nosw=1 = 캐시 전면 우회 탈출구(순수 네트워크)
//          ⓒ 재검증이 리다이렉트/401·403 감지 시 클라이언트에 nm-auth-stale 통지 → 페이지가 ?nosw=1 재진입
//             = Access 세션 만료 시 '깨진 앱'에 안 갇히고 로그인 화면으로 자가치유(index 리스너와 한 쌍).
// 롤백 런북(평의회 4): sw.js *삭제(404) 금지* — 삭제해도 브라우저는 기존 SW를 언레지스터하지 않고 캐시 서빙
//    계속함. 반드시 '무해화 sw.js 배포'(fetch 핸들러 제거 + activate에서 nm-shell-* *전량* delete)로 되돌릴 것.
const SHELL_CACHE = 'nm-shell-v1';
const SHELL_PATHS = ['/', '/index.html'];   // 캐시 화이트리스트 — 여기 없는 HTML은 SW가 손 안 댐

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET' || req.mode !== 'navigate') return;   // 최상위/iframe HTML 문서 외 불간섭
  const url = new URL(req.url);
  if (url.origin !== self.location.origin || !SHELL_PATHS.includes(url.pathname) || url.searchParams.has('nosw')) return;
  event.respondWith((async () => {
    const key = url.origin + url.pathname;   // 쿼리 제거 정규화 = 딥링크(?a=·?msg=) 변형이 캐시를 늘리지도 가르지도 않음
    const cache = await caches.open(SHELL_CACHE);
    const cached = await cache.match(key);
    const cachedClone = cached ? cached.clone() : null;   // 새버전 감지(본문 폴백)용 = 반환 전 클론(스트림 락 회피 · text()는 필요 시만)
    const netP = fetch(req).then(async res => {
      if (res.ok && !res.redirected && res.type === 'basic') {
        let changed = false;   // 새 index 셸 배포 감지(옛≠새) → 열린 페이지에 nm-shell-updated 통지(운영자 260717 새버전 토스트)
        if (cached) {
          const norm = e => (e || '').replace(/^W\//, '');   // 약(W/)·강 ETag 정규화 = Cloudflare 압축·PoP별 W/ 변이가 같은 바이트를 '다름'으로 오판하는 것 차단(평의회 260717)
          const scrub = s => (s || '').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, m => (/cdn-cgi|cloudflareinsights/i.test(m) ? '' : m));   // 엣지 주입 노이즈 소거(운영자 260717 무한루프 실기록) — Cloudflare가 응답마다 다르게 심는 스크립트(RUM beacon rayId·챌린지 토큰)를 비교에서 제외. 같은 셸인데 주입 토큰만 달라 '다름' 오판 → 반영 탭 직후 또 "새 버전" 무한 재알림의 근원 차단(앱 자체 스크립트는 cdn-cgi·cloudflareinsights 문자열 0 = 소거 비대상)
          const oe = norm(cached.headers.get('etag')), ne = norm(res.headers.get('etag'));
          if (oe && ne && oe === ne) changed = false;   // ETag 동일 = 확실히 동일 = 빠른 경로(본문 안 읽음)
          else { const [a, b] = await Promise.all([cachedClone.text().catch(() => null), res.clone().text().catch(() => null)]); changed = a != null && b != null && scrub(a) !== scrub(b); }   // ETag 다르거나 없으면 본문(주입 노이즈 소거 후)으로 최종 확인 = 오탐 차단(실배포 때만 본문 읽음)
        }
        await cache.put(key, res.clone()).then(() => {}, () => {});   // put을 체인에 태움 = waitUntil 수명 안(쓰기 유실 차단·평의회 1) · 실패(quota 등)해도 진행 = 정상 응답 폐기 안 함
        if (changed) self.clients.matchAll({ type: 'window' }).then(list => list.forEach(c => c.postMessage({ type: 'nm-shell-updated' })));   // 갱신 완료 후 통지 = 탭→reload가 새 셸 서빙 보장
        return res;
      }
      if (cached && (res.redirected || res.type === 'opaqueredirect' || res.status === 401 || res.status === 403)) {
        // Access 세션 만료 추정 — 캐시는 안 덮고(로그인 페이지 오염 방지) 열린 페이지에 통지
        self.clients.matchAll({ type: 'window' }).then(list => list.forEach(c => c.postMessage({ type: 'nm-auth-stale' })));
      }
      return res;
    });
    if (cached) { event.waitUntil(netP.catch(() => {})); return cached; }   // 캐시 즉시 응답 + 뒤에서 갱신
    return netP.catch(() => Response.error());                              // 첫 방문 = 네트워크 그대로
  })());
});
self.addEventListener('push', event => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch { d = { body: event.data && event.data.text() }; }
  const title = d.title || '🚨 긴급 속보';
  const opts = {
    body: d.body || '',
    icon: d.icon || '/assets/brand/icon-192-260706c.png',   // c판 = 웨이브 질감+워드마크(스플래시 연속 설계 · 260706 5차)
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

// 구독 로테이션 자가치유(운영자 260707 "ON 해놔도 어느 순간 OFF") — 브라우저(FCM)가 push 구독을 만료·교체하면
//   이 이벤트가 오는데 미처리 시 구독이 조용히 죽어 다음 진입 때 OFF로 보임(표준 원인). 여기서 즉시 재구독+서버 저장.
//   VAPID_PUB = index.html:VAPID_PUB와 짝(키 교체 시 두 곳 동시 갱신).
const VAPID_PUB = 'BORNTh3cNd05vsxi2fZ-BykxM0NwKGTvIETz81g757RVFL6cDu29aAv5I7uit0WbGOmiZ4hlyMOEvb8B2HptU-I';
function b64ToU8(s) {
  const pad = '='.repeat((4 - s.length % 4) % 4);
  const raw = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/'));
  const u8 = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) u8[i] = raw.charCodeAt(i);
  return u8;
}
self.addEventListener('pushsubscriptionchange', event => {
  event.waitUntil((async () => {
    try {
      const sub = await self.registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToU8(VAPID_PUB) });
      await fetch('api/push', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ action: 'subscribe', subscription: sub.toJSON() }) });
      const old = event.oldSubscription;   // 옛 endpoint = 서버에서 정리(죽은 구독 잔존 방지 · 미지원 브라우저면 undefined = 스킵)
      if (old) await fetch('api/push', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ action: 'unsubscribe', subscription: old.toJSON() }) }).catch(() => {});
    } catch (e) { /* 재구독 실패(권한 회수 등) = 다음 앱 진입 시 pushHeal이 재시도 */ }
  })());
});

self.addEventListener('install', () => self.skipWaiting());           // 새 sw 즉시 활성
self.addEventListener('activate', event => event.waitUntil((async () => {
  const keys = await caches.keys();                                    // 구버전 셸 캐시 청소(SHELL_CACHE 버전업 대비)
  await Promise.all(keys.filter(k => k.startsWith('nm-shell-') && k !== SHELL_CACHE).map(k => caches.delete(k)));
  await self.clients.claim();
})()));
