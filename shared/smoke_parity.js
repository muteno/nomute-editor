#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_parity.js — 크로스-탭 미리보기 '렌더 등가' 상비 실측 스모크 (운영자 260719
//   "너가 실측해서 바꿨다는데 이 둘이 완전 다르다 — 안 그러게 해야된다" = 260719 이식 사고 근본원인 기계화)
//
// ▷ 왜 신설: CII 「합성 미리보기 쉘」을 thumb→index(.geni-prev)로 이식할 때, CSS 텍스트는 복제했으나
//   `var(--line)`/`var(--bg)`가 thumb 툴톤(#2a2c31/#0b0d0c)과 index 팔레트(흰알파/#121212)에서 값이 갈라져
//   테두리·툴 플레이트 색이 달라졌고, 높이 29svh가 iframe↔부모창 문맥차로 어긋났다(284.8 vs 300).
//   단일 뷰 프로브(smoke_preview·픽토 4분할)로는 '편집 탭 대비 갈라짐'이 원리상 안 잡힌다 →
//   이 스모크가 편집 탭과 AI 생성 탭을 **같은 창에서 실전환·나란히 computedStyle 대조**해 등가를 강제.
//
// 원커맨드:  node shared/smoke_parity.js        (종료코드 0 = 코어 전부 PASS)
//
// 담당 표면(이 파일 헤더 선언 = 변경 시 커밋 전 실행 rc=0): viewer/index.html #geniPrev/#geniPrevBox/#geniSum/#geniStyleEx/#geniRefGhost·#geniWishRow(기본 숨김 · #geniTxtBtn 탭 = 노출 — 운영자 260721 반갈)·빈 상태 중앙 업로드 픽토 단독(#geniRefBtn 무대 정중앙 · #geniTxtBtn = 코너 레일 · 260802)·.genihost .geni-lead(도크 mat·스커트) ↔ viewer/thumb.html #cpPrev .cpprev-box/#optStrip/#topDock(정본)
// 어서션 축: 기하(박스 높이·폭 Δ) + computedStyle 문자열 동일(bg·border·radius·padding·활자·스커트 그라데) + 스트립 상태 점등 문법(라벨+값 쌍·기본 소등·상태 추종 C10~C13 · 운영자 260720) — 환경 간 스크린샷 diff 금지(smoke_preview 규율 계승)
// 리스크 통제: 라이브 코드 무접촉(페이지 전역 실호출 = openTool·geniApply·geniRefPick) · 픽스처 = 페이지 내 canvas(외부 바이너리 0) · 서버 자체 종료 · 결정론 2런.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');

function loadPlaywright() {
  try { return require('playwright-core'); } catch (_) {}
  const cache = path.join(os.tmpdir(), 'nomute-smoke-deps');
  const mod = path.join(cache, 'node_modules', 'playwright-core');
  if (!fs.existsSync(mod)) {
    console.log('· playwright-core 미설치 → 임시 캐시 설치(1회): ' + cache);
    fs.mkdirSync(cache, { recursive: true });
    execSync('npm i --prefix "' + cache + '" playwright-core --no-audit --no-fund --loglevel=error', { stdio: 'inherit' });
  }
  return require(mod);
}
function chromiumPath() {
  const cands = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'];
  try { cands.push(execSync('which chromium chromium-browser google-chrome 2>/dev/null | head -1').toString().trim()); } catch (_) {}
  for (const c of cands) { if (c && fs.existsSync(c)) return c; }
  throw new Error('크로미엄 실행 파일을 못 찾음 — CHROMIUM_PATH env로 지정해라');
}
async function startServer() {
  for (let port = 8831; port < 8836; port++) {   // 8831~ = geni/preview/…/editdock(8826~) 다음 슬롯(무충돌)
    const srv = spawn('python3', ['-m', 'http.server', String(port), '-d', VIEWER], { stdio: 'ignore' });
    const ok = await new Promise(res => {
      let done = false;
      srv.on('exit', () => { if (!done) { done = true; res(false); } });
      setTimeout(async () => {
        if (done) return;
        try { const r = await fetch('http://127.0.0.1:' + port + '/index.html', { method: 'HEAD' }); done = true; res(r.ok); }
        catch (_) { done = true; try { srv.kill(); } catch (e) {} res(false); }
      }, 700);
    });
    if (ok) return { srv, port };
    try { srv.kill(); } catch (_) {}
  }
  throw new Error('정적 서버 기동 실패(8831~8835 전부 불가)');
}

