// Cloudflare Pages Function — 설정 ▸ 다운로드: **받기 전에 「무엇인지」 미리보기**(운영자 260803
//   "링크를 입력해서 다운로드를 누르면 어떤 내용 인지가 떠야돼. 다운로더들 다 그렇더라고").
//   입력: GET ?u=<영상 게시물 주소> · 출력: { plat, title, author, thumb, desc }
//
// 왜 이 방식인가(설계 근거 = 실측):
//   ⓐ 「받을 파일 목록」(캐러셀 몇 장·해상도)은 yt-dlp가 있어야 안다 = 러너 몫이고, 러너는 부팅만 40~60초라
//      미리보기용으로 왕복시키면 「내용 확인」이 도리어 느려진다.
//   ⓑ 반면 **무엇인지**(제목·작성자·대표 이미지)는 게시물 페이지가 og: 메타로 공개한다 — 토큰·로그인 0.
//      실측 260803: 스레드 원글 페이지가 og:title·og:description·og:image 전건 보유(비-브라우저 UA 요청 시).
//   → 그래서 이 엔드포인트는 **엣지에서 og 메타만** 읽는다(러너 무관 · 수백 ms · 과금 0).
//
// ⚠ UA = 일부러 **비-브라우저**다(nomute-viewer). 스레드가 브라우저 UA에는 공유/게시물 주소를 클라이언트
//   라우팅 셸(og 메타 0건)로 주고, 비-브라우저 UA에만 302 + 정규 페이지를 준다(260803 실측 · 같은 날
//   apps/vidl/plugins/…/nomute_threads.py `_SHARE_HEADERS`와 **같은 사유·같은 처방**).
//
// 가드 = vidl.js 문자 계승(SSRF·플랫폼 화이트리스트) — 이 엔드포인트도 임의 호스트를 fetch하면 안 된다.
// 실패는 전부 fail-soft: { plat, title:'' } → 뷰어는 미리보기만 생략하고 종전 흐름 그대로(발사 경로 무영향).

const UA = 'nomute-viewer';   // 비-브라우저 UA(위 ⚠ 참조) · 크롤러 취급 = og 메타를 주는 쪽
const HTML_MAX = 2 * 1024 * 1024;   // 응답 상한(og 메타는 <head>에 있다 = 앞부분이면 충분)

