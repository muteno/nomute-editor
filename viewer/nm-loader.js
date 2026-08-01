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
      /* vertical-align:middle = 인라인 흐름에서 로더와 붙은 글자를 **둘 다 박스중앙 기준**으로 세운다(운영자 260731 한 수).
         ⚠ 실측으로 잡은 기존 결함: `.nm-load`는 inline-flex라 인라인 baseline이 **orb 박스 하단**에 잡힌다 →
         부모가 flex가 아닌 표면(인라인 흐름)에서는 붙은 글자가 라벨보다 **7.66px 아래**로 밀려 있었다(Δ 실측 · fs 13.5).
         둘 다 middle이면 박스중앙이 같은 선에 서고, .nm-shim의 -.049em 보정이 박스중앙=잉크중심을 만들어 주므로 결과가 곧 **잉크선 일치**다.
         부모가 flex인 표면(.row·버튼 등)에서는 align-items가 지배해 vertical-align은 무시된다 = 무해(양쪽 표면 동시 성립). */
      '.nm-load{display:inline-flex;align-items:center;gap:9px;vertical-align:middle}' +
      '.nm-load .nm-orb{width:22px;height:22px}' +
      /* .nm-shim = 빛 스윕 **도료만**(로더에 붙어 있는 경과시간·주석 등 어디에나 부착 가능 · 폰트 무간섭).
         -webkit-text-fill-color = 붙는 쪽 스타일시트의 color(예 `.go .gtime{color:var(--mut)}` = 더 높은 특정성)가
         투명 클립을 되돌려 스윕이 안 보이던 것을 막는 잠금(다른 프로퍼티라 특정성 싸움 자체가 없다). */
      '.nm-shim{background:linear-gradient(100deg,var(--mut,#8fa697) 0%,var(--mut,#8fa697) 38%,#ffffff 50%,var(--mut,#8fa697) 62%,var(--mut,#8fa697) 100%);' +
        'background-size:220% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent;' +
        'animation:nmshim 1.9s linear infinite;' +
        /* 활자·보정도 도료와 한 벌(운영자 260731 한 수 "붙은 글자도 라벨과 같은 잉크선") — 붙은 글자(경과시간·예상·회차)가
           라벨과 **같은 크기·굵기·같은 -.049em 보정**을 쓰면 baseline이 정확히 겹쳐 한 줄이 한 덩어리로 읽힌다.
           보정을 라벨에만 걸면 라벨만 0.66px 떠서 오히려 붙은 글자와 어긋난다(같은 em이라 함께 걸어야 Δ0).
           tabular-nums = 초 카운터 자릿수 흔들림 0(붙은 글자 대부분이 숫자 · 기존 각 사이트 선언과 동의도). */
        'font-size:13.5px;font-weight:700;line-height:1;font-variant-numeric:tabular-nums;vertical-align:middle;transform:translateY(-.049em)}' +
      /* 로더 안 라벨만 = 종전 타이포(붙은 글자엔 안 물림) + **광학 잉크 정렬 보정**(운영자 260731 "점 세개랑 옆 글자 광학 잉크 기준 픽셀단위 수평 확인").
         실측(Playwright · 20배 확대 measureText = 0.05px 해상도 · 애니 0% 정지 프레임): 한글 잉크가 baseline 위 10.336 / 아래 2.320으로 비대칭이라
         **글자 잉크중심이 박스중심보다 0.667px 아래**(fs 13.5) · 0.575px 아래(fs 13.5→12.5 좁은버튼). 도트는 cy=50 = 박스 정중앙이라 그만큼 위로 떠 보였다.
         → 라벨을 자기 폰트 비례(-0.049em)만큼 올려 잉크중심끼리 맞춘다(13.5×.049=0.662 · 12.5×.049=0.613 = 두 티어 동시 수렴 · 도트를 내리면 em 기준이 상속 폰트라 불안정). */
      '.nm-load>.nm-shim{letter-spacing:0;display:inline-flex;align-items:center}' +   // 로더 안 라벨만 = 도트와 같은 줄에 정중앙 배치(활자·보정은 위 .nm-shim 공통)
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
  /* type='loading' = **글자만**(도트 픽토 미부착 · 운영자 260731 "나우로딩은 그냥 글자만 — 옆에 ...이 있으니까")
     — 라벨 끝 말줄임(…)이 이미 점 3개라 도트3까지 붙으면 점이 두 벌로 읽힌다. 나머지 3종(thinking·solving·prompting)만 도트3. */
  window.nmLoader = function (type, label, opts) {
    opts = opts || {}; var g = opts.gap != null ? opts.gap : 9;
    var fs = opts.fs ? ' style="font-size:' + opts.fs + 'px"' : '';
    var orb = orbType(type) === 'loading' ? '' : orbHTML(type, opts.size);
    return '<span class="nm-load" style="gap:' + g + 'px">' + orb + '<span class="nm-shim"' + fs + '>' + esc(label) + '</span></span>';
  };
  window.nmOrbHTML = orbHTML;   // orb만(버튼 좁은 폭 등)
  function hydrate(root) {   // 선언형: <span class="nm-load" data-orb="thinking" data-label="Thinking…"></span>
    var els = (root || document).querySelectorAll('.nm-load[data-orb]:not([data-nm-done])'), i, e;
    for (i = 0; i < els.length; i++) { e = els[i]; e.setAttribute('data-nm-done', '1');
      e.innerHTML = (orbType(e.getAttribute('data-orb')) === 'loading' ? '' : orbHTML(e.getAttribute('data-orb'))) + '<span class="nm-shim">' + esc(e.getAttribute('data-label')) + '</span>'; }   // loading = 글자만(위 nmLoader와 동일 규칙)
  }
  window.nmLoaderHydrate = hydrate;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { hydrate(); }); else hydrate();

})();

