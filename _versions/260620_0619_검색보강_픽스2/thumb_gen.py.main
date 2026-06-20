#!/usr/bin/env python3
# thumb_gen.py — 픽한 기사(queue/*.md)별 썸네일 후보: 검색이미지(기사 og:image+유사) + AI 4화풍(Gemini).
#
# 기존 카드 이미지 경로(외부 Apps Script + Drive + Cloud Run compose)와 완전 분리된 레포 내 경로:
#   - GitHub Actions가 Gemini(gemini-3.1-flash-image-preview = Nanobanana 2 Pro·4:5)를 직접 호출
#   - 기사 타이틀(헤드라인) 문구는 이미지에 안 박음 = 글자 없는 장면만(현장 간판 등 자연 글자는 무관). 고해상 2K.
#   - 산출 → Cloudflare R2 업로드(공개 URL) + gen.json([{sid,img,label}]) → build-viewer가 뷰어로 투영
#     (R2 미설정 시 git 폴백 = cards/<stem>/thumbs/gen-<style>.png 로컬 커밋·아무것도 안 깨짐)
#
# 안전: GEMINI_API_KEY 없으면 즉시 no-op(스캐폴드). 어떤 기사/화풍 실패도 fail-soft(파이프라인 안 깸).
# 비용: 픽한 기사당 이미지 4장(유료·4화풍). MAX_BATCH로 1런당 상한(최신 우선·이미 생성된 기사 skip).
#
# 정본 = 이 파일(썸네일 프롬프트 SSOT). 참조 = apps/news/03_자동화_레퍼런스.md §썸네일 후보.

import os, sys, re, json, base64, time, glob, subprocess, tempfile, ipaddress, socket
import urllib.request, urllib.error, urllib.parse

MODEL = "gemini-3.1-flash-image-preview"   # 카드와 동일 모델(03 레퍼런스). 4:5 · 썸네일 2K / 카드 1K.
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(MODEL)

def _int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default

MAX_BATCH = _int_env("THUMB_MAX_BATCH", 3)   # 1런당 기사 수 상한(비용 바운드)
# 활성화 기준일(YYMMDD) — 파일명이 이 날짜 이후인 기사만 생성 = 신규 픽 한정(기존 큐 백로그 폭탄 차단).
# 빈값이면 전체(백로그 포함). 워크플로가 활성화 날짜를 박는다.
SINCE = os.environ.get("THUMB_SINCE", "").strip()
KEY = os.environ.get("GEMINI_API_KEY", "").strip()
# ⚠️ 검색이미지는 더 이상 Google CSE JSON API를 안 씀(2025 신규고객 차단 死 → "this project does not have
#    access" 403 PERMISSION_DENIED). 대체 = 기사 본인 og:image 추출(fetch_article_images). CSE 시크릿 미사용.
# ── 저장소 = Cloudflare R2 (설정 시) → 공개 URL 직접 서빙(레포 비대 회피·egress 0). 미설정이면 git 폴백. ──
R2_ACCOUNT = os.environ.get("R2_ACCOUNT_ID", "").strip()
R2_BUCKET = os.environ.get("R2_BUCKET", "").strip()
R2_PUBLIC = os.environ.get("R2_PUBLIC_BASE", "").strip().rstrip("/")   # 예: https://pub-xxxx.r2.dev
R2_KEY = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
R2_ON = all([R2_ACCOUNT, R2_BUCKET, R2_PUBLIC, R2_KEY, R2_SECRET])

