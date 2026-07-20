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
