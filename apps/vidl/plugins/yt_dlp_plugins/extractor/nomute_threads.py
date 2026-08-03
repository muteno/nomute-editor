# coding: utf-8
"""
노뮤트 Threads extractor — yt-dlp 플러그인 (배치 v7.0 무수정 배선용)

왜 필요한가:
  yt-dlp 코어에도 gallery-dl에도 Threads extractor가 없다(2026-07 실측).
  그래서 다운로더 v7.0의 TH 경로는 "불안정"이 아니라 구조적으로 100% 실패였다.

어떻게 받는가(추가 요청 0 · 토큰 0 · 로그인 0):
  Threads 웹앱은 Next.js가 아니라 Meta의 Relay/Comet 스택("Barcelona")이라
  __NEXT_DATA__가 없다. 대신 포스트 페이지 HTML 안에
      <script type="application/json" data-sjs>...</script>
  들이 SSR 데이터를 통째로 인라인으로 싣고 있고, 그 안에 서명된 CDN 미디어
  주소가 이미 들어 있다. 페이지 1회 fetch → JSON 파싱이면 끝난다.

함정(실측으로 확인한 것):
  · 한 페이지에 video_versions 블록이 여러 개 있다(추천글 relatedPosts 포함).
    실측 = 7블록 중 타깃 2 / 추천글 5. code == shortcode 검증이 필수다.
  · 캐러셀 항목에는 media_type이 안 실려 있다 → video_versions 유무로 판별한다.
  · 영상 서명(oe)은 약 1일, 이미지는 약 4일에 만료된다 → 주소 캐싱 금지.
"""

import json
import re

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError, int_or_none, traverse_obj

# ⚠ 버전은 반드시 올린다 — 260803 실사고: /share/ 지원이 들어간 뒤에도 1.0.0 그대로라
#   운영자 PC(OneDrive) 사본과 레포 정본이 **눈으로 구분이 안 됐다**(둘 다 1.0.0인데 한쪽만 공유 링크를 못 받는다).
#   PC 다운로더가 이 파일을 OneDrive 경로에서 읽으므로, 여기서 고친 건 그 사본을 갱신해야 라이브가 된다.
__version__ = '1.1.0'   # 1.1.0 = /share/ 공유 링크 지원(302 정규주소 해소 + 메타 폴백)

# 페이지가 "봇이 아니라 사람의 항해"로 보이게 하는 최소 세트.
# 이게 없으면 로그인 월/챌린지가 200 text/html로 조용히 돌아온다.
_NAV_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'),
    'Accept': ('text/html,application/xhtml+xml,application/xml;q=0.9,'
               'image/avif,image/webp,*/*;q=0.8'),
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
}

# 공유 링크(/share/<코드>) **전용** 헤더 — 브라우저 UA를 일부러 안 쓴다(운영자 260803 "스레드 다운로드 잘 안되더라고").
#   왜: 같은 공유 URL이 요청자에 따라 전혀 다른 응답을 준다(실측 260803).
#     · 브라우저 UA(_NAV_HEADERS) → **200 + 클라이언트 라우팅 셸**(og:url·al:ios:url 0건 · data-sjs 0건)
#       = 아래 find_shared_post가 읽을 정답 신호가 **페이지에 아예 없다** → 「어느 글인지 못 찾았다」로 전량 실패.
#     · 비-브라우저 UA(yt-dlp 기본·curl·requests 전부) → **302 Location = 정규 주소**
#       (`/@user/post/<shortcode>`) → 따라가면 SSR JSON까지 실린 원글 페이지(실측 560KB·data-sjs 29블록).
#   즉 지금은 **서버가 직접 알려주는 쪽**(리다이렉트)이 HTML 파싱보다 정확하고 싸다(요청 1회 그대로).
#   ⚠ 스코프 = share 첫 요청만. /post/·/t/(id가 곧 shortcode)와 그 뒤 모든 요청은 종전 _NAV_HEADERS 그대로 —
#     원글 페이지 자체는 브라우저 UA라야 로그인 월을 안 맞는다(위 주석의 사유는 여전히 유효).
_SHARE_HEADERS = {'Accept-Language': _NAV_HEADERS['Accept-Language']}