# ── 4화풍 (label = 뷰어 캡션) ─────────────────────────────────────────────
# 구도/카메라 어휘 = apps/k 라이브러리(카메라·거리·앵글·조명) 증류 인라인(빌드주입 X = 재과금 폭탄 회피).
# 글자: NO_TITLE이 타이틀 오버레이 전면금지 + 현장 자연글자도 최소만(아래).
# ⚠️ sid 리네임 금지 = 기존 카드 재과금 0(process_one이 sid로 보존). 추가만 허용(웹툰/포토 sid 유지).
STYLES = [
    ("webtoon", "웹툰 극화",
     "한국 웹툰 극화체 일러스트레이션. 굵고 선명한 잉크 라인, 극적인 명암 대비, 강한 감정 표현. "
     "인물 상반신 중심의 타이트한 프레이밍, 살짝 로우앵글로 긴장감, 단일 하드 측광."),
    ("photo", "포토 에디토리얼 — 와이드",
     "사실적인 보도/에디토리얼 사진 스타일. 자연광, 저널리즘적 현장감, 고급 잡지 표지 톤. "
     "와이드 설정샷(롱샷)으로 현장 전체와 맥락을 넓게 담고, 깊은 심도로 배경까지 또렷, 아이레벨."),
    ("photo_close", "포토 에디토리얼 — 클로즈업",
     "사실적인 보도/에디토리얼 사진 스타일. 자연광, 저널리즘적 현장감, 고급 잡지 표지 톤. "
     "핵심 인물·사물의 타이트한 클로즈업, 얕은 심도 보케로 배경 흐림, 표정·눈빛·디테일 강조, 살짝 로우앵글."),
    ("cartoon", "시사만평",
     "한국 신문 시사만평(편집 카툰) 스타일. 펜·잉크 캐리커처 선화에 담백한 단색/수채 채색, "
     "은유와 풍자가 담긴 단일 장면 구성. 특정 실존 인물의 얼굴을 닮게 그리지 말고 역할·직군을 상징하는 "
     "익명 캐리커처로(예: 양복 입은 관료, 헬멧 쓴 노동자). 모욕적·혐오적 묘사 금지, 사안에 대한 점잖은 풍자만."),
]

COMPOSITION = (
    "세로 4:5 비율. 핵심 피사체와 주요 요소(인물의 눈·눈빛·표정·손짓, 핵심 사물·증거·간판 글귀 등 시선이 머무는 부분)는 "
    "화면 상단 2/3 안에 또렷하게 모이도록 배치한다. 화면 하단 약 1/3은 인물의 몸통·바닥·배경 등 단순하고 비교적 어두운 영역으로 "
    "두어 비교적 비운다 — 중요한 디테일을 화면 맨 아래에 두지 말 것(이 하단 여백은 추후 기사 타이틀 자막이 얹히는 자리다). "
    "한 장면 = 하나의 명확한 주인공(과밀 금지). "
    "한국인·한국 배경을 기본값으로(국제 기사 등 명백히 외국이면 해당 지역). 자극적·선정적 묘사 금지, 미성년자 안전. 워터마크·로고 없음."
)

# 글자 = 양방향 정의: 오버레이/타이틀 전면금지 + 현장 자연글자도 "최소·작게·흐릿"까지만(읽히게 그리지 말 것 = 한글 깨짐 방지).
NO_TITLE = (
    "이미지 속 글자는 최소화한다. 기사 제목·헤드라인·자막·설명 문장 등 오버레이/텍스트 밴드는 전면 금지. "
    "현장에 자연스러운 글자(간판·표지판·도로명 등)는 화면 구석에 작게 1~2개까지만 허용하고, 화면 중앙·다수·또렷한 글자판은 금지. "
    "글자를 읽을 수 있게 또렷이 렌더링하지 말 것(읽히는 한글은 깨질 위험이 크다)."
)

def build_prompt(art_dir, scene):
    parts = [art_dir]
    if scene:
        parts.append("장면: " + scene)
    parts.append(COMPOSITION)
    parts.append(NO_TITLE)
    return " ".join(parts)

# ── queue md 파싱: frontmatter title + 본문 h1(에디토리얼 헤드라인) + 한줄요약 ──
def parse_md(path):
    raw = open(path, encoding="utf-8").read()
    fm = {}
    m = re.search(r"^---\s*$(.*?)^---\s*$", raw, re.M | re.S)
    body = raw
    if m:
        for line in m.group(1).splitlines():
            kv = re.match(r'\s*([a-zA-Z_]+)\s*:\s*"?(.*?)"?\s*$', line)
            if kv:
                fm[kv.group(1)] = kv.group(2)
        body = raw[m.end():]
    h1 = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    head = (h1.group(1) if h1 else fm.get("title", "")).strip()
    head = re.sub(r"^[\U0001F000-\U0001FAFF☀-➿️\s]+", "", head)  # 앞 이모지 제거
    lead = ""
    lm = re.search(r"한줄\s*요약\s*\n+(.+?)(?:\n\n|\n#|\Z)", body, re.S)
    if lm:
        lead = re.sub(r"\s+", " ", lm.group(1)).strip()
    # 상단 검색이미지용 키워드(요약이 뽑은 entity 중심) — 없거나 플레이스홀더면 빈 문자열(→ head 폴백).
    iq = fm.get("image_query", "").strip()
    if iq in ("삼성전자 반도체 평택공장",):   # 프롬프트 예시값을 모델이 그대로 베끼면 무시(→ head 폴백)
        iq = ""
    return head, lead, iq, fm.get("url", "").strip(), fm.get("alt_urls", "").split()

