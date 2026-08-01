// Cloudflare Pages Function — 요약 요청 링크 사전 판별(운영자 260731 "링크에 자막이 있으면 자막 켜져있다는 걸 동그라미 디밍으로").
//   입력: GET ?u=<링크> · 출력: { kind:'media'|'article', subs:true|false|null, dur:초|0 }
//     dur   = 영상 길이(초 · 0=미상) — 뷰어 예상시간(전사는 길이 비례) 산출 원료(운영자 260731 "걸린시간을 유튜브 시간과 대조해 예상 시간이 항상 나오게")
//     kind  = media(영상·음성 = 전사 대상) / article(기사 = 원문 활용)
//     subs  = true(자막 있음 → 자막 경로) · false(자막 없음 → Whisper large-v3 전사 경로) · null(확인 불가)
//   ⚠️ 이건 **화면 리드백 전용 사전판별**이다 — 실제 파이프 판정 정본은 `.github/scripts/ask_link.py`(호스트 목록)와
//      `ask_link_stt.sh`(자막 2패스 실측)다. 여기서 null·오판이 나도 파이프 동작은 안 바뀐다(표시만 보수적으로 흐림).
//   자막 유무 = 유튜브 watch HTML 안 `captionTracks` 존재로 판정(키 불필요·읽기 전용). 봇 차단·비유튜브 = null.
const MEDIA_HOSTS = [
  'youtube.com', 'youtu.be', 'm.youtube.com', 'music.youtube.com',
  'vimeo.com', 'dailymotion.com', 'twitch.tv', 'tiktok.com',
  'soundcloud.com', 'podbbang.com', 'spotify.com', 'audioclip.naver.com',
  'tv.naver.com', 'tv.kakao.com', 'vod.afreecatv.com', 'play.sooplive.co.kr',
];   // ask_link.py MEDIA_HOSTS 미러(사본 = 리드백용 · 정본은 파이썬 쪽)
const MEDIA_EXT = ['.mp4', '.m4a', '.mov', '.webm', '.mkv', '.mp3', '.wav', '.aac', '.flac', '.ogg', '.m3u8'];

const hostOf = (u) => { const h = u.hostname.toLowerCase(); return h.startsWith('www.') ? h.slice(4) : h; };

function classify(u) {
  const host = hostOf(u);
  if (MEDIA_HOSTS.some(h => host === h || host.endsWith('.' + h))) return 'media';
  if (MEDIA_EXT.some(e => u.pathname.toLowerCase().endsWith(e))) return 'media';
  return 'article';
}

function ytId(u) {   // watch?v= · youtu.be/<id> · /shorts/<id> · /live/<id> · /embed/<id>
  const host = hostOf(u);
  if (host === 'youtu.be') return u.pathname.slice(1).split('/')[0] || '';
  if (!host.endsWith('youtube.com')) return '';
  const v = u.searchParams.get('v');
  if (v) return v;
  const m = u.pathname.match(/^\/(?:shorts|live|embed)\/([^/?#]+)/);
  return m ? m[1] : '';
}

export async function onRequestGet({ request }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), {
    status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
  const raw = (new URL(request.url).searchParams.get('u') || '').trim().slice(0, 500);
  let u;
  try { u = new URL(raw); } catch { return json({ error: '잘못된 링크' }, 400); }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return json({ error: '잘못된 링크' }, 400);

  const kind = classify(u);
  if (kind !== 'media') return json({ kind, subs: null, dur: 0 });

  const id = ytId(u);
  if (!/^[A-Za-z0-9_-]{5,20}$/.test(id)) return json({ kind, subs: null, dur: 0 });   // 유튜브 외 미디어 = 자막 유무·길이 미상(파이프가 실측)

  try {
    const r = await fetch(`https://www.youtube.com/watch?v=${id}&hl=ko`, {
      headers: { 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36', 'accept-language': 'ko,en;q=0.8' },
      cf: { cacheTtl: 300, cacheEverything: true },   // 같은 영상 반복 타이핑 = 엣지 캐시(과호출 억제)
    });
    if (!r.ok) return json({ kind, subs: null, dur: 0 });
    const html = (await r.text()).slice(0, 3000000);
    const dm = html.match(/"lengthSeconds"\s*:\s*"(\d+)"/);   // 영상 길이(초) — 예상시간 산출 원료
    const dur = dm ? Math.min(parseInt(dm[1], 10) || 0, 86400) : 0;
    // 판정(실측 260731 · 유튜브 2편 대조): 자막 있는 영상 = `"captions":` 객체 + `captionTracks` 배열이 함께 옴 /
    //   자막 없는 영상 = **`"captions":` 키 자체가 없다**(유튜브가 통째로 생략) — 이 둘을 가르는 게 핵심.
    //   단 `ytInitialPlayerResponse`(플레이어 응답)가 실려야 판정 유효 = 동의 페이지·봇 차단(응답 없음)은 미상으로 남긴다.
    if (/"captionTracks"\s*:\s*\[\s*\{/.test(html)) return json({ kind, subs: true, dur });    // 자막 트랙 1개 이상 = 자막 경로
    if (!/ytInitialPlayerResponse/.test(html) || !/"playabilityStatus"/.test(html)) return json({ kind, subs: null, dur });   // 페이지를 제대로 못 받음 = 미상
    if (/"captions"\s*:/.test(html) || /"playerCaptionsTracklistRenderer"/.test(html)) return json({ kind, subs: false, dur });   // 자막 블록은 있는데 트랙 0 = 전사 경로
    return json({ kind, subs: false, dur });   // 정상 응답 + captions 키 자체 없음 = 자막 없는 영상 = large-v3 전사 경로
  } catch { return json({ kind, subs: null, dur: 0 }); }
}