_SJS_RE = re.compile(
    r'<script[^>]+type="application/json"[^>]*\bdata-sjs\b[^>]*>(.*?)</script>', re.S)

_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'


def _walk(node):
    """dict/list를 재귀로 훑는다. 고정 경로는 스키마가 바뀌면 바로 깨지니 쓰지 않는다."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def shortcode_to_pk(shortcode):
    """shortcode → 숫자 postID. 위치기반 base64(바이트 디코드는 하위 2비트가 잘린다)."""
    pk = 0
    for c in shortcode:
        idx = _ALPHABET.find(c)
        if idx < 0:
            return None
        pk = pk * 64 + idx
    return pk


def extract_post_nodes(webpage, shortcode):
    """페이지 HTML에서 이 포스트에 해당하는 노드를 골라 돌려준다.

    식별은 code(문자) 우선, 없으면 pk(숫자)로도 맞춰본다 — 응답 형태에 따라
    둘 중 하나만 실리는 경우가 있다. 순수 함수라 네트워크 없이 검증 가능.
    """
    pk = shortcode_to_pk(shortcode)
    pk_s = str(pk) if pk is not None else None
    found = []
    for raw in _SJS_RE.findall(webpage):
        if shortcode not in raw and (not pk_s or pk_s not in raw):
            continue                                  # 이 포스트가 안 든 블록은 건너뛴다
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        for node in _walk(data):
            code = node.get('code')
            hit = (code == shortcode) or (code is None and pk_s and str(node.get('pk')) == pk_s)
            if hit and node not in found:
                found.append(node)
    return found


def collect_media(post):
    """post 노드 '안에서' 실제 미디어를 가진 딕트를 등장 순서대로 모은다.

    고정 경로(carousel_media 또는 자기 자신)로 찍으면 중간에 래퍼가 하나만 끼어도
    통째로 놓친다 — 실제로 그렇게 놓쳤다. 여기서만 재귀로 훑고, 미디어를 가진
    노드를 만나면 더 파고들지 않는다(캐러셀 항목이 자기 자식을 또 뱉는 것 방지).
    탐색 범위가 이미 '이 포스트 노드 안'이라 추천글이 섞일 여지는 없다.
    """
    out = []

    def has_media(x):
        # 캐러셀 컨테이너는 자기도 대표 썸네일(image_versions2)을 물고 있다.
        # 여기서 멈추면 슬라이드 14장이 통째로 사라지므로 자식에게 양보한다.
        if x.get('carousel_media'):
            return False
        return bool(x.get('video_versions')
                    or traverse_obj(x, ('image_versions2', 'candidates', 0, 'url')))

    def rec(x):
        if isinstance(x, dict):
            if has_media(x):
                if not any(x is o for o in out):
                    out.append(x)
                return
            for v in x.values():
                rec(v)
        elif isinstance(x, list):
            for v in x:
                rec(v)

    rec(post)
    return out


def _pick_video(media):
    """video_versions에서 변형들을 formats로 바꾼다. type 101 > 102 > 103.

    실측 함정 둘:
      · video_versions 항목에는 width/height가 아예 없다(전부 None).
        진짜 크기는 부모의 original_width/original_height에 있으므로 계승한다.
        이걸 안 채우면 배치 v7.0의 화질 사전조회가 'NA x NA'로 뜬다.
      · 해상도를 모르면 yt-dlp는 "리스트의 마지막이 최고"라는 관례로 고른다.
        그래서 나쁜 것 → 좋은 것 순으로 정렬해 넣어야 -f "bv*+ba/b/best"가
        최저(103)가 아니라 최고(101)를 집는다.
    """
    ow = int_or_none(media.get('original_width'))
    oh = int_or_none(media.get('original_height'))
    has_audio = media.get('has_audio')

    formats = []
    for v in traverse_obj(media, ('video_versions', ...)) or []:
        url = v.get('url')
        if not url:
            continue
        vtype = int_or_none(v.get('type'))
        formats.append({
            'url': url,
            'ext': 'mp4',
            'format_id': f'v{vtype}' if vtype else 'video',
            'width': int_or_none(v.get('width')) or ow,
            'height': int_or_none(v.get('height')) or oh,
            'vcodec': 'h264',
            'acodec': None if has_audio is None else ('aac' if has_audio else 'none'),
            # 101이 최선호라 값이 작을수록 좋다 → 부호를 뒤집어 quality로 쓴다
            'quality': -vtype if vtype else 0,
        })
    formats.sort(key=lambda f: f['quality'])       # 마지막이 최고가 되도록
    return formats


def _pick_image(media):
    """image_versions2.candidates에서 최고 해상도 1장을 formats로 바꾼다."""
    cands = traverse_obj(media, ('image_versions2', 'candidates', ...)) or []
    best, best_px = None, -1
    for c in cands:
        if not c.get('url'):
            continue
        px = (int_or_none(c.get('width')) or 0) * (int_or_none(c.get('height')) or 0)
        if px > best_px:
            best, best_px = c, px
    if not best:
        return []
    return [{
        'url': best['url'],
        'ext': 'jpg',
        'format_id': 'image',
        'width': int_or_none(best.get('width')),
        'height': int_or_none(best.get('height')),
    }]


_META_RE = re.compile(r'<meta\b[^>]*>', re.I)
_PROP_RE = re.compile(r'property=["\']([^"\']+)["\']', re.I)
_CONTENT_RE = re.compile(r'content=["\']([^"\']*)["\']', re.I)
# @ 는 페이지 안에서 &#064; 로 이스케이프돼 있다(실측) — 그래서 '@' 만 보는 정규식은 못 잡는다.
_POST_PATH_RE = re.compile(
    r'threads\.(?:net|com)/(?:@|&#0*64;|%40)(?P<user>[^/"\'?#&]+)/post/(?P<code>[\w-]+)', re.I)
_IOS_RE = re.compile(r'shortcode=(?P<code>[\w-]+)', re.I)


def page_metas(webpage):
    """<meta property=… content=…> 를 dict로. 속성 순서가 뒤집혀도 잡히게 태그 단위로 훑는다."""
    out = {}
    for tag in _META_RE.findall(webpage or ''):
        p, c = _PROP_RE.search(tag), _CONTENT_RE.search(tag)
        if p and c:
            out.setdefault(p.group(1).lower(), c.group(1))
    return out


def find_shared_post(webpage):
    """공유 링크(/share/<코드>) 페이지 → 그 글의 진짜 shortcode(+계정).

    공유 코드는 포스트 shortcode가 아니라서 SSR JSON과 그대로는 대조가 안 된다.
    다행히 페이지가 **메타에 정답을 싣는다**(실측 260802):
        og:url            = https://www.threads.com/&#064;oleg_mikushkin/post/DbgefN_D39T
        al:android:url    = 같은 주소
        al:ios:url        = barcelona://media?shortcode=DbgefN_D39T
    ⚠ 본문 아무 데서나 정규 주소 형태를 줍는 폴백은 두지 않는다 — 한 페이지에 추천글 코드가
      36개씩 섞여 있어(실측) 엉뚱한 글을 받아 버린다. 메타(= 메타사가 스스로 밝힌 정답)만 믿는다.
    """
    metas = page_metas(webpage)
    for key in ('og:url', 'al:android:url'):
        m = _POST_PATH_RE.search(metas.get(key) or '')
        if m:
            return m.group('user'), m.group('code')
    m = _IOS_RE.search(metas.get('al:ios:url') or '')
    return (None, m.group('code')) if m else None


class NomuteThreadsIE(InfoExtractor):
    IE_NAME = 'threads'
    IE_DESC = 'Meta Threads (노뮤트 플러그인)'
    # /post/(정규) · /t/(구 공유) · /share/(현 공유 시트) 세 형식 — 앞의 둘은 id가 곧 shortcode,
    # /share/ 는 공유 코드라 아래에서 페이지를 열어 정규 주소로 한 번 갈아탄다(운영자 260802 "스레드 다운로드가 안되네").
    _VALID_URL = (r'https?://(?:www\.)?threads\.(?:net|com)/'
                  r'(?:@(?P<user>[^/?#]+)/)?(?P<kind>post|t|share)/(?P<id>[\w-]+)')
    _TESTS = []

    def _real_extract(self, url):
        shortcode = self._match_id(url)
        mobj = self._match_valid_url(url)
        user = mobj.group('user')
        is_share = mobj.group('kind') == 'share'

        webpage, urlh = self._download_webpage_handle(
            url, shortcode, headers=(_SHARE_HEADERS if is_share else _NAV_HEADERS),
            note='포스트 페이지 받는 중', errnote='포스트 페이지를 못 받았다')

        if is_share:
            # ① 1순위 = **최종 URL**(302를 따라간 결과 = 서버가 지정한 정규 주소 · 260803 개정)
            #    본문 파싱보다 앞에 둔다 — 추천글 코드가 섞일 여지 자체가 없고, 셸 응답이 와도 여기서 갈린다.
            fin = _POST_PATH_RE.search(getattr(urlh, 'url', '') or '')
            hit = (fin.group('user'), fin.group('code')) if fin else find_shared_post(webpage)   # ② 폴백 = 종전 메타(og:url·al:*) 경로 그대로
            if not hit:
                raise ExtractorError(
                    '공유 링크가 어느 글인지 못 찾았다 — 스레드 앱에서 「링크 복사」로 나오는 '
                    'threads.com/@계정/post/… 주소를 넣어줘', expected=True)
            user, shortcode = hit[0] or user, hit[1]
            # 공유 페이지 자체가 그 글의 SSR JSON을 이미 싣고 있다(실측) → 추가 요청 0.
            # 혹시 안 실렸으면(축약 응답) 그때만 정규 주소로 한 번 더 연다.
            if not extract_post_nodes(webpage, shortcode) and user:
                url = f'https://www.threads.com/@{user}/post/{shortcode}'
                webpage = self._download_webpage(
                    url, shortcode, headers=_NAV_HEADERS,
                    note='공유 링크 → 원글 페이지 받는 중', errnote='원글 페이지를 못 받았다')

        posts = extract_post_nodes(webpage, shortcode)
        self.write_debug(f'포스트 노드 {len(posts)}개 · data-sjs 블록 {len(_SJS_RE.findall(webpage))}개')
        if not posts:
            if 'accounts/login' in webpage or 'LoginForm' in webpage:
                self.raise_login_required('비공개 포스트이거나 로그인 월에 막혔다')
            raise ExtractorError(
                'SSR JSON에서 이 포스트를 못 찾았다 — 비공개이거나 Threads가 구조를 바꿨다',
                expected=True)

        # 노드가 여럿이면 미디어를 가장 많이 문 것을 고른다(축약본과 완본이 함께 실릴 수 있다)
        slides, post = [], posts[0]
        for cand in posts:
            got = collect_media(cand)
            if len(got) > len(slides):
                slides, post = got, cand
        self.write_debug(f'미디어 노드 {len(slides)}개')

        uploader = (traverse_obj(post, ('user', 'username')) or user or 'threads')
        caption = traverse_obj(post, ('caption', 'text')) or ''
        title = (caption.strip().splitlines() or [''])[0][:80] or shortcode

        entries = []
        for idx, media in enumerate(slides, 1):
            formats = _pick_video(media) or _pick_image(media)
            if not formats:
                continue
            single = len(slides) == 1
            entries.append({
                'id': shortcode if single else f'{shortcode}_{idx}',
                'title': title if single else f'{title} ({idx})',
                'formats': formats,
                'uploader': uploader,
                'uploader_id': f'@{uploader}',
                'webpage_url': url,
                'timestamp': int_or_none(post.get('taken_at')),
                'description': caption or None,
            })

        if not entries:
            raise ExtractorError(
                '이 포스트엔 받을 미디어가 없다 — 글자만 있는 글이거나 Threads가 구조를 바꿨다. '
                '-v 를 붙여 다시 돌리면 찾은 노드 수가 보인다', expected=True)

        if len(entries) == 1:
            return entries[0]

        # 배치 v7.0은 /post/ URL을 PLPOST=1로 잡아 --no-playlist만 걸고
        # --playlist-items 1은 빼므로, 캐러셀 전량이 그대로 받아진다.
        return self.playlist_result(
            entries, playlist_id=shortcode, playlist_title=title,
            playlist_count=len(entries), multi_video=True)