def _md_url(path):
    """프런트매터 url만 가볍게 추출(main의 백필 판정용 · 파일 앞부분만 읽음)."""
    try:
        m = re.search(r'^\s*url\s*:\s*"?([^"\n]*)', open(path, encoding="utf-8").read(2000), re.M)
        return (m.group(1).strip() if m else "")
    except Exception:
        return ""

def gemini_image(prompt, image_size="1K"):
    """Gemini 이미지 1장 생성 → PNG bytes(실패 시 None, fail-soft).

    image_size: "1K"(기본·gen_cards 재사용 시 유지)·"2K"·"4K"(대문자 K 필수). 썸네일은 2K 호출(고해상).
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"],
                             "imageConfig": {"aspectRatio": "4:5", "imageSize": image_size}},
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API + "?key=" + KEY, data=data,
                                headers={"Content-Type": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.loads(r.read().decode())
            for cand in j.get("candidates", []):
                for p in cand.get("content", {}).get("parts", []):
                    inl = p.get("inlineData") or p.get("inline_data")
                    if inl and inl.get("data"):
                        return base64.b64decode(inl["data"])
            print("  ⚠️ 이미지 파트 없음(응답에 inlineData 부재)", flush=True)
            return None
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:300]
            print("  ⚠️ HTTP {} — {}".format(e.code, msg), flush=True)
            if e.code in (429, 500, 503) and attempt == 0:
                time.sleep(4); continue
            return None
        except Exception as e:
            print("  ⚠️ 호출 실패: {}".format(e), flush=True)
            if attempt == 0:
                time.sleep(4); continue
            return None
    return None

# ── 검색이미지 = 기사 본인 대표사진(og:image) + 관련기사 유사사진 추출 — Google CSE JSON API 대체(2025 신규차단 死) ──
# 구글 검색 대신 "원기사 URL의 og:image(대표) + 관련기사 og:image(유사·대표와 다른 사진)"를 끌어와 검색이미지 칸을 채운다.
# 대표=라벨'' / 유사=라벨'유사'. R2 설정 시 재호스팅(핫링크·리퍼러 차단 0)·미설정이면 외부 핫링크. 차단매체(403)·paste(url無)면 [].
# 🔑 신뢰원: og:image/twitter/JSON-LD = 발행사 선언만 사용(대표 보존·크기/크롭 면제). 본문 <img>는
#    '속보' 배너 등 그래픽 오염으로 폐지(260620) — body=True 분기·필터는 보존(미호출). 분신술 10인 감사 반영.
# 🔗 유사 보강(260620): 대표 1장 + 자리 남으면 '유사' 채움 — ① 클러스터 멤버(픽이 심은 같은 사건 타매체
#    url = frontmatter `alt_urls`, analyze.sh가 보존) og:image **우선**(신뢰·다른 앵글) ② 마커 매체(SBS oaid·
#    이투데이 trc=view_joinnews) 관련기사 og 폴백. 대표와 중복/소형/잡것 컷. 비전 게이트 OFF 훅(THUMB_VISION).
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
# 대표·본문 공통 컷 = 명백한 비콘텐츠(플레이스홀더·스페이서·파비콘)
_PLACEHOLDER = re.compile(r"(og[-_]?default|no[-_]?image|noimage|placeholder|blank|spacer|"
                          r"1x1|/pixel|favicon|sprite)", re.I)
# 본문 <img> 전용 잡것(로고·아이콘·광고·동영상썸네일) — 경계화로 본문단어(shareholder·iconic…) 오탐 방지
_BODY_SKIP = re.compile(
    r"((?:^|[/_.-])(?:logo|icons?|btn|button|banner|share|sharebtn|avatar|emoji|"
    r"thumb|sthumb|mini|small|resize|argon)(?:[/_.-]|$)|"
    r"[/_-]ads?(?=[/_.-])|adfit|doubleclick|googlesyndication|googleads|"          # 광고
    r"ytimg|youtube|youtu\.be|[mhs]qdefault|maxresdefault|/vi/)",                  # 동영상 썸네일
    re.I)

def _dom_core(host):
    """호스트 → 핵심 도메인 라벨(img.etoday.co.kr·www.etoday.co.kr → 'etoday'). 같은 매체 판정용."""
    SUF = {"co", "com", "net", "org", "kr", "jp", "go", "or", "ne", "gov", "edu", "io"}  # 'news'=라벨 오붕괴 → 제외
    parts = [p for p in (host or "").lower().split(".") if p]
    while len(parts) > 1 and parts[-1] in SUF:
        parts.pop()
    return parts[-1] if parts else (host or "")

def _norm_key(u):
    """리사이즈 변형(같은 사진·다른 크기·다른 size디렉터리) 중복제거 키.

    뉴스 CDN 파일명은 날짜/시퀀스 고유ID(예: 20260419144431_2323414…) → 같은 파일명 = 같은 사진(다른 크기/디렉터리).
    파일명 기준 dedup하되, generic 파일명(photo01·image·1)은 오수집(서로 다른 사진 손실) 방지 위해 전체 URL로 폴백.
    """
    base = urllib.parse.urlparse(u).path.lower().rsplit("/", 1)[-1].split("?")[0]
    base = re.sub(r"[_-]\d{2,4}x\d{2,4}(?=\.)", "", base)    # _800x600 접미사
    base = re.sub(r"[_-](?:th|sm|lg|xl|s|m|l)(?=\.)", "", base)  # _th _s 접미사
    return base if sum(c.isdigit() for c in base) >= 7 else u   # 고유ID성 파일명만 basename dedup

def _small_dim(u):
    """URL에 박힌 치수가 작은 썸네일(둘 다 <400 or 쿼리 치수 max<400)인지 — 큰 값 있으면 통과(OG카드 1200×630 보존)."""
    nums = [int(x) for x in re.findall(r"[?&](?:w|width|h|height|size)=(\d{1,5})", u, re.I)]
    if nums and max(nums) < 400:
        return True
    m = re.search(r"[_/-](\d{2,4})x(\d{2,4})(?=[._/]|$)", u)
    if m and int(m.group(1)) < 400 and int(m.group(2)) < 400:
        return True
    mh = re.search(r"[_-](\d{2,4})[_-](\d{2,4})\.(?:jpe?g|png|webp|gif)(?:[?#]|$)", u, re.I)   # etoday류 _W_H.jpg 트레일링 치수
    if mh and int(mh.group(1)) < 400 and int(mh.group(2)) < 400:
        return True
    m2 = re.search(r"[?&]type=w(\d{1,4})", u, re.I)          # 네이버 mblogthumb type=w80
    return bool(m2 and int(m2.group(1)) < 400)

def _img_candidates(html, base):
    """기사 HTML → 이미지 후보(대표 먼저·중복제거). 대표(og/twitter/JSON-LD)=신뢰·최소필터 / 본문 img=엄격필터."""
    import html as _html
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)      # 주석 제거(주석 og 오대표·주석 img 차단)
    out, seen, seen_key = [], set(), set()
    def core_of(u):
        return _dom_core(urllib.parse.urlparse(u).hostname or "")
    def seg0(u):
        return ([s for s in urllib.parse.urlparse(u).path.split("/") if s] or [""])[0].lower()
    def add(u, body=False, junk=False):
        if not u:
            return
        u = _html.unescape(u.strip())
        if u.startswith("//"):
            u = "https:" + u
        u = urllib.parse.urljoin(base, u)
        if not re.match(r"https?://", u, re.I):
            return
        if not re.search(r"\.(jpe?g|png|webp|gif)(?:[/?#]|$)", u, re.I):
            return
        if _PLACEHOLDER.search(u):
            return
        if (body or junk) and _BODY_SKIP.search(u):         # 본문·JSON-LD = 로고/아바타/광고/동영상 컷
            return
        if body:   # 본문 <img> = 비신뢰 → 추가 엄격: 같은매체(대표 호스트)·같은 디렉터리·작은썸네일 컷
            ref = out[0] if out else base                   # 대표(og) 호스트 기준 = 네이버/다음(기사≠CDN) 구제
            if core_of(u) != core_of(ref):
                return
            # 같은 사진 디렉터리 컷(프로모·배너) — 대표와 정확히 같은 호스트일 때만(리사이저=다른 host면 면제: nate·daum)
            if (out and urllib.parse.urlparse(u).hostname == urllib.parse.urlparse(out[0]).hostname
                    and seg0(u) != seg0(out[0])):
                return
            if _small_dim(u):
                return
        k = _norm_key(u)                                    # 리사이즈 변형 중복 제거(정규화 키)
        if u in seen or k in seen_key:
            return
        seen.add(u); seen_key.add(k); out.append(u)
    # 1) 대표 = og:image / twitter:image (속성 순서 무관 · 발행사 선언=신뢰, 호스트·크기 무관 허용)
    for tag in re.findall(r"<meta\b[^>]*>", html, re.I):
        if re.search(r'(?:property|name)\s*=\s*["\'](?:og:image(?::url)?|twitter:image(?::src)?)["\']', tag, re.I):
            cm = re.search(r'content\s*=\s*["\']([^"\']+)', tag, re.I)
            if cm:
                add(cm.group(1))
    # 2) JSON-LD "image" — og/twitter 못 찾았을 때만(fallback) · 윈도 400자·앞 2개·로고/아바타/동영상 컷(bleed 방지)
    if not out:
        for m in re.finditer(r'"image"\s*:', html):
            for u in re.findall(r'"(https?:[^"]+?\.(?:jpe?g|png|webp|gif)[^"#?]*)', html[m.end():m.end() + 400])[:2]:
                add(u, junk=True)
    # 3) (본문 <img> 긁기 폐지 — 운영자 260620: 매체 '속보' 배너 등 본문 그래픽이 '유사'로 새어 차단.
    #    이 함수는 한 기사당 og/twitter/JSON-LD 1장만 = 발행사 선언만. 다장 '유사'는 관련기사 og로 채운다
    #    [phase2 = fetch_article_images._related_urls, 마커 신뢰 매체만].)
    return out

def _url_ok(u):
    """fetch 허용 = http(s) + 호스트가 (DNS resolve 후) 전역 공인 IP만. SSRF 게이트.

    ⚠️ 문자열만 보면 8진수/정수(2130706433)/16진수/단축(127.1)/nip.io 난독화에 우회됨
    (ipaddress는 거부하지만 OS 리졸버는 사설로 풂) → 실제 resolve해 모든 A/AAAA가 is_global인지 검사
    (사설·루프백·링크로컬169.254·CGNAT100.64·예약·멀티캐스트 전부 차단). 동적 리바인딩은 잔여(수용).
    """
    try:
        p = urllib.parse.urlparse(u)
    except Exception:
        return False
    if p.scheme.lower() not in ("http", "https"):
        return False                                        # file://·ftp://·data:· gopher:// 차단
    host = (p.hostname or "").lower()
    if not host or host == "localhost" or host.endswith(".localhost"):
        return False
    ips = set()
    try:
        ips.add(str(ipaddress.ip_address(host)))            # 정규형 IP literal
    except ValueError:
        pass
    try:                                                    # 도메인·난독화 literal을 OS 리졸버로 실제 해석
        ips |= {ai[4][0] for ai in socket.getaddrinfo(host, None)}
    except Exception:
        pass
    if not ips:
        return False                                        # resolve 실패 = fail-closed
    for s in ips:
        try:
            ip = ipaddress.ip_address(s.split("%")[0])      # IPv6 zone id 제거
        except ValueError:
            return False
        if not ip.is_global or ip.is_reserved:              # 비전역(사설/루프백/링크로컬/CGNAT)·예약 = 거부
            return False
    return True

class _NoPrivateRedirect(urllib.request.HTTPRedirectHandler):
    """리다이렉트 매 hop 재검증 — 공개 URL → 302 내부IP/file 우회(SSRF) 차단."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _url_ok(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)

