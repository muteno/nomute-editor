# 42일 만의 발사, 그런데 이름이 없다

**[프롬프트 설계]**
- 화풍: B 극화 — 군사·안보 사안의 무게와 상황실의 긴장을 한국 웹툰 극화의 강한 명암으로 잡되, 자극이 아니라 사실의 건조함으로 누른다
- 분위기: 확인된 것이 한 문장뿐인 저녁의 정보 공백 — 위협의 크기가 아니라 '모른다'는 상태에서 오는 서늘한 불안, 차가운 청색 계열의 저조도
- 연출 방향: 뉴스를 안 보는 독자가 멈추는 지점은 미사일의 위력이 아니라 「쐈는데 뭘 쐈는지 아무도 모른다」는 빈칸이다. 그래서 이 덱은 폭발을 그리지 않고 **비어 있는 것**을 그린다 — 이름표 없는 궤적선 하나, 절반이 빈 보고 양식, 답을 기다리며 멈춘 손. 정보가 채워지는 순서(공백 → 42일이라는 숫자 → 그 숫자마저 절반은 틀렸다는 사실)를 시선의 이동으로 옮기고, 마지막에만 인물이 정면을 마주 봐 독자에게 판단을 넘긴다. thumb_dispatch의 차가운 스크린 언더글로 톤과 초점 잃은 응시의 정조를 키노트로 계승(앵글은 카드마다 분산)
- 독자 동선: **발단** 카드1→**전개** 카드2→**피크** 카드3→**해소** 카드4→**시사점** 카드5 · 훅=카드1 끝(단서형: 합참이 낸 문장이 그게 전부였다)+카드2 끝(예고형: 종류가 정해져야 숫자가 붙는다 → 카드3 첫 줄이 42일로 즉시 회수) · 착지 한 줄 요지 = 이 사건의 크기는 오늘의 첫 문장이 아니라 뒤이어 붙을 두 번째 문장이 정한다
- 연속성 앵커: Recurring subject - a Korean man in his 40s with close-cropped hair and thick straight brows, wearing a plain dark olive military jacket with no insignia (카드1·2·5) / Recurring location - a dim military operations room with one large wall display and rows of low desks (카드1·5)

### [카드 1]
**텍스트**
```text
8월 6일 오후 5시를 갓 넘겨
속보 한 줄이 동시에 걸렸다
*북한이 동해상으로 발사체를 쐈다*
합참이 낸 문장은 그게 다였다
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the commander's eyes locked on one unlabeled arc climbing across the big wall display. Recurring subject - a Korean man in his 40s with close-cropped hair and thick straight brows, wearing a plain dark olive military jacket with no insignia, stands at the center of the room and looks up toward the right side of the screen. Recurring location - a dim military operations room with one large wall display and rows of low desks. Four staff officers seated at the desks hold phone handsets and turn their heads the same way, toward the display. The display is the only bright thing in the room.
Camera: wide shot from eye-level, shot on 35mm lens, natural documentary perspective, nose room on the right, gaze directed toward the right edge
Lighting/mood: flat cold even surveillance light, no shadow no warmth, detached and watchful
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02) on the single arc line of the display, film-noir low-key lighting, deep shadows
Text handling: no writing on the display, no labels, no numbers, only a plain glowing curve and dots.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the operations room wall) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
합동참모본부 지휘통제실
```

### [카드 2]
**텍스트**
```text
제원도 사거리도 분석 중이라 했다
'미상'은 종류를 모른다는 뜻이다
무엇을 몇 발 쐈는지도 비어 있었다
*종류가 정해져야 숫자 하나가 붙는다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: a pen held motionless between two fingers, its tip stopped just above an empty field on the form. The same officer's hand, sleeve of a plain dark olive military jacket, rests on a reporting form whose lower half is entirely blank. A second hand grips a phone handset at the edge of the desk. The paper is cropped by the frame so that no line of writing is complete or readable, and a folded map lies half under it.
Camera: extreme close-up from high angle, shot on 100mm macro lens, fine detail, shallow depth of field
Lighting/mood: harsh single overhead light pooling on the table, deep surrounding black, oppressive interrogation
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02) on a small printed check box left unmarked on the form, film-noir low-key lighting, deep shadows
Text handling: the paper is cropped and angled so its writing is cut off and illegible; no readable words anywhere.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the desk top) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
군 상황보고서 서류 책상
```

### [카드 3]
**텍스트**
```text
탄도미사일로 확인되면 42일 만이다
기준점은 지난 *6월 25일*이다
김정은 위원장이 지켜본 자리에서
남측을 사정권에 둔 전술무기를 쐈다
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: a vacant thousand-yard stare in the eyes of a uniformed officer, unfocused and looking past everything, as a launch flash floods him from behind. He is a generic North Korean military officer in his 50s in a peaked cap, filling most of the frame, jaw set and unmoving. Behind him and much smaller, a few observers in dark coats stand in a row on the open launch ground, all facing the same distant flash. No face resembles any real public figure.
Camera: tight close-up from a Dutch angle, canted frame, shot on 85mm portrait lens, unstable mood
Lighting/mood: single hard side-light cutting across the subject, deep chiaroscuro shadows, tense atmosphere
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02) reflected as a thin rim on the cap brim and collar, film-noir low-key lighting, deep shadows
Text handling: no insignia lettering, no banners, no signage anywhere in the frame.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the night sky over the launch ground) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
북한 전술탄도미사일 발사 참관
```

### [카드 4]
**텍스트**
```text
다만 그 42일이 공백은 아니었다
7월 3일 북한은 구축함 강건호에서
전략순항미사일을 시험 발사했다
*비어 있던 건 탄도 축 하나였다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the tilted heads of two sailors on the deck, both tracking a single thin exhaust trail rising off the bow. A large grey warship cuts across open sea, seen from above and behind, its foredeck launch cells open. Six crew members stand small along the rail, none facing the camera, all looking up along the same line. Flat grey water fills the rest of the frame.
Camera: wide shot from high angle, shot on 24mm wide lens, cinematic wide shot, spatial context
Lighting/mood: overcast diffused daylight, flat soft shadows, muted somber mood
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02) on the thin exhaust trail above the deck, muted daylight contrast
Text handling: no hull numbers, no ship name, no flags, no lettering anywhere.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the open sea) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
북한 구축함 강건호 순항미사일
```

### [카드 5]
**텍스트**
```text
그래서 남은 건 쐈다는 사실 하나다
종류에 이름이 붙어야 42일도
비행거리도 비로소 뜻을 얻는다
*사건의 크기는 두 번째 문장이 정한다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the officer's steady, unblinking eye contact looking straight into the camera. Recurring subject - a Korean man in his 40s with close-cropped hair and thick straight brows, wearing a plain dark olive military jacket with no insignia, stands still and faces forward, arms at his sides. Recurring location - a dim military operations room with one large wall display and rows of low desks. Most desks are dark and empty now; a single desk lamp burns behind him and the wall display still carries the same single unlabeled arc.
Camera: medium shot from eye-level, front-on shot, direct gaze, symmetrical composition, shot on 50mm standard lens
Lighting/mood: warm soft desk-lamp light, quiet wistful tone
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02) on the unlabeled arc still glowing behind him, film-noir low-key lighting, deep shadows
Text handling: no writing on the display, no name plates, no signage, no readable characters anywhere.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the operations room wall) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
합참 상황판 동해 궤적
```
