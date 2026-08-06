# 고장 난 굴착기 고치던 옆, 다른 굴착기가 덮쳤다

**[프롬프트 설계]**
- 화풍: B 극화 — 중장비가 오가는 채석장의 무게와 작업 구조를 사실적으로 고발해야 하는 산업재해 사건이라 극화 1스타일 고정
- 분위기: 한여름 정오의 마른 먼지와 쇳덩이의 질량감, 소리가 지워진 듯한 정적 — 비명이 아니라 침묵으로 무게를 싣는다
- 연출 방향: 뉴스를 안 보는 독자도 "중장비 옆을 걸어본 적 있는 사람"이면 즉시 멈추는 지점은 *고치러 간 자리가 곧 사고 자리였다*는 낙차다(독자훅=허탈). 그래서 이 덱은 사람과 쇳덩이의 **거리**를 계속 재는 방식으로 간다 — 멈춘 장비 옆에 붙은 사람, 그 사람을 못 보는 운전석의 시야, 그를 스치는 버킷의 그림자. 전하려는 것(💡시사점)은 "정비는 계획표 밖에서 벌어지고 그 순간 현장의 규칙이 잠시 비워진다"는 구조이므로, 인물을 크게 그리기보다 **인물과 장비가 같은 바닥을 쓰는 프레임**을 반복해 위험이 사람의 부주의가 아니라 배치에서 왔음을 보이게 한다. 상속 키노트 = 정오 직사광의 억압적 노출(LGT07)과 부재의 정조(SG-09), 악센트는 안전조끼의 형광 한 점.
- 독자 동선: **제시** 카드1(5W 착지+단서 훅)→**발단** 카드2(고장→고치러 간 자리)→**전개** 카드3(멈춘 장비 옆 사람·운전석 사각·같은 반경으로 들어온 또 한 대)→**피크** 카드4(버킷이 지나간 자리 · 3줄·최저 명도·최타이트)→**해소** 카드5(경찰 조사·통제와 신호수 미확인)→**시사점** 카드6 · 훅=카드1 끝(단서형: 그를 덮친 건 그 장비가 아니었다 → 카드2 첫 줄 즉시 회수)+카드3 끝(예고형: 같은 반경으로 또 한 대) · 착지 한 줄 요지 = 고장은 일과인데 그 사이 사람은 쇳덩이 옆에 선다
- 연속성 앵커: Recurring subject — an Asian man in his 40s, short cropped black hair, a dust-stained gray work shirt over a scuffed high-visibility vest, a worn hard hat. / Recurring location — an open-pit quarry with a terraced rock cut face and gravel ground.

### [카드 1]
**텍스트**
```text
지난 8월 5일 오후 1시 11분
제주 서귀포 표선면의 한 채석장에서
40대 노동자가 굴착기에 부딪혀 숨졌다
*그가 고치던 굴착기가 아니었다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the small back of a lone worker walking toward a stalled machine, seen from behind so his face is never shown. Recurring subject — an Asian man in his 40s, short cropped black hair, a dust-stained gray work shirt over a scuffed high-visibility vest, a worn hard hat — carries a toolbox in his right hand as he crosses the open gravel. Recurring location — an open-pit quarry with a terraced rock cut face and gravel ground, two excavators standing far apart on the same flat ground, one of them silent with its bucket lowered. His gaze and his walking direction both lead toward the right edge of the frame, and dust hangs in the hot still air.
Camera: wide shot from eye-level, shot on 35mm lens
Lighting/mood: harsh overexposed midday sunlight, hard shadows, oppressive heat
Accent: monochrome desaturated base with a single color accent (the high-visibility yellow-green #0FFD02 of the worker's vest), muted daylight contrast
Korean default: a Korean quarry work site, Korean-style machinery and site markers with no legible letters, nose room on the right, gaze directed toward the right edge.
Text handling: keep all incidental writing out of frame by composition; no signage text, no machine decals, no logos, no numbers rendered.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the quarry gravel ground) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
서귀포 표선 채석장
```

### [카드 2]
**텍스트**
```text
*그를 친 건 지나가던 다른 굴착기였다*
숨진 사람은 중국 국적 40대 A씨다
고장 난 장비를 고치러 간 자리였다
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: his grease-marked fingertips resting on a cold hydraulic arm, the hand of someone in the middle of a job. Recurring subject — an Asian man in his 40s, short cropped black hair, a dust-stained gray work shirt over a scuffed high-visibility vest, a worn hard hat — crouches beside the stalled excavator's lowered bucket, one knee on the gravel, eyes down on the machine joint he is inspecting. An open toolbox sits by his boot. Far behind him and out of his line of sight, the blurred shape of a second excavator is already in motion across the same flat ground.
Camera: medium close-up from eye-level, shot on 85mm portrait lens
Lighting/mood: overcast diffused daylight, flat soft shadows, muted somber mood
Accent: monochrome desaturated base with a single color accent (the high-visibility yellow-green #0FFD02 of the worker's vest), muted daylight contrast
Korean default: a Korean quarry work site, Korean-style machinery with no legible letters or decals.
Text handling: keep all incidental writing out of frame by composition; no signage text, no machine decals, no logos, no numbers rendered.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the quarry gravel ground) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
굴착기 정비 작업자
```