_OPENER = urllib.request.build_opener(_NoPrivateRedirect)   # urlopen 대신 사용(리다이렉트 게이트 적용)

_MAGIC = ((b"\xff\xd8\xff", "image/jpeg", "jpg"), (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
          (b"GIF87a", "image/gif", "gif"), (b"GIF89a", "image/gif", "gif"))
def _img_type(b):
    """매직바이트 → (안전 content-type, ext) 또는 (None, None). SVG·HTML·스크립트 등 비이미지 차단(R2 저장형 XSS 방지)."""
    if len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp", "webp"
    for sig, ct, ext in _MAGIC:
        if b.startswith(sig):
            return ct, ext
    return None, None

def _fetch_html(u):
    """기사 URL → 디코드 HTML 또는 None(실패·비허용 url). 대표·관련기사 fetch 공용(SSRF·리다이렉트 게이트)."""
    if not (u and _url_ok(u)):
        return None
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        with _OPENER.open(req, timeout=20) as r:
            raw = r.read(1500000)
            charset = r.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, "replace")
        except LookupError:                                 # 알 수 없는 charset 라벨 → utf-8 폴백(fail-soft)
            return raw.decode("utf-8", "replace")
    except Exception as e:
        print("  ⚠️ fetch 실패({}…): {}".format(u[:45], e), flush=True)
        return None

