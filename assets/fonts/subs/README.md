# 자막 폰트 정본(assets/fonts/subs) — 깃에 넣으면 번인·미리보기 양쪽에서 쓰는 자리

- **여기가 정본.** `build-viewer.mjs`가 `assets/fonts` 전체를 `viewer/assets/fonts`로 복사해 Pages가 서빙(pretendard 동축)하고, 러너(`ly_burn.py register_repo_fonts`)가 체크아웃의 이 폴더를 fontconfig에 등록해 번인에 쓴다.
- 현재 동봉: `Paperlogy-5Medium.ttf`(페이퍼로지 5 Medium · 운영자 260805 업로드 — 원본 zip·라이선스 = `자료/폰트/Paperlogy-1.001.zip`).
- 운영자가 최상위에 폰트를 떨궈도 번인은 산다(러너가 루트 직하 ttf/otf 관용 수용) — 단 **미리보기는 이 폴더만** 서빙되므로 정리 시 여기로 옮긴다.

## 새 폰트를 선택자로 올리는 절차(4곳 각 1줄)
1. 폰트 파일을 이 폴더에 커밋(패밀리명 = `fc-scan <파일> | grep family` **실측** — 추측 금지).
2. `.github/scripts/ly_burn.py` — `FONT_FAMILY`에 `"키": "실측 패밀리명"` + `REPO_FONT_KEYS`에 키.
3. `functions/api/edit.js`·`functions/api/ly.js` — font 화이트리스트 배열에 키.
4. `viewer/edit.html` — `FONT_PV`에 `{lbl,fam,ff,lf,lw}` 1줄 + '글자 형태' 배열에 키 / `viewer/ly.html` — 폰트 행 버튼 1줄.