/* ══ nmEta — 「예상 : N분 NN초」 값 SSOT(운영자 260731 "예상도 일단 다 보이게, 점차 많이 쓰면 평균값으로 안정화") ══
   · 왜 = 각 작업의 실제 소요는 아무도 모른다(운영자 확인). 그래서 **초기엔 시드(추정)로 다 보여주고,
     쓸 때마다 실측을 누적해 평균으로 수렴**시킨다. "처음엔 틀려도 된다"가 설계 전제.
   · 저장 = localStorage `nm-eta-v1` = { key: {n, avg} } (기기 로컬 · 서버 왕복 0 · 실패해도 시드로 폴백 = 표시는 절대 안 깨짐).
   · 수렴 = EMA(가중 .3) — 최근 실행에 더 무게. 첫 실측 1건은 시드를 즉시 대체하지 않고(n<MIN) 섞이는 동안 시드 유지 = 튐 방지.
   · 이상치 방어 = 0초 이하·10시간 초과 표본은 버린다(탭 방치·시계 점프).
   · **계측**(CLAUDE.md [관측]) = `nmEta.dump()`가 {키 · 시드 · 표본수 · 현재 평균}을 한 줄씩 콘솔에 찍는다.
     조용히 학습이 멈추는 사고(스토리지 차단·done 미배선)를 표본수 0으로 즉시 구분할 수 있어야 한다.
   · 배선 = 표시 `nmEta.label(key)` / 학습 `nmEta.done(key, 경과초)`(**성공 완료 지점에서만** — 실패·타임아웃을 섞으면 평균이 오염된다).
   · 시드 근거 = 코드에 이미 있던 문구·주석(k 3분/15분 · sb·ly·edit "1~3분" · track "보통 2–6분" · index "1~2분")을 우선 채택,
     근거가 없던 축(conv·song·tr·카드뉴스·편집)은 잡 예산의 1/3 안팎을 임시 시드로 두고 실측이 덮게 한다(운영자 승인 = "처음엔 틀려도"). */
