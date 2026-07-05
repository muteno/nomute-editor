# ⚠️ 전체복원 금지 — 부분 롤백 전용 스냅샷

이 `index.html.bak`은 **PR #1704(헤더 워드마크 News Curation·CI 로고 제거) 머지 이전 base**의 스냅샷이다(분신술 5인 실측 260706 — brandmark 0·brandlogo 잔존·CI preload 잔존).

- **이 파일로 viewer/index.html 전체복원 = 배포된 #1704 헤더가 조용히 회귀**(워드마크 소멸·CI 로고 부활). check_refs도 못 잡는다(회귀본도 유효 HTML).
- 앰비언트 웨이브 롤백이 목적이면 **`git revert 12f7490`(PR #1706)** 또는 해당 블록(CSS `.amb`·JS 앰비언트 엔진)만 이 백업에서 발췌 이식할 것.
