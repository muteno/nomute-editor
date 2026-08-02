# 5년간 5809명 붙잡았는데, 외사계는 1명이었다

**[프롬프트 설계]**
- 화풍: B 극화 — 범죄 재구성과 대응 인프라 공백 고발이 한 축이라 무게·사실성이 필요하다.
- 분위기: 사건이 지나간 뒤의 새벽 푸른 정적과 무력감. 소리치는 분노가 아니라 "신고해도 못 잡는다"는 체념이 깔린 톤(thumb_dispatch의 차가운 새벽광·부재·허탈한 응시를 조명 톤과 정조로만 상속).
- 연출 방향: 뉴스를 안 보는 독자도 멈추는 지점은 사건의 잔혹함이 아니라 '그 다음이 없다'는 감각이다 — 그래서 카메라는 가해 순간이 아니라 **사건이 지나간 자리**(떨어진 각목, 텅 빈 노상, 결과가 뜨지 않는 조회 화면, 불 켜진 책상 하나)와 그 자리를 보고 있는 사람의 눈에 붙는다. 명도는 낮의 평범한 거리에서 시작해 상인의 얼굴에서 가장 어두워지고, 마지막 새벽 사무실에서만 풀린다. 화면에서 가장 오래 남아야 할 것은 사람이 아니라 **비어 있는 자리**다.
- 독자 동선: **발단** 카드1→**전개** 카드2~4→**피크** 카드5→**해소** 카드6→**시사점** 카드7 · 훅=카드1 끝(예고형: 달라진 건 사건의 결)+카드4 끝(단서형: 각목 등장 → 카드5 첫 줄이 즉시 회수) · 착지 한 줄 요지=외사계 1명 체제가 그대로인 동안, 잡기 어렵다는 사실이 다음 사건의 문턱을 낮춘다.
- 연속성 앵커: Recurring subject A - a Korean man in his 60s, thinning grey hair, deep lines around the eyes, a faded dark work vest over a checked shirt (카드1·5) / Recurring subject B - a Korean man in his 50s, short greying hair, a plain navy windbreaker over a shirt, a lanyard at his chest (카드6·7) / Recurring location - a small provincial Korean police office with rows of steel desks (카드6·7).

### [카드 1]
**텍스트**
```text
충북에서 검거된 외국인은
해마다 1000명 선을 넘겼다
올해도 상반기에만 625명이 붙잡혔다
*그런데 달라진 건 사건의 결이었다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the shopkeeper's steady, weary eyes following the street from under his half-raised shutter. Recurring subject A - a Korean man in his 60s, thinning grey hair, deep lines around the eyes, a faded dark work vest over a checked shirt. He stands at the edge of his small storefront with one hand still resting on the shutter handle, looking toward the right side of the frame, where several workers in plain work clothes walk past a row of low shops. The whole scene is an ordinary provincial Korean commercial street on one continuous asphalt road, quiet and unremarkable in daylight, with nose room on the right and the gaze directed toward the right edge.
Camera: wide shot from eye-level, shot on 24mm wide lens
Lighting/mood: overcast diffused daylight, flat soft shadows, muted somber mood
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), muted daylight contrast
Korean setting: Korean provincial city streetscape, right-hand traffic, Korean shop awning and signboard shapes with no legible text.
Text handling: keep all signage lettering out of frame or cropped and out of focus, no readable characters anywhere.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the asphalt street) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
충북 외국인 밀집 상가거리
```

### [카드 2]
**텍스트**
```text
절도와 폭력에 머물던 사건이
*흉기를 쥔 강력범죄로 옮겨갔다*
같은 5년간 도내 중범죄는
살인·강도를 포함해 30여 건이다
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the gloved fingertips tightening as they seal a clear evidence bag. A forensic officer in dark gloves crouches on the wet asphalt and holds up the bag containing a broken wooden club, eyes fixed on the object rather than on the camera. Behind the hands, a strip of police cordon tape sags across the same wet road surface, and two blurred officers stand far back. Nothing else occupies the frame, so the bag and the hands carry the whole weight of the moment.
Camera: medium close-up from eye-level, shot on 85mm portrait lens
Lighting/mood: cold blue pre-dawn tone, lone streetlight reflection on wet ground, desolate stillness
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), film-noir low-key lighting, deep shadows
Korean setting: Korean provincial street at night, right-hand traffic, Korean road markings with no legible text.
Text handling: the evidence bag carries no readable label, all lettering cropped or out of focus, no readable characters anywhere.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the wet asphalt ground) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
경찰 압수 증거물 봉투
```

### [카드 3]
**텍스트**
```text
7월 26일 새벽 3시 음성 대소읍
길거리에 10여 명이 뒤엉켰다
말레이시아 국적 40대 남성이
*휘두른 흉기에 20대가 숨졌다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: one man's clenched fist frozen in the air as two others drag him backward. On a small-town street at three in the morning, a dozen adult men are breaking apart rather than clashing, some staggering away, some turned aside with their backs to us. A wooden club and a shattered bottle lie on the same asphalt between them, and one man crouches low with his head down. The instant shown is strictly after the fight, no contact and no impact anywhere in the frame.
Camera: medium shot from a high Dutch-tilted angle, shot on 20mm wide lens
Lighting/mood: single pool of hard light isolating the figures in surrounding blackness, claustrophobic loneliness
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), film-noir low-key lighting, deep shadows
Korean setting: Korean small-town street at night, right-hand traffic, Korean storefront shapes with no legible text.
Text handling: all shop lettering cropped or lost in shadow, no readable characters anywhere.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the night street asphalt) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
- no blood, no wounds, no weapon pointed at a person, no moment of impact
```
**검색어**
```text
음성 대소읍 집단 난투극
```

