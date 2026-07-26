#!/usr/bin/env python3
"""뷰어 '+N장 더' (검색 이미지 카러셀) — 기사 요약·시사점을 읽고 Claude(Opus 5·effort high)가
**오버레이 뒤 후킹용 카드뉴스 배경**으로 가장 효과적인 관련 뉴스이미지 소스를 *기존과 중복 없이*
더 제안 → og:image 추출(thumb_gen 재사용·R2 재호스팅) → cards/<stem>/thumbs/search.json **앞쪽**에 append.

+ 원문 URL 백필(운영자 260726 "봇차단 당해도 url까진 받을 수 있다 — 공유에 링크"): frontmatter url:"" 인
기사(전문 붙여넣기·차단매체)면 같은 Claude 콜에 매체·기자·제목 단서로 원문 URL 찾기 임무를 얹어
queue/<stem>.md url 을 채운다 → 뷰어 요약 헤더 원문(#src)·공유가 활성(재빌드 후).

CSE(키워드 이미지 API) 死의 대체 — 위키미디어(백과사전형)보다 관련도 높은 뉴스소스 직접 검색.
입력: env MOREIMG_STEM(=기사 file 베이스, queue/<stem>.md & cards/<stem>) · MOREIMG_WANT(기본 5).
산출물은 검색이미지(og:image fetch=과금0) + Claude WebSearch 1콜(구독 쿼터). 카드 제미나이 0 불변(無관여)."""
import os, sys, re, json, subprocess, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # __main__ 가드 있음 = import 안전(파이프라인 실행 X). fetch_article_images·http_image·r2_upload·parse_md·_norm_key·R2_ON 재사용.
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared")))
from claude_py import run_claude   # 폴오버 SSOT(쿼터 한도 시 백업계정 4체인 자동 전환 · breaking_judge·gate_judge 공용 · 운영자 260718 "전사 적용")

STEM = os.environ.get("MOREIMG_STEM", "").strip()
WANT = max(1, min(10, int(os.environ.get("MOREIMG_WANT", "5") or "5")))
MODEL = os.environ.get("PIPE_MODEL", "claude-opus-5")   # 모델 단일 원천 정합(shared/model_env.sh와 동일 키 · 260702 SYS-08 완결)


def die(msg, code=1):
    print("::error::" + msg, flush=True); sys.exit(code)


if not STEM or not re.match(r'^[A-Za-z0-9._-]+$', STEM) or '..' in STEM:
    die("MOREIMG_STEM 누락/부적격: {!r}".format(STEM))

mdpath = os.path.join("queue", STEM + ".md")
if not os.path.exists(mdpath):
    die("기사 md 없음: " + mdpath)
md = open(mdpath, encoding="utf-8").read()   # 본문(요약·시사점) 발췌용
head, lead, iq, thumb_scene, art_url, alt_urls, image_sources, dispatch, _extras = tg.parse_md(mdpath)   # parse_md = 경로 인자(파일을 자기가 open) — 내용 문자열 넘기면 OSError(평의회 검증) · extras(hook·emotion·foreign)는 썸네일 프롬프트 전용이라 여기선 미사용(260703)
if not head:
    die("헤드라인 파싱 실패: " + STEM)


def _fm(txt, key):
    """frontmatter 따옴표 값 1필드 — 없으면 ''(원문 URL 찾기 단서용 · fail-soft)."""
    m = re.search(r'^{}:\s*"(.*?)"\s*$'.format(key), txt, re.M)
    return (m.group(1) if m else "").strip()


need_url = not art_url   # 원문 url 부재(전문 붙여넣기·차단매체) = 이 런이 URL 백필 임무 겸무(운영자 260726)
fm_media, fm_reporter, fm_title = _fm(md, "media"), _fm(md, "reporter"), _fm(md, "title")

tdir = os.path.join("cards", STEM, "thumbs")
os.makedirs(tdir, exist_ok=True)
sjson = os.path.join(tdir, "search.json")
existing = []
if os.path.exists(sjson):
    try:
        existing = json.load(open(sjson, encoding="utf-8")) or []
    except Exception:
        existing = []