# phase2 = 관련기사 og:image를 '유사'로(대표와 다른 사진). '이 기사의 관련'임을 보증하는 마커 있는 매체만
# (오염·무관 차단 — 운영자 "무관 금지" 우선). 도메인코어 → 관련링크 정규식. 마커 없는 매체·차단매체·paste면 [].
_RELATED_RULES = {
    "sbs":    re.compile(r'href\s*=\s*["\']([^"\']*?endPage\.do\?[^"\']*?oaid=[^"\']+)', re.I),                 # oaid=원기사id 백레프
    "etoday": re.compile(r'href\s*=\s*["\']([^"\']*?/news/view/\d{5,}[^"\']*?trc=view_joinnews[^"\']*)', re.I),  # trc=조인뉴스(관련)
}
def _related_urls(html, base):
    """기사 HTML → 관련기사 URL(마커 신뢰 매체만·중복제거·최대 6). 화이트리스트 규칙만(범용 추출=오염 위험이라 금지)."""
    import html as _h
    pat = _RELATED_RULES.get(_dom_core(urllib.parse.urlparse(base).hostname or ""))
    if not pat:
        return []
    out, seen = [], set()
    for m in pat.findall(html):
        u = urllib.parse.urljoin(base, _h.unescape(m).replace("&amp;", "&"))
        if u != base and u not in seen and _url_ok(u):
            seen.add(u); out.append(u)
    return out[:6]

