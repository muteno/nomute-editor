#!/usr/bin/env python3
# FB 게시물 주제 LLM 분류(운영자 260724 채택) — FB 발행 헤드라인은 편집 재작성이라 뉴스 원본 제목·CAT_KW 매칭이 빈약(실측 기타 80%).
# → Claude Haiku로 헤드라인을 6주제(정치·사회·경제·국제·문화·테크)로 정확 분류 → 주제별 반응(topics) 승격. 인스타 cat_overrides 수기라벨의 자동 등가물.
# 비용 최소화 = ① 캐시(viewer/fb_cat_cache.json {제목:주제}) = 이미 분류한 글 재호출 0 → 하루 새 글 1~2개만 LLM ② Haiku(최저 티어) ③ 배치 1콜.
# fail-soft = LLM/파싱/쿼터 실패 시 fb_data.json topics 무변경(fb_fetch 키워드 폴백 유지) · rc 항상 0(수집 커밋 비차단).
# 입력 = viewer/fb_data.json d['topic_sample']([{nm,e}]) · 출력 = 같은 파일 d['topics'] 승격 + 캐시 갱신. LLM = claude CLI(chan_brief 계정 체인 env 공유).
import json, os, sys, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # .github/scripts → repo root
sys.path.insert(0, str(ROOT / 'shared'))
from claude_py import run_claude   # 쿼터 한도 시 4계정 자동 폴오버(SSOT · 자체 쿼터처리 금지 게이트 준수)  # noqa: E402

FB = 'viewer/fb_data.json'
CACHE = 'viewer/fb_cat_cache.json'
CATS = ['정치', '사회', '경제', '국제', '문화', '테크']   # 인스타 topics 6버킷 동일(기타 = 분류 실패/미해당 · 뷰어 표시 제외)
MODEL = os.environ.get('FB_CLS_MODEL', 'claude-haiku-4-5-20251001')   # 최저 티어 = 분류 충분·최저 쿼터


def jload(p, dflt):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return dflt


def classify(names):
    """미분류 제목 배치 → {제목: 주제}. LLM 1콜(Haiku) · 실패 = 빈 dict(폴백)."""
    if not names:
        return {}
    listing = '\n'.join(f'{i}. {n}' for i, n in enumerate(names))
    prompt = (
        '너는 한국 뉴스 헤드라인 주제 분류기다. 아래 헤드라인 각각을 다음 6개 중 하나로 분류하라: '
        '정치, 사회, 경제, 국제, 문화, 테크. (스포츠·연예는 문화 · 어디에도 안 맞으면 사회). '
        'JSON 배열로만 답하라(설명 금지): [{"i":0,"c":"사회"}, ...]\n\n헤드라인:\n' + listing
    )
    cmd = ['claude', '-p', '--model', MODEL, '--safe-mode', '--max-turns', '1']
    p, rc, err = run_claude(cmd, prompt, timeout=180, source='fbcls')   # 쿼터면 4계정 1단씩 폴오버(SSOT)
    if p is None:
        print(f'fb-classify: LLM 호출 실패(rc={rc}) — 폴백: {(err or "")[:160]}')
        return {}
    out = (p.stdout or '').strip()
    s, e = out.find('['), out.rfind(']')
    if s < 0 or e < 0:
        print(f'fb-classify: LLM 응답에 JSON 배열 없음 — 폴백. 원문[:200]={out[:200]}')
        return {}
    try:
        arr = json.loads(out[s:e + 1])
    except Exception as ex:
        print(f'fb-classify: JSON 파싱 실패 — 폴백: {ex}')
        return {}
    mp = {}
    for o in arr:
        i, c = o.get('i'), o.get('c')
        if isinstance(i, int) and 0 <= i < len(names) and c in CATS:
            mp[names[i]] = c
    print(f'fb-classify: LLM 분류 {len(mp)}/{len(names)}건 성공(model={MODEL})')
    return mp


def main():
    d = jload(FB, None)
    if not d or not d.get('topic_sample'):
        print('fb-classify: topic_sample 없음 — 스킵(수집 미성립 또는 리치필드 권한 없음)')
        return 0
    sample = d['topic_sample']
    cache = jload(CACHE, {})
    uncached = sorted({s['nm'] for s in sample if s.get('nm') and s['nm'] not in cache})
    if uncached:
        cache.update(classify(uncached))
        try:
            with open(CACHE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=1)
        except Exception as ex:
            print(f'fb-classify: 캐시 쓰기 실패(비치명) — {ex}')
    else:
        print('fb-classify: 신규 제목 0 = 전량 캐시 히트(LLM 0콜)')
    # 캐시 라벨로 주제별 반응 집계(기타/미분류 제외 · 유의미 주제 n≥5 2개↑일 때만 승격 = fb_fetch 게이트 동일)
    grp = {}
    for s in sample:
        c = cache.get(s.get('nm'))
        if c in CATS:
            grp.setdefault(c, []).append(s.get('e') or 0)
    strong = [c for c, v in grp.items() if len(v) >= 5]
    if len(strong) >= 2:
        d['topics'] = {c: {'n': len(v), 'views_med': round(statistics.median(v))} for c, v in grp.items()}
        d.pop('topic_sample', None)   # 승격 후 표본 제거(뷰어 파일 슬림)
        try:
            with open(FB, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            print(f"fb-classify: 주제별 반응 승격 → {len(grp)}주제 · 유의미 {len(strong)}개 = {', '.join(f'{c}:{len(v)}' for c, v in grp.items())}")
        except Exception as ex:
            print(f'fb-classify: fb_data 쓰기 실패(비치명) — {ex}')
    else:
        print(f"fb-classify: 유의미 주제 {len(strong)}개(<2) = 승격 보류(키워드 폴백 유지) · 분포 {', '.join(f'{c}:{len(v)}' for c, v in grp.items()) or '없음'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