async function runOnce(pg) {
  const out = { core: [], errs: [] };
  const core = (n, c, d) => { out.core.push({ n, c: !!c, d }); };

  await pg.evaluate(() => { openTool('/thumb.html', 'Image Studio', THUMB_TABS, 'thumb'); });
  await pg.waitForTimeout(2600);   // iframe 로드 + thumbTabBridge

  // ── 카드 생성 탭(app2) 실측 = 파리티 기준(정본) ──
  //    ⚠ 계약 갱신(운영자 260731 승인 · 구 기준 = 편집 탭 app7): 편집 도크가 「좌 미리보기 / 우 옵션 컬럼」 2분할로 재편되며
  //    미리보기 폭·요약 스트립이 AI 생성 도크와 구조적으로 갈라졌다(스트립 = 카드 생성 전용 복귀 · 폭 = 옵션 컬럼에 양도).
  //    파리티가 지켜야 할 계약 = 「AI 생성 도크 ↔ 이미지 스튜디오 1단 도크」 동형이므로, 1단을 유지하는 카드 생성 탭으로 기준을 옮긴다.
  //    편집 2분할 도크의 자체 계약(컬럼 폭·폭맞춤·잠금)은 별도 축 = 여기서 감시하지 않는다.
  await pg.evaluate(() => { const t = document.querySelector('#toolTabs .tooltab[data-app="2"]'); if (t) t.click(); });
  await pg.waitForTimeout(1200);
  const ed = await pg.evaluate(() => {
    const fr = document.querySelector('#tooldlg .toolfr.active'); if (!fr) return null;
    const d = fr.contentDocument, w = fr.contentWindow;
    const box = d.querySelector('#cpPrev .cpprev-box');
    const strip = d.querySelector('#optStrip'), spec = strip ? strip.querySelector('.gospec:not(.none)') : null;
    const dock = d.querySelector('#topDock'), dcs = w.getComputedStyle(dock), dca = w.getComputedStyle(dock, '::after');   // 도크 mat·페이드 스커트 = 리드 파리티 정본(운영자 260720 "그라데이션 닫힘 이식")
    const cs = el => { const c = w.getComputedStyle(el); return { bg: c.backgroundColor, bd: c.borderColor, bw: c.borderTopWidth, rad: c.borderRadius, pt: c.paddingTop, pl: c.paddingLeft, mb: c.marginBottom }; };
    const rail = d.querySelector('#cpPrev #cpRail'), rbb = box.getBoundingClientRect();
    const rr = rail ? d.querySelector('#cpRailWrap').getBoundingClientRect() : null;   // 레일 = **창 밖 우측**(운영자 260802 2차 "네비게이션바를 우측으로") — 구 계약(창 안 우상단 여백 0)의 갱신 · 간격 8 = .trailwrap 캡슐 gap 동값
    const bwT = parseFloat(w.getComputedStyle(box).borderTopWidth) || 0;
    return { boxH: box.getBoundingClientRect().height, boxW: box.getBoundingClientRect().width, boxCS: cs(box),
      rail: rr ? { gap: +(rr.left - rbb.right).toFixed(1), t: +(rr.top - rbb.top).toFixed(1) } : null,   // gap = 창 우변↔레일 좌변(8) · t = 상변 정렬(0)
      toolsInRail: !!(rail && d.querySelector('#cpImgSwap') && rail.contains(d.querySelector('#cpImgSwap')) && rail.contains(d.querySelector('#cpImgDel'))),
      stripInRail: !!(rail && strip && rail.contains(strip)),
      stripVis: !!(strip && !strip.classList.contains('none') && strip.getBoundingClientRect().height),
      stripCS: strip ? cs(strip) : null, specFs: spec ? w.getComputedStyle(spec).fontSize : '', specLh: spec ? w.getComputedStyle(spec).lineHeight : '',
      dockBg: dcs.backgroundColor, dockBb: dcs.borderBottomWidth, skirtH: dca.height, skirtBg: dca.backgroundImage,
      specGram: spec ? { lbl: spec.querySelectorAll('.gs-lbl').length, v: spec.querySelectorAll('.gs-v').length } : null };
  });
  core('E0 카드 생성 탭 미리보기·옵션(레일 안 #optStrip) 실측 성립', !!(ed && ed.boxH > 0 && ed.stripVis), ed ? JSON.stringify({ boxH: Math.round(ed.boxH), stripVis: ed.stripVis }) : '편집 프레임 미탐');
  if (!ed) return out;

  // ── AI 생성 탭(app6) 전환 + 실측 ──
  await pg.evaluate(() => { const t = document.querySelector('#toolTabs .tooltab[data-app="6"]'); if (t) t.click(); });
  await pg.waitForTimeout(1300);
  const ai = await pg.evaluate(() => {
    const host = document.querySelector('#geniHost'), box = document.querySelector('#geniPrevBox'), sum = document.querySelector('#geniSum');
    const lead = document.querySelector('#geniHost .geni-lead'), lcs = lead ? getComputedStyle(lead) : null, lca = lead ? getComputedStyle(lead, '::after') : null;   // 리드 = thumb 도크 파리티(mat·스커트 · 운영자 260720)
    const cs = el => { const c = getComputedStyle(el); return { bg: c.backgroundColor, bd: c.borderColor, bw: c.borderTopWidth, rad: c.borderRadius, pt: c.paddingTop, pl: c.paddingLeft, mb: c.marginBottom }; };
    return { hostVis: !!(host && !host.hidden), boxH: box ? box.getBoundingClientRect().height : 0, boxW: box ? box.getBoundingClientRect().width : 0, boxCS: box ? cs(box) : null,
      sumCS: sum ? cs(sum) : null, sumFs: sum ? getComputedStyle(sum).fontSize : '', sumLh: sum ? getComputedStyle(sum).lineHeight : '',
      leadBg: lcs ? lcs.backgroundColor : '', leadBb: lcs ? lcs.borderBottomWidth : '', skirtH: lca ? lca.height : '', skirtBg: lca ? lca.backgroundImage : '',
      sumGram: sum ? { lbl: sum.querySelectorAll('.gs-lbl').length, v: sum.querySelectorAll('.gs-v').length, on: sum.querySelectorAll('.gs-v.on').length } : null,
      wishHidden: (() => { const r = document.querySelector('#geniWishRow'), h = document.querySelector('#geniWishHead'); return !!(r && r.hidden && h && h.hidden); })(),
      wishAlive: !!document.querySelector('#geniWish') };
  });
  core('C0 AI 탭 = genihost 폼 표시(app6 역동기)', ai.hostVis, 'hostVis=' + ai.hostVis);
  core('C1 미리보기 박스 높이 = 편집 탭 등가(Δ≤1px)', Math.abs(ai.boxH - ed.boxH) <= 1, 'card=' + ed.boxH.toFixed(1) + ' ai=' + ai.boxH.toFixed(1) + ' Δ=' + (ai.boxH - ed.boxH).toFixed(2));
  core('C2 박스 쉘 색 동일(bg·border·radius — 크로스-파일 토큰 갈라짐 게이트)', !!ai.boxCS && ai.boxCS.bg === ed.boxCS.bg && ai.boxCS.bd === ed.boxCS.bd && ai.boxCS.bw === ed.boxCS.bw && ai.boxCS.rad === ed.boxCS.rad,
    JSON.stringify({ edit: ed.boxCS, ai: ai.boxCS }));
  core('C3 요약 스트립 박스 동일(bg·border·radius·padding — .optstrip 정본)', !!(ed.stripCS && ai.sumCS) && ai.sumCS.bg === ed.stripCS.bg && ai.sumCS.bd === ed.stripCS.bd && ai.sumCS.rad === ed.stripCS.rad && ai.sumCS.pt === ed.stripCS.pt && ai.sumCS.pl === ed.stripCS.pl,
    JSON.stringify({ edit: ed.stripCS, ai: ai.sumCS }));
  core('C4 스트립 활자 동일(fs·lh)', ai.sumFs === ed.specFs && ai.sumLh === ed.specLh, 'card=' + ed.specFs + '/' + ed.specLh + ' ai=' + ai.sumFs + '/' + ai.sumLh);
  core('C5 텍스트칸 상시 노출(#geniWishRow/Head 고정 — 운영자 260802 「아래에 입력창을 고정값으로」 · 구 픽토 관문 폐지)', !ai.wishHidden && ai.wishAlive, JSON.stringify({ hidden: ai.wishHidden, alive: ai.wishAlive }));

  // ── C5b·C5c 미리보기 빈 상태 반갈(운영자 260721 "좌측은 글 픽토그램, 우측은 사진 픽토그램으로 좌우세로 균형 마진") ──
  //   계약 갱신(운영자 260802 "중앙에는 사진 업로드 그것만 있고 텍스트 버튼은 우측 네비게이션으로") —
  //   구 계약 = 반갈 듀오(글|사진 각 반쪽 중앙) → 신 계약 = **중앙 = 업로드 픽토 단독·무대 4분할 정중앙** + 글 픽토는 코너 레일 안.
  const duo = await pg.evaluate(() => {
    const st = document.querySelector('#geniPrevStage'), em = st && st.querySelector('.cpv-empty');
    const btns = em ? [...em.querySelectorAll('.cpv-photobtn')] : [];
    const txt = document.querySelector('#geniTxtBtn'), rail = document.querySelector('#geniPrev #geniRail');   // 레일 = 창 밖 우측으로 이설(260802 2차) → 조회 기준도 창(#geniPrevBox)이 아닌 미리보기 블록(#geniPrev)
    if (btns.length !== 1) return { n: btns.length };
    const sr = st.getBoundingClientRect();
    const r = btns[0].querySelector('svg').getBoundingClientRect();
    return { n: 1, isPhoto: btns[0].id === 'geniRefBtn', txtGone: !txt,   // 글 픽토 = 폐지(운영자 260802 — 주문칸이 아래 고정이라 진입점 불요)
      dx: (r.left + r.width / 2) - (sr.left + sr.width / 2), dy: (r.top + r.height / 2) - (sr.top + sr.height / 2) };
  });
  core('C5b 중앙 = 사진 픽토 단독·무대 정중앙(Δ≤0.5px) · 글 픽토 폐지(주문칸 아래 고정)', duo.n === 1 && duo.isPhoto && duo.txtGone && [duo.dx, duo.dy].every(v => Math.abs(v) <= 0.5),
    JSON.stringify(duo, (k, v) => typeof v === 'number' ? +v.toFixed(2) : v));
  const wsh = await pg.evaluate(() => { const r = document.querySelector('#geniWishRow'), h = document.querySelector('#geniWishHead'); return { rowVis: !!(r && !r.hidden), headVis: !!(h && !h.hidden) }; });
  core('C5c 주문칸 = 관문 없이 바로 보임(글 픽토 폐지분 · 발사 = 기존 wish 배선 그대로)', wsh.rowVis && wsh.headVis, JSON.stringify(wsh));

  // ── C6 첨부 고스트(운영자 260719 승인) = 같은 이미지 cover .22 언더레이 + 원본 contain 겹침 ──
  await pg.evaluate(async () => {
    const cv = document.createElement('canvas'); cv.width = 640; cv.height = 360;
    const cx = cv.getContext('2d'); cx.fillStyle = '#365a78'; cx.fillRect(0, 0, 640, 360); cx.fillStyle = '#e8eef4'; cx.fillRect(40, 40, 200, 120);
    const blob = await new Promise(r => cv.toBlob(r, 'image/png'));
    await geniRefPick(new File([blob], 'qa.png', { type: 'image/png' }));
  });
  await pg.waitForTimeout(500);
  const gh = await pg.evaluate(() => {
    const g = document.querySelector('#geniRefGhost'), t = document.querySelector('#geniRefThumb');
    const q = s => document.querySelector(s).getBoundingClientRect();
    const box = document.querySelector('#geniPrevBox'); const bw = parseFloat(getComputedStyle(box).borderTopWidth) || 0; const br = box.getBoundingClientRect();
    const xb = document.querySelector('#geniRefX'), sw = document.querySelector('#geniRefSwap');
    const rail = document.querySelector('#geniPrev #geniRail'), rw = document.querySelector('#geniRailWrapPv'), rr = rw ? rw.getBoundingClientRect() : null;   // 레일 = 창 밖 우측(260802 2차)
    return { gVis: !g.hidden && g.getBoundingClientRect().height > 0, gFit: getComputedStyle(g).objectFit, gOp: getComputedStyle(g).opacity,
      tFit: getComputedStyle(t).objectFit, same: g.src === t.src && !!g.src,
      railGap: rr ? +(rr.left - br.right).toFixed(1) : null, railT: rr ? +(rr.top - br.top).toFixed(1) : null,
      toolsInRail: !!(rail && xb && sw && rail.contains(xb) && rail.contains(sw)),
      toolPos: xb ? getComputedStyle(xb).position : '', sumInRail: !!(rail && rail.contains(document.querySelector('#geniSum'))) };
  });
  core('C6 고스트 = cover·opacity .22·원본 contain·동일 src', gh.gVis && gh.gFit === 'cover' && gh.gOp === '0.22' && gh.tFit === 'contain' && gh.same, JSON.stringify({ fit: gh.gFit, op: gh.gOp, t: gh.tFit, same: gh.same }));
  // C7 계약 갱신(운영자 260802 "배경·축약·opa 이런거 우측 네비게이션바로 · 모든 페이지에 해당 미리보기 똑같이"):
  //   구 계약(260801) = 레일이 창 **안** 우상단 여백 0 → 신 계약(운영자 260802 2차 "네비게이션바를 우측으로") = 레일이 창 **밖** 우측, 간격 8·상변 정렬.
  //   thumb(카드 생성)·AI 생성 양쪽에서 같은 계약을 재니 크로스-파일 파리티는 그대로 지켜진다(구 좌표 어서션의 역할 승계).
  core('C7 교체·삭제 = 코너 레일 흡수(절대좌표 퇴역·position static) · 레일 = 창 밖 우측 간격 8·상변 정렬(Δ≤0.5px) · 카드 생성 탭 동형',
    gh.toolsInRail && gh.toolPos === 'static' && Math.abs(gh.railGap - 8) <= 0.5 && Math.abs(gh.railT) <= 0.5 &&
    !!ed.rail && ed.toolsInRail && Math.abs(ed.rail.gap - 8) <= 0.5 && Math.abs(ed.rail.t) <= 0.5,
    JSON.stringify({ ai: { inRail: gh.toolsInRail, pos: gh.toolPos, gap: gh.railGap, t: gh.railT }, card: { inRail: ed.toolsInRail, rail: ed.rail } }));
  core('C7b 옵션 = 레일 값 칩 이주(하단 옵션바 퇴역 — 카드 생성 #optStrip · AI 생성 #geniSum 둘 다 레일 안)', ed.stripInRail && gh.sumInRail,
    JSON.stringify({ card: ed.stripInRail, ai: gh.sumInRail }));
  await pg.evaluate(() => { geniRefClear(); geniApply(); });

  // ── C10~C13 리드 도크·폭·스트립 점등 파리티(운영자 260720 "겉 도형 너비·다 점등·그라데이션 닫힘이 다르다 — 다른쪽 이식") ──
  core('C10 미리보기 박스 폭 = 카드 생성 탭 등가(Δ≤1px — 리드 거터 16 정본)', Math.abs(ai.boxW - ed.boxW) <= 1, 'card=' + ed.boxW.toFixed(1) + ' ai=' + ai.boxW.toFixed(1) + ' Δ=' + (ai.boxW - ed.boxW).toFixed(2));
  core('C11 리드 = thumb 도크 파리티(mat 배경·경계선 0·페이드 스커트 h/그라데 동일)', ai.leadBg === ed.dockBg && ai.leadBb === ed.dockBb && ai.skirtH === ed.skirtH && ai.skirtBg === ed.skirtBg,
    JSON.stringify({ edit: { bg: ed.dockBg, bb: ed.dockBb, sh: ed.skirtH }, ai: { bg: ai.leadBg, bb: ai.leadBb, sh: ai.skirtH, sameGrad: ai.skirtBg === ed.skirtBg } }));
  core('C12 스트립 문법 = 6항 나열(모델·비율·화풍·세부 = 라벨+값 4쌍 · 한국웹툰화·문구 = 자립 토글 2 · 운영자 260727 "ON/OFF 없애고 글자만") · 기본 상태 = 값 축 4 + 웹툰화 ON = 5점등(운영자 260728 "선택된 옵션은 모두 강조색" — 구 "한국웹툰화만 점등" 계약 갱신 · 문구 OFF만 소등)', !!(ai.sumGram && ed.specGram) && ed.specGram.lbl > 0 && ai.sumGram.lbl === 4 && ai.sumGram.v === 6 && ai.sumGram.on === 5,
    JSON.stringify({ edit: ed.specGram, ai: ai.sumGram }));
  await pg.evaluate(() => { const b = document.querySelector('#geniHost .geni-opts[data-k="aspect"] .geni-opt[data-v="9:16"]'); if (b) b.click(); });   // 상태 추종 실측 = 비율 9:16 선택(구 해상도 2K = 5항 축소로 요약 밖 → 잔존 5항 안 옵션으로 교체)
  const lit = await pg.evaluate(() => { const s = document.querySelector('#geniSum'); const on = [...s.querySelectorAll('.gs-v.on')].map(e => e.textContent); return { n: on.length, has916: on.includes('9:16') }; });
  core('C13 점등 = 값 축 상시(비율 9:16 선택 → 값은 바뀌어도 점등 유지 = 5점등 · 기본값이든 아니든 고른 값은 선택이다)', lit.n === 5 && lit.has916, JSON.stringify(lit));
  const tog = await pg.evaluate(() => {   // 요약바 글자 탭 = 그 옵션 전환(운영자 260728 "글자 클릭하면 옵션이 바뀌게 · 각 옵션에 따라 귀속") — 값 축 = 다음 값 순환 · ON/OFF 축 = 뒤집기 · 본문 칩 동기까지 실측
    const q = k => document.querySelector('#geniHost #geniSum [data-tg="' + k + '"]');
    const a0 = q('aspect').textContent.trim(); q('aspect').click();
    const a1 = q('aspect').textContent.trim();
    const bodyAsp = (document.querySelector('#geniHost .geni-opts[data-k="aspect"] .geni-opt.on') || {}).dataset;
    const t0 = q('textOn').classList.contains('on'); q('textOn').click();
    const t1 = q('textOn').classList.contains('on');
    const bodyTxt = (document.querySelector('#geniHost #geniTextOn') || {}).textContent;
    q('textOn').click();   // 원복(결정론 2런)
    return { a0, a1, bodyAsp: bodyAsp && bodyAsp.v, t0, t1, bodyTxt };
  });
  core('C14 요약바 글자 탭 = 옵션 전환(값 축 순환 + ON/OFF 뒤집기 · 본문 칩 동기)', tog.a0 === '9:16' && tog.a1 === '16:9' && tog.bodyAsp === '16:9' && tog.t0 === false && tog.t1 === true && tog.bodyTxt === '켜짐', JSON.stringify(tog));
  await pg.evaluate(() => { const b = document.querySelector('#geniHost .geni-opts[data-k="aspect"] .geni-opt[data-v="4:5"]'); if (b) b.click(); });   // 기본값 원복(결정론 2런)

  // ── C15 레일 칩 **광학 잉크선** 4탭 정합(운영자 260802 "광학-잉크" · 이번 롤백 사고의 기계화) ──
  //   왜 잉크인가: 박스 x가 같아도 padding-left가 갈리면 **눈에 보이는 글자 시작선**이 어긋난다.
  //   260802 실측 = 박스는 4탭 전부 330.5로 같았는데 잉크는 편집만 330.5(pad 0) / 나머지 335.5(pad 5) →
  //   박스 기준 검사였다면 통과했을 어긋남이다. 그래서 판정 축 = Range 잉크 사각형(사람이 보는 것과 동일).
  //   기준선 = 카드 생성 탭(파리티 정본 · 위 C10~C14와 동일 기준). 낱말 칩만 대상(OPA ± 스테퍼는 자체 좁은 패딩이 정본).
  const INK_BASE = {};   // **비어 있음 = 4탭 전부 한 세로선이 현재 정본**(260802 3차 실측 9px). 구 `{편집:2.6}` 면책은 그 드리프트가 실제로 해소되며 회수 — 처방은 주석이 예고했던 그 한 줄(`.cpprev .trail-v.dockopt .rsz-opts .ropt{padding:0 5px;font-size:10.5px}` 특이도 0,5,0 승격 = 컬럼 시절 규칙 `.dockopt .rsz-opts .ropt{padding:2px 0}`의 소스 후행 승리 차단). ⚠ 면책을 남겨두면 같은 2.6px 회귀가 조용히 다시 통과한다 = 회수가 수리의 일부 · 여기 적힌 값 **이하**면 통과, 커지거나 새 탭이 갈라지면 FAIL(= check_refs raw 값 baseline 문법 동문)
  const ink = {};
  for (const [app, ko] of [['2', '카드생성'], ['7', '편집'], ['tr', '번역'], ['6', 'AI생성']]) {
    await pg.evaluate(a => { const t = document.querySelector('#toolTabs .tooltab[data-app="' + a + '"]'); if (t) t.click(); }, app);
    await pg.waitForTimeout(1300);
    ink[ko] = await pg.evaluate(() => {
      const fr = document.querySelector('#tooldlg .toolfr.active');
      const d = (fr && fr.contentDocument) ? fr.contentDocument : document;
      const rail = d.querySelector('#cpRail') || document.querySelector('#geniRail');
      const c = [...(rail ? rail.querySelectorAll('.gs-v, .ropt') : [])].filter(e => e.offsetParent !== null && !e.closest('.gs-og'))[0];
      if (!c) return null;
      const rg = d.createRange(); rg.selectNodeContents(c);
      // 잉크선 = **캡슐 좌변 기준 상대값**(절대 x 금지 — 레일은 미리보기 창 우변에 붙어 탭마다 창 폭이 다르면 절대 x가 갈린다 = 정렬과 무관한 위양성)
      return { t: c.textContent.trim().slice(0, 6), inkX: +(rg.getBoundingClientRect().x - rail.getBoundingClientRect().x).toFixed(1), padL: getComputedStyle(c).paddingLeft, fs: getComputedStyle(c).fontSize };
    });
  }
  const ref = ink['카드생성'] ? ink['카드생성'].inkX : null;
  const drift = Object.entries(ink).filter(([, v]) => v).map(([ko, v]) => ({ ko, d: +(v.inkX - ref).toFixed(1), over: Math.abs(v.inkX - ref) > (INK_BASE[ko] || 0) + 0.5 }));
  core('C15 레일 칩 광학 잉크 시작선 = 4탭 한 세로선(기준 = 카드 생성 · 알려진 baseline 초과·신규 어긋남 = FAIL · 운영자 260802 "광학-잉크")',
    ref !== null && drift.length === 4 && drift.every(x => !x.over),
    JSON.stringify({ ref, drift: drift.map(x => x.ko + ':' + (x.d > 0 ? '+' : '') + x.d + (x.over ? '⚠' : '')), 상세: ink }));

  return out;
}

