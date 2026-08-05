/* 결과·이전 제작 레일 부품 SSOT — 상속 1줄로 어느 스튜디오 탭에도 같은 세트가 선다(운영자 260806 "항상 저렇게 유지되어야하고, 사진끼리는 저렇게 공유하고, 영상끼리도 저렇게 공유할수있게해줘").
 * ─────────────────────────────────────────────────────────────────────────────
 * 무엇 = 「결과 = [요약 줄(완료 · N장 · 시각 + 수정 · 전체 다운로드)] + [개별 썸네일 타일]」 + 「이전 제작」 한 세트.
 *   부품·값 = 이미지 스튜디오 정본 100% 사본(마크업 = thumb `.out` 블록 · CSS = nm-hist.css `.hist-*` + nm-job.css `.job*` · 신규 클래스·값·색 0).
 *   ⚠ 마크업을 **여기서 한 번만** 만든다 = 표면마다 사본을 두지 않는다. 260806 하루에 이 레일이 네 번 갈라졌고(결론형/썸네일형 · 타일 배경 투명 · 요약 줄 부재 · 마진 상쇄 10px)
 *   전부 운영자 눈이 유일한 검출기였다 — 사본이 있는 한 같은 일이 반복된다는 게 그날의 결론이라, 신규 표면은 **사본 대신 상속**으로 간다.
 *
 * 데이터 격리 = 스코프별 저장소(운영자 260806 "근데 사진 과 영상은 작업 결과를 공유하지 않음 - 형태 목업만 일치").
 *   img = `nomute_thumb_hist`(이미지 스튜디오 5탭이 이미 쓰는 공유 키 · 이 모듈은 **읽지도 쓰지도 않는다** = 그쪽은 종전 자체 배선 유지)
 *   cap = `nomute_cap_hist`(영상 스튜디오 5탭 전용 · 신설) → 영상끼리는 공유, 사진과는 완전 분리.
 *
 * 쓰는 법(신규 탭 3줄):
 *   <link rel="stylesheet" href="nm-hist.css"> <link rel="stylesheet" href="nm-job.css"> <script src="nm-rail.js"></script>
 *   그리고 마운트 1줄 = nmRail.mount(document.getElementById('out'), { scope:'cap', dlname:'video.mp4' })
 *   완료 시 1줄 = nmRail.add({ url, cap:'편집', dlname:'…' })   // ts 생략 = 지금
 *
 * 의존 = nm-svg.js(DOWNLOAD_SVG·EDIT_SVG) · nm-hist.css · nm-job.css · 각 문서 :root(--hist-accent/--hist-rgb/--pan/--line).
 */
