/* nomute 로더 팩토리 — yeulmaru-promo/docs/reports/260707_로더픽토그램_플레이그라운드.html 의 mkLoader 이식·복제(beui 17종 바닐라).
   · 색 = 부모 color 상속(= var(--accent) 터쿼이즈 계승, "강조색만 노뮤트") · 기본 로딩 표시 = dots(.nmld).
   · API:  window.mkLoader(variant, size, speed, ease) → DOM 노드(17종)  ·  window.nmLoaderHTML({size,label}) → dots HTML 문자열(innerHTML 컨텍스트용).
   · 라이브러리 불요(CSS keyframes + SMIL 모프 + JS 인터벌) · reduced-motion 가드 · .nmld/키프레임 CSS 1회 자체주입(#nmld-css 가드). */
(function () {
  var EASE = 'var(--ease,cubic-bezier(.2,.7,.3,1))';   // 노뮤트 모션 커브 계승(프로모 beui 신규 커브 대신)

  /* ── 공유 CSS 1회 주입(.nmld 도트 + 17종 keyframes) ── */
  if (!document.getElementById('nmld-css')) {
    var css = ''
      + '.nmld{--sz:7px;--gap:5px;--bnc:-6px;display:inline-flex;align-items:center;justify-content:center;gap:var(--gap,5px);line-height:0;color:var(--accent)}'
      + '.nmld i{width:var(--sz,7px);height:var(--sz,7px);border-radius:50%;background:currentColor;animation:nmldBounce .9s ' + EASE + ' infinite}'
      + '.nmld i:nth-child(2){animation-delay:.15s}.nmld i:nth-child(3){animation-delay:.3s}'
      + '@keyframes nmldBounce{0%,100%{transform:translateY(0);opacity:.5}50%{transform:translateY(var(--bnc,-6px));opacity:1}}'
      + '.ld-host{display:inline-flex;align-items:center;justify-content:center;line-height:0}'
      + '.ld-mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-variant-numeric:tabular-nums;line-height:1}'
      + '@keyframes ldRot{to{transform:rotate(360deg)}}'
      + '@keyframes ldBars{0%,100%{transform:scaleY(.3)}50%{transform:scaleY(1)}}'
      + '@keyframes ldMx{0%,100%{opacity:.2;transform:scale(.7)}50%{opacity:1;transform:scale(1)}}'
      + '@keyframes ldDit{0%,100%{opacity:.1}50%{opacity:1}}'
      + '@keyframes ldMbA{0%,100%{cx:30px}50%{cx:70px}}'
      + '@keyframes ldMbB{0%,100%{cx:70px}50%{cx:30px}}'
      + '@keyframes ldNwL{0%{transform:translateX(0)}28%{transform:translateX(var(--nx))}50%,100%{transform:translateX(0)}}'
      + '@keyframes ldNwR{0%,50%{transform:translateX(0)}78%{transform:translateX(var(--nxr))}100%{transform:translateX(0)}}'
      + '@keyframes ldHxA{0%,100%{transform:translateX(var(--amp)) scale(1);opacity:1}50%{transform:translateX(var(--ampN)) scale(.5);opacity:.45}}'
      + '@keyframes ldHxB{0%,100%{transform:translateX(var(--ampN)) scale(.5);opacity:.45}50%{transform:translateX(var(--amp)) scale(1);opacity:1}}'
      + '@keyframes ldMorphT{0%,10%{transform:rotate(0deg) scale(1)}20%,30%{transform:rotate(72deg) scale(.88)}40%,50%{transform:rotate(144deg) scale(1)}60%,70%{transform:rotate(216deg) scale(.88)}80%,90%{transform:rotate(288deg) scale(1)}100%{transform:rotate(360deg) scale(1)}}'
      + '@media (prefers-reduced-motion:reduce){.nmld i{animation:none;opacity:.6}.ld-host *{animation:none!important}}';
    var st = document.createElement('style'); st.id = 'nmld-css'; st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  }

  /* ── dots HTML 문자열(innerHTML 컨텍스트용) — size = 도트 지름(px) ── */
  window.nmLoaderHTML = function (o) {
    o = o || {}; var s = o.size || 7, g = Math.max(2, Math.round(s * 0.72)), b = -Math.max(3, Math.round(s * 0.86));
    return '<span class="nmld" role="status" aria-label="' + (o.label || '불러오는 중')
      + '" style="--sz:' + s + 'px;--gap:' + g + 'px;--bnc:' + b + 'px"><i></i><i></i><i></i></span>';
  };

  /* ── 팩토리 세부(promo 원본 파라미터 그대로 이식) ── */
  var ASCII_SETS = {
    'ascii': ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏'],
    'ascii-line': ['|','/','-','\\'],
    'ascii-braille': ['⣾','⣽','⣻','⢿','⡿','⣟','⣯','⣷'],
    'ascii-blocks': ['▁','▂','▃','▄','▅','▆','▇','█','▇','▆','▅','▄','▃','▂'],
    'ascii-bounce': ['⠁','⠂','⠄','⡀','⢀','⠠','⠐','⠈']
  };
  var BAYER4 = [0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5];
  var MORPH_POINTS = 24;
  function ngonRadius(ang, n, phase) { phase = phase || 0; var seg = 2 * Math.PI / n; var a = ang - phase; var local = (((a % seg) + seg) % seg) - seg / 2; return Math.cos(Math.PI / n) / Math.cos(local); }
  function morphPath(radiusAt) { var parts = []; for (var i = 0; i < MORPH_POINTS; i++) { var ang = (i / MORPH_POINTS) * 2 * Math.PI - Math.PI / 2; var r = Math.min(1.05, radiusAt(ang)); var x = (50 + Math.cos(ang) * 46 * r).toFixed(2), y = (50 + Math.sin(ang) * 46 * r).toFixed(2); parts.push((i === 0 ? 'M' : 'L') + x + ' ' + y); } return parts.join(' ') + ' Z'; }
  var MORPH_PATHS = [morphPath(function () { return 1; }), morphPath(function (a) { return ngonRadius(a, 4, Math.PI / 4); }), morphPath(function (a) { return ngonRadius(a, 3); }), morphPath(function (a) { return ngonRadius(a, 6); }), morphPath(function (a) { return ngonRadius(a, 4); })];
  var MORPH_SEQ = []; MORPH_PATHS.forEach(function (p) { MORPH_SEQ.push(p, p); }); MORPH_SEQ.push(MORPH_PATHS[0]);
  var SVGNS = 'http://www.w3.org/2000/svg';
  function svgEl(t, at) { var e = document.createElementNS(SVGNS, t); for (var k in at) e.setAttribute(k, at[k]); return e; }
  function dotsNode(diam) { var s = diam || 7, g = Math.max(2, Math.round(s * 0.72)), b = -Math.max(3, Math.round(s * 0.86)); var h = document.createElement('span'); h.className = 'nmld'; h.style.cssText = '--sz:' + s + 'px;--gap:' + g + 'px;--bnc:' + b + 'px'; h.innerHTML = '<i></i><i></i><i></i>'; return h; }

  window.mkLoader = function (v, size, speed, ease) {
    size = size || 24; speed = speed || 1; ease = ease || EASE;
    var s = size, sp = speed, i;
    if (v === 'dots' || !v) return dotsNode(Math.max(5, Math.round(s * 0.29)));   // 기본 = .nmld 도트(약 s*.24 지름 근사)
    var h = document.createElement('span'); h.className = 'ld-host';
    if (v === 'spinner') {
      var stw = Math.max(2, s * .09), r = (s - stw) / 2;
      var sv = svgEl('svg', { width: s, height: s, viewBox: '0 0 ' + s + ' ' + s }); sv.style.cssText = 'animation:ldRot ' + sp + 's linear infinite';
      sv.appendChild(svgEl('circle', { cx: s / 2, cy: s / 2, r: r, fill: 'none', stroke: 'currentColor', 'stroke-opacity': '0.2', 'stroke-width': stw }));
      sv.appendChild(svgEl('path', { d: 'M ' + (s / 2) + ' ' + (s / 2 - r) + ' A ' + r + ' ' + r + ' 0 0 1 ' + (s / 2 + r) + ' ' + (s / 2), fill: 'none', stroke: 'currentColor', 'stroke-width': stw, 'stroke-linecap': 'round' }));
      h.appendChild(sv);
    } else if (v === 'bars') {
      var bw = s * .16; h.style.cssText += 'gap:' + (s * .1) + 'px;height:' + s + 'px';
      for (i = 0; i < 4; i++) { var b2 = document.createElement('span'); b2.style.cssText = 'width:' + bw + 'px;height:' + s + 'px;border-radius:999px;background:currentColor;transform-origin:center bottom;animation:ldBars ' + sp + 's ' + ease + ' ' + (i * sp * .12) + 's infinite'; h.appendChild(b2); }
    } else if (v === 'dot-matrix') {
      var g2 = s * .14, dm = (s - g2 * 2) / 3; h.style.cssText += 'display:grid;grid-template-columns:repeat(3,' + dm + 'px);gap:' + g2 + 'px';
      for (i = 0; i < 9; i++) { var x = i % 3, y = Math.floor(i / 3), dl = ((x + y) / 4) * sp; var c = document.createElement('span'); c.style.cssText = 'width:' + dm + 'px;height:' + dm + 'px;border-radius:50%;background:currentColor;animation:ldMx ' + sp + 's ' + ease + ' ' + dl + 's infinite'; h.appendChild(c); }
    } else if (v === 'dither') {
      var gp = Math.max(1, s * .05), cl = (s - gp * 3) / 4; h.style.cssText += 'display:grid;grid-template-columns:repeat(4,' + cl + 'px);gap:' + gp + 'px';
      BAYER4.forEach(function (ord) { var c = document.createElement('span'); c.style.cssText = 'width:' + cl + 'px;height:' + cl + 'px;background:currentColor;animation:ldDit ' + sp + 's ' + ease + ' ' + ((ord / 16) * sp) + 's infinite'; h.appendChild(c); });
    } else if (v === 'morph') {
      var sv2 = svgEl('svg', { width: s, height: s, viewBox: '0 0 100 100' }); var p = svgEl('path', { fill: 'currentColor', d: MORPH_PATHS[0] });
      p.style.cssText = 'transform-box:fill-box;transform-origin:center;animation:ldMorphT ' + (sp * 5) + 's ' + ease + ' infinite';
      var kt = [], ks = []; for (i = 0; i <= 10; i++) kt.push((i / 10).toFixed(1)); for (i = 0; i < 10; i++) ks.push('0.4 0 0.2 1');
      var an = svgEl('animate', { attributeName: 'd', values: MORPH_SEQ.join(';'), keyTimes: kt.join(';'), dur: (sp * 5) + 's', repeatCount: 'indefinite', calcMode: 'spline', keySplines: ks.join(';') });
      p.appendChild(an); sv2.appendChild(p); h.appendChild(sv2);
    } else if (v === 'comet') {
      var head = s * .2, r2 = s / 2 - head / 2; var rot = document.createElement('span'); rot.style.cssText = 'position:relative;display:block;width:' + s + 'px;height:' + s + 'px;animation:ldRot ' + sp + 's linear infinite';
      for (i = 0; i < 6; i++) { var sc = 1 - i * .13, sz = head * sc; var t = document.createElement('span'); t.style.cssText = 'position:absolute;top:50%;left:50%;width:' + sz + 'px;height:' + sz + 'px;border-radius:50%;background:currentColor;margin-left:' + (-sz / 2) + 'px;margin-top:' + (-sz / 2) + 'px;opacity:' + (1 - i * .16) + ';transform:rotate(' + (-i * 15) + 'deg) translateY(' + (-r2) + 'px)'; rot.appendChild(t); }
      h.appendChild(rot);
    } else if (v === 'metaballs') {
      var id = 'mb' + Math.floor(Math.random() * 1e9);
      var sv3 = svgEl('svg', { width: s, height: s, viewBox: '0 0 100 100' }); var df = svgEl('defs', {}), fl = svgEl('filter', { id: id });
      fl.appendChild(svgEl('feGaussianBlur', { 'in': 'SourceGraphic', stdDeviation: '5', result: 'b' }));
      fl.appendChild(svgEl('feColorMatrix', { 'in': 'b', values: '1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -8' }));
      df.appendChild(fl); sv3.appendChild(df);
      var gr = svgEl('g', { filter: 'url(#' + id + ')', fill: 'currentColor' }); var c1 = svgEl('circle', { cy: '50', r: '15', cx: '30' }), c2 = svgEl('circle', { cy: '50', r: '15', cx: '70' });
      c1.style.cssText = 'animation:ldMbA ' + (sp * 1.6) + 's ' + ease + ' infinite'; c2.style.cssText = 'animation:ldMbB ' + (sp * 1.6) + 's ' + ease + ' infinite';
      gr.appendChild(c1); gr.appendChild(c2); sv3.appendChild(gr); h.appendChild(sv3);
    } else if (v === 'newton') {
      var d2 = s * .2, out2 = d2 * 1.1; h.style.height = d2 + 'px';
      for (i = 0; i < 5; i++) { var bl = document.createElement('span'); var base = 'width:' + d2 + 'px;height:' + d2 + 'px;border-radius:50%;background:currentColor;'; if (i === 0) base += '--nx:' + (-out2) + 'px;animation:ldNwL ' + (sp * 1.5) + 's ' + ease + ' infinite'; if (i === 4) base += '--nxr:' + out2 + 'px;animation:ldNwR ' + (sp * 1.5) + 's ' + ease + ' infinite'; bl.style.cssText = base; h.appendChild(bl); }
    } else if (v === 'helix') {
      var rows = 7, dt = s * .14, amp = s * .32; var rl = document.createElement('span'); rl.style.cssText = 'position:relative;display:block;width:' + s + 'px;height:' + s + 'px';
      for (i = 0; i < rows; i++) { var top = (i / (rows - 1)) * (s - dt), dl2 = (i / rows) * sp;['A', 'B'].forEach(function (k) { var dd = document.createElement('span'); dd.style.cssText = 'position:absolute;width:' + dt + 'px;height:' + dt + 'px;border-radius:50%;background:currentColor;left:' + (s / 2 - dt / 2) + 'px;top:' + top + 'px;--amp:' + amp + 'px;--ampN:' + (-amp) + 'px;animation:ldHx' + k + ' ' + sp + 's ' + ease + ' ' + dl2 + 's infinite'; rl.appendChild(dd); }); }
      h.appendChild(rl);
    } else if (v === 'scramble') {
      var TG = 'LOADING', GL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<>/*#@'; var sp1 = document.createElement('span'); sp1.className = 'ld-mono'; sp1.style.cssText = 'font-weight:500;letter-spacing:.2em;font-size:' + (s * .42) + 'px'; sp1.textContent = TG; h.appendChild(sp1);
      var tick = 0, total = TG.length + 4; var iv = setInterval(function () { if (!document.body.contains(h)) { clearInterval(iv); return; } var rev = tick % total, out = ''; for (var j = 0; j < TG.length; j++) out += j < rev ? TG[j] : GL[Math.floor(Math.random() * GL.length)]; sp1.textContent = out; tick++; }, (sp / TG.length) * 1000 * .55);
    } else if (v === 'percent') {
      var wrap = document.createElement('span'); wrap.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:' + (s * .14) + 'px;width:' + (s * 1.4) + 'px'; var num = document.createElement('span'); num.className = 'ld-mono'; num.style.cssText = 'font-weight:500;font-size:' + (s * .42) + 'px'; num.textContent = '0%'; var tr = document.createElement('span'); tr.style.cssText = 'width:100%;overflow:hidden;border-radius:999px;height:' + Math.max(3, s * .1) + 'px;position:relative;background:transparent'; var trBg = document.createElement('span'); trBg.style.cssText = 'position:absolute;inset:0;background:currentColor;opacity:.15;border-radius:999px'; var fill = document.createElement('span'); fill.style.cssText = 'position:absolute;left:0;top:0;bottom:0;width:0%;background:currentColor;border-radius:999px'; tr.appendChild(trBg); tr.appendChild(fill); wrap.appendChild(num); wrap.appendChild(tr); h.appendChild(wrap);
      var t2 = 0, dur = sp * 1000; var iv2 = setInterval(function () { if (!document.body.contains(h)) { clearInterval(iv2); return; } t2 += 40; var nx = Math.min(100, Math.round(t2 / dur * 100)); num.textContent = nx + '%'; fill.style.width = nx + '%'; if (nx >= 100) t2 = 0; }, 40);
    } else if (ASCII_SETS[v]) {
      var fr = ASCII_SETS[v], f0 = 0; var sp2 = document.createElement('span'); sp2.className = 'ld-mono'; sp2.style.cssText = 'font-size:' + s + 'px'; sp2.textContent = fr[0]; h.appendChild(sp2);
      var iv3 = setInterval(function () { if (!document.body.contains(h)) { clearInterval(iv3); return; } f0 = (f0 + 1) % fr.length; sp2.textContent = fr[f0]; }, (sp / fr.length) * 1000);
    } else {
      return dotsNode(Math.max(5, Math.round(s * 0.29)));   // 미지 variant = dots 폴백
    }
    return h;
  };
})();

/* ══ orb 로더(운영자 260723 승인 시안 v3 · Q459/Q460 → 260731 도트 단일화) — 앱 전반 로딩 표기 SSOT ══
   · 매핑 = Now loading(데이터 불러오는 중) · Thinking(요약·분석·큐레이션·2차수정 판단) · Solving(영상 편집·변환·렌더·이미지·음원 산출·재수정) · Prompting(프롬프팅·콘티 설계)
   · 【260731 그래픽 단일화 = 운영자 "솔빙 이런 것들 다 점 3개 통통 튀는 로딩 그래픽으로"】 4종 **전부 통통 튀는 도트3** 렌더.
     구 소용돌이 링(thinking·prompting)·흩뿌린 입자(solving)는 폐지 — 로딩 그래픽이 화면마다 달라 보이던 것을 1종으로 통일.
     type 인자는 **의미 라벨로 존속**(data-orb 속성 = 스모크·CSS 훅 계약 불변 · 호출부 수정 0). 그래픽만 갈아끼운 것.
   · shimmer = 글자 위 빛 스윕(background-clip:text) — `.nm-shim` = 스윕 도료(재사용 가능 · 로더 옆 경과시간·주석 등 **붙어 있는 글자 전부**에 부착) ·
     크기·굵기는 `.nm-load>.nm-shim`(로더 안 라벨) 전용 = 도료만 물려받는 곳의 폰트를 안 흔든다(운영자 260731 "로딩 그래픽하고 붙어있는 글자들").
   · 4분할 중앙선 정렬 = align-items:center + line-height:1(Δ0 실측)
   · API:  el.innerHTML = nmLoader('solving','Solving…')  ·  <span class="nm-load" data-orb="thinking" data-label="Thinking…"></span> 자동 수화
   · 색 = 레퍼런스대로 흰/은빛 도트 + 흰빛 스윕(콘텐츠 축 · UI 팔레트 무관) · 기존 mkLoader/nmLoaderHTML(도트 팩토리) 무접촉 병존 */
(function () {
  if (window.nmLoader) return;
  if (!document.getElementById('nm-orb-css')) {
    var css =
      '.nm-orb{display:inline-block;position:relative;vertical-align:middle;flex:0 0 auto}' +
      '.nm-orb svg{display:block;width:100%;height:100%;overflow:visible}' +
      '.nm-orb .nm-dot{fill:#e9eef0}' +
      /* 도트3 = 전 type 공통(260731 단일화) — 셀렉터에서 [data-orb] 조건을 뺀다(속성은 의미 라벨로 존속) */
      '.nm-orb .nm-bd{transform-box:fill-box;transform-origin:center;animation:nmbd .92s var(--ease,cubic-bezier(.2,.7,.3,1)) infinite}' +
      '.nm-orb .nm-bd.b2{animation-delay:.15s}.nm-orb .nm-bd.b3{animation-delay:.3s}' +
      '@keyframes nmbd{0%,100%{transform:translateY(0);opacity:.5}50%{transform:translateY(-52%);opacity:1}}' +
      '.nm-load{display:inline-flex;align-items:center;gap:9px}' +
      '.nm-load .nm-orb{width:22px;height:22px}' +
      /* .nm-shim = 빛 스윕 **도료만**(로더에 붙어 있는 경과시간·주석 등 어디에나 부착 가능 · 폰트 무간섭).
         -webkit-text-fill-color = 붙는 쪽 스타일시트의 color(예 `.go .gtime{color:var(--mut)}` = 더 높은 특정성)가
         투명 클립을 되돌려 스윕이 안 보이던 것을 막는 잠금(다른 프로퍼티라 특정성 싸움 자체가 없다). */
      '.nm-shim{background:linear-gradient(100deg,var(--mut,#8fa697) 0%,var(--mut,#8fa697) 38%,#ffffff 50%,var(--mut,#8fa697) 62%,var(--mut,#8fa697) 100%);' +
        'background-size:220% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent;' +
        'animation:nmshim 1.9s linear infinite}' +
      '.nm-load>.nm-shim{font-size:13.5px;font-weight:700;letter-spacing:0;line-height:1;display:inline-flex;align-items:center}' +   // 로더 안 라벨만 = 종전 타이포(붙은 글자엔 안 물림)
      '@keyframes nmshim{from{background-position:120% 0}to{background-position:-120% 0}}' +
      '@media(prefers-reduced-motion:reduce){.nm-shim{animation:none;color:var(--mut,#8fa697);-webkit-text-fill-color:var(--mut,#8fa697)}.nm-orb *{animation:none!important}}';
    var st = document.createElement('style'); st.id = 'nm-orb-css'; st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  }
  function dotsSVG() {   // 통통 튀는 도트 3(흰 입자 .nm-dot · 기존 .nmld 바운스 계승) — 260731부터 **전 type 단일 그래픽**(운영자 승인)
    return '<svg viewBox="0 0 100 100"><circle class="nm-dot nm-bd" cx="21" cy="50" r="9.5"/><circle class="nm-dot nm-bd b2" cx="50" cy="50" r="9.5"/><circle class="nm-dot nm-bd b3" cx="79" cy="50" r="9.5"/></svg>';
  }
  function orbType(t) { return t === 'solving' ? 'solving' : t === 'prompting' ? 'prompting' : t === 'loading' ? 'loading' : 'thinking'; }   // 의미 라벨(data-orb 계약 유지) — 그래픽 분기는 없다
  function orbHTML(type, size) { var sz = size ? ' style="width:' + size + 'px;height:' + size + 'px"' : ''; return '<span class="nm-orb" data-orb="' + orbType(type) + '"' + sz + '>' + dotsSVG() + '</span>'; }
  function esc(x) { return String(x == null ? '' : x).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  // nmLoader(type,label[,opts]) — opts={size:orb px, gap, fs:글자 px}. 좁은 버튼 = size 18·fs 12.5, 기본 pill = 22·13.5
  window.nmLoader = function (type, label, opts) {
    opts = opts || {}; var g = opts.gap != null ? opts.gap : 9;
    var fs = opts.fs ? ' style="font-size:' + opts.fs + 'px"' : '';
    return '<span class="nm-load" style="gap:' + g + 'px">' + orbHTML(type, opts.size) + '<span class="nm-shim"' + fs + '>' + esc(label) + '</span></span>';
  };
  window.nmOrbHTML = orbHTML;   // orb만(버튼 좁은 폭 등)
  function hydrate(root) {   // 선언형: <span class="nm-load" data-orb="thinking" data-label="Thinking…"></span>
    var els = (root || document).querySelectorAll('.nm-load[data-orb]:not([data-nm-done])'), i, e;
    for (i = 0; i < els.length; i++) { e = els[i]; e.setAttribute('data-nm-done', '1'); e.innerHTML = orbHTML(e.getAttribute('data-orb')) + '<span class="nm-shim">' + esc(e.getAttribute('data-label')) + '</span>'; }
  }
  window.nmLoaderHydrate = hydrate;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { hydrate(); }); else hydrate();

})();

/* ── nmFavBusy — 작업 중에만 브라우저 탭 파비콘(지구본)이 돈다 ─────────────────────────
   운영자 260727 "뉴스 요약·이미지 제작 등 작업중에는 저 로고가 돌아가고, 작업중인게 없으면 그냥 일반 로고".
   · 그림 = 기존 favicon-globe-260724.svg **그대로** 캔버스에 얹어 회전만(새 그림·새 색 창작 0 = B1).
     SVG 안의 prefers-color-scheme 스왑(라이트 파랑 / 다크 시그니처)도 <img> 렌더가 그대로 따라온다.
   · 작업중 판정 = index `lkProdBusy()`(index.html §유휴감시) 셀렉터 문법 계승 + 부모 문서 진행 신호(.firing/.picking) 합본.
     iframe 관통도 그 함수와 같은 방식(도구 탭이 자식 문서라 부모가 대신 칠한다 = 도구 6탭 파일 무접촉).
   · 끝나면 href를 원본 문자열로 되돌린다 = 평소엔 손 안 댄 상태와 동일.
   · 검증 = `node shared/smoke_favtab.js --url /?qa=1`(탭바 픽셀 재도색 실측 · href 변경은 증거 아님 = 인수인계서 §7-3-1).
   · 한계 = 비활성 탭은 크롬이 타이머를 1fps로 조여 '회전'이 '깜빡임'으로 읽힌다(활성 탭은 정상). */
(function () {
  if (window.nmFavBusy || window.top !== window.self) return;   // 최상위 문서만(도구 iframe이 자기 파비콘을 돌려봐야 탭에 안 보임)

  var SEL = '[aria-busy="true"], .firing, .picking, #jobs .job:not(.done):not(.err)';
  var SRC = 'favicon-globe-260724.svg';
  /* 값·모션 = 플레이그라운드 `docs/reports/260727_파비콘애니_플레이그라운드.html` 계승(운영자 선택분).
     mode=spin(§305 = 세로축 자전 · 평면 rotate 아님) · period 980 · fps 60 · res 64 · size 78% · amp 100 · ease=--ease 계승. */
  /* 【260729 2차 = 5fps 회귀 원복 · 운영자 "높은 프레임으로 원이 회전해야함 · 지금은 6개 사진이 반복 움직이는 느낌"】
     ⚠ 1차(5fps)는 **틀린 전제**로 낮췄다 — 「크로미엄이 탭 파비콘을 초당 3~4.5회로 조인다」는 실측이
     **리눅스 Xvfb 크로미엄 한정**이었고, 운영자 환경(윈도 Brave)에는 그 상한이 없다. 그 증거가 운영자 관찰이다:
     5fps × 2420ms = **12장**, 자전은 |cos| 좌우대칭이라 고유 모양은 절반 = **6개** → "6개 사진이 반복"과 정확히 일치.
     넣은 fps가 그대로 보이는 환경이라는 뜻이므로 fps = 부드러움이 성립한다. ∴ 30fps 복귀.
     비용은 프리렌더 캐시가 감당한다 — 30fps여도 매 프레임 굽기(toDataURL)가 0이라
     64px·30fps·라이브(구본) 대비 **여전히 20% 가볍다**(순증 700→560ms · Xvfb headful 실측).
     운영자 판정 = "화질이 중요한 게 아니라 높은 프레임" → PX는 32 유지(굽고 버리던 픽셀), FPS만 되돌린다. */
  var PX = 32;             // res — 탭 렌더 16~20px의 2x(레티나)까지 커버 · 64는 굽고 버리는 픽셀이었다
  var SIZE = .78;          // size 78% — 캔버스 대비 로고 크기(플레이그라운드 DEFAULTS)
  var FPS = 60, POLL = 350;   // 60fps × 2420ms = 145장 캐시(32px ~310KB) = 고유 72모양(운영자 260729 "60fps 한번 가보자")
  var MAXF = 180;             // 캐시 장수 상한 — reduced-motion(SPIN 4800)에서 288장까지 불어나는 것만 막는 방어선(정상 경로 145장은 무영향)
  var slow = false;
  try { slow = matchMedia('(prefers-reduced-motion:reduce)').matches; } catch (_) {}
  var SPIN = slow ? 4800 : 2420;   // 1회전 ms · reduced-motion = 저속(정지시키면 '작업중 알림'이라는 목적 자체가 사라진다)
  /* 2420ms·30fps = 운영자 260727 첫 선택값 복귀. 980ms·60fps는 플랫폼 비교판 맥락의 수치였고
     실제 탭에서 "너무 빠르게 동작한다"는 판정을 받았다(운영자 260728). */
  /* 【260729 이징 폐지 = 등속 회전 · 운영자 "도는거 끝날때 처음으로 돌아가면서 팡 튀는 부분이 있다"】
     원인은 **주기 불일치**였다 — 그림은 `|cos|`라 **반 바퀴**마다 한 사이클(정면→옆면→정면)인데
     이징(등속 × easeInOutCubic 반반 블렌드)은 **한 바퀴** 주기라, 첫 사이클은 느리게 시작하고
     둘째 사이클은 최고속으로 통과한다. 같은 정면 모양을 매번 다른 속도로 지나가니 '팡'으로 읽힌다.
     ⚠ 루프 이음매(마지막 프레임→첫 프레임)는 무죄였다 — 폭 변화량 0.0002로 사실상 연속(실측).
     등속 전환 실측(60fps·145프레임·scaleX 기준) = 급변(최대/평균) 2.18배 → **1.66배** ·
     불균일도(편차/평균) 0.72 → **0.53**. 남은 1.66배는 `|cos|` 자체의 곡률(옆면 근처가 빠름)이고
     그건 실제 3D 자전의 원근 효과라 **없애면 안 되는 자연스러움**이다.
     구 이징의 도입 사유(260728 "안 움직이다 가끔 깜빡")는 easeInOutCubic을 통째로 먹였을 때의
     정면 붙박임 문제였고, 등속은 그 반대 극단이라 그 결함이 원천적으로 없다. */

  var spin = null, kept = [], img = null, ready = false;
  var cv = null, cx = null, tick = null, t0 = 0, on = false, cache = null;
  function busy() {
    try {
      if (document.querySelector(SEL)) return true;
      var fr = document.getElementsByTagName('iframe'), i, d;
      for (i = 0; i < fr.length; i++) {
        d = null; try { d = fr[i].contentDocument; } catch (_) {}
        if (d && d.querySelector(SEL)) return true;
      }
    } catch (_) {}
    return false;
  }
  function paint(ph) {   // ph = 한 바퀴 안 위상(0~1) — 그림만 그린다(굽기는 buildCache가 한 번만)
    var ang = ph * Math.PI * 2;   // 등속 = 각속도 일정 → 정면 통과 속도가 매 사이클 같다(팡 소멸)
    var s = Math.cos(ang), S = PX * SIZE;
    cx.clearRect(0, 0, PX, PX);
    cx.save(); cx.translate(PX / 2, PX / 2);
    cx.scale(Math.max(.06, Math.abs(s)), 1);   // ★ 세로축 자전 — 가로만 줄었다 펴진다(플레이그라운드 spin §305 · rotate = 팽이라 오답)
    cx.globalAlpha = .55 + .45 * Math.abs(s);  // 옆면일수록 어둡게 = 앞뒤 입체감(같은 줄 a 계승)
    cx.drawImage(img, -S / 2, -S / 2, S, S);
    cx.restore();
  }
  /* 프리렌더 캐시(260729) — 한 바퀴치 프레임을 **처음 한 번만** 굽고 이후엔 문자열만 갈아끼운다.
     구 방식은 매 프레임 toDataURL(= PNG 인코딩)을 다시 돌렸다(30fps × 8초 = 90~140ms 순수 인코딩).
     12장 × 32px ≈ 25KB · 굽는 시간 3ms(실측) = 시작 지연 체감 0. */
  function buildCache() {
    var n = Math.min(MAXF, Math.max(2, Math.round(SPIN / (1000 / FPS)))), a = [], i;
    for (i = 0; i < n; i++) { paint(i / n); a.push(cv.toDataURL('image/png')); }
    return a;
  }
  function draw() {
    if (!cache) { try { cache = buildCache(); } catch (_) { stop(); return; } }   // toDataURL 실패(오염 등) = 조용히 원복
    var i = Math.floor(((Date.now() - t0) % SPIN) / SPIN * cache.length) % cache.length;   // 위상 기준 = setInterval 지터가 회전 속도를 안 흔든다
    try { spin.setAttribute('href', cache[i]); } catch (_) { stop(); }
  }
  /* 기존 <link rel=icon>의 href만 갈아끼우면 크롬이 안 그린다(실측 260727: type="image/svg+xml" 태그에 PNG를
     넣으면 무시하고 앞의 .ico를 계속 씀). ∴ 도는 동안은 icon 링크를 통째로 떼고 PNG 전용 링크 하나만 세운다. */
  function start() {
    if (on || !ready) return;
    if (!cv) { cv = document.createElement('canvas'); cv.width = cv.height = PX; cx = cv.getContext('2d'); }
    kept = [].slice.call(document.querySelectorAll('link[rel~="icon"]'));   // apple-touch-icon은 rel 단어가 달라 미매치 = 무접촉
    spin = document.createElement('link');
    spin.setAttribute('rel', 'icon'); spin.setAttribute('type', 'image/png'); spin.setAttribute('sizes', PX + 'x' + PX);
    on = true; t0 = Date.now(); draw();
    kept.forEach(function (l) { if (l.parentNode) l.parentNode.removeChild(l); });
    document.head.appendChild(spin);
    tick = setInterval(draw, Math.round(1000 / FPS));
  }
  function stop() {
    if (!on) return;
    on = false; clearInterval(tick); tick = null;
    if (spin && spin.parentNode) spin.parentNode.removeChild(spin);
    kept.forEach(function (l) { document.head.appendChild(l); });   // 원본 태그 그대로 복귀 = 평소 지구본
    spin = null; kept = [];
  }

  img = new Image();
  img.onload = function () { ready = true; };
  img.src = SRC;

  setInterval(function () { var b = busy(); if (b) start(); else stop(); }, POLL);
  window.addEventListener('pagehide', stop);

  window.nmFavBusy = { start: start, stop: stop, busy: busy, on: function () { return on; } };   // 진단용
})();
