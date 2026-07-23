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

/* ══ orb 로더(운영자 260723 승인 시안 v3 · Q459/Q460) — 앱 전반 로딩 표기 SSOT ══
   · 매핑 = Thinking(요약·분석·큐레이션·2차수정 판단) · Solving(영상 편집·변환·렌더·이미지·음원 산출·재수정) · Prompting(프롬프팅·콘티 설계)
   · orb = CSS/SVG 근사(WebGL 원본 orbs.jakubantalik.com 스크랩 불가) · Thinking/Prompting = 소용돌이 링 · Solving = 흩뿌린 입자
   · shimmer = 글자 위 빛 스윕(background-clip:text) · 4분할 중앙선 정렬 = align-items:center + line-height:1(Δ0 실측)
   · API:  el.innerHTML = nmLoader('solving','Solving…')  ·  <span class="nm-load" data-orb="thinking" data-label="Thinking…"></span> 자동 수화
   · 색 = 레퍼런스대로 흰/은빛 입자 + 흰빛 스윕(콘텐츠 축 · UI 팔레트 무관) · 기존 mkLoader/nmLoaderHTML(도트 팩토리) 무접촉 병존 */
(function () {
  if (window.nmLoader) return;
  if (!document.getElementById('nm-orb-css')) {
    var css =
      '.nm-orb{display:inline-block;position:relative;vertical-align:middle;flex:0 0 auto}' +
      '.nm-orb svg{display:block;width:100%;height:100%;overflow:visible}' +
      '.nm-orb .nm-dot{fill:#e9eef0}' +
      '.nm-orb[data-orb="thinking"] .nm-r,.nm-orb[data-orb="prompting"] .nm-r{transform-origin:50% 50%;animation:nmspin 3.2s linear infinite}' +
      '.nm-orb[data-orb="thinking"] .nm-r2,.nm-orb[data-orb="prompting"] .nm-r2{animation-duration:4.6s;animation-direction:reverse;opacity:.72}' +
      '.nm-orb[data-orb="thinking"] .nm-r3,.nm-orb[data-orb="prompting"] .nm-r3{animation-duration:6s;opacity:.5}' +
      '.nm-orb[data-orb="solving"] .nm-cloud{transform-origin:50% 50%;animation:nmspin 9s linear infinite}' +
      '.nm-orb[data-orb="solving"] .nm-dot{animation:nmtwk 1.8s ease-in-out infinite}' +
      '@keyframes nmspin{to{transform:rotate(360deg)}}' +
      '@keyframes nmtwk{0%,100%{opacity:.26}50%{opacity:1}}' +
      '.nm-load{display:inline-flex;align-items:center;gap:9px}' +
      '.nm-load .nm-orb{width:22px;height:22px}' +
      '.nm-shim{font-size:13.5px;font-weight:700;letter-spacing:0;line-height:1;display:inline-flex;align-items:center;' +
        'background:linear-gradient(100deg,var(--mut,#8fa697) 0%,var(--mut,#8fa697) 38%,#ffffff 50%,var(--mut,#8fa697) 62%,var(--mut,#8fa697) 100%);' +
        'background-size:220% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;animation:nmshim 1.9s linear infinite}' +
      '@keyframes nmshim{from{background-position:120% 0}to{background-position:-120% 0}}' +
      '@media(prefers-reduced-motion:reduce){.nm-shim{animation:none;color:var(--mut,#8fa697);-webkit-text-fill-color:var(--mut,#8fa697)}.nm-orb *{animation:none!important}}';
    var st = document.createElement('style'); st.id = 'nm-orb-css'; st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  }
  function solvingSVG() {   // 흩뿌린 입자(결정적 시드 — Math.random 미사용 = 렌더 결정론)
    var s = 9301, rnd = function () { s = (s * 9301 + 49297) % 233280; return s / 233280; };
    var d = '', N = 44, i, a, r;
    for (i = 0; i < N; i++) {
      a = rnd() * 6.2832; r = Math.sqrt(rnd()) * 45 + 3;
      d += '<circle class="nm-dot" cx="' + (50 + Math.cos(a) * r * 0.9).toFixed(1) + '" cy="' + (50 + Math.sin(a) * r * 0.9).toFixed(1) +
           '" r="' + (0.85 + rnd() * 1.7).toFixed(2) + '" style="animation-delay:' + ((i % 7) * 0.26).toFixed(2) + 's"/>';
    }
    return '<svg viewBox="0 0 100 100"><g class="nm-cloud">' + d + '</g></svg>';
  }
  function ringSVG() {   // 소용돌이 3링(원근 fake)
    function ring(cls, ry, n, rd, rot) {
      var d = '', i, a;
      for (i = 0; i < n; i++) { a = i / n * 6.2832; d += '<circle class="nm-dot" cx="' + (50 + Math.cos(a) * 40).toFixed(1) + '" cy="' + (50 + Math.sin(a) * ry).toFixed(1) + '" r="' + rd + '"/>'; }
      return '<g class="nm-r ' + cls + '" style="transform:rotate(' + rot + 'deg)">' + d + '</g>';
    }
    return '<svg viewBox="0 0 100 100">' + ring('', 40, 20, 2, 0) + ring('nm-r2', 15, 16, 1.7, 30) + ring('nm-r3', 26, 13, 1.4, 60) + '</svg>';
  }
  function orbType(t) { return t === 'solving' ? 'solving' : (t === 'prompting' ? 'prompting' : 'thinking'); }
  function orbHTML(type, size) { var t = orbType(type), sz = size ? ' style="width:' + size + 'px;height:' + size + 'px"' : ''; return '<span class="nm-orb" data-orb="' + t + '"' + sz + '>' + (t === 'solving' ? solvingSVG() : ringSVG()) + '</span>'; }
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
