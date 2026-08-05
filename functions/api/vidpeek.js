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

// ── 스레드 항목 구성 파서(운영자 260805 3차 "몇개가 엮여있는지 미리 + 각각 최대화질") ──
//    ① SSR = 러너 플러그인(nomute_threads.py extract_post_nodes·collect_media) 문법 **포팅**(정본 계승 · 신규 기법 0)
//       — 종류 + 원본 치수(original_width/height · 이미지 후보 최대 픽셀)까지 나온다.
//       ⚠ 실측 260805: 로그아웃 응답이 본글 media를 감출 때가 있다(candidates:[] — 추천글 media는 멀쩡) → 그땐 ②로.
//    ② 임베드 = 종류·개수만(치수 없음 = 지어내지 않음) — 미디어 창(Solo/Scroll 컨테이너 ~ PostDate/ActionBar) 안에서만 센다
//       (실측: 영상 = <video> 태그 · 사진 = 창 안 img.img · 아바타 img.img는 창 밖이라 오염 0).
const _SJS_RE = /<script[^>]+type="application\/json"[^>]*\bdata-sjs\b[^>]*>([\s\S]*?)<\/script>/g;
function* _walkJson(n) {
  if (Array.isArray(n)) { for (const v of n) yield* _walkJson(v); }
  else if (n && typeof n === 'object') { yield n; for (const v of Object.values(n)) yield* _walkJson(v); }
}
// 재생용 미디어 주소 — **메타 CDN만** 통과시킨다(thembed.js IMG_HOST_RE 문자 계승 · SSR이 준 값이라도 호스트는 검문).
//   ⚠ 서명(oe=) 만료가 있어 캐싱 금지 = 미리보기 그 순간에만 쓰는 값(플러그인 독스트링 「주소 캐싱 금지」와 같은 축).
const _MEDIA_HOST_RE = /^[a-z0-9-]+(\.[a-z0-9-]+)*\.(cdninstagram\.com|fbcdn\.net|twimg\.com)$/;   // twimg = X 사진(pbs)·영상(video) CDN(260805 6차 X 편입)
function _mediaUrl(s) {
  try { const u = new URL(String(s || '')); return (u.protocol === 'https:' && _MEDIA_HOST_RE.test(u.hostname)) ? u.toString() : ''; } catch { return ''; }
}
function _thCollectMedia(post) {   // 플러그인 collect_media 미러 — 캐러셀 컨테이너는 자식에게 양보 · 미디어 노드에서 정지
  const out = [];
  const hasMedia = (x) => !x.carousel_media && !!(x.video_versions
    || (x.image_versions2 && Array.isArray(x.image_versions2.candidates) && x.image_versions2.candidates[0] && x.image_versions2.candidates[0].url));
  (function rec(x) {
    if (Array.isArray(x)) { for (const v of x) rec(v); return; }
    if (x && typeof x === 'object') {
      if (hasMedia(x)) { if (!out.includes(x)) out.push(x); return; }
      for (const v of Object.values(x)) rec(v);
    }
  })(post);
  return out;
}
function thSsrItems(html, code, truncated) {
  let bad = 0;   // JSON.parse 실패 블록 수 — 하나라도 있으면 「완본이 빠지고 축약본만 잡힌」 상태일 수 있다(평의회4 D3)
  try {
    if (!html || !code) return { items: [], trust: false };
    let pk = 0n;   // shortcode → pk = 위치기반 base64(플러그인 shortcode_to_pk 미러 · 64^11 > 2^53이라 BigInt)
    const AB = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
    for (const ch of code) { const i = AB.indexOf(ch); if (i < 0) { pk = null; break; } pk = pk * 64n + BigInt(i); }
    const pkS = pk === null ? '' : String(pk);
    const posts = [];
    _SJS_RE.lastIndex = 0;
    let m;
    while ((m = _SJS_RE.exec(html))) {
      const raw = m[1];
      if (raw.indexOf(code) < 0 && !(pkS && raw.indexOf(pkS) >= 0)) continue;   // 이 포스트가 안 든 블록은 건너뛴다
      let d; try { d = JSON.parse(raw); } catch { bad++; continue; }
      for (const nd of _walkJson(d)) {
        if (nd.code === code || (nd.code == null && pkS && String(nd.pk) === pkS)) posts.push(nd);
      }
    }
    // 노드가 여럿이면 ① 미디어를 가장 많이 문 것 → ② **같으면 치수가 큰 쪽**(운영자 260805 5차 실측 봉합).
    //   ⚠ 실측: 같은 글이 축약본(original 720×760)과 완본(1080×1140) 두 노드로 실린다. 개수가 1:1이라
    //   구판(개수만 비교 = 플러그인 289행 미러)은 **문서순 첫 노드 = 축약본**을 집어 720×760이라고 말했다 —
    //   외부 다운로더가 같은 글에 1080×1140을 보여준 것과 갈린 지점이 정확히 여기다.
    let best = [], bestPx = -1;
    for (const p of posts) {
      const g = _thCollectMedia(p);
      const px = g.reduce((a, md) => a + (+md.original_width || 0) * (+md.original_height || 0), 0);
      if (g.length > best.length || (g.length === best.length && px > bestPx)) { best = g; bestPx = px; }
    }
    const items = best.slice(0, 20).map((md) => {
      const vv = Array.isArray(md.video_versions) ? md.video_versions : (md.video_versions ? [md.video_versions] : []);
      if (vv.length) {   // ⚠ 길이로 판정 — `video_versions: []`는 파이썬(플러그인)에선 거짓이라 사진인데 JS에선 참이라 영상으로 둔갑한다(평의회4 D4)
        const v0 = vv.find(v => v && (+v.width || +v.height)) || {};   // 버전 자체 w/h **먼저**, 없으면 부모 원본치수(플러그인 _pick_video 172행 순서 계승 · 평의회4 D5)
        const src = vv.find(v => v && v.url) || {};   // 재생용 주소 = 등장 순서 첫 항목(SSR은 101>102>103 = 좋은 것부터 · 플러그인 quality 정렬과 같은 순서)
        return { kind: 'video', w: +v0.width || +md.original_width || 0, h: +v0.height || +md.original_height || 0, u: _mediaUrl(src.url) };
      }
      let bw = 0, bh = 0, px = -1, bu = '';
      for (const c of md.image_versions2.candidates) {
        const p2 = (+c.width || 0) * (+c.height || 0);
        if (c.url && p2 > px) { px = p2; bw = +c.width || 0; bh = +c.height || 0; bu = c.url; }
      }
      return { kind: 'img', w: bw, h: bh, u: _mediaUrl(bu) };
    });
    return { items, trust: !bad && !truncated };
  } catch { return { items: [], trust: false }; }   // fail-soft — 구성 표시만 생략
}
function thEmbedItems(eh) {
  try {
    const s = eh.search(/SoloMediaContainer|MediaScrollImageContainer/);
    if (s < 0) return [];   // 미디어 컨테이너 없음 = 글만 있는 게시물(항목 표기 생략 — 실측 emb3·4)
    let e = -1;
    for (const stop of ['PostDateContainer', 'ActionBarContainer', 'QuoteContainer']) {
      const j = eh.indexOf(stop, s + 1); if (j >= 0 && (e < 0 || j < e)) e = j;
    }
    if (e < 0) return [];   // ⚠ 창의 **끝**을 못 찾으면 포기한다(평의회5 D2) — 구판은 문서 끝까지를 미디어 창으로 세어
    //   아바타·인용·파비콘까지 사진에 합류시켰다(실측 = 항목 2가 항목 20으로 날조). 날조보다 침묵이 낫다.
    const seg = eh.slice(s, e).replace(/<video\b[\s\S]*?<\/video>/gi, m => ' '.repeat(1));   // 영상 블록은 통째로 치환 = 그 안 포스터 img가 사진으로 이중계수되는 길을 원천 차단(평의회4 D7)
    const nv = (eh.slice(s, e).match(/<video\b/gi) || []).length;
    const ni = (seg.match(/<img\b[^>]*class="[^"]*\bimg\b[^"]*"/gi) || []).length;   // 클래스 판정 = 같은 파일 썸네일 축(:234)과 **한 문법**(정확일치는 `class="img "`·`class="img Photo"`에서 조용히 0이 됐다 = 평의회4 D1·평의회5 D3)
    const out = [];
    for (let k = 0; k < nv && out.length < 20; k++) out.push({ kind: 'video' });
    for (let k = 0; k < ni && out.length < 20; k++) out.push({ kind: 'img' });
    return out;
  } catch { return []; }
}

