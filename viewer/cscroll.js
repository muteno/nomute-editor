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
})();