existing_urls = set(tg._norm_key(x.get("url", "")) for x in existing if x.get("url"))
existing_links = set((x.get("link") or "").rstrip("/") for x in existing if x.get("link"))
# Claude·fetch가 다시 안 고르게 제외할 소스 = 기존 search.json link + 기사url + 이미 쓴 image_sources/alt.
exclude_srcs = set(existing_links) | set(
    (u or "").rstrip("/") for u in (list(image_sources or []) + list(alt_urls or []) + ([art_url] if art_url else [])) if u)

# 본문(요약·시사점) 발췌 — frontmatter 뒤, 코드블록 제거, 길이 절제.
body = md.split('---', 2)[-1] if md.count('---') >= 2 else md
body = re.sub(r'```.*?```', '', body, flags=re.S).strip()[:3500]

prompt = """다음은 한 뉴스기사의 큐레이션 요약·시사점이다. 이 기사의 **카드뉴스 썸네일 배경 이미지**로 쓸 관련 사진을 더 찾아라.

[기준 — 매우 중요]
- 이 이미지들은 **텍스트 오버레이 *뒤* 배경**에 깔리는 **후킹용 카드뉴스 배경**이다(전경 자막을 안 가리게 시선이 머무는 강한 장면).
- 요약과 **시사점**을 읽고, 이 기사를 **가장 효과적으로 대표**하는 사진을 고른다(사건의 결정적 순간·핵심 인물/장소·감정·맥락).
- **기존 이미지와 중복 없이 고유하게** — 아래 '이미 쓴 소스'는 제외(같은 사진/같은 기사 금지).
- 출력 = 그 사진이 실린 **뉴스기사 원문 URL**(WebSearch/WebFetch로 실제 접근·확인한 것만). 그 기사 og:image(대표사진)를 배경으로 쓴다. 스니펫 추측 URL 금지.
- 선정·시신·실존인물 닮기 위험 사진은 피한다(안전).

[기사 제목] {head}
[요약·시사점]
{body}

[이미 쓴 소스(제외 — 같은 기사/사진 다시 고르지 말 것)]
{excl}
{urltask}
[출력 형식 — 엄수]
실제 확인한 관련 뉴스기사 URL을 **{want}개 내외**, **한 줄에 하나씩만** 출력하라. 설명·번호·마크다운·따옴표 없이 URL만. 적절한 게 없으면 빈 출력.{urlfmt}""".format(
    head=head, body=body, excl=("\n".join(sorted(exclude_srcs)[:30]) or "(없음)"), want=WANT,
    urltask=("" if not need_url else """
[추가 임무 — 이 기사의 원문 URL 찾기(지금 원문 링크가 비어 있다)]
- 단서: 매체="{m}" · 기자="{r}" · 제목="{t}". WebSearch(매체+기자명+제목 핵심어 조합)로 **그 매체 공식 사이트의 바로 그 기사** URL을 찾아라.
- 봇차단 매체라 WebFetch가 403이어도 **검색 결과에 실제로 나온 URL이면 충분**(내용 접근 불필요). 검색 결과에 없는 URL 지어내기 금지(사실 무결성).
- 원 매체에서 못 찾으면 포털(네이버/다음) 재게재본 URL 허용(원 매체 우선). 그래도 없으면 '없음'.
""".format(m=fm_media or "미상", r=fm_reporter or "미상", t=fm_title or head)),
    urlfmt=("" if not need_url else " 단, **출력 맨 첫 줄**은 원문 URL 임무의 결과로 `ORIG_URL: <URL>` 한 줄(못 찾았으면 `ORIG_URL: 없음`) — 이미지 소스 URL들은 그 다음 줄부터."))

print("Claude({}) 관련 뉴스이미지 소스 검색 — '{}'".format(MODEL, head[:40]), flush=True)
_args = ["claude", "-p", "--model", MODEL, "--effort", "high",   # --bare 제거(OAuth 즉사 방지 · 260718) — 계정 로테이션은 폴오버 SSOT가 담당
         "--allowedTools", "WebFetch,WebSearch",
         "--disallowedTools", "Write,Edit,NotebookEdit,Bash,Task",
         "--max-turns", "40"]
# 폴오버 SSOT 경유 — 주계정 쿼터(주간한도) 시 백업 4계정 자동 전환(운영자 260718 "전사 적용" · 예외도 내부 처리 = fail-soft)
res, rc, err = run_claude(_args, prompt, timeout=900, source="moreimg")
out = (res.stdout if res else "") or ""
if rc != 0:
    print("::warning::claude rc={} · stderr(head): {}".format(rc, (err or "")[:300]), flush=True)