// ── 유튜브 실제 포맷 목록(운영자 260805 4차 "그 가능한 포맷만 리스트업에 띄워달라는거임") ──
//   왜 필요한가: 화질 목록은 정적 6값이라 30fps가 한계인 영상에도 「4K 60fps」를 **고를 수 있게** 제시했다
//   (= 운영자 1차 지적 「가능하지도 않은데 4k 60fps가 나오거든」의 후반부 = 「영상에 맞게끔 지정 가능하게」).
//   수단 = innertube player 1콜(키·로그인·토큰 0 · 러너 왕복 0). ⚠ 클라이언트 선택이 전부다 —
//   실측 260805: ANDROID_VR·MWEB·TVHTML5 = LOGIN_REQUIRED/UNPLAYABLE, **IOS만 OK**(그 영상 8종·최대 2160@24
//   = 같은 영상을 실제로 받아 ffprobe로 잰 「4K 24fps」와 정확히 일치 = 값이 진짜라는 교차 증명).
//   반환 = [[height, fps], …] 중복 제거분. 실패·빈 값 = 키 자체를 안 실어 종전 6값 목록 유지(fail-soft).
const YT_ID_RE = /(?:v=|\/shorts\/|\/live\/|\/embed\/|youtu\.be\/)([A-Za-z0-9_-]{11})/;
async function ytFormats(u) {
  try {
    const m = YT_ID_RE.exec(u); if (!m) return [];
    const r = await fetch('https://www.youtube.com/youtubei/v1/player?prettyPrint=false', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'user-agent': 'com.google.ios.youtube/20.03.02 (iPhone16,2; U; CPU iOS 18_2_1 like Mac OS X)' },
      body: JSON.stringify({ context: { client: { clientName: 'IOS', clientVersion: '20.03.02', deviceMake: 'Apple', deviceModel: 'iPhone16,2', osName: 'iPhone', osVersion: '18.2.1.22C161' } }, videoId: m[1] }),
    });
    if (!r.ok) return [];
    const d = await r.json().catch(() => null);
    const fs = (d && d.streamingData && d.streamingData.adaptiveFormats) || [];
    const seen = new Set(), out = [];
    for (const f of fs) {
      // ⚠ 축 = **짧은 변**(운영자 260805 6차) — 러너 qual_fmt가 상한을 거는 축이 짧은 변이고(세로=width·가로=height),
      //   화면 라벨(_dgActualLbl)도 min(w,h)다. 구판은 height만 실어 세로 영상(1080×1920)이 티어 매칭에서 통째로 빠졌다.
      const h = +f.height || 0, w = +f.width || 0; if (!h && !w) continue;
      const s = Math.min(w || h, h || w);
      const fp = Math.round(+f.fps || 0);
      const k = s + 'x' + fp;
      if (!seen.has(k)) { seen.add(k); out.push([s, fp]); }
    }
    return out.slice(0, 40);
  } catch { return []; }   // fail-soft — 목록만 종전(정적 6값)으로 남는다
}