(async () => {
  let srv = null, browser = null; let fail = 0;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath() });
    const runs = [];
    for (let i = 0; i < 2; i++) {   // 결정론 2회(뷰포트 고정 = 크로스-탭 등가는 뷰포트 무관 축)
      const pg = await browser.newPage({ viewport: { width: 1012, height: 1218 } });
      const errs = [];
      const reqLog = { ext: [], api: [] };
      pg.on('request', rq => { const u = rq.url(); if (!u.startsWith('http://127.0.0.1:') && !u.startsWith('data:') && !u.startsWith('blob:')) reqLog.ext.push(u.slice(0, 60)); if (u.includes('/api/')) reqLog.api.push(u.slice(0, 60)); });
      pg.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
      await pg.goto('http://127.0.0.1:' + st.port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
      await pg.waitForTimeout(1600);
      const o = await runOnce(pg);
      o.core.push({ n: 'C8 페이지 에러 0', c: errs.length === 0, d: errs.join(' · ') || '0건' });
      o.core.push({ n: 'C9 외부 호스트 유출 0(로컬 /api = 실앱 부팅 정상 · 크로스탭이라 index 전체 로드)', c: reqLog.ext.length === 0, d: JSON.stringify({ ext: reqLog.ext.slice(0, 2), 로컬api: reqLog.api.length }) });
      runs.push(o);
      await pg.close();
    }
    const [a, b] = runs;
    const sig = o => o.core.map(x => x.n + x.c).join('|');
    const stable = sig(a) === sig(b);
    console.log('── [코어] (합격 필수 · 편집 탭 vs AI 생성 탭 렌더 등가)');
    a.core.forEach(x => { if (!x.c) fail++; console.log((x.c ? 'PASS' : 'FAIL') + ' | ' + x.n + (x.d ? ' | ' + x.d : '')); });
    console.log('── 2회 판정 동일 = ' + (stable ? 'PASS' : 'FAIL(플레이크)'));
    if (!stable) fail++;
  } catch (e) { console.log('ABORT | ' + String(e.message).slice(0, 200)); fail++; }
  finally { if (browser) { try { await browser.close(); } catch (_) {} } if (srv) { try { srv.kill(); } catch (_) {} } }
  console.log('── smoke_parity ' + (fail ? 'FAIL ' + fail + '건' : '코어 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})();