urls = []
orig_url = ""
for line in out.splitlines():
    s = line.strip()
    mo = re.match(r'^`?ORIG_URL`?\s*[:=]\s*(.+)$', s, re.I)   # 원문 URL 임무 응답 줄 = 이미지 소스와 분리 수거
    if mo:
        cu = mo.group(1).strip().strip('`"\' ').rstrip('.,);]')
        if cu.startswith("http") and '"' not in cu and tg._url_ok(cu):   # _url_ok = SSRF·스킴 게이트 재사용
            orig_url = cu
        continue
    m = re.search(r'https?://[^\s<>"\')]+', s)
    if not m:
        continue
    u = m.group(0).rstrip('.,);]')
    if u.rstrip("/") in exclude_srcs or u in urls:
        continue
    urls.append(u)
urls = urls[:WANT + 3]   # 여유분(fetch 실패·중복 대비)
print("Claude 제안 신규 소스 {}개".format(len(urls)), flush=True)

# 원문 URL 백필(운영자 260726) — frontmatter `url: ""` 를 찾은 URL로 교체. 이미지 0장이어도 이건 저장하고 나가야
# 해서 아래 '새 소스 0' 종료보다 먼저. 커밋은 moreimg.yml 이 queue/ 도 add(치환 실패 = 경고만·fail-soft).
if need_url and orig_url:
    md2 = re.sub(r'^url:\s*""\s*$', lambda _m: 'url: "{}"'.format(orig_url), md, count=1, flags=re.M)
    if md2 != md:
        open(mdpath, "w", encoding="utf-8").write(md2)
        print("🔗 원문 URL 백필 → {} ({})".format(mdpath, orig_url), flush=True)
    else:
        print("::warning::원문 URL 찾았으나 frontmatter url:\"\" 라인 없음(백필 스킵): " + orig_url, flush=True)
elif need_url:
    print("· 원문 URL 미발견(ORIG_URL 없음) — url 백필 스킵", flush=True)

if not urls:
    print("새 소스 0 — 이미지 변경 없음 종료"); sys.exit(0)

# og:image 추출(thumb_gen 재사용) — 원기사 URL(방금 백필분 포함)이 있으면 그 대표 og:image도 1순위로 시도
# (차단매체면 fetch만 실패 = 무해), 없으면 종전대로 image_sources만(과금 0).
cand = tg.fetch_article_images(orig_url or None, alt_urls=None, image_sources=urls, want=WANT)
new_items = []
for i, c in enumerate(cand):
    if tg._norm_key(c.get("src", "")) in existing_urls:
        continue
    if (c.get("link") or "").rstrip("/") in existing_links:
        continue
    final = None
    if tg.R2_ON:
        b, ctype, ext = tg.http_image(c["src"])
        if b and tg._is_logo_card(b):   # 매체 로고/브랜딩 카드(솔리드+텍스트) = 픽셀 직접 검사 컷(운영자 260622)
            print("  ⏭ 매체 로고/브랜딩 컷 ({}…)".format((c.get("link") or c["src"])[:42])); continue
        if b:
            h = hashlib.sha1((c["src"] or "").encode("utf-8")).hexdigest()[:10]   # src 해시 = 키 고유(런 반복·같은 len 덮어쓰기 방지·평의회 검증). 같은 이미지=같은 키=동일내용 덮어씀(무해)
            final = tg.r2_upload(b, "thumbs/{}/more-{}.{}".format(STEM, h, ext), ctype)
    url = final or c["src"]
    new_items.append({"url": url, "link": c.get("link", ""), "label": "유사"})   # 신규 = '유사'(원본 대표 라벨 보존)
    existing_urls.add(tg._norm_key(url))

if not new_items:
    print("새 이미지 0(중복·차단·사진無) — 변경 없음"); sys.exit(0)

merged = new_items + existing   # 앞쪽(좌측) prepend = 뷰어 카러셀 맨 앞에 신규 노출
json.dump(merged, open(sjson, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("✅ +{}장 → {} 총 {}장".format(len(new_items), sjson, len(merged)), flush=True)