def _vision_keep(rep_src, cand_src):
    """비전 훅(기본 OFF=pass-through). THUMB_VISION=1일 때만 Gemini로 '대표와 같은 인물/장면이면 컷' 판정.
    기본(미설정)은 cand 그대로 반환 = 과금 0. 점화는 후속(운영자 승인 시 여기에 Gemini 1콜 배선)."""
    if os.environ.get("THUMB_VISION", "") != "1":
        return cand_src
    return cand_src   # (점화 시: 대표와 동일 인물/장면이면 None 반환해 컷)

def fetch_article_images(art_url, alt_urls=None, want=3):
    """기사 URL → [{src,link,label}] 최대 want장. 대표=원기사 og(라벨'') ·
    유사=클러스터 멤버(같은 사건 타매체 alt_urls) og + 마커매체 관련기사 og(라벨'유사', 대표와 다른 사진). 실패·빈url이면 [] (fail-soft)."""
    if not (art_url and _url_ok(art_url)):
        return []
    text = _fetch_html(art_url)
    if text is None:
        return []
    out = []
    for u in _img_candidates(text, art_url)[:want]:
        out.append({"src": u, "link": art_url, "label": "" if not out else "유사"})
    # 유사 보강: 클러스터 멤버(픽이 심은 같은 사건 타매체 = 신뢰·다른 앵글) 우선 + 마커매체 관련기사 폴백.
    if out and len(out) < want:
        seen = {_norm_key(it["src"]) for it in out}
        rep = out[0]["src"]
        related = [u for u in (alt_urls or []) if _url_ok(u) and u != art_url]
        related += _related_urls(text, art_url)
        for ru in related[:8]:
            if len(out) >= want:
                break
            rc = _img_candidates(_fetch_html(ru) or "", ru)
            rog = rc[0] if rc else None
            if not rog or _norm_key(rog) in seen or _small_dim(rog) or _BODY_SKIP.search(rog):
                continue
            if not _vision_keep(rep, rog):
                continue
            seen.add(_norm_key(rog))
            out.append({"src": rog, "link": ru, "label": "유사"})
            print("  🔗 유사 +1 ({}…)".format(ru[:42]))
    return out

