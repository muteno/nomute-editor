// Cloudflare Pages Function — 발행본 공개 서빙 /s/<slug> (pending.js raw 읽기 패턴 계승).
// published/<slug>.json(publish.js가 커밋) 읽어 → 만료·공개범위·핀 게이트 → 자기완결 HTML 응답.
// ⚠️ 이 경로(/s/*)만 Cloudflare Access Bypass(공개)로 열림 — 나머지 apps.nomute.kr은 비번 그대로(CLAUDE.md §🔒).
//    저장된 html은 자기완결(API 호출0·데이터 인라인)이라 이 구멍으로 본체·다른 발행본 접근 불가.
// noindex 헤더로 검색 인덱싱 차단. 만료/비공개/핀틀림은 콘텐츠 대신 안내 페이지.
// env: GH_TOKEN(contents:read · publish/pending 동일 PAT).
const REPO = 'muteno/nomute-editor';

export async function onRequestGet({ params, request, env }) {
  const slug = String(params.slug || '').toLowerCase().replace(/[^a-z0-9-]/g, '').slice(0, 30);   // 시각프리픽스(base36)+hex+하이픈만(경로주입·확장자 차단 — /·. 불가)
  if (!slug) return page('링크가 올바르지 않습니다.', 404);
  if (!env.GH_TOKEN) return page('서버 설정 오류입니다.', 500);

  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/published/${slug}.json?ref=main`, {
    headers: { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' },
  });
  if (!r.ok) return page('없는 링크이거나 이미 삭제된 발행본입니다.', 404);

  let m;
  try { m = JSON.parse(await r.text()); } catch { return page('발행본을 읽을 수 없습니다.', 500); }

  if (m.scope !== 'public') return page('비공개로 설정된 발행본입니다.', 403);
  if (m.exp && Date.now() > m.exp) return page('만료된 링크입니다. (발행 후 기간이 지났어요)', 410);

  // 핀 잠금 — ?p=123456. 없거나 틀리면 입력 폼. 오류 5회 누적 = 10분 접속 잠금(운영자 260703).
  // 카운터 = Cloudflare Cache API(colo 단위·TTL 600s) — KV 바인딩 없는 이 프로젝트의 무설정 서버측 상태.
  // 같은 이용자는 같은 colo라 체감상 전역이지만 분산 IP·캐시 축출엔 fail-open(가용성 우선·완화 목적).
  if (m.pinHash) {
    const pin = new URL(request.url).searchParams.get('p') || '';
    const isMaster = pin === PIN_MASTER;                          // 마스터 = 잠금 즉시 해제·오류 미집계(운영자 전용)
    let fails = await lockGet(slug);
    if (fails >= LOCK_MAX) {
      if (isMaster) { await lockClear(slug); return pinForm(slug, 0, MASTER_NOTICE); }   // 마스터 = 잠금 초기화 + 안내(운영자 260703)
      return pinForm(slug, fails);
    }
    if (!/^\d{6}$/.test(pin)) return pinForm(slug, 0);
    const h = await sha256hex(pin + ':' + slug);
    if (h !== m.pinHash) {
      if (isMaster) { await lockClear(slug); return pinForm(slug, 0, MASTER_NOTICE); }   // 마스터 = 잠금 초기화 + 안내(문서 안 엶 = 리셋 도구)
      fails += 1; await lockSet(slug, fails);
      return pinForm(slug, fails);
    }
    await lockClear(slug);                                        // 성공 = 카운터 리셋
  }

  const cacheable = !m.pinHash;   // 핀 있으면 캐시 금지(응답 유출 방지) · 무핀만 짧은 엣지캐시 → 반복/프리뷰봇 히트를 CF가 흡수 = 공용 PAT DoS 완화(검증10 H1)
  // ⚠️ s-maxage 60s = 발행 후 사후 잠금(api/relock ON) 시 엣지에 캐시된 무핀 본문 노출창을 ≤60s로 축소(relock가 CF 캐시를 퍼지 못 함 · 옛 300s는 최대 5분 노출 = 잠금 의미 훼손 · 평의회 260702).
  return new Response(m.html || '', {
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': cacheable ? 'public, max-age=60, s-maxage=60' : 'no-store',
      'x-robots-tag': 'noindex, nofollow',
      'x-content-type-options': 'nosniff',
      'referrer-policy': 'no-referrer',
      // CSP: connect-src 'none' = 발행본 페이지서 동일오리진 fetch 차단(본체 API 우회 원천봉쇄·검증1/2/4/5 5명 지적). frame-ancestors 'none'·form-action 'none'.
      'content-security-policy': "default-src 'none'; img-src data: https:; style-src 'unsafe-inline'; font-src https://cdn.jsdelivr.net; script-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    },
  });
}

async function sha256hex(s) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, '0')).join('');
}

// 핀 오류 잠금 — 5회 누적 = 10분(운영자 260703). 카운터는 colo 캐시(키 = .invalid 가상 URL·실서빙 충돌 0).
// 실패 시마다 TTL 갱신(슬라이딩) → 잠금은 마지막 오류로부터 10분. try/catch 전부 fail-open(잠금이 열람을 못 죽이게).
const PIN_MASTER = '898900';
const MASTER_NOTICE = '마스터 확인 · 접속 잠금을 초기화했어요 — 원래 PIN을 입력하면 열려요';   // 마스터 입력 시 안내(운영자 260703 · 문서를 여는 게 아니라 5회 잠금 카운터를 리셋하는 도구)
const LOCK_MAX = 5, LOCK_TTL = 600;
function lockKey(slug) { return 'https://pinlock.nomute.invalid/' + slug; }
async function lockGet(slug) {
  try { const r = await caches.default.match(lockKey(slug)); return r ? (parseInt(await r.text(), 10) || 0) : 0; } catch { return 0; }
}
async function lockSet(slug, n) {
  try { await caches.default.put(lockKey(slug), new Response(String(n), { headers: { 'cache-control': `max-age=${LOCK_TTL}` } })); } catch {}
}
async function lockClear(slug) {
  try { await caches.default.delete(lockKey(slug)); } catch {}
}

// 안내/에러 페이지 — 자기완결(외부 리소스0·다크). 본체 링크·API 노출 없음(우회 차단).
// 색·반지름은 viewer/index.html :root 토큰을 그대로 인라인 복제(CSP가 외부 CSS 차단 → 링크 불가 · 기틀 계승).
function shell(inner) {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark">
<meta name="robots" content="noindex,nofollow"><title>노뮤트 발행본</title>
<style>:root{--accent:#0FFD02;--accent-rgb:15,253,2;--accent-dim:rgba(15,253,2,.13);--on-accent:#062108;--fg:#eef7f0;--mut:#8fa697;--danger:#ff5b4a;--danger-rgb:255,91,74;--r-modal:22px}
html,body{margin:0;height:100%;background:#0b0d0c;color:var(--fg);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
.wrap{min-height:100%;display:grid;place-items:center;padding:24px;box-sizing:border-box}
.card{max-width:360px;width:100%;text-align:center;background:linear-gradient(165deg,rgba(28,30,33,.96),rgba(15,16,18,.98));border:1px solid rgba(255,255,255,.08);border-radius:var(--r-modal);padding:26px 22px}
.card .m{font-size:15px;font-weight:800;color:var(--mut);letter-spacing:-.2px}
.err{color:var(--danger);font-size:12px;margin-top:11px;font-weight:700;white-space:nowrap}</style></head><body><div class="wrap"><div class="card">${inner}</div></div></body></html>`;
}
function page(msg, status = 200) {
  return new Response(shell(`<div class="m">${esc(msg)}</div>`), {
    status, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex, nofollow' },
  });
}
// 핀 입력 폼 — 뷰어 기틀 계승. 6자리 채우면 *자동 검증*(별도 '열기' 버튼 없음 · 카드 배경 제거 = 글자·입력칸만 · 운영자 260703).
// PIN 마스킹(현재 입력한 숫자만 노출·나머지 •) + MUT색 눈 토글(전체 표시). CSP 헤더 없음 → 인라인 style/script 동작.
// 흐름: 6자리 입력 → 140ms 후 자동 발사(중립 '확인 중' 글로우) → GET 네비게이션으로 서버 검증(빠른 확인 = 운영자 260703).
//   성공 = 서버가 문서 HTML로 응답(페이지 교체 = 자동 오픈) / 실패 = 서버가 이 폼을 fails>0으로 재응답 → 로드 시 흔들림+빨강 점등+처음부터(입력 빈 상태).
//   notice(마스터 입력 시) = 접속 잠금 초기화 안내(.info accent · 에러 아님 → 흔들림 없음).
// ⚠️ 화면 입력칸에 pattern 금지 + form novalidate — 마스킹값(•)이 숫자 패턴에 걸려 브라우저 기본 말풍선이 submit을 가로챔(260702 실측). 검증은 JS(real.length)·에러는 .err 한 줄 텍스트로만.
function pinForm(slug, fails, notice) {
  const locked = fails >= LOCK_MAX;
  const msg = locked ? 'PIN 오류 5회 누적으로 10분 간 접속이 불가합니다'
    : fails > 0 ? `핀이 맞지 않아요 (${fails}/${LOCK_MAX})` : '';
  const info = notice ? esc(notice) : '';
  const inner = `<div class="m">PIN으로 잠긴 문서입니다.</div>
<form id="f" method="get" action="/s/${slug}" novalidate>
  <div class="pinwrap" id="pinwrap">
    <input id="pin" name="p" type="text" inputmode="numeric" maxlength="6" placeholder="••••••" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" autofocus>
    <button type="button" id="eye" class="eye" aria-label="PIN 표시">
      <svg class="on" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>
      <svg class="off" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7c2 0 3.7.6 5.2 1.5M22 12s-3.5 7-10 7c-2 0-3.7-.6-5.2-1.5"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><path d="M3 3l18 18"/></svg>
    </button>
  </div>
</form><div class="err" id="verr"${msg ? '' : ' hidden'}>${msg}</div><div class="info" id="vinfo"${info ? '' : ' hidden'}>${info}</div>
<style>
.card{background:none;border:none;padding:6px 4px}   /* 카드 패널(글자 뒤 배경) 제거 — 글자·입력칸만 흑배경 위에(운영자 260703 · pinForm 한정 오버라이드·에러/안내 page()는 카드 유지) */
.pinwrap{position:relative;margin-top:18px}
#pin{width:100%;box-sizing:border-box;height:56px;padding:0 46px;text-align:center;font-size:22px;letter-spacing:10px;font-weight:800;font-family:inherit;border-radius:14px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);color:var(--fg);caret-color:var(--accent);outline:none;transition:border-color .18s ease,box-shadow .18s ease,color .18s ease}
#pin::placeholder{color:var(--mut);letter-spacing:8px}
#pin:focus{border-color:rgba(var(--accent-rgb),.55);box-shadow:0 0 0 3px rgba(var(--accent-rgb),.14)}
.eye{position:absolute;right:8px;top:50%;transform:translateY(-50%);width:34px;height:34px;display:grid;place-items:center;padding:0;border:none;background:none;color:var(--mut);cursor:pointer;border-radius:9px;-webkit-tap-highlight-color:transparent}
.eye:active{transform:translateY(-50%) scale(.85)}
.eye svg{grid-area:1/1;width:21px;height:21px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.eye .off{display:none}
/* 확인 중 = 중립 accent 글로우 펄스(성공/실패는 서버가 결정 = 가짜 성공 애니 없음) */
#pin.checking{border-color:rgba(var(--accent-rgb),.7);color:var(--accent);caret-color:transparent;pointer-events:none;animation:pinPulse .85s ease infinite}
@keyframes pinPulse{0%,100%{box-shadow:0 0 0 3px rgba(var(--accent-rgb),.16)}50%{box-shadow:0 0 0 6px rgba(var(--accent-rgb),.30)}}
/* 틀림 = 빨강 점등 + 좌우 흔들림(처음부터 입력) */
#pin.bad{border-color:var(--danger);box-shadow:0 0 0 3px rgba(var(--danger-rgb),.26);color:var(--danger);caret-color:var(--danger)}
#pin.bad::placeholder{color:rgba(var(--danger-rgb),.55)}
@keyframes pinShake{0%,100%{transform:translateX(0)}12%{transform:translateX(-9px)}28%{transform:translateX(8px)}44%{transform:translateX(-6px)}60%{transform:translateX(4px)}76%{transform:translateX(-2px)}}
.pinwrap.shake{animation:pinShake .45s cubic-bezier(.36,.07,.19,.97)}
.err{margin-top:13px}
.info{color:var(--accent);font-size:12.5px;margin-top:13px;font-weight:700;line-height:1.5}   /* 마스터 초기화 안내 = accent(정보·에러 아님) */
@media (prefers-reduced-motion:reduce){.pinwrap.shake{animation-duration:.01s}#pin.checking{animation:none;box-shadow:0 0 0 4px rgba(var(--accent-rgb),.22)}}
</style>
<script>
(function(){
  var f=document.getElementById('f'),pin=document.getElementById('pin'),eye=document.getElementById('eye'),verr=document.getElementById('verr'),pw=document.getElementById('pinwrap');
  var real='',reveal=false,fired=false,autoT=null;
  pin.removeAttribute('name');                                   // 화면값=마스킹 → 제출 금지. 실제값은 hidden으로.
  var hid=document.createElement('input');hid.type='hidden';hid.name='p';f.appendChild(hid);
  function ff(){if(!fired)try{pin.focus({preventScroll:true});}catch(e){pin.focus();}}   // 입력창 자동 포커스(첫 로드·복귀 시 · 운영자 260703)
  function mask(){return real.length?Array(real.length).join('•')+real.slice(-1):'';}   // 마지막(방금 입력한) 숫자만 노출
  function render(){hid.value=real;pin.value=reveal?real:mask();try{pin.setSelectionRange(pin.value.length,pin.value.length);}catch(e){}}
  function shake(){pw.classList.remove('shake');void pw.offsetWidth;pw.classList.add('shake');}
  function clearBad(){if(pin.classList.contains('bad'))pin.classList.remove('bad');verr.hidden=true;}
  function arm(){clearTimeout(autoT);if(real.length===6&&!fired)autoT=setTimeout(fire,140);}   // 6자리 = 자동 검증(빠르게 · 운영자 260703)
  function fire(){                                                // 자동 발사 = 중립 '확인 중' → 서버 검증(성공=문서 열림 / 실패=흔들림 재응답)
    if(fired||real.length!==6)return;
    fired=true;clearTimeout(autoT);hid.value=real;
    pin.classList.remove('bad');pin.classList.add('checking');pin.blur();
    setTimeout(function(){f.submit();},150);                     // 확인중 글로우 1페인트 → 즉시 발사(글로우는 네비게이션 동안 유지)
  }
  function upd(){clearBad();render();arm();}
  pin.addEventListener('beforeinput',function(e){
    if(fired){e.preventDefault();return;}
    var t=e.inputType||'';
    if(t==='insertText'||t==='insertFromPaste'||t==='insertCompositionText'){real=(real+((e.data||'').replace(/\\D/g,''))).slice(0,6);e.preventDefault();}
    else if(t.indexOf('delete')===0){if(t==='deleteContentBackward'||t==='deleteContentForward'||t==='deleteByCut')real=real.slice(0,-1);else real='';e.preventDefault();}
    else{e.preventDefault();}
    upd();
  });
  pin.addEventListener('input',function(){                       // beforeinput 미지원 브라우저 폴백
    if(fired||pin.value===(reveal?real:mask()))return;
    real=pin.value.replace(/\\D/g,'').slice(0,6);upd();
  });
  eye.addEventListener('click',function(){
    reveal=!reveal;
    eye.querySelector('.on').style.display=reveal?'none':'';
    eye.querySelector('.off').style.display=reveal?'':'none';
    render();ff();
  });
  f.addEventListener('submit',function(e){e.preventDefault();fire();});   // Enter 등 = 자동발사 경유(6자리 미만이면 무시)
  document.addEventListener('click',function(e){if(!fired&&e.target!==eye&&!(eye.contains&&eye.contains(e.target)))ff();});   // 아무 데나 탭 = 입력창 포커스(모바일 키보드)
  window.addEventListener('pageshow',ff);                        // bfcache 복귀 시 재포커스
  // 서버가 틀린 핀으로 이 폼을 재응답(verr 메시지 존재) → 즉시 흔들림 + 빨강 점등(입력은 이미 빈 상태 = 처음부터). 마스터 안내(.info)는 정보라 흔들림 없음.
  if(!verr.hidden&&verr.textContent.trim()){pin.classList.add('bad');shake();}
  ff();setTimeout(ff,60);                                        // 첫 로드 자동 포커스(레이아웃 후 재시도)
})();
</script>`;
  return new Response(shell(inner), {
    status: locked ? 429 : fails > 0 ? 401 : 200,
    headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex, nofollow' },
  });
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