// ── X(트위터) 항목·화질(운영자 260805 6차 "최대화질이 이게 아닌데 이렇게 뜸 · 이미지 2개인데 영상처럼 하나만") ──
//   구판은 items·fmts가 **스레드/유튜브 전용**이라 X는 정적 6값으로 떨어져 「최대 4K 60fps」를 말했고(X 최대는 보통 1080),
//   사진 2장짜리 트윗도 「영상만」 한 줄로 뭉갰다. 재료 = X **공개 신디케이션**(키·로그인 0 · 임베드가 쓰는 그 경로).
//   실측 260805: mediaDetails[]가 photo면 media_url_https + original_info(1206×2010 등),
//   video면 video_info.variants[](mp4 · URL 경로에 320x568…1080x1920 = 실제 사다리)를 그대로 준다.
const X_ID_RE = /\/status\/(\d+)/;
const X_DIM_RE = /\/(\d+)x(\d+)\//;
async function xMedia(u) {
  try {
    const m = X_ID_RE.exec(u); if (!m) return null;
    const r = await fetch('https://cdn.syndication.twimg.com/tweet-result?id=' + m[1] + '&lang=ko&token=a',
      { headers: { 'user-agent': UA, accept: 'application/json' } });
    if (!r.ok) return null;
    const d = await r.json().catch(() => null); if (!d) return null;
    const items = [], fmts = [], seen = new Set();
    for (const md of (d.mediaDetails || []).slice(0, 20)) {
      const oi = md.original_info || {};
      const w = +oi.width || 0, h = +oi.height || 0;
      if (md.type === 'photo') {
        const uu = _mediaUrl(md.media_url_https);
        if (uu) items.push({ kind: 'img', w, h, u: uu });
        continue;
      }
      const vs = ((md.video_info || {}).variants || []).filter(v => v && v.content_type === 'video/mp4' && v.url);
      let best = null;
      for (const v of vs) {
        if (!best || (+v.bitrate || 0) > (+best.bitrate || 0)) best = v;
        const dm = X_DIM_RE.exec(v.url);
        if (dm) { const s = Math.min(+dm[1], +dm[2]); if (!seen.has(s)) { seen.add(s); fmts.push([s, 0]); } }   // fps = X가 안 준다 = 0 = 라벨에서 생략(지어내지 않음)
      }
      const bu = best ? _mediaUrl(best.url) : '';
      if (bu) items.push({ kind: 'video', w, h, u: bu });
    }
    const first = _mediaUrl((d.mediaDetails || [])[0] && (d.mediaDetails || [])[0].media_url_https);
    const txt = String(d.text || '').replace(/https:\/\/t\.co\/\w+/g, '').trim();   // 꼬리 t.co 단축주소 = 내용이 아니다
    const au = (d.user && d.user.screen_name) ? '@' + String(d.user.screen_name).slice(0, 40) : '';
    return { items, fmts, title: txt.slice(0, 200), desc: txt.slice(0, 300), thumb: first, author: au };
  } catch { return null; }   // fail-soft — 종전 og 경로로 계속
}

