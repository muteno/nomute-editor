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
const MASTER_NOTICE = '비밀번호 초기화 완료';   // 마스터 입력 시 안내(운영자 260703 · mut 회색 · 문구 간결화 · 5회 잠금 카운터 리셋)
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
// 핀 입력 폼 — PAYCO식 보안 키패드(방식 계승·운영자 260703). 6칸 슬롯(입력한 것만 강조색) + 자체 셔플 숫자 키패드(OS 키보드 X).
// 키패드 셔플 = 2판제(운영자 260703 개정): 1~4자리 = 판A 고정 · 5~6자리 = 판B 고정(입력마다 재셔플 X — 위치 학습 가능해 오입력↓).
//   백스페이스로 3자리 이하로 되돌아가면 판A로 복귀 = 자리수↔판 매핑이 항상 유지(어깨너머 완화는 2판 전환+매 로드 새 셔플로 확보).
// 입력 순간 = 방금 누른 자리만 숫자 잠깐 노출(0.7s·다음 입력/검증 시 즉시 마스킹 — 폰 비번 관례·운영자 260703).
// 6칸 채우면 *자동 검증*(별도 열기 버튼 X) → GET 네비게이션으로 서버 검증.
//   성공 = 서버가 문서 HTML로 응답(페이지 교체 = 자동 오픈) / 실패 = 폼 재응답(fails>0) → 로드 시 슬롯 빨강+흔들림+처음부터(입력 빈 상태).
//   빨강(슬롯·입력부만)은 3초 유지 후 처음 색으로 자동 복귀(입력 시작해도 즉시 복귀) — 잠금(locked) 문구는 상태라 유지(운영자 260703).
//   notice(마스터 입력 시) = '비밀번호 초기화 완료' 안내(.info mut · 에러 아님 → 흔들림 없음).
// 카드 배경 제거(글자·슬롯·패드만 흑배경 위) · CSP 헤더 없음 → 인라인 style/script 동작.
// ⚠️ 실제 PIN은 hidden input(name=p)로 GET 제출 = 서버 검증(클라 셔플은 표시용·검증 무관). 슬롯/키패드는 표시 UI라 pattern·novalidate 무관.
// ※ 이 폼 = PIN 입력 UI 정본(범용 — 다른 화면에 이식 시 이 슬롯·2판 키패드·에러 상태머신 그대로 계승).
function pinForm(slug, fails, notice) {
  const locked = fails >= LOCK_MAX;
  const msg = locked ? 'PIN 오류 5회 누적으로 10분 간 접속이 불가합니다'
    : fails > 0 ? `PIN 번호가 틀립니다 (${fails}/${LOCK_MAX})` : '';
  const info = notice ? esc(notice) : '';
  const inner = `<div class="m">PIN으로 잠긴 문서입니다.</div>
<div class="slots" id="slots" aria-hidden="true">${'<span class="slot"></span>'.repeat(6)}</div>
<div class="err" id="verr"${msg ? '' : ' hidden'}>${msg}</div><div class="info" id="vinfo"${info ? '' : ' hidden'}>${info}</div>
<div class="pad" id="pad"></div>
<form id="f" method="get" action="/s/${slug}" novalidate><input type="hidden" name="p" id="hid"></form>
<style>
.card{background:none;border:none;padding:6px 4px}   /* 카드 패널(글자 뒤 배경) 제거 — 글자·슬롯·패드만 흑배경 위에(운영자 260703 · pinForm 한정 오버라이드·에러/안내 page()는 카드 유지) */
.slots{display:flex;justify-content:center;gap:18px;margin:24px 0 2px}
.slot{width:13px;height:13px;box-sizing:border-box;border-radius:50%;border:2px solid var(--mut);background:none;opacity:.5;display:grid;place-items:center;font-size:17px;font-weight:800;line-height:1;color:var(--accent);transition:background .15s ease,border-color .15s ease,opacity .15s ease,transform .15s ease}
.slot.on{background:var(--accent);border-color:var(--accent);opacity:1;transform:scale(1.1)}   /* 입력한 것만 강조색(운영자 260703) */
.slot.peek{border-color:transparent;background:none;opacity:1;transform:scale(1.15)}   /* 방금 입력한 자리 = 점 대신 숫자 잠깐 노출(0.7s·운영자 260703) */
.slots.bad .slot{border-color:var(--danger)}
.slots.bad .slot.on{background:var(--danger);border-color:var(--danger)}
.slots.checking .slot.on{animation:slotPulse .8s ease infinite}
@keyframes slotPulse{0%,100%{opacity:1}50%{opacity:.45}}
@keyframes slotShake{0%,100%{transform:translateX(0)}12%{transform:translateX(-9px)}28%{transform:translateX(8px)}44%{transform:translateX(-6px)}60%{transform:translateX(4px)}76%{transform:translateX(-2px)}}
.slots.shake{animation:slotShake .45s cubic-bezier(.36,.07,.19,.97)}
.err{margin-top:15px;min-height:15px}
.info{color:var(--mut);font-size:12.5px;margin-top:15px;font-weight:700;line-height:1.5}   /* 마스터 초기화 안내 = mut 회색(정보·에러 아님·운영자 260703) */
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;max-width:288px;margin:26px auto 0}
.key{height:58px;display:grid;place-items:center;font-size:23px;font-weight:700;font-family:inherit;color:var(--fg);background:none;border:none;border-radius:16px;cursor:pointer;-webkit-tap-highlight-color:transparent;-webkit-user-select:none;user-select:none;transition:background .12s ease,transform .07s ease}
.key:active{background:rgba(255,255,255,.09);transform:scale(.93)}
.key.empty{visibility:hidden;pointer-events:none}
.key.back svg{width:26px;height:26px;stroke:var(--fg);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.pad.off{pointer-events:none;opacity:.45;transition:opacity .2s ease}   /* 확인 중 = 패드 비활성 */
@media (prefers-reduced-motion:reduce){.slots.shake{animation-duration:.01s}.slots.checking .slot.on{animation:none}.key:active{transform:none}}
</style>
<script>
(function(){
  var f=document.getElementById('f'),hid=document.getElementById('hid'),pad=document.getElementById('pad'),
      slots=document.getElementById('slots'),dots=slots.getElementsByClassName('slot'),verr=document.getElementById('verr');
  var real='',fired=false,kds=null,peekT=null,badT=null,LOCKED=${locked ? 'true' : 'false'};
  var BSVG='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 5H9l-6 7 6 7h11a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1z"/><path d="M16 9l-4 4M12 9l4 4"/></svg>';
  function mkOrder(){var o=[0,1,2,3,4,5,6,7,8,9];for(var i=9;i>0;i--){var j=Math.floor(Math.random()*(i+1)),t=o[i];o[i]=o[j];o[j]=t;}return o;}
  var orderA=mkOrder(),orderB=mkOrder();                        // 2판제: 1~4자리=판A · 5~6자리=판B(입력 중 재셔플 X·백스페이스로 돌아가도 매핑 유지·운영자 260703)
  function build(){                                              // 12칸 = 숫자 9 + 빈칸 + 숫자 1 + 지우기. 버튼 노드는 고정, 라벨만 셔플(누름 :active 유지·DOM 파괴 없음)
    var h='';for(var i=0;i<9;i++)h+='<button type="button" class="key kd"></button>';
    h+='<button type="button" class="key empty" tabindex="-1" aria-hidden="true"></button>';
    h+='<button type="button" class="key kd"></button>';
    h+='<button type="button" class="key back" data-back="1" aria-label="지우기">'+BSVG+'</button>';
    pad.innerHTML=h;kds=pad.querySelectorAll('.kd');            // 10개 숫자 버튼(DOM 순서 = order 인덱스)
  }
  function applyOrder(){var o=real.length>=4?orderB:orderA;for(var i=0;i<10;i++){kds[i].textContent=o[i];kds[i].setAttribute('data-d',o[i]);}}   // 자리수로 판 결정 = 지웠다 다시 쳐도 같은 판
  function fill(peek){                                          // peek=true → 방금 입력한 자리만 숫자 노출(0.7s 후·다음 입력 시 즉시 마스킹)
    clearTimeout(peekT);
    for(var i=0;i<6;i++){dots[i].className='slot'+(i<real.length?' on':'');dots[i].textContent='';}
    if(peek&&real.length){var d=dots[real.length-1];d.className='slot peek';d.textContent=real.slice(-1);
      peekT=setTimeout(function(){fill();},700);}
  }
  function unbad(){                                             // 입력 시작 = 빨강 즉시 복귀(3초 타이머보다 우선·잠금 문구는 유지)
    clearTimeout(badT);slots.classList.remove('bad','shake');
    if(!LOCKED&&verr&&!verr.hidden)verr.hidden=true;
  }
  function press(d){
    if(fired||real.length>=6)return;
    unbad();real+=String(d);fill(true);
    applyOrder();                                               // 4자리 채우는 순간 판B로 전환(그 전까진 판A 고정)
    if(real.length===6)setTimeout(fire,340);
  }
  function back(){if(fired||!real.length)return;unbad();real=real.slice(0,-1);fill();applyOrder();}
  function fire(){                                              // 6칸 채움 → 확인 중 → 서버 검증(성공=문서 열림 / 실패=슬롯 빨강 흔들림 재응답)
    if(fired||real.length!==6)return;
    fired=true;clearTimeout(peekT);fill();                      // 검증 들어갈 땐 숫자픽 즉시 마스킹(노출 잔류 차단)
    hid.value=real;slots.classList.add('checking');pad.classList.add('off');
    setTimeout(function(){f.submit();},150);
  }
  pad.addEventListener('click',function(e){
    var b=e.target.closest('.key');if(!b)return;
    if(b.getAttribute('data-back')!==null)back();
    else if(b.getAttribute('data-d')!==null)press(b.getAttribute('data-d'));
  });
  document.addEventListener('keydown',function(e){             // 데스크톱 물리 키보드도 허용
    if(fired)return;
    if(e.key>='0'&&e.key<='9'){press(e.key);e.preventDefault();}
    else if(e.key==='Backspace'){back();e.preventDefault();}
  });
  build();applyOrder();fill();
  // 서버가 틀린 핀으로 이 폼을 재응답(verr 메시지) → 슬롯 빨강 + 흔들림(입력 빈 상태 = 처음부터). 마스터 안내(.info)는 정보라 흔들림 없음.
  // 빨강은 3초 유지 후 처음 색으로 자동 복귀(입력부만·운영자 260703). 잠금(locked) 문구는 상태 표시라 유지(타이머 미적용).
  if(!verr.hidden&&verr.textContent.trim()){
    slots.classList.add('bad');void slots.offsetWidth;slots.classList.add('shake');
    if(!LOCKED)badT=setTimeout(function(){slots.classList.remove('bad','shake');verr.hidden=true;},3000);
  }
})();
</script>`;
  return new Response(shell(inner), {
    status: locked ? 429 : fails > 0 ? 401 : 200,
    headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex, nofollow' },
  });
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