(function () {
  if (window.nmEta) return;
  var KEY = 'nm-eta-v1', MIN = 2, W = 0.3, MAXS = 36000;
  var SEED = {           // 초(sec) · 근거는 위 주석 참조
    'k-img': 180, 'k-ref': 900,          // k.html 기존 문구(3분 / 레퍼런스 15분)
    'sb': 180,                            // sb.html 기존 "보통 1–3분"
    'ly-burn': 180, 'edit-burn': 180,     // ly·edit 기존 "(1~3분)"
    'track-analyze': 360,                 // track.html 폴백 문구 "보통 2–6분"
    'track-render': 900,                  // track.html RENDER_BUDGET 900s(소프트 예산)
    'conv': 600,                          // 근거 없음 — 잡 캡 58분의 1/6 임시 시드
    'song': 300, 'song-voice': 900,       // 근거 없음 — 잡 캡 25분/70분 기준 임시 시드
    'tr': 120,                            // 근거 없음 — 임시 시드
    'edit-video': 600,                    // 근거 없음 — 잡 캡 85분 기준 임시 시드
    'cards-prompt': 300, 'cards-img': 600,// index 타임아웃(프롬프팅 25분·렌더 10분) 기준 임시 시드
    'thumb-copy': 180,                    // thumb "변환 실측 1~3분"
    'img-gen': 120, 'img-research': 120,  // index 주석·툴팁 "1~2분"
    // ── 요약 요청 링크 레일(운영자 260731 "걸린시간을 유튜브 시간과 대조해서 예상 시간이 항상 나오게") ──
    //   예상 = `ask-link`(고정 오버헤드) + `ask-link-stt-min` × 영상분. ⚠️ `ask-link-stt-min` 만 단위가 **영상 1분당 초**다
    //   (다른 키 = 총 소요초). 전사는 영상 길이에 비례해 늘어나 단일 스칼라로는 3분짜리와 40분짜리를 같이 못 맞춘다.
    //   학습도 같은 단위로 넣는다 — done('ask-link-stt-min', (총소요 − 오버헤드) / 영상분). nmEta 내부(EMA·이상치·저장)는 불변.
    'ask-link': 500, 'ask-link-stt-min': 90
    // 실측 근거(260731) — 오버헤드 = ask 2건 428s(19초 영상·전사 경로)·594s(3분33초·자막 경로) 평균 ≈ 500s.
    //   분당배율 = **10분(600초) 오디오 직접 전사 실측 475s = 0.79×RT**(4코어 · 85줄 정상 산출). 짧은 클립뿐이던
    //   러너 A/B(260728 · 1.39×RT)의 외삽을 이 실측이 교정한다 — 긴 오디오일수록 모델 로드 고정비가 희석돼 배율이 내려간다.
    //   그런데도 90s(1.5×RT)를 유지하는 이유 = 측정 박스가 4코어인데 GitHub 러너는 그보다 적을 수 있어(2코어면 ~1.7배 느림)
    //   0.79×RT 를 그대로 쓰면 러너에서 예상이 모자란다. 예상은 넉넉한 쪽이 안전하다(빨리 끝나는 건 문제가 아니다).
    //   러너에서 10분+ 무자막 영상 실측이 잡히면 그때 이 값을 내려라.
  };
  function db() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (_) { return {}; } }
  function save(d) { try { localStorage.setItem(KEY, JSON.stringify(d)); } catch (_) {} }   // quota·프라이빗모드 = 조용히 포기(시드로 계속 표시)
  function seed(k) { return SEED[k] || 180; }
  function sec(k) { var e = db()[k]; return (e && e.n >= MIN && e.avg > 0) ? e.avg : seed(k); }
  function fmt(s) { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + '분 ' + String(s % 60).padStart(2, '0') + '초'; }
  function label(k) { return ' (예상 : ' + fmt(sec(k)) + ')'; }
  function done(k, s) {
    s = Number(s); if (!(s > 0) || s > MAXS) return false;   // 이상치 = 학습 안 함(표본 오염 차단)
    var d = db(), e = d[k] || { n: 0, avg: seed(k) };
    e.avg = e.n ? e.avg * (1 - W) + s * W : (seed(k) + s) / 2;   // 첫 표본 = 시드와 반반(급변 방지) · 이후 EMA
    e.n = e.n + 1; d[k] = e; save(d); return true;
  }
  function dump() {   // 계측 = 학습이 조용히 멈추는 사고(스토리지 차단·done 미배선)를 표본수로 구분
    var d = db(), ks = Object.keys(SEED), i, k, e, live = 0;
    for (i = 0; i < ks.length; i++) { k = ks[i]; e = d[k];
      console.log('[nmEta] ' + k + ' · 시드 ' + fmt(seed(k)) + ' · 표본 ' + ((e && e.n) || 0) + ' · 현재 ' + fmt(sec(k)));
      if (e && e.n) live++; }
    console.log('[nmEta] 학습된 축 ' + live + ' / 등록 ' + ks.length + ' · 미학습 ' + (ks.length - live) + '(표본 0 = done() 미배선이거나 아직 완료 이력 없음)');
    return { live: live, total: ks.length };
  }
  window.nmEta = { sec: sec, fmt: fmt, label: label, done: done, dump: dump, seed: seed, SEED: SEED };
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