(function () {
  'use strict';
  if (window.nmRail) return;   // 중복 로드 = 무동작(idempotent · nm-clip/nm-sync 관례)

  var KEYS = { img: 'nomute_thumb_hist', cap: 'nomute_cap_hist' };   // ⚠ 스코프별 저장소 = 사진↔영상 결과 격리 계약(운영자 260806) — 한 키로 합치면 영상 결과가 사진 레일에 섞인다
  var HMS = 12 * 3600e3;      // 보관창 = 이미지 정본 동값(12h 로컬 브리지)
  var HMAX = 240;             // 상한 = thumb THUMB_HMAX 동값
  var T0 = Date.now();        // 이 문서 부팅 = '이번 세션' 경계(이미지 GENI_T0·TR_T0 동문)
  var mounts = [];            // 이 문서에 마운트된 레일들(보통 1개)

  function esc(s) { return String(s == null ? '' : s); }
  function keyOf(u) { return String(u || '').split('?')[0].replace(/^https?:\/\/[^/]+\//, ''); }   // 중복판정 키 = 이미지 정본 동문(호스트 제거)
  function load(scope) { try { var a = JSON.parse(localStorage.getItem(KEYS[scope]) || '[]'); return Array.isArray(a) ? a : []; } catch (e) { return []; } }
  function save(scope, a) { try { localStorage.setItem(KEYS[scope], JSON.stringify(a)); } catch (e) {} }
  function prune(a) { var cut = Date.now() - HMS; return a.filter(function (e) { return e && e.ts && e.ts >= cut; }); }

  function histTime(ts) {   // 표기 = 이미지 정본 동문(오늘/어제 · M/D 접두 · 오전/오후 H:MM)
    var d = new Date(ts), h = d.getHours(), m = d.getMinutes(), ap = h < 12 ? '오전' : '오후';
    h = h % 12 || 12;
    var now = new Date();
    var dd = Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);
    var pre = dd === 0 ? '오늘 ' : dd === 1 ? '어제 ' : (d.getMonth() + 1) + '/' + d.getDate() + ' ';
    return pre + ap + ' ' + h + ':' + String(m).padStart(2, '0');
  }
  function dlBlob(url, name) {   // R2(교차출처) = api/dl 프록시 강제 저장 · 비R2 = download 직접 — 이미지 정본 동문
    var a = document.createElement('a');
    a.href = /\/\/pub-[0-9a-fA-F]+\.r2\.dev\//.test(url) ? ('api/dl?u=' + encodeURIComponent(url) + '&n=' + encodeURIComponent(name || 'out')) : url;
    a.download = name || 'out';
    document.body.appendChild(a); a.click(); a.remove();
  }
  var DL_SVG = function () { return window.DOWNLOAD_SVG || '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7 11l5 5 5-5M4 21h16"/></svg>'; };
  var CK_SVG = function () { return window.CHECK_SVG || '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>'; };
  var CHEV = '<svg class="hist-ar" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';

  /* 레일 셸 = thumb `.out` 정본 마크업 그대로(결과 헤더 → 요약 줄 → 타일 → 빈 상태 → 이전 제작 접이).
     ⚠ 순서가 계약이다 — 요약 줄이 **타일 위**(운영자 260806 "이게 저 개별 썸네일형 위에 있어야됨 · 원래 저게 세트였는데 갈라진거네"). */
  function shellHTML(id) {
    return '<button class="hist-h car-h" id="' + id + 'ResH" type="button" aria-expanded="true">'
      + '<span class="hist-ttl"><span class="car-bul" aria-hidden="true">•</span>결과 <span class="hist-cnt" id="' + id + 'ResCnt">(0)</span></span>' + CHEV + '</button>'
      + '<div class="jobs" id="' + id + 'ResJobs"></div>'
      + '<div class="hist-grid" id="' + id + 'ResGrid"></div>'
      + '<div class="hist-empty" id="' + id + 'ResEmpty">아직 제작한 게 없습니다</div>'
      + '<div class="hist" id="' + id + 'Hist">'
      + '<button class="hist-h" id="' + id + 'PrevH" type="button" aria-expanded="false">'
      + '<span class="hist-ttl"><span class="hist-bul" aria-hidden="true">•</span>이전 제작 <span class="hist-cnt" id="' + id + 'PrevCnt">(0)</span></span>'
      + '<span class="hist-note">전 기기 제작 내역</span>' + CHEV + '</button>'
      + '<div class="hist-body" id="' + id + 'PrevBody" hidden>'
      + '<div class="hist-empty" id="' + id + 'PrevEmpty" hidden>아직 제작한 게 없습니다</div>'
      + '<div class="hist-grid" id="' + id + 'PrevGrid"></div></div></div>';
  }

  function tileEl(m, e, gridSel, cntSel) {   // 항목 = 이미지 정본 `.hist-it` 빌더 그대로(시각 라벨 + 타일 + 캡션칩 + [연필][↓])
    var it = document.createElement('div'); it.className = 'hist-it';
    var hd = document.createElement('div'); hd.className = 'hist-hd'; hd.textContent = histTime(e.ts);
    var th = document.createElement('div'); th.className = 'hist-thumb';
    var dl = document.createElement('a'); dl.className = 'imgdl dlbtn'; dl.href = e.url;
    dl.setAttribute('aria-label', '다운로드'); dl.innerHTML = DL_SVG();
    dl.addEventListener('click', function (ev) { ev.preventDefault(); ev.stopPropagation(); dlBlob(e.url, e.dlname || m.opt.dlname); });
    var img = document.createElement('img'); img.loading = 'lazy'; img.alt = ''; img.src = e.poster || e.url;
    img.onerror = function () { it.remove(); m.dead[keyOf(e.url)] = 1; var cc = document.getElementById(cntSel); var g = document.getElementById(gridSel); if (cc && g) cc.textContent = '(' + g.children.length + ')'; };   // 죽은 슬롯 제거 + 카운트 정정 = 이미지 정본 동문
    var cap = document.createElement('span'); cap.className = 'hist-cap'; cap.textContent = esc(e.cap);
    if (e.varStr) { var v = document.createElement('span'); v.className = 'hist-cap-v'; v.textContent = e.varStr; cap.appendChild(v); }
    th.append(dl, img, cap);
    if (e.src && e.src.app && typeof m.opt.onEdit === 'function') {   // 수정(연필) = 복원 경로를 **가진 표면만** 그린다(갈 곳 없는 버튼 금지 = 이미지 정본 canEditSrc 계약 동문)
      var ed = document.createElement('button'); ed.type = 'button'; ed.className = 'imgedit'; ed.title = '이 설정으로 수정'; ed.setAttribute('aria-label', '수정');
      ed.innerHTML = window.EDIT_SVG || '';
      ed.addEventListener('click', function (ev) { ev.preventDefault(); ev.stopPropagation(); m.opt.onEdit(e.src, e.url); });
      th.appendChild(ed);
    }
    it.append(hd, th);
    return it;
  }

  function jobRow(m, a) {   // 요약 줄 = thumb `renderJob` 완료 행(.job.done > .jlab + .jst + .jsave-row) 마크업 그대로
    var host = document.getElementById(m.id + 'ResJobs'); if (!host) return;
    host.innerHTML = '';
    if (!a.length) return;
    var row = document.createElement('div'); row.className = 'job done';
    var lab = document.createElement('span'); lab.className = 'jlab'; lab.textContent = esc(a[0].cap) || '결과';
    var st = document.createElement('span'); st.className = 'jst';
    st.innerHTML = CK_SVG() + '<span>완료 · ' + a.length + '장 · ' + histTime(a[0].ts) + '</span>';
    row.append(lab, st);
    var sv = document.createElement('div'); sv.className = 'jsave-row';
    if (a[0].src && a[0].src.app && typeof m.opt.onEdit === 'function') {
      var ed = document.createElement('button'); ed.type = 'button'; ed.className = 'imgedit'; ed.title = '이 설정으로 수정'; ed.setAttribute('aria-label', '수정');
      ed.innerHTML = window.EDIT_SVG || '';
      ed.addEventListener('click', function (ev) { ev.preventDefault(); ev.stopPropagation(); m.opt.onEdit(a[0].src, a[0].url); });
      sv.appendChild(ed);
    }
    var dl = document.createElement('button'); dl.type = 'button'; dl.className = 'sbtn cref-dlall dlbtn'; dl.title = '전체 다운로드'; dl.setAttribute('aria-label', '전체 다운로드');
    dl.innerHTML = (window.DLSEQ_IC || DL_SVG()) + '<span class="cref-dllbl">전체</span>';
    dl.addEventListener('click', function () { a.forEach(function (e, i) { setTimeout(function () { dlBlob(e.url, e.dlname || m.opt.dlname); }, i * 220); }); });   // 순차 저장 = 이미지 정본 간격(브라우저 다중저장 차단 회피)
    sv.appendChild(dl);
    row.appendChild(sv);
    host.appendChild(row);
  }

  function render(m) {
    var all = prune(load(m.opt.scope)).filter(function (e) { return e && e.url && !m.dead[keyOf(e.url)]; });
    all.sort(function (x, y) { return (y.ts || 0) - (x.ts || 0); });
    var res = all.filter(function (e) { return (e.ts || 0) >= T0; });          // 결과 = 이번 세션 완료분
    if (!res.length && all.length) res = [all[0]];                             // 세션분 0이면 최신 1건 추종 = 이미지 정본(followNewest) 동축 — 창을 다시 열어도 결과가 비지 않는다
    var resK = {}; res.forEach(function (e) { resK[keyOf(e.url)] = 1; });
    var prev = all.filter(function (e) { return !resK[keyOf(e.url)]; });       // 이전 제작 = 결과에 뜬 것 제외(이중노출 차단 = 이미지 정본 동문)

    var rc = document.getElementById(m.id + 'ResCnt'); if (rc) rc.textContent = '(' + res.length + ')';
    var re = document.getElementById(m.id + 'ResEmpty'); if (re) re.hidden = !!res.length;
    var rg = document.getElementById(m.id + 'ResGrid');
    if (rg) { rg.innerHTML = ''; res.forEach(function (e) { rg.appendChild(tileEl(m, e, m.id + 'ResGrid', m.id + 'ResCnt')); }); }
    jobRow(m, res);

    var pc = document.getElementById(m.id + 'PrevCnt'); if (pc) pc.textContent = '(' + prev.length + ')';
    var pe = document.getElementById(m.id + 'PrevEmpty'); if (pe) pe.hidden = !!prev.length;
    var pg = document.getElementById(m.id + 'PrevGrid');
    if (pg) { pg.innerHTML = ''; prev.forEach(function (e) { pg.appendChild(tileEl(m, e, m.id + 'PrevGrid', m.id + 'PrevCnt')); }); }
  }

  function bindFold(m) {   // 접이 = 이미지 정본 동문(hidden + closing 촤르륵 · reduced-motion 즉시)
    var pairs = [[m.id + 'PrevH', m.id + 'PrevBody']];
    pairs.forEach(function (p) {
      var h = document.getElementById(p[0]), b = document.getElementById(p[1]);
      if (!h || !b) return;
      var t = null;
      h.addEventListener('click', function () {
        var open = b.hidden;
        clearTimeout(t); b.classList.remove('closing');
        h.setAttribute('aria-expanded', String(open));
        var hist = document.getElementById(m.id + 'Hist'); if (hist) hist.classList.toggle('open', open);
        if (open) { b.hidden = false; }
        else if (matchMedia('(prefers-reduced-motion:reduce)').matches) { b.hidden = true; }
        else { b.classList.add('closing'); t = setTimeout(function () { b.hidden = true; b.classList.remove('closing'); }, 270); }
      });
    });
    var rh = document.getElementById(m.id + 'ResH');
    if (rh) {
      var els = [m.id + 'ResJobs', m.id + 'ResGrid'];
      rh.addEventListener('click', function () {
        var open = rh.getAttribute('aria-expanded') !== 'true';
        rh.setAttribute('aria-expanded', String(open));
        els.forEach(function (i) { var e = document.getElementById(i); if (e) e.hidden = !open; });
        var re = document.getElementById(m.id + 'ResEmpty'); if (re && !open) re.hidden = true;
      });
    }
  }

  var api = {
    mount: function (anchor, opt) {   // anchor = 이 요소 **뒤**에 레일을 붙인다(기존 산출 블록 무접촉 = 회귀 0)
      if (!anchor || !anchor.parentNode) return null;
      opt = opt || {};
      var scope = KEYS[opt.scope] ? opt.scope : 'cap';
      var m = { id: 'nmr', opt: { scope: scope, dlname: opt.dlname || 'out', onEdit: opt.onEdit }, dead: {} };
      var wrap = document.createElement('div'); wrap.className = 'out nm-rail'; wrap.innerHTML = shellHTML(m.id);
      anchor.parentNode.insertBefore(wrap, anchor.nextSibling);
      m.el = wrap;
      mounts.push(m);
      bindFold(m);
      render(m);
      return m;
    },
    add: function (e) {   // 완료 1건 적재 = 이 문서 + 형제 탭(같은 스코프) 즉시 반영
      if (!e || !e.url) return;
      mounts.forEach(function (m) {
        var a = prune(load(m.opt.scope));
        var k = keyOf(e.url);
        if (a.some(function (x) { return keyOf(x.url) === k; })) return;   // 중복 적재 차단
        a.push({ url: e.url, poster: e.poster || '', dlname: e.dlname || m.opt.dlname, cap: e.cap || '', varStr: e.varStr || '', ts: e.ts || Date.now(), src: e.src || null });
        while (a.length > HMAX) a.shift();
        save(m.opt.scope, a);
        render(m);
      });
    },
    refresh: function () { mounts.forEach(render); }
  };
  window.nmRail = api;

  /* 자동 마운트 = **상속을 진짜 1줄로**(운영자 260806 "항상 저렇게 유지되어야하고") ──
     구판은 각 문서가 마운트 1줄을 따로 들었는데, 그 한 줄이 문서마다 다른 자리에 놓이며 **콘티·큐영상 2탭이 조용히 안 붙었다**(실측 260806:
     `nmRail` 로드·`#out` 실존인데 `.nm-rail` 0 = 스니펫 미실행 · 에러 0 = 무증상). 사본이 있으면 갈라진다는 오늘의 결론과 같은 축이라 진입점을 여기로 회수한다.
     앵커 = 문서가 이미 가진 산출 컨테이너를 순서대로 탐색(그 블록 **뒤**에 붙어 무접촉) · 하나도 없으면 본문 말미 = 어느 문서든 반드시 선다.
     스코프·파일명은 `<script src="nm-rail.js" data-scope="cap" data-dlname="video.mp4">`로 문서가 선언(속성 없으면 cap 기본). */
  function autoMount() {
    if (document.querySelector('.nm-rail')) return;   // 이미 수동 마운트한 문서 = 무동작(idempotent)
    var tag = document.querySelector('script[src$="nm-rail.js"]');
    var scope = (tag && tag.getAttribute('data-scope')) || 'cap';
    var dln = (tag && tag.getAttribute('data-dlname')) || 'out';
    var want = tag && tag.getAttribute('data-anchor');   // 문서가 자기 앵커를 지목할 수 있다(자동 탐색이 못 고르는 골격 = vd처럼 `#jobs`가 팝업 안에 있는 문서)
    var vis = function (e) { return !!(e && (e.offsetParent || e.getClientRects().length)); };   // 숨은 조상 안 앵커 = 레일도 같이 사라진다(실측 260806 큐영상: DOM엔 섰는데 rect 0 = 무증상 실종) → 가시성까지 판정
    var anchor = null;
    if (want) { var w = document.querySelector(want); if (vis(w)) anchor = w; }
    if (!anchor) ['out', 'jobs'].some(function (id) { var e = document.getElementById(id); if (vis(e)) { anchor = e; return true; } return false; });
    if (!anchor) ['.out', '.jobs'].some(function (q) { var e = document.querySelector(q); if (vis(e)) { anchor = e; return true; } return false; });
    if (!anchor) {   // 산출 컨테이너가 없는 문서 = 본문 말미에 자기 자리를 만든다(빈 상태 레일이 서고, add()가 들어오면 그대로 채워진다)
      var wrapEl = document.querySelector('.wrap') || document.body;
      anchor = document.createElement('div'); anchor.className = 'nm-rail-anchor'; wrapEl.appendChild(anchor);
    }
    api.mount(anchor, { scope: scope, dlname: dln });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', autoMount);
  else autoMount();

  /* 형제 탭 동기 = 같은 스코프 키를 쓰는 다른 탭의 적재를 즉시 수신(이미지 정본 storage 수신 동문) + 복귀 3축.
     ⚠ 영상 5탭은 각자 iframe 문서라 같은 키를 공유하면 이 리스너만으로 전부 수렴한다(폴링 불요 = 부하 0). */
  window.addEventListener('storage', function (ev) {
    if (!ev) return;
    var hit = Object.keys(KEYS).some(function (s) { return KEYS[s] === ev.key; });
    if (hit) api.refresh();
  });
  document.addEventListener('visibilitychange', function () { if (!document.hidden) api.refresh(); });
  window.addEventListener('focus', function () { api.refresh(); });
})();