### [카드 4]
**텍스트**
```text
청주 봉명동 편의점 앞 노상이
*흉기난동 장소가 됐다*
용암동에선 대낮 납치극이 벌어졌다
주말 새벽엔 각목까지 등장했다
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the tense empty gap between two small groups of men standing still on the same pavement. Outside a convenience store at night, three men near the plastic tables face four others waiting a few steps away, none of them moving, all eyelines locked across the gap. One plastic stool lies overturned on the ground and a dome camera juts from the eaves above them. The nearest man turns his head toward the right edge of the frame, and the composition leaves nose room on that side.
Camera: wide shot from a ground-level worm's-eye view, shot on 35mm lens
Lighting/mood: flat cold even surveillance light, no shadow no warmth, detached and watchful
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), film-noir low-key lighting, deep shadows
Korean setting: Korean convenience store forecourt at night, right-hand traffic, Korean signboard and awning shapes with no legible text.
Text handling: the store sign is cropped above the frame edge, all packaging and signage lettering unreadable, no readable characters anywhere.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the convenience store forecourt pavement) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
- no weapon in anyone's hand, no physical contact between the two groups
```
**검색어**
```text
청주 봉명동 편의점 노상
```

### [카드 5]
**텍스트**
```text
각목은 그 거리의 주말 풍경이 됐다
거기서 장사하는 60대 정길영씨는
*"막연한 공포 속에 하루를 보내고 있다"*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: a vacant thousand-yard stare, unfocused eyes looking past everything, with the jaw clenched tight and the muscle flexing at the jawline. Recurring subject A - a Korean man in his 60s, thinning grey hair, deep lines around the eyes, a faded dark work vest over a checked shirt. His face fills the frame as he stands just outside his shop before dawn, one shoulder brushing the corrugated steel shutter behind him, not looking at the camera. The shutter runs unbroken across the whole background as the single surface of the image.
Camera: tight close-up with the face filling the frame, from eye-level, shot on 85mm portrait lens
Lighting/mood: single hard side-light cutting across the subject, deep chiaroscuro shadows, tense atmosphere
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), film-noir low-key lighting, deep shadows
Korean setting: a Korean university-area food alley before dawn, Korean roll-down shop shutter with no legible text.
Text handling: no writing on the shutter, all lettering absent or lost in shadow, no readable characters anywhere.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the corrugated steel shutter behind him) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
청주 대학가 먹자골목 새벽
```

### [카드 6]
**텍스트**
```text
*그런데 경찰은 이들을 쫓기 어렵다*
명의 휴대전화도 통장도 주소도 없어
동선을 좇을 기록이 남지 않는다
조사마다 통역을 거쳐 시간도 몇 배다
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: the investigator's fingers stopped dead on the keyboard, his eyes fixed on a screen that gives nothing back. Recurring subject B - a Korean man in his 50s, short greying hair, a plain navy windbreaker over a shirt, a lanyard at his chest. He sits alone at a steel desk late at night, leaning over a monitor whose search panel glows blank, with a thin stack of printouts and a cold paper cup spread across the same desktop. Recurring location - a small provincial Korean police office with rows of steel desks, the other desks dark and unoccupied behind him.
Camera: medium shot from a high angle, shot on 50mm standard lens
Lighting/mood: cold blue screen under-glow lighting the face from below in a dark room, restless paranoid unease
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), film-noir low-key lighting, deep shadows
Korean setting: a Korean provincial police office interior, Korean office furniture shapes with no legible text.
Text handling: the monitor shows only an empty glowing panel, the printouts are angled away and unreadable, no readable characters anywhere.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the office desk surface) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
- no agency logo, no emblem, no institutional insignia
```
**검색어**
```text
청주흥덕경찰서 수사과 사무실
```

### [카드 7]
**텍스트**
```text
5809명을 붙잡아온 5년 동안
음성·진천경찰서 외사계는 각 1명이다
잡기 어렵다는 게 알려질수록
*다음 사건의 문턱은 낮아진다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: one lit desk lamp beside an empty chair that no one has pulled in. Recurring subject B - a Korean man in his 50s, short greying hair, a plain navy windbreaker over a shirt, a lanyard at his chest. He is seen from behind, seated alone and centered in the room at the only lit desk, shoulders lowered, facing a window where the dark street lies beyond. Recurring location - a small provincial Korean police office with rows of steel desks, the paired desk next to him bare and its chair empty, the composition centered and static.
Camera: wide shot from eye-level, shot on 35mm lens
Lighting/mood: cold blue pre-dawn tone, lone streetlight reflection on wet ground beyond the window, desolate stillness
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), film-noir low-key lighting, deep shadows
Korean setting: a Korean provincial police office interior at dawn, Korean office furniture and window frame shapes with no legible text.
Text handling: the section nameplate is turned away and unreadable, all lettering absent, no readable characters anywhere.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the office floor) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
- no agency logo, no emblem, no institutional insignia
```
**검색어**
```text
음성경찰서 외사계 사무실
```
