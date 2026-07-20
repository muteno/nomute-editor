// Cloudflare Pages Function — 같은-출처 다운로드 프록시 (교차출처 이미지 다운로드 우회).
// 왜: 썸네일/카드 이미지는 R2 공개 URL(pub-*.r2.dev) + 일부 외부 매체 CDN(R2 업로드 실패분)으로 서빙되는데
//     교차출처라 뷰어의 a[download]/fetch 가 막힘 → '새 탭 열림'으로 떨어져 파일이 안 받아짐.
// 해결: 이 Function 이 이미지를 *서버에서* 받아 Content-Disposition: attachment 로 되돌려준다.
//     뷰어는 같은 출처(Pages)로 요청 → CORS 무관 · 브라우저가 무조건 '파일 저장'.
// 보안(SSRF): https 만 · 사설/예약 IP·내부 호스트 차단 · 리다이렉트 비추종 · image/* 만 통과 ·
//     attachment+nosniff 로 인라인 렌더(저장형 XSS) 차단. (R2 호스트는 항상 허용.)
// 호출: GET api/dl?u=<이미지 절대URL>&n=<저장 파일명>
const R2_HOST = 'pub-83f8cf3892ae44c38bebf1805c954508.r2.dev';   // = functions/api/thumb.js R2_BASE 호스트(시크릿 R2_PUBLIC_BASE). ⚠️ 베이스 변경 시 thumb.js:9 와 함께 갱신.

// 사설/예약/내부 대상 차단 — Cloudflare 엣지는 사설망 라우팅이 없지만 IP 리터럴·내부 호스트는 방어적으로 컷.
function _blockedHost(host) {
  host = (host || '').toLowerCase().replace(/^\[|\]$/g, '');   // IPv6 대괄호 제거
  if (!host) return true;
  if (host === 'localhost' || host.endsWith('.localhost') || host.endsWith('.local')
      || host.endsWith('.internal') || host === 'metadata.google.internal') return true;
  // 대체 IP 표기 차단 — fetch/OS 리졸버는 hex(0x7f000001)·10진정수(2130706433)·octal(0177.0.0.1)·축약(127.1)·혼합(0x7f.0.0.1)도
  //   127.0.0.1/169.254.169.254 등으로 해석 → 점4개 10진 정규식만으론 우회됨. 정상 도메인(문자 라벨·정규 TLD)은 아래 어디에도 안 걸림.
  if (!host.includes(':')) {                                   // IPv6 리터럴은 아래 별도 처리
    if (/(^|\.)0x[0-9a-f]+/i.test(host)) return true;          // hex 리터럴 라벨(0x7f000001 · 0x7f.0.0.1)
    const labels = host.split('.');
    if (labels.some(l => /^0\d+$/.test(l))) return true;       // octal형 라벨(0177 등 — 0으로 시작하는 다자리 숫자)
    if (/^\d+$/.test(host)) return true;                       // 순수 10진정수 호스트(2130706433)
    if (labels.length < 4 && /^\d{1,3}(\.\d{1,3}){0,3}$/.test(host)) return true;   // 축약 IPv4(점4개 미만·전부 숫자 — 127.1·10.1)
  }
  const m4 = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (m4) {
    const o = m4.slice(1).map(Number);
    if (o.some(x => x > 255)) return true;
    const a = o[0], b = o[1];
    if (a === 0 || a === 10 || a === 127) return true;          // this/private/loopback
    if (a === 169 && b === 254) return true;                    // 링크로컬 + 클라우드 메타데이터
    if (a === 172 && b >= 16 && b <= 31) return true;           // 사설
    if (a === 192 && b === 168) return true;                    // 사설
    if (a === 100 && b >= 64 && b <= 127) return true;          // CGNAT
    if (a >= 224) return true;                                  // 멀티캐스트/예약
    return false;
  }
  if (host.includes(':')) {                                     // IPv6 리터럴
    if (host === '::1' || host === '::') return true;           // 루프백/미지정
    if (host.startsWith('::ffff:')) return true;                // IPv4-mapped
    if (/^f[cd]/.test(host)) return true;                       // fc00::/7 ULA
    if (/^fe[89ab]/.test(host)) return true;                    // fe80::/10 링크로컬
    return false;
  }
  return false;
}

export async function onRequestGet({ request, env }) {
  const q = new URL(request.url).searchParams;
  const u = q.get('u') || '';
  const name = (q.get('n') || 'download').replace(/[\r\n"\\/]+/g, '_').replace(/[\x00-\x1f]/g, '').slice(0, 180) || 'download';
  let t;
  try { t = new URL(u); } catch { return new Response('bad url', { status: 400 }); }
  // R2 공개 베이스(env 우선·없으면 하드코딩)는 항상 허용. 그 외 호스트는 https + SSRF 가드 통과해야 함.
  let allow = R2_HOST;
  if (env && env.R2_PUBLIC_BASE) { try { allow = new URL(env.R2_PUBLIC_BASE).host; } catch { /* 잘못된 env → 하드코딩 사용 */ } }
  if (t.protocol !== 'https:') return new Response('https only', { status: 403 });
  const isR2 = (t.host === allow || t.host === R2_HOST);
  if (!isR2 && _blockedHost(t.hostname)) return new Response('forbidden host', { status: 403 });
  let up;
  try { up = await fetch(t.toString(), { redirect: 'manual', headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': 'image/*,*/*' } }); }   // redirect:manual = 리다이렉트 비추종(SSRF 차단). 외부 CDN UA/Accept 동봉.
  catch { return new Response('fetch failed', { status: 502 }); }
  if (!up.ok) return new Response('upstream ' + up.status, { status: 502 });   // 리다이렉트(3xx/0)·4xx·5xx 전부 !up.ok로 차단
  const ct = up.headers.get('content-type') || 'application/octet-stream';
  if (!/^(image|video|audio)\//i.test(ct) && ct !== 'application/octet-stream') return new Response('unsupported type', { status: 415 });   // video/* = 자막 번인 완성영상(R2) 다운로드 경유(260707) · audio/* = 음원(Lyria 곡 R2 mp3/wav) 다운로드 경유(260712) — attachment+nosniff 불변이라 인라인 실행면 동일
  const h = new Headers();
  h.set('content-type', ct);
  h.set('content-disposition', "attachment; filename*=UTF-8''" + encodeURIComponent(name));
  h.set('x-content-type-options', 'nosniff');
  h.set('cache-control', 'no-store');   // 다운로드는 1회성 — 캐시 안 함(같은 R2 키 덮어쓰기[edit-card 등] 후 옛 이미지 방지)
  const len = up.headers.get('content-length'); if (len) h.set('content-length', len);
  return new Response(up.body, { status: 200, headers: h });
}