### [카드 3]
**텍스트**
```text
장비가 서면 사람이 그 옆에 붙는다
그동안 나머지 장비는 그대로 움직인다
*버킷은 운전석에서 앞아래가 안 보인다*
같은 반경으로 또 한 대가 들어왔다
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the blind wedge of ground swallowed by the raised bucket, where a pair of work boots is only half visible. The view is from inside an excavator cab looking forward, the operator's gloved hands on the levers in the near foreground, the massive bucket arm filling the upper center and cutting off everything below it. Recurring location — an open-pit quarry with a terraced rock cut face and gravel ground stretches ahead. Beyond the bucket, the stalled second machine sits with a small crouching figure beside it, hidden from this seat except for his boots and the edge of a high-visibility vest. The forward travel direction points toward the right edge of the frame.
Camera: medium shot from the operator's POV, shot on 24mm wide lens
Lighting/mood: single hard side-light cutting across the subject, deep chiaroscuro shadows, tense atmosphere
Accent: monochrome desaturated base with a single color accent (the high-visibility yellow-green #0FFD02 glimpsed at the edge of the blind zone), muted daylight contrast
Korean default: a Korean quarry work site, Korean-style machinery with no legible letters, gauges and dials shown as shapes only, nose room on the right.
Text handling: keep all incidental writing out of frame by composition; no gauge numbers, no warning labels, no decals, no signage text rendered.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the quarry gravel ground seen through the cab opening) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
굴착기 운전석 시야
```

### [카드 4]
**텍스트**
```text
*멈춰 선 장비 옆, 사람이 서 있었다*
그 옆을 다른 버킷이 지나갔다
40대 노동자는 그 자리에서 숨졌다
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the hard shadow of a passing bucket sliding across his turned cheek, his eyes still down on the machine, unaware. Recurring subject — an Asian man in his 40s, short cropped black hair, a dust-stained gray work shirt over a scuffed high-visibility vest, a worn hard hat — stands close beside the stalled excavator with a wrench in one hand, half his face already inside the advancing shadow. Nothing touches him in this frame; only the darkness of the moving arm has arrived. Recurring location — an open-pit quarry with a terraced rock cut face and gravel ground surrounds them in deep shade.
Camera: tight close-up from eye-level, shot on 85mm portrait lens
Lighting/mood: single pool of hard light isolating the figure in surrounding blackness, claustrophobic loneliness
Accent: monochrome desaturated base with a single color accent (the high-visibility yellow-green #0FFD02 of the worker's vest), film-noir low-key lighting, deep shadows
Korean default: a Korean quarry work site, Korean-style machinery with no legible letters or decals.
Text handling: keep all incidental writing out of frame by composition; no signage text, no machine decals, no logos, no numbers rendered.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the shaded quarry rock face behind him) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no impact moment, no collision shown, no injury, no blood, no body on the ground, no contact between the machine and the person
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
굴착기 버킷 근접
```

### [카드 5]
**텍스트**
```text
경찰은 채석장 관계자 등을 상대로
사고 원인을 조사하고 있다
작업 구역 통제와 신호수 배치 여부는
*아직 확인되지 않았다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the flat unreadable faces of two investigators as they measure the empty distance between the two machines. Three figures stand on the open ground — two plainclothes investigators in dark shirts taking notes and pointing along the gravel, and one site manager in a hard hat standing slightly apart with his arms at his sides, head lowered. Recurring location — an open-pit quarry with a terraced rock cut face and gravel ground; the stalled excavator and the second excavator sit at either side, roped off with plain tape. No worker is present between them now.
Camera: wide shot from a high angle, shot on 50mm standard lens
Lighting/mood: flat cold even surveillance light, no shadow no warmth, detached and watchful
Accent: monochrome desaturated base with a single color accent (a single strip of high-visibility yellow-green #0FFD02 tape across the gravel), muted daylight contrast
Korean default: a Korean quarry work site, Korean police investigators in plain clothes, Korean-style machinery and tape with no legible letters.
Text handling: keep all incidental writing out of frame by composition; the tape and notebooks carry no readable characters; no signage text, no logos, no numbers rendered.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the quarry gravel ground) extending edge to edge from top to bottom of the frame. The main subjects are anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
산업재해 현장 경찰 조사
```

### [카드 6]
**텍스트**
```text
채석장에서 장비 고장은 일과다
한 대가 서면 사람이 그 옆으로 간다
그동안 나머지 장비는 그대로 움직인다
*그 사이 사람은 쇳덩이 옆에 선다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the narrow strip of empty gravel between two machines, where a toolbox and a hard hat still sit with no one beside them. Recurring location — an open-pit quarry with a terraced rock cut face and gravel ground, seen at the end of the day; one excavator stands silent with its bucket lowered to the ground, and a second excavator waits further off with fresh track marks running past the first. The centre of the frame belongs to the vacant ground between them, and the composition is still and symmetrical rather than directional.
Camera: extreme long shot from eye-level, shot on 20mm wide lens
Lighting/mood: cold blue pre-dawn tone, lone light reflection on the packed ground, desolate stillness
Accent: monochrome desaturated base with a single color accent (the abandoned high-visibility yellow-green #0FFD02 vest folded on the toolbox), film-noir low-key lighting, deep shadows
Korean default: a Korean quarry work site, Korean-style machinery with no legible letters or decals.
Text handling: keep all incidental writing out of frame by composition; no signage text, no machine decals, no logos, no numbers rendered.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the quarry gravel ground) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE - strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
채석장 굴착기 절개면
```
