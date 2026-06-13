# knews_scraper — 한국 주요 뉴스 RSS 수집 모듈

뉴스 파이프라인의 **① 수집 단계**. 검증된 언론사 공개 RSS만 긁어, 여러 매체에 교차
등장하는 '주요 기사'를 골라 URL을 뽑는다. 봇 탐지를 우회하지 않는다 — 공개 RSS만 쓰니
차단 위험 0. (인계 원문: 작성자 핸드오프 문서.)

```
[① 수집: 이 모듈] → top_urls.txt → [② Termux가 pending/ 에 push] → [③ Actions 분석] → queue/ → 뷰어
                                    └ 이 모듈의 범위는 ①까지. ②~⑤ 연결은 별도 작업.
```

## 실행
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 knews_scraper.py --out ./out          # 기본: 주요 섹션(politics/economy/society/international), 최근 24h
python3 knews_scraper.py --categories all --hours 12 --min-cross 2 --top 30
```
출력 2종 → `out/`:
- `articles.json` — 수집 전체 + 교차등장(주요도) 점수, 주요도순 정렬
- `top_urls.txt` — 주요도 상위 클러스터 대표 기사의 원문 URL (② 연결용)

## 실측 (2026-06-13, 첫 실가동)
- **61/82 피드 생존 · 595건 수집** — 기본 동작·유의미한 수집 확인됨.
- 매체 분포는 뉴시스(통신사)가 과반 — 교차/상위 선정이 뉴시스로 쏠림(조건 단계에서 보정 대상).

## ⚠️ 알고 가야 할 것 (실측으로 드러난 것)

### 1. 죽은 피드 정리는 *배포처에서* 해라 — 이 레포 클라우드 환경 기준 금지
이 환경 egress 정책이 **동아일보·조선일보·한겨레**(15개 피드)를 차단한다("Blocked by
egress policy"). 즉 여기서 "죽음"으로 잡혀도 **폰/GitHub Actions(열린 egress)에선 정상**일
가능성이 높다. 실제로 죽은 후보(이 환경 무관)는 좁다:
- 국민일보(`rss.kmib.co.kr`): 연결불가 — 배포처서 재확인
- 시사인 정치(`S1N6`): 진짜 403 (다른 시사인 섹션은 살아있음) → 솎기 후보
- 매일노동뉴스: 200이나 빈/깨진 피드 → 확인
→ **feeds.csv 정리는 Actions 러너에서 1회 돌려 그 로그로 판단할 것.**

### 2. top_urls.txt → pending 은 1:1로 안 떨어진다 (fan-out 필요)
- pending 입력 = **파일 1개당 URL 1개** (`.github/scripts/analyze.sh`가 `head -n1`만 읽음).
- 이 모듈 출력 `top_urls.txt` = **한 파일에 URL 여러 줄**.
- ② 연결을 짤 때 `top_urls.txt`를 **줄마다 별도 `pending/*.txt` 파일로 펼쳐야** 한다.
  그냥 복사하면 첫 줄 1개만 분석되고 나머지는 버려진다.

### 3. 프레시안 RSS 엔티티 깨짐 보정 적용됨
프레시안 RSS는 엔티티의 `&`를 흘려 `ldquo;`처럼 깨진 이름만 내보낸다. 그대로 두면 제목이
깨질 뿐 아니라 `ldquo`·`hellip` 등이 가짜 공통 토큰이 돼 무관 기사들이 거짓 교차클러스터로
묶인다. → `strip_tags()`가 `&`를 복원해 unescape 한다(다른 매체의 정상 제목은 불변).

## 다음 (조건 단계 — 미착수)
기본 수집·저장이 확인되면 그 위에 조건(시간창·매체 가중·뉴시스 쏠림 보정·교차 임계 튜닝·
연합뉴스 추가 등)을 얹는다. 클러스터링 임계(`MIN_TOKEN_OVERLAP`/`JACCARD_BACKUP`)도 실데이터
보고 조정.