def http_image(url):
    """이미지 URL → (bytes, 안전 content-type, ext) 또는 (None,None,None). 매직바이트로 실제 이미지만 통과."""
    if not _url_ok(url):
        return None, None, None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with _OPENER.open(req, timeout=20) as r:
            b = r.read(8000000)
    except Exception as e:
        print("  ⚠️ 이미지 다운로드 실패({}…): {}".format(url[:45], e), flush=True)
        return None, None, None
    ct, ext = _img_type(b or b"")
    if not ct:                                              # SVG/HTML/비이미지 → 거부(R2 오염·저장형 XSS 차단)
        print("  ⚠️ 비이미지 응답 거부({}…)".format(url[:45]), flush=True)
        return None, None, None
    return b, ct, ext

def r2_upload(png_bytes, key, content_type="image/png"):
    """바이트 → R2 업로드(aws cli S3호환·러너 기본설치) → 공개 URL. 실패 시 None(fail-soft → 로컬 폴백)."""
    endpoint = "https://{}.r2.cloudflarestorage.com".format(R2_ACCOUNT)
    env = dict(os.environ, AWS_ACCESS_KEY_ID=R2_KEY, AWS_SECRET_ACCESS_KEY=R2_SECRET,
               AWS_DEFAULT_REGION="auto")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(png_bytes); tmp = f.name
        subprocess.run(["aws", "s3", "cp", tmp, "s3://{}/{}".format(R2_BUCKET, key),
                        "--endpoint-url", endpoint, "--content-type", content_type,
                        "--only-show-errors"], check=True, env=env, timeout=90)
        return "{}/{}".format(R2_PUBLIC, key)
    except Exception as e:
        print("  ⚠️ R2 업로드 실패: {}".format(e), flush=True)
        return None
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)

def _load_gen(tdir):
    try:
        g = json.load(open(os.path.join(tdir, "gen.json"), encoding="utf-8"))
        return g if isinstance(g, list) else []
    except Exception:
        return []

