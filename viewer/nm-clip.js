// ═══ nm-clip.js — 입력칸 클립(복사·붙여넣기·지우개/되돌리기) 단일정본 ═══════════════════
// 운영자 260803 "모든 텍스트 입력창에는 (클립이) 붙어있어야돼 · 공식처럼가야함".
//   구조: 이 파일 1개 = 전 뷰어 공용 부품(nm-svg.js·nm-loader.js·nm-sync.js 하우스 패턴 동축).
//   상속 = `<link rel="stylesheet" href="nm-clip.css">` + `<script src="nm-clip.js"></script>` 2줄.
//   ⚠ 아이콘 의존 = nm-svg.js(CHECK/COPY/PASTE/ERASE/UNDO_SVG) → nm-svg.js를 **먼저** 로드한다.
//   내용 = index.html 인라인 정본의 **바이트 이관**(로직 무변경 · 260627~260702 계약 그대로).
//   신규 칸을 만들면 attachCopyPaste(el, true) 한 줄이 계약(강제 = check_refs.check_clip_coverage).
// ── 입력칸 복사/붙여넣기/지우개·되돌리기 = 이미지 제작(thumb.html) attachCopyPaste 그대로 이식 (운영자 260627) ──
const ERASE_UNDO_MS = 10000;   // 지움 후 되돌리기 노출 시간(~10초)
async function clipCopy(text, btn, after) {   // 복사 → ✓ 피드백
  try { await navigator.clipboard.writeText(text || ''); } catch {}
  btn.innerHTML = CHECK_SVG; btn._icon = 'check'; btn.classList.add('ok');   // _icon 갱신 = 'ok' 해제 후 refresh가 원아이콘 복원하게(번쩍 가드와 짝)
  setTimeout(() => { btn.classList.remove('ok'); after(); }, 1200);
}
// ⚠️⚠️ 통일 기틀(운영자 260628): 칩/입력칸 붙여넣기 = readText 우선 / 막힌 환경(모바일 iframe·칩은 네이티브 길게눌러 붙여넣기 불가)엔 '길게 눌러 붙여넣기' 폴백.
//   index.html(카드 변경 칩·입력칸) ↔ thumb.html(카드뉴스 제작 칩·입력칸) **양쪽 동일 유지** — 한쪽 바뀌면 반드시 양쪽 통일. 정본 동기화 의무(§📐 드리프트 차단).
async function clipPasteText() {   // 클립보드 텍스트 읽기(폴백 포함) — 칩·textarea 공용
  try { if (navigator.clipboard && navigator.clipboard.readText) { const t = await navigator.clipboard.readText(); if (t) return t; } } catch {}
  return await clipPasteFallback();   // readText 거부/빈값 → 사용자 네이티브 붙여넣기 받는 입력
}
function clipPasteFallback() {
  return new Promise(resolve => {
    const ov = document.createElement('dialog'); ov.className = 'pastefb';   // dialog = top-layer(카드변경 등 열린 모달 위에도 보장)
    ov.innerHTML = '<div class="pastefb-box"><div class="pastefb-msg">아래 칸을 <b>길게 눌러 “붙여넣기”</b> 하면 자동 반영돼</div>'
      + '<textarea class="pastefb-ta" placeholder="여기에 붙여넣기" autocapitalize="off" autocomplete="off" spellcheck="false"></textarea>'
      + '<div class="pastefb-row"><button type="button" class="pastefb-btn pastefb-cancel">취소</button><button type="button" class="pastefb-btn pastefb-ok">적용</button></div></div>';
    document.body.appendChild(ov);
    const ta = ov.querySelector('.pastefb-ta'); let done = false;
    const finish = v => { if (done) return; done = true; try { ov.close(); } catch {} ov.remove(); resolve(v || null); };
    ta.addEventListener('paste', () => setTimeout(() => { if (ta.value) finish(ta.value); }, 30));   // 붙여넣기 즉시 자동 반영
    ov.querySelector('.pastefb-ok').onclick = () => finish(ta.value);
    ov.querySelector('.pastefb-cancel').onclick = () => finish(null);
    ov.addEventListener('cancel', e => { e.preventDefault(); finish(null); });   // ESC
    ov.addEventListener('click', e => { if (e.target === ov) finish(null); });   // 백드롭 탭
    try { ov.showModal(); } catch { ov.setAttribute('open', ''); }
    setTimeout(() => { try { ta.focus(); } catch {} }, 60);
  });
}
function attachCopyPaste(el, withErase) {   // 빈칸=붙여넣기 / 내용 있으면 [복사][붙여넣기](+지우개) · 지우개 누르면 비움→~10초 되돌리기. thumb.html 정본과 동일 로직(운영자 260627)
  if (!el || el._clipBound) return; el._clipBound = true;   // 중복 부착 가드
  const wrap = document.createElement('div'); wrap.style.position = 'relative'; wrap.classList.add('iowrap');
  el.parentNode.insertBefore(wrap, el); wrap.appendChild(el);
  const split = true;   // 붙여넣기 항상 유지 + 복사 별도(좌측)
  const nBtn = (split ? 2 : 1) + (withErase ? 1 : 0);
  el.style.paddingRight = (el.tagName !== 'TEXTAREA') ? (14 + nBtn * 32) + 'px' : '42px';   // 텍스트칸 = 버튼이 1행 위 테두리로 떠 안 겹침 → 42 유지
  const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'iobtn iobtn-edge' + (withErase ? ' iobtn-pp' : ''); wrap.appendChild(btn);
  let copyB = null;
  if (split) {
    copyB = document.createElement('button'); copyB.type = 'button'; copyB.className = 'iobtn iobtn-edge iobtn-copy' + (withErase ? ' iobtn-copy-e' : '') + ' iobtn-hide';
    copyB.innerHTML = COPY_SVG; copyB.setAttribute('aria-label', '복사'); copyB.title = '복사';
    copyB.onclick = ev => { ev.preventDefault(); clipCopy(el.value, copyB, refresh); };
    wrap.appendChild(copyB);
  }
  let eraser = null, undoTimer = null, undoVal = '', prog = false, armUndo = null;   // prog = 프로그램적 변경(지움/복원) = 되돌리기창 종료 트리거 아님 · armUndo = 되돌리기 무장(지움·붙여넣기 공용)
  const setIcon = (b, svg, key) => { if (b._icon !== key) { b.innerHTML = svg; b._icon = key; } };   // 아이콘 동일하면 innerHTML 재대입 안 함 = 타이핑마다 SVG 파괴·재생성(번쩍거림) 차단(운영자 260628)
  const refresh = () => {
    const filled = (el.value || '').trim().length > 0;
    if (!btn.classList.contains('ok')) { setIcon(btn, PASTE_SVG, 'paste'); btn.dataset.mode = 'paste'; btn.setAttribute('aria-label', '붙여넣기'); btn.title = '붙여넣기'; }
    if (copyB && !copyB.classList.contains('ok')) { setIcon(copyB, COPY_SVG, 'copy'); copyB.classList.toggle('iobtn-hide', !filled); }
    if (eraser) eraser.classList.toggle('iobtn-off', !filled && !eraser.classList.contains('iobtn-undo'));
  };
  if (withErase) {
    eraser = document.createElement('button'); eraser.type = 'button'; eraser.className = 'iobtn iobtn-edge iobtn-erase';
    eraser.innerHTML = ERASE_SVG; eraser.setAttribute('aria-label', '입력 지우기'); eraser.title = '입력 지우기';
    const exitUndo = () => {
      if (undoTimer) { clearTimeout(undoTimer); undoTimer = null; }
      eraser.classList.remove('iobtn-undo'); eraser.innerHTML = ERASE_SVG;
      eraser.setAttribute('aria-label', '입력 지우기'); eraser.title = '입력 지우기'; refresh();
    };
    armUndo = prev => {   // 직전 입력(prev) 복원용 되돌리기 무장 — 지움·붙여넣기 공용
      undoVal = prev;
      eraser.classList.remove('iobtn-off'); eraser.classList.add('iobtn-undo');
      eraser.innerHTML = UNDO_SVG; eraser.setAttribute('aria-label', '되돌리기'); eraser.title = '되돌리기 (직전 입력 복원)';
      if (undoTimer) clearTimeout(undoTimer); undoTimer = setTimeout(exitUndo, ERASE_UNDO_MS);
    };
    eraser.onclick = ev => {
      ev.preventDefault();
      if (el.disabled) return;   // 비활성 칸 우회 입력 차단(운영자 260628)
      if (eraser.classList.contains('iobtn-undo')) {   // 되돌리기 모드 = 직전 입력 복원
        prog = true; el.value = undoVal; el.dispatchEvent(new Event('input', { bubbles: true })); prog = false;
        try { el.focus(); } catch {} exitUndo(); return;
      }
      if (!(el.value || '').length) return;
      const prev = el.value;
      prog = true; el.value = ''; el.dispatchEvent(new Event('input', { bubbles: true })); prog = false;
      try { el.focus(); } catch {}
      armUndo(prev);
    };
    el.addEventListener('input', () => { if (!prog && undoTimer) exitUndo(); });
    wrap.appendChild(eraser);
  }
  btn.onclick = async ev => {
    ev.preventDefault();
    if (el.disabled) return;   // 비활성 칸 우회 입력 차단(운영자 260628)
    const selS = el.selectionStart, selE = el.selectionEnd;   // await 전 캐럿/선택 스냅
    const t = await clipPasteText();   // readText→폴백 공용(통일 기틀)
    if (t) {
      const prev = el.value;
      prog = true;
      if (typeof el.setRangeText === 'function' && typeof selS === 'number') el.setRangeText(t, selS, selE, 'end');   // 캐럿/선택영역에 삽입(기존 보존) = 일반 붙여넣기 · 덮어쓰기 폐지(운영자 260702)
      else el.value += t;   // 폴백 = 끝에 이어붙임
      el.dispatchEvent(new Event('input', { bubbles: true })); prog = false;   // 삽입 후 수동 input(refresh·자간 등) · prog=되돌리기창 즉시종료 방지
      if (armUndo && prev) armUndo(prev);   // 붙여넣기도 되돌리기 가능(직전 전체값 복원·운영자 260628)
    }
    refresh();   // 붙여넣기(캐럿삽입)
  };
  el.addEventListener('input', refresh); refresh();
}
