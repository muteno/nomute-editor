# LOVE ♥ — 펫 마퀴 리빌 (pet marquee reveal)

Claude "Fable 5 is back" 픽셀 프로모 영상을 **키워드만 `LOVE ♥`로 바꿔** 재현한 자립형
애니메이션. "NOW SHOWING" 마퀴·사다리 이젤·하프톤 점묘 배경·점등 글로우를 그대로 살렸다.
**펫 캐릭터는 원본 영상에서 스프라이트를 직접 오려내(색키+실루엣 추출) 3프레임 걷기
사이클로 심음** — 재해석 0, 100% 원본 크리터(옆모습·눈1·주둥이·다리4).

## 파일
| 파일 | 설명 |
|---|---|
| `love-pet.html` | **마스터**. 자립형 HTML5 canvas 애니메이션(외부 의존 0). 브라우저로 열면 루프 재생 + ↻REPLAY. |
| `love-pet.mp4` | 렌더 결과(1080×1080·24fps·13s·원본 오디오 유지). |
| `love-pet_silent.mp4` | 무음 버전(직접 음악 얹을 때). |

## 시퀀스 (13초)
펫 등장(좌하) → 사다리 이젤 등반 → 마퀴 위를 걸으며 `L·O·V·E·♥` 한 글자씩 새김 →
간판 크림색 점등 + "NOW SHOWING" 앰버 + 워밍 글로우 → 펫이 앞으로 또각또각 나와 퇴장 → 루프.

## 다시 렌더하려면
`love-pet.html`이 결정론적 `renderAt(t)`(t=초)를 노출한다. 헤드리스 캡처:
```bash
# love-pet.html?cap=1 로 열고 프레임마다 renderAt(t)+canvas.toDataURL 캡처 → ffmpeg
python3 capture.py love-pet.html frames_out          # 24fps × 13s = 312 프레임
ffmpeg -framerate 24 -i frames_out/f%04d.png -c:v libx264 -crf 18 -pix_fmt yuv420p out.mp4
```
`?t=6.0` 은 6초 지점 단일 프레임 정지 렌더(스틸용).

## 커스터마이즈 (love-pet.html 상단)
- **키워드**: `KEY=['L','O','V','E','H']` (`H`=하트). 글자는 `FONT` 5×7 비트맵.
- **하트**: `drawHeart()` — 촘촘한 픽셀 + 코럴 base/핑크 하이라이트/흰 반짝임(원본 핑크 `#db5d61` 계열).
- **펫**: `PET_SRC` — 원본에서 오려낸 3프레임 PNG 데이터 URI(옆모습 크리터). `blitPet()`이 바닥정렬로 배치, `WALK` 배열이 걷기 사이클. (재추출 스크립트 = `extract_pet_png.py`)
- **색**: `P` 팔레트(배경/크림/코럴/앰버/펫 = 원본 실측값).
- **타임라인**: `T` 세그먼트(walkIn·climb·type·illum·trot·hold).