def process_one(md, stem):
    """기사 1건 = 검색이미지(기사 og:image + 유사) + AI 4화풍. 저장 = R2(공개 URL) 또는 git 폴백."""
    head, lead, iq, art_url, alt_urls = parse_md(md)
    if not head:
        print("· {} — 헤드라인 파싱 실패, skip".format(stem)); return False
    print("· {} — “{}”".format(stem, head[:40]), flush=True)
    tdir = os.path.join("cards", stem, "thumbs")
    os.makedirs(tdir, exist_ok=True)
    search_written = False
    # 검색이미지 = 기사 본인 대표사진(og:image) + 유사 — Google CSE JSON API 대체(2025 신규차단 死).
    # url 있고 아직 없을 때만. 대표=라벨'' / 유사='유사'. R2 재호스팅(핫링크 0), 실패 시 외부 핫링크 폴백.
    if art_url and not os.path.exists(os.path.join(tdir, "search.json")):
        cand = fetch_article_images(art_url, alt_urls=alt_urls, want=3)
        items = []
        for i, c in enumerate(cand):
            final = None
            if R2_ON:
                b, ctype, ext = http_image(c["src"])        # 매직바이트 검증된 안전 ctype·ext
                if b:
                    final = r2_upload(b, "thumbs/{}/search-{}.{}".format(stem, i, ext), ctype)
            items.append({"url": final or c["src"], "link": c["link"], "label": c["label"]})
        # 빈 결과(차단매체·사진無)도 search.json=[] 1회 기록 → 매 런 재fetch(좀비 슬롯잠식) 차단(앵글7·10)
        json.dump(items, open(os.path.join(tdir, "search.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        search_written = True
        if items:
            print("  🖼 검색이미지 {}장 (대표 1 + 유사 {})".format(len(items), len(items) - 1))
        else:
            print("  · 검색이미지 0장 기록(차단·사진無 → AI썸네일 커버·재fetch 차단)")
    # AI 생성 4화풍 — 기존 gen.json의 완료 화풍(sid)은 보존·재호출(재과금) 안 함 = 부분성공 자동 보완(폐지된 watercolor sid는 STYLES에 없어 자동 드롭)
    existing = {g.get("sid"): g for g in _load_gen(tdir) if g.get("sid")}
    gen = []
    changed = False
    for sid, label, art_dir in STYLES:
        if sid in existing:                      # 이미 완료(R2 URL or 로컬) → 보존
            gen.append(existing[sid]); continue
        png = gemini_image(build_prompt(art_dir, iq or lead), "2K")   # 장면 = entity(iq) 우선·없으면 한줄요약(글자 환각↓·일관성↑)
        if not png:
            print("  ✗ {} 실패".format(label)); continue
        if R2_ON:                                # R2 = 공개 URL(레포 미저장)
            url = r2_upload(png, "thumbs/{}/gen-{}.png".format(stem, sid))
            if url:
                gen.append({"sid": sid, "img": url + "?v=" + str(int(time.time())), "label": label}); changed = True   # ?v=캐시버스트(재생성 시 같은 R2 키 덮어써도 새 이미지 반영)
                print("  ✓ {} → R2".format(label)); continue
            # R2 업로드 실패 → 로컬 폴백(아래로 떨어짐)
        fp = os.path.join(tdir, "gen-{}.png".format(sid))   # git 폴백 = 로컬 PNG
        open(fp, "wb").write(png)
        gen.append({"sid": sid, "file": "gen-{}.png".format(sid), "label": label}); changed = True
        print("  ✓ {} ({:.0f}KB, 로컬)".format(label, len(png) / 1024))
    if changed:
        json.dump(gen, open(os.path.join(tdir, "gen.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    return changed or search_written

def main():
    if not KEY:
        print("GEMINI_API_KEY 없음 — 썸네일 생성 생략(스캐폴드 no-op)")
        return 0
    print("저장소: {}".format("Cloudflare R2" if R2_ON else "git 폴백(R2 미설정)"))
    # ── 단일 기사 강제 재생성 (뷰어 '다시 만들기' → thumb-redo.yml · THUMB_ONLY=stem) ──
    # gen.json만 비워 4화풍 전부 재생성(검색 search.json=기사 og:image는 보존). SINCE/MAX_BATCH 무관.
    only = os.environ.get("THUMB_ONLY", "").strip()
    if only:
        md = os.path.join("queue", only + ".md")
        if not os.path.exists(md):
            print("THUMB_ONLY 대상 없음:", md); return 0
        gp = os.path.join("cards", only, "thumbs", "gen.json")
        try:
            if os.path.exists(gp):
                os.remove(gp); print("  ↻ gen.json 비움 → 4화풍 재생성:", only)
        except Exception as e:
            print("  ⚠️ gen.json 제거 실패:", e)
        process_one(md, only)
        print("THUMB_ONLY 재생성 완료:", only)
        return 0
    # 미완성 기사만(최신 우선) = gen.json에 4화풍(sid) 다 있으면 완성으로 보고 skip(부분이면 보완).
    target_sids = {s[0] for s in STYLES}
    todo = []
    for md in sorted(glob.glob("queue/*.md"), reverse=True):
        stem = os.path.basename(md)[:-3]
        if SINCE and stem[:6] < SINCE:
            continue   # 활성화 기준일 이전(백로그) 제외 = 신규 픽 한정
        tdir = os.path.join("cards", stem, "thumbs")
        ai_done = {g.get("sid") for g in _load_gen(tdir)} >= target_sids
        # url 있는데 search.json 없으면 검색이미지(og:image) 백필 대상에 포함.
        # AI 완료분은 process_one이 기존 sid 보존 → Gemini 0회, 검색이미지만 채움(추가 과금 없음).
        search_pending = bool(_md_url(md)) and not os.path.exists(os.path.join(tdir, "search.json"))
        if ai_done and not search_pending:
            continue
        todo.append((md, stem))
    if not todo:
        print("새 썸네일 대상 없음")
        return 0
    print("썸네일 대상 {}건 중 {}건 처리(SINCE={})".format(len(todo), min(len(todo), MAX_BATCH), SINCE or "전체"))
    made = 0
    for md, stem in todo[:MAX_BATCH]:
        try:
            if process_one(md, stem):
                made += 1
        except Exception as e:   # 기사 1건 실패가 배치 전체를 안 끊게(기사 단위 fail-soft)
            print("  ⚠️ {} 처리 실패(건너뜀): {}".format(stem, e), flush=True)
            continue
    print("완료 — {}건 처리".format(made))
    return 0

if __name__ == "__main__":
    sys.exit(main())
