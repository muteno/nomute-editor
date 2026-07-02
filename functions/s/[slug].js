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

  // 핀 잠금 — ?p=1234. 없거나 틀리면 입력 폼.
  if (m.pinHash) {
    const pin = new URL(request.url).searchParams.get('p') || '';
    if (!/^\d{4}$/.test(pin)) return pinForm(slug, false);
    const h = await sha256hex(pin + ':' + slug);
    if (h !== m.pinHash) return pinForm(slug, true);
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

// 안내/에러 페이지 — 자기완결(외부 리소스0·다크). 본체 링크·API 노출 없음(우회 차단).
// 색·반지름은 viewer/index.html :root 토큰을 그대로 인라인 복제(CSP가 외부 CSS 차단 → 링크 불가 · 기틀 계승).
function shell(inner) {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark">
<meta name="robots" content="noindex,nofollow"><title>노뮤트 발행본</title>
<style>:root{--accent:#0FFD02;--accent-rgb:15,253,2;--accent-dim:rgba(15,253,2,.13);--on-accent:#062108;--fg:#eef7f0;--mut:#8fa697;--danger:#ff5b4a;--r-modal:22px}
html,body{margin:0;height:100%;background:#0b0d0c;color:var(--fg);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
.wrap{min-height:100%;display:grid;place-items:center;padding:24px;box-sizing:border-box}
.card{max-width:360px;width:100%;text-align:center;background:linear-gradient(165deg,rgba(28,30,33,.96),rgba(15,16,18,.98));border:1px solid rgba(255,255,255,.08);border-radius:var(--r-modal);padding:26px 22px}
.card .m{font-size:15px;font-weight:800;color:var(--mut);letter-spacing:-.2px}
.err{color:var(--danger);font-size:12px;margin-top:11px;font-weight:700}</style></head><body><div class="wrap"><div class="card">${inner}</div></div></body></html>`;
}
function page(msg, status = 200) {
  return new Response(shell(`<div class="m">${esc(msg)}</div>`), {
    status, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex, nofollow' },
  });
}
// 핀 입력 폼 — 뷰어 기틀 계승: 입력칸(포커스 강조링)·글래스 강조 버튼(.mkbtn goFill 게이지 풀필→자물쇠 해제 모션).
// PIN 마스킹(현재 입력한 숫자만 노출·나머지 •) + MUT색 눈 토글(전체 표시). CSP 헤더 없음 → 인라인 style/script 동작.
function pinForm(slug, wrong) {
  const inner = `<div class="m">PIN으로 잠긴 문서입니다.</div>
<form id="f" method="get" action="/s/${slug}">
  <div class="pinwrap">
    <input id="pin" name="p" type="text" inputmode="numeric" pattern="\\d*" maxlength="4" placeholder="••••" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" autofocus>
    <button type="button" id="eye" class="eye" aria-label="PIN 표시">
      <svg class="on" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>
      <svg class="off" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7c2 0 3.7.6 5.2 1.5M22 12s-3.5 7-10 7c-2 0-3.7-.6-5.2-1.5"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><path d="M3 3l18 18"/></svg>
    </button>
  </div>
  <button type="submit" id="go" class="go">
    <span class="go-t">열기</span>
    <svg class="lock" viewBox="0 0 24 24" aria-hidden="true"><rect class="lbody" x="5" y="11" width="14" height="10" rx="2.6"/><path class="lshackle" d="M8.2 11V8a3.8 3.8 0 0 1 7.6 0v3"/></svg>
  </button>
</form>${wrong ? '<div class="err">핀이 맞지 않아요</div>' : ''}
<style>
.pinwrap{position:relative;margin-top:16px}
#pin{width:100%;box-sizing:border-box;height:52px;padding:0 46px;text-align:center;font-size:20px;letter-spacing:10px;font-weight:800;font-family:inherit;border-radius:14px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);color:var(--fg);caret-color:var(--accent);outline:none;transition:border-color .18s ease,box-shadow .18s ease}
#pin::placeholder{color:var(--mut);letter-spacing:8px}
#pin:focus{border-color:rgba(var(--accent-rgb),.55);box-shadow:0 0 0 3px rgba(var(--accent-rgb),.14)}
.eye{position:absolute;right:8px;top:50%;transform:translateY(-50%);width:34px;height:34px;display:grid;place-items:center;padding:0;border:none;background:none;color:var(--mut);cursor:pointer;border-radius:9px;-webkit-tap-highlight-color:transparent}
.eye:active{transform:translateY(-50%) scale(.85)}
.eye svg{grid-area:1/1;width:21px;height:21px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.eye .off{display:none}
.go{position:relative;display:block;width:100%;margin:12px 0 0;padding:14px;font-size:14px;font-weight:800;font-family:inherit;background:rgba(0,0,0,.34);color:var(--accent);border:1px solid rgba(var(--accent-rgb),.36);border-radius:999px;cursor:pointer;overflow:hidden;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);transition:transform .12s ease,background .15s ease,border-color .15s ease}
.go:active{transform:scale(.955);background:rgba(0,0,0,.44)}
.go .lock{display:none;width:26px;height:26px}
.go.firing{color:var(--on-accent);pointer-events:none;background:linear-gradient(var(--accent),var(--accent)) left/0% 100% no-repeat,linear-gradient(var(--accent-dim),var(--accent-dim));animation:goFill .72s linear forwards}
@keyframes goFill{from{background-size:0% 100%,100% 100%}to{background-size:100% 100%,100% 100%}}
.go.opening{background:var(--accent);color:var(--on-accent);border-color:var(--accent);display:grid;place-items:center}
.go.opening .go-t{display:none}
.go.opening .lock{display:block}
.lock .lbody{fill:var(--on-accent);stroke:none}
.lock .lshackle{fill:none;stroke:var(--on-accent);stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round;transform-origin:15.5px 9px;transition:transform .5s cubic-bezier(.2,.7,.3,1)}
.go.unlocked .lshackle{transform:rotate(-32deg) translateY(-1px)}
@media (prefers-reduced-motion:reduce){.go.firing{animation-duration:.2s}.lock .lshackle{transition-duration:.15s}}
</style>
<script>
(function(){
  var f=document.getElementById('f'),pin=document.getElementById('pin'),eye=document.getElementById('eye'),go=document.getElementById('go');
  var real='',reveal=false;
  pin.removeAttribute('name');                                   // 화면값=마스킹 → 제출 금지. 실제값은 hidden으로.
  var hid=document.createElement('input');hid.type='hidden';hid.name='p';f.appendChild(hid);
  function mask(){return real.length?Array(real.length).join('•')+real.slice(-1):'';}   // 마지막(방금 입력한) 숫자만 노출
  function render(){hid.value=real;pin.value=reveal?real:mask();try{pin.setSelectionRange(pin.value.length,pin.value.length);}catch(e){}}
  pin.addEventListener('beforeinput',function(e){
    var t=e.inputType||'';
    if(t==='insertText'||t==='insertFromPaste'||t==='insertCompositionText'){real=(real+((e.data||'').replace(/\\D/g,''))).slice(0,4);e.preventDefault();}
    else if(t.indexOf('delete')===0){if(t==='deleteContentBackward'||t==='deleteContentForward'||t==='deleteByCut')real=real.slice(0,-1);else real='';e.preventDefault();}
    else{e.preventDefault();}
    render();
  });
  pin.addEventListener('input',function(){                       // beforeinput 미지원 브라우저 폴백
    if(pin.value===(reveal?real:mask()))return;
    real=pin.value.replace(/\\D/g,'').slice(0,4);render();
  });
  eye.addEventListener('click',function(){
    reveal=!reveal;
    eye.querySelector('.on').style.display=reveal?'none':'';
    eye.querySelector('.off').style.display=reveal?'':'none';
    render();pin.focus();
  });
  f.addEventListener('submit',function(e){
    e.preventDefault();
    if(real.length!==4){pin.focus();if(go.animate)go.animate([{transform:'translateX(0)'},{transform:'translateX(-6px)'},{transform:'translateX(6px)'},{transform:'translateX(0)'}],{duration:280});return;}
    hid.value=real;go.classList.add('firing');
    setTimeout(function(){go.classList.remove('firing');go.classList.add('opening');requestAnimationFrame(function(){go.classList.add('unlocked');});},720);
    setTimeout(function(){f.submit();},1280);                    // 게이지(0.72s) → 자물쇠 해제(0.5s) 후 이동
  });
  pin.focus();
})();
</script>`;
  return new Response(shell(inner), {
    status: wrong ? 401 : 200,
    headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex, nofollow' },
  });
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
