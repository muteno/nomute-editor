// cscroll.js — 커스텀 오버레이 스크롤바(중립 *불투명* 다크 · 운영자 260626 초록→검정). 모바일 포함 전 플랫폼 동일 동작.
// ⚠️ thumb은 반드시 불투명(#23252b 등)일 것 — 반투명이면 도구 모달의 #tooldlg backdrop-filter:blur가 뒤 피드 초록을 비춰 thumb이 다시 초록으로 보임(5인 검증2 kill-test 확정). 거의 안보이되 비침 0.
// 왜: 모바일 webkit(iOS Safari·Android Chrome)은 네이티브 오버레이 스크롤바라
//     ::-webkit-scrollbar 커스터마이즈를 무시한다 → JS 오버레이로 통일(뉴스 요약기 톤 계승).
// 동작: 네이티브 스크롤바 숨김 + position:fixed 초록 thumb를 스크롤 위치에 맞춰 그림.
//       스크롤 가능할 때 상시 노출(idle 시 은은, 스크롤 중 밝게). pointer-events:none(터치 방해 X).
(function () {
  if (window.__cscroll) return; window.__cscroll = 1;
  var doc = document, root = doc.documentElement;

  var st = doc.createElement('style');
  st.textContent =
    'html{scrollbar-width:none;-ms-overflow-style:none;}' +
    'html::-webkit-scrollbar,body::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}' +
    '.cscroll{position:fixed;top:0;right:2px;width:10px;height:100%;z-index:99999;pointer-events:none;opacity:0;transition:opacity .3s;}' +
    '.cscroll.on{opacity:1;}' +
    '.cscroll i{position:absolute;right:2px;top:0;width:4px;min-height:24px;border-radius:999px;' +
    'background:#23252b;' +
    'transition:background .25s,width .15s;will-change:transform;}' +
    '.cscroll.act i{background:#3a3d44;width:5px;}' +
    '.cscroll.cscroll-el{position:absolute;}' +   // 요소 부착 모드 = 호스트 내 absolute(top/height는 update가 실측 주입 · fixed 금지 = top-layer·backdrop-filter 컨테이닝 함정 §디자인 h)
    '.cscroll-host{scrollbar-width:none;-ms-overflow-style:none;}' +
    '.cscroll-host::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}' +
    '@media (prefers-reduced-motion:reduce){.cscroll{transition:none;}}';
  (doc.head || root).appendChild(st);

  var bar = doc.createElement('div'); bar.className = 'cscroll';
  var thumb = doc.createElement('i'); bar.appendChild(thumb);

  function update() {
    var sh = root.scrollHeight,
        ch = window.innerHeight || root.clientHeight,
        sp = window.scrollY != null ? window.scrollY : root.scrollTop;
    if (sh <= ch + 2) { bar.classList.remove('on'); return; }   // 스크롤 불필요 = 숨김
    bar.classList.add('on');
    var th = Math.max(24, Math.min(64, ch * ch / sh));          // thumb 높이 = 화면비, 단 상한 64px 캡 = 짧은 알약(뉴스 요약처럼 · 운영자 260626)
    var top = (sp / (sh - ch)) * (ch - th);                     // thumb 위치 = 스크롤 진행
    thumb.style.height = th + 'px';
    thumb.style.transform = 'translateY(' + Math.round(top) + 'px)';
  }
  var actT;
  function onScroll() {
    update();
    bar.classList.add('act');
    clearTimeout(actT); actT = setTimeout(function () { bar.classList.remove('act'); }, 700);
  }
  function mount() { (doc.body || root).appendChild(bar); update(); }

  if (doc.body) mount(); else doc.addEventListener('DOMContentLoaded', mount);
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', update);
  window.addEventListener('load', update);
  try { new MutationObserver(update).observe(root, { childList: true, subtree: true, characterData: true }); } catch (e) {}
  setTimeout(update, 250); setTimeout(update, 800);   // 비동기 렌더(이미지·결과) 후 재측정

  // ── 요소 부착 모드(운영자 260713 "다 같게" — window가 아니라 내부 컨테이너가 스크롤하는 표면용 · 첫 사용처 = 프롬프팅 .geni-body) ──
  // 바 = 가까운 positioned 호스트(.genihost/dialog) 안 absolute(rect 실측 배치) · 부착 요소 네이티브 바 = .cscroll-host로 숨김
  // DOM 이식(팝업 #genidlg ↔ 탭 #geniHost)에도 update가 호스트 재귀속 · 시각·거동(24~64 알약·act 밝힘·불투명 다크)은 window 모드와 동일 상수.
  window.cscrollAttach = function (el) {
    if (!el || el.__cscrollEl) return; el.__cscrollEl = 1;
    el.classList.add('cscroll-host');
    var b = doc.createElement('div'); b.className = 'cscroll cscroll-el';
    var t = doc.createElement('i'); b.appendChild(t);
    function upd() {
      var host = el.closest('.genihost') || el.closest('dialog') || el.parentElement;
      if (!host) return;
      if (b.parentNode !== host) host.appendChild(b);
      var sh = el.scrollHeight, ch = el.clientHeight, sp = el.scrollTop;
      if (!el.offsetParent || sh <= ch + 2) { b.classList.remove('on'); return; }   // 숨김(display:none 체인)·스크롤 불필요 = 미표시
      var er = el.getBoundingClientRect(), hr = host.getBoundingClientRect();
      b.style.top = Math.round(er.top - hr.top) + 'px'; b.style.height = Math.round(er.height) + 'px';   // rect 차 = offsetParent 체인 무관 정확 배치
      b.classList.add('on');
      var th = Math.max(24, Math.min(64, ch * ch / sh));
      t.style.height = th + 'px';
      t.style.transform = 'translateY(' + Math.round((sp / (sh - ch)) * (ch - th)) + 'px)';
    }
    var aT;
    el.addEventListener('scroll', function () { upd(); b.classList.add('act'); clearTimeout(aT); aT = setTimeout(function () { b.classList.remove('act'); }, 700); }, { passive: true });
    window.addEventListener('resize', upd);
    doc.addEventListener('click', function () { setTimeout(upd, 60); }, true);   // 무변이 가시성 전환(탭 이식·팝업 열림) 재측정 — 캡처·경량(rect 산술뿐)
    try { new MutationObserver(upd).observe(el, { childList: true, subtree: true, characterData: true, attributes: true }); } catch (e) {}
    upd(); setTimeout(upd, 250); setTimeout(upd, 800);
  };
})();