// ── 인스타그램 항목(운영자 260805 7차 링크 실측) ──
//   게시물 페이지는 로그인월이지만 **임베드**(/embed/captioned/)는 제3자 삽입용이라 열려 있다(스레드 임베드와 같은 축).
//   실측 260805: 103KB · 본문 이미지가 `srcset`으로 240~1440w 사다리를 그대로 준다 → 최대폭 1장을 항목으로 싣는다.
//   ⚠ 한계(정직) = 임베드는 **대표 1장**만 준다 — 캐러셀 2번째 이후·영상 실주소는 로그인 없이 안 나온다.
//     그래서 여기서 만드는 항목은 「받기 전 눈확인」용이고, 실제 받기는 종전대로 러너(쿠키 보유)가 전량 처리한다.
const IG_CODE_RE = /\/(?:p|reel|reels|tv)\/([\w-]{5,30})/;
async function igMedia(u) {
  try {
    const m = IG_CODE_RE.exec(u); if (!m) return null;
    const r = await fetch('https://www.instagram.com/p/' + m[1] + '/embed/captioned/', {
      headers: { 'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1', accept: 'text/html' },
      redirect: 'follow',
    });
    if (!r.ok) return null;
    const b = await r.arrayBuffer();
    const eh = new TextDecoder('utf-8').decode(b.byteLength > HTML_MAX ? b.slice(0, HTML_MAX) : b);
    if (!/EmbeddedMedia/.test(eh)) return null;   // 로그인월·형식 변경 = 포기(깨진 값 안 만든다)
    let best = '', bw = 0;
    const SRCSET_RE = /srcset="([^"]+)"/gi;
    let s;
    while ((s = SRCSET_RE.exec(eh))) {
      for (const part of unent(s[1]).split(',')) {
        const mm = /(\S+)\s+(\d+)w/.exec(part.trim());
        if (mm && +mm[2] > bw && /scontent[^/]*\.cdninstagram\.com/.test(mm[1])) { bw = +mm[2]; best = mm[1]; }
      }
    }
    const uu = _mediaUrl(best);
    const cm = /class="Caption"[^>]*>([\s\S]*?)<\/div>/i.exec(eh);
    const cap = cm ? unent(cm[1].replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim() : '';
    const au = /class="UsernameText"[^>]*>([^<]+)</i.exec(eh);
    return { items: uu ? [{ kind: 'img', w: bw, h: 0, u: uu }] : [], title: cap.slice(0, 200), desc: cap.slice(0, 300), thumb: uu, author: au ? '@' + au[1].trim().slice(0, 40) : '' };
  } catch { return null; }   // fail-soft — 종전 og 경로로 계속
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
      const [r, fmts] = await Promise.all([   // 포맷 조회는 oEmbed와 **동시** 발사 = 미리보기 지연 +0(둘 다 수백 ms)
        fetch(OEMBED[plat](t.toString()), { headers: { 'user-agent': UA, accept: 'application/json' } }),
        plat === 'YT' ? ytFormats(t.toString()) : Promise.resolve([]),
      ]);
      if (r.ok) {
        const d = await r.json().catch(() => null);
        if (d && d.title) {
          let th = '';
          try { const iu = new URL(String(d.thumbnail_url || '')); if (iu.protocol === 'https:') th = iu.toString(); } catch { th = ''; }
          const base = { plat, title: String(d.title).slice(0, 200), desc: '', thumb: th, author: String(d.author_name || '').slice(0, 60) };
          return json(fmts.length ? { ...base, fmts } : base);   // fmts 없음 = 키 자체 생략 = 뷰어가 종전 6값 목록 유지
        }
      }
    } catch { /* fail-soft = 아래 og 경로로 계속 */ }
  }

  // ── ①-c 인스타 = 임베드 한 경로(게시물 페이지는 로그인월 · 260805 7차) ──
  if (plat === 'IG') {
    const im = await igMedia(t.toString());
    if (im && (im.items.length || im.title)) {
      const base = { plat, title: im.title, desc: im.desc, thumb: im.thumb, author: im.author };
      if (im.items.length) base.items = im.items;
      return json(base);
    }   // 실패 = 아래 og 경로로 계속(악화 0)
  }

  // ── ①-b X = 신디케이션 한 경로로 제목·작성자·항목·화질이 전부 나온다(og보다 정확 · 260805 6차) ──
  if (plat === 'X') {
    const xm = await xMedia(t.toString());
    if (xm && (xm.items.length || xm.title)) {
      const base = { plat, title: xm.title, desc: xm.desc, thumb: xm.thumb, author: xm.author };
      if (xm.items.length) base.items = xm.items;
      if (xm.fmts.length) base.fmts = xm.fmts;
      return json(base);
    }   // 실패 = 아래 og 경로로 계속(악화 0)
  }

  let html = '', finalUrl = '', truncated = false;
  try {
    const r = await fetch(t.toString(), {
      headers: { 'user-agent': UA, accept: 'text/html,*/*;q=0.8', 'accept-language': 'ko-KR,ko;q=0.9' },
      redirect: 'follow',   // 스레드 공유 링크(/share/) = 302로 정규 주소를 알려준다 → 따라가야 og 메타가 있는 페이지에 닿는다
    });
    finalUrl = r.url || '';   // 리다이렉트 종착(정규 @계정/post/코드) — 아래 스레드 임베드 폴백의 재료(og가 비어도 주소는 건진다)
    if (r.ok) {
      const buf = await r.arrayBuffer();
      truncated = buf.byteLength > HTML_MAX;   // 절단분에서 나온 항목 구성은 「완본이 빠진 축약본」일 수 있다 = 신뢰 불가(평의회4 D3)
      html = new TextDecoder('utf-8').decode(truncated ? buf.slice(0, HTML_MAX) : buf);
    }
  } catch { /* fail-soft — 스레드는 아래 임베드 폴백이 한 번 더 시도(비스레드는 html='' = 미리보기 생략) */ }
  if (!html && plat !== 'TH') return json({ plat, title: '' });

  const m = ogMetas(html);
  let title = unent(m['og:title'] || m['twitter:title'] || '').slice(0, 200);
  let desc = unent(m['og:description'] || m['twitter:description'] || '').slice(0, 300);
  // ② 「Threads의 _(@계정)님」류 = **계정 껍데기라 내용이 0**이다(실측 260803) — 그 글의 내용은 og:description(본문)에 있다.
  //    운영자가 보려는 건 "어떤 내용인지"이므로, 제목이 껍데기면 본문을 제목 자리로 올린다(둘 다 없으면 미리보기 자체를 생략).
  if (desc && (!title || /\(@[^)]+\)/.test(title))) title = desc.slice(0, 200);
  const thumbRaw = (m['og:image'] || m['twitter:image'] || '').trim();
  let thumb = '';
  try { const iu = new URL(unent(thumbRaw)); if (iu.protocol === 'https:') thumb = iu.toString(); } catch { thumb = ''; }

  // 작성자 = og:title의 「_ (@계정) on Threads」류에서 계정만(실측 스레드 형식) · 없으면 빈칸(추측 금지)
  const am = /@([A-Za-z0-9._-]{2,40})/.exec(title) || /@([A-Za-z0-9._-]{2,40})/.exec(unent(m['og:url'] || ''));
  let author = am ? '@' + am[1] : '';

  // ── ③ 스레드 = 항목 구성(260805 3차) + 임베드 폴백(260805 2차 "입력하자마자 얘는 내용에 대한 미리 출력이 안됨") ──
  //    게시물 페이지 og는 엣지(데이터센터) IP에서 로그인월로 비기 일쑤인데 /embed는 제3자 삽입용이라 열려 있다
  //    — thembed.js가 260727부터 프로덕션에서 매일 실증하는 경로·UA를 **문자 계승**(신규 기법 창작 0).
  //    항목 구성 = SSR(치수까지) 우선 → 임베드(개수·종류만) 폴백 · 실패는 전부 fail-soft(미리보기·구성만 생략).
  let items = [];
  if (plat === 'TH') {
    // ⚠ 좌표(계정·코드)는 **주소의 경로에서만·앞부터 앵커링해** 읽는다(평의회5 D1) — 구판은 앵커 없는 정규식을
    //   `raw`(운영자 입력 원문) 전체에 돌려서 `…/share/@남의계정/post/XXXX` 같은 문자열이 오면 **엉뚱한 글**의
    //   제목·썸네일·항목을 「받을 내용」에 그렸다(실발사는 원 주소로 간다 = 화면과 실물 불일치).
    //   러너 정본이 같은 이유로 이미 금지한 축이다(nomute_threads.py:230 「본문 아무 데서나 줍는 폴백은 두지 않는다」).
    const _path = (s) => { try { return new URL(s).pathname; } catch { return ''; } };
    const _POST = /^\/@([A-Za-z0-9._]{1,60})\/post\/([\w-]{5,30})\/?$/;
    //   ③ og:url = **메타사가 스스로 밝힌 정답**(플러그인 find_shared_post와 같은 원천) — 리다이렉트가 안 일어난
    //      /share/·/t/ 응답에서 좌표를 얻는 유일한 정공법이다(share 코드로는 임베드가 404 = 실측).
    const cm = _POST.exec(_path(finalUrl)) || _POST.exec(_path(raw)) || _POST.exec(_path(t.toString()))
      || _POST.exec(_path(unent(m['og:url'] || '')));
    const ssr = thSsrItems(html, cm && cm[2], truncated);
    items = ssr.items;
    // ⚠ og가 **비는** 게 아니라 **로그인월 제목으로 차는** 경우가 실재한다(평의회1 실측 = 라이브 18건 중 2건 「Threads • 로그인」).
    //   그 상태로 두면 아래 폴백 조건(`!title`)이 안 걸려 임베드가 본문을 정상 파싱하고도 제목을 못 덮는다
    //   → 게시물 내용이 아닌 로그인 안내가 「받을 내용」에 제목으로 뜬다 = 1차 사고(거짓 표기)와 같은 죄.
    const _t = title.trim();
    if (/^threads(\s*[•·|-]\s*(로그인|가입|log\s?in|sign\s?up).*)?$/i.test(_t)) { title = ''; if (/로그인|log\s?in/i.test(desc)) desc = ''; }
    if (cm && (!title || !items.length || !ssr.trust)) {   // 제목이 og로 잡혔고 **믿을 수 있는** 항목까지 얻었으면 임베드 요청 자체를 안 한다
      try {
        const EMBED_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';   // thembed.js UA 동값
        const r2 = await fetch(`https://www.threads.com/@${cm[1]}/post/${cm[2]}/embed`, {
          headers: { 'user-agent': EMBED_UA, accept: 'text/html', 'accept-language': 'ko-KR,ko;q=0.9' }, redirect: 'follow',
        });
        if (r2.ok) {
          const b2 = await r2.arrayBuffer();
          const eh = new TextDecoder('utf-8').decode(b2.byteLength > HTML_MAX ? b2.slice(0, HTML_MAX) : b2);
          if (/EmbedContainer/.test(eh)) {   // 로그인월·형식 변경 = 폴백도 포기(깨진 값 안 만든다 · thembed 게이트 동문)
            // 본문 = <span class="BodyTextContainer"><span>텍스트</span></span>(실측 260805 — div 아님 · 첫 매치 = 원 게시물, 뒤 매치 = 인용/슬라이드)
            const bm = /class="BodyTextContainer"\s*>([\s\S]*?)<\/span>\s*<\/span>/i.exec(eh);
            const btxt = bm ? unent(bm[1].replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim() : '';
            if (btxt && !title) { title = btxt.slice(0, 200); if (!desc) desc = btxt.slice(0, 300); }
            if (!thumb) {
              const im = /<img\b[^>]*class="[^"]*\bimg\b[^"]*"[^>]*\bsrc="([^"]+)"/i.exec(eh);
              if (im) { try { const iu2 = new URL(unent(im[1])); if (iu2.protocol === 'https:') thumb = iu2.toString(); } catch { /* 썸네일만 생략 */ } }
            }
            if (!author) author = '@' + cm[1];
            // 신뢰 불가 SSR(파싱 실패 블록·절단)은 **틀린 개수를 확신 있게 말하는 쪽**이라 빈 값보다 위험하다(평의회4 D3)
            //   → 임베드가 개수를 주면 그쪽을 채택한다(치수는 없지만 개수·종류가 맞는 게 먼저).
            const emb = (!items.length || !ssr.trust) ? thEmbedItems(eh) : [];
            if (emb.length && (!items.length || !ssr.trust)) items = emb;
          }
        }
      } catch { /* fail-soft — 미리보기만 생략(발사 경로 무영향) */ }
    }
  }
  return json(items.length ? { plat, title, desc, thumb, author, items } : { plat, title, desc, thumb, author });
}