// ── 플랫폼 판정 = functions/api/vidl.js 사본(3면 동값: 뷰어 _dgVidPlat · 엣지 vidl · 러너 detect_plat) ──
function platOf(u) {
  const uh = u.hostname.toLowerCase();
  const path = u.pathname.toLowerCase();
  const bh = uh.replace(/^www\./, '');
  const hb = (d) => bh === d || bh.endsWith('.' + d);
  const hostIs = (d) => uh === d || uh.endsWith('.' + d);
  if (hb('youtu.be')) return path.length > 1 ? 'YT' : '';
  if (hb('youtube.com')) return /^\/(watch|shorts\/|live\/|embed\/)/.test(path) ? 'YT' : '';
  if (hb('instagram.com')) return /^\/(p|reel|reels|tv)\//.test(path) ? 'IG' : '';
  if (hb('x.com') || hb('twitter.com')) return /\/status\/\d/.test(path) ? 'X' : '';
  if (hb('tiktok.com')) return (/\/(video|photo)\/\d/.test(path) || /^\/(t|v)\//.test(path) || hostIs('vm.tiktok.com') || hostIs('vt.tiktok.com')) ? 'TT' : '';
  if (hb('fb.watch')) return path.length > 1 ? 'FB' : '';
  if (hb('facebook.com')) return (/\/(videos|reel|watch)\//.test(path) || path === '/watch') ? 'FB' : '';
  if (hb('threads.net') || hb('threads.com')) return /\/(post|t|share)\//.test(path) ? 'TH' : '';
  return '';
}

const META_RE = /<meta\b[^>]*>/gi;
const PROP_RE = /\b(?:property|name)\s*=\s*["']([^"']+)["']/i;
const CONTENT_RE = /\bcontent\s*=\s*["']([^"']*)["']/i;

function ogMetas(html) {   // <meta property=… content=…> → dict (속성 순서 뒤집힘 대응 = thembed·플러그인 page_metas 동문)
  const out = {};
  const tags = html.match(META_RE) || [];
  for (const tag of tags) {
    const p = PROP_RE.exec(tag), c = CONTENT_RE.exec(tag);
    if (p && c) {
      const k = p[1].toLowerCase();
      if (!(k in out)) out[k] = c[1];
    }
  }
  return out;
}

const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'", '#x27': "'", nbsp: ' ', '#064': '@', '#x40': '@' };
function unent(s) {   // og content는 HTML 엔티티로 인코딩돼 온다(실측: `&#064;` = @ · `&#xb098;` = 한글)
  return String(s || '')
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(+d))
    .replace(/&([a-z]+|#x?[0-9a-f]+);/gi, (m, k) => (k.toLowerCase() in ENT ? ENT[k.toLowerCase()] : m));
}

export async function onRequestGet({ request }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), {
    status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
  const raw = (new URL(request.url).searchParams.get('u') || '').trim().slice(0, 500);
  if (!raw || !/^https?:\/\//i.test(raw) || /[\r\n\t]/.test(raw)) return json({ plat: '', title: '' });

  let t;
  try { t = new URL(raw); } catch { return json({ plat: '', title: '' }); }
  if (t.protocol !== 'https:' && t.protocol !== 'http:') return json({ plat: '', title: '' });
  const uh = t.hostname.toLowerCase();
  // SSRF 가드 = vidl.js 문자 계승(IP 리터럴·내부·메타데이터 호스트 거부)
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(uh) || uh === 'localhost' || uh.endsWith('.local') || uh.startsWith('[')
    || uh === 'metadata.google.internal' || uh.endsWith('.internal') || uh === 'instance-data'
    || !/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(uh)) return json({ plat: '', title: '' });

  const plat = platOf(t);
  if (!plat) return json({ plat: '', title: '' });   // 영상 게시물이 아니면 미리보기 없음 = 페이지 스캔 갈래(뷰어가 판단)

  // ── ① oEmbed 우선(유튜브·틱톡) — 공개·키 0 · og보다 정확하다.
  //    실측 260803: 유튜브는 **비-브라우저 UA에 og 메타를 안 준다**(제목 0건) → og 한 경로만으론 유튜브가 통째로 빈다.
  //    반대로 oEmbed는 제목·작성자·썸네일을 바로 준다. 스레드는 반대(oEmbed 없음·og 완비)라 두 경로가 서로를 메운다.
  const OEMBED = {
    YT: (x) => 'https://www.youtube.com/oembed?format=json&url=' + encodeURIComponent(x),
    TT: (x) => 'https://www.tiktok.com/oembed?url=' + encodeURIComponent(x),
  };
  if (OEMBED[plat]) {
    try {
      const r = await fetch(OEMBED[plat](t.toString()), { headers: { 'user-agent': UA, accept: 'application/json' } });
      if (r.ok) {
        const d = await r.json().catch(() => null);
        if (d && d.title) {
          let th = '';
          try { const iu = new URL(String(d.thumbnail_url || '')); if (iu.protocol === 'https:') th = iu.toString(); } catch { th = ''; }
          return json({ plat, title: String(d.title).slice(0, 200), desc: '', thumb: th, author: String(d.author_name || '').slice(0, 60) });
        }
      }
    } catch { /* fail-soft = 아래 og 경로로 계속 */ }
  }

  let html = '';
  try {
    const r = await fetch(t.toString(), {
      headers: { 'user-agent': UA, accept: 'text/html,*/*;q=0.8', 'accept-language': 'ko-KR,ko;q=0.9' },
      redirect: 'follow',   // 스레드 공유 링크(/share/) = 302로 정규 주소를 알려준다 → 따라가야 og 메타가 있는 페이지에 닿는다
    });
    if (!r.ok) return json({ plat, title: '' });
    const buf = await r.arrayBuffer();
    html = new TextDecoder('utf-8').decode(buf.byteLength > HTML_MAX ? buf.slice(0, HTML_MAX) : buf);
  } catch { return json({ plat, title: '' }); }

  const m = ogMetas(html);
  let title = unent(m['og:title'] || m['twitter:title'] || '').slice(0, 200);
  const desc = unent(m['og:description'] || m['twitter:description'] || '').slice(0, 300);
  // ② 「Threads의 _(@계정)님」류 = **계정 껍데기라 내용이 0**이다(실측 260803) — 그 글의 내용은 og:description(본문)에 있다.
  //    운영자가 보려는 건 "어떤 내용인지"이므로, 제목이 껍데기면 본문을 제목 자리로 올린다(둘 다 없으면 미리보기 자체를 생략).
  if (desc && (!title || /\(@[^)]+\)/.test(title))) title = desc.slice(0, 200);
  const thumbRaw = (m['og:image'] || m['twitter:image'] || '').trim();
  let thumb = '';
  try { const iu = new URL(unent(thumbRaw)); if (iu.protocol === 'https:') thumb = iu.toString(); } catch { thumb = ''; }

  // 작성자 = og:title의 「_ (@계정) on Threads」류에서 계정만(실측 스레드 형식) · 없으면 빈칸(추측 금지)
  const am = /@([A-Za-z0-9._-]{2,40})/.exec(title) || /@([A-Za-z0-9._-]{2,40})/.exec(unent(m['og:url'] || ''));
  return json({ plat, title, desc, thumb, author: am ? '@' + am[1] : '' });
}
