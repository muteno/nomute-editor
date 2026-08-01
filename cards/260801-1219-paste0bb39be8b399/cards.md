# 500통의 문자와 한 통의 먼저 건 전화, 그 사이의 책임

**[프롬프트 설계]**
- 화풍: B 극화 — 형사 사건과 여론 저울이 동시에 걸린 사안이라, 인물 표정의 미세한 균열까지 잡아내는 극화가 맞다
- 분위기: 화면빛과 술집 어둠으로 눌린 밤의 온도 — 분노가 향할 곳을 잃고 서성이는 불쾌한 양가감정, 판단을 유보한 채 관찰하는 거리
- 연출 방향: 독자가 멈추는 자리는 '가해자가 명확한 줄 알았던 사건에 여지를 준 쪽이 끼어드는 순간'이다. 그래서 이 덱은 사람을 심판하는 컷이 아니라 **경계가 흐려진 지점의 물증**(밤의 폰 화면·테이블 위 두 잔·놓인 휴대폰)을 붙잡는다. 마지막엔 사람이 아무도 없는 자리를 비춰, 소란 속에서 지워진 쪽이 누구였는지를 보게 한다. thumb_dispatch에서 상속하는 것은 차갑고 답답한 실내 저조도 톤과 미세표정의 정조뿐 — 앵글은 카드마다 분산한다.
- 독자 동선: **발단** 카드1 → **전개** 카드2~3 → **피크** 카드4 → **해소** 카드5 → **시사점** 카드6 · 훅 = 카드1 끝(예고형: 영상 하나가 저울을 뒤집었다)+카드2 끝(단서형: 먼저 짚은 건 팬의 행위) · 착지 = 남녀 서사가 앞자리를 차지하는 동안 협박 메시지를 받은 아들이 이야기에서 사라진다
- 연속성 앵커: Recurring subject A — a Korean man in his late 30s with short cropped black hair and thick black-framed glasses, wearing a dark charcoal zip-up hoodie. / Recurring subject B — a Korean woman in her early 40s with shoulder-length dark hair tied back, slim build, wearing a muted beige knit top. / 반복 장소 — a dim night interior lit only by a screen.

### [카드 1]
**텍스트**
```text
배우 황정민을 스토킹한 혐의였다
벌금 300만 원 약식명령이 나왔고
팬 K씨는 불복해 재판을 청구했다
*그런데 영상 하나가 저울을 뒤집었다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: her tightened grip on a folded envelope, knuckles pale. Recurring subject B — a Korean woman in her early 40s with shoulder-length dark hair tied back, slim build, wearing a muted beige knit top — walks away down a long Korean courthouse corridor, seen from behind and above, her head lowered. A single official envelope is clutched against her side, and her body is angled toward the far right end of the corridor. Rows of closed hearing-room doors line both walls of the otherwise empty passage, nose room on the right, movement directed toward the right edge.
Camera: wide shot, full body, surrounding environment, spatial context from high angle shot, looking down, vulnerable subject, small, observed, shot on 35mm lens, natural documentary perspective, balanced subject and background, minimal distortion
Lighting/mood: overcast diffused daylight, flat soft shadows, muted somber mood
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), muted daylight contrast
Korean setting: Korean faces and physique, Korean institutional interior conventions.
Text handling: avoid incidental lettering on doors and signs by framing and angle; no garbled or fake script, no meaningless letters, no random characters, no dense text.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the corridor floor) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
법원 복도 형사법정
```

### [카드 2]
**텍스트**
```text
유튜버 이진호가 지난 7월 31일
자신의 채널에 폭로 영상을 올렸다
*"100대 0으로 볼 사안이 아니다"*
그가 먼저 짚은 건 팬의 행위였다
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: his steady unwavering eyes, fixed on something just past the lens. Recurring subject A — a Korean man in his late 30s with short cropped black hair and thick black-framed glasses, wearing a dark charcoal zip-up hoodie — sits at a desk in a darkened room and leans toward a large studio microphone as he speaks, one hand flat on the desk. A blank editing monitor glows in front of him and washes his face from below. The room behind him dissolves into black, nose room on the right, gaze directed toward the right edge.
Camera: medium shot, waist-up framing, face and gestures, conversational from eye-level shot at a three-quarter angle, natural face depth, dimensional portrait, shot on 50mm standard lens, minimal distortion, natural cinematic composition
Lighting/mood: cold blue screen under-glow lighting the face from below in a dark room, restless paranoid unease
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), film-noir low-key lighting, deep shadows
Korean setting: Korean faces and physique, Korean interior conventions.
Text handling: the monitor stays blank and featureless; no garbled or fake script, no meaningless letters, no random characters, no dense text.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the dark studio wall) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
연예뒤통령 이진호 유튜브
```

### [카드 3]
**텍스트**
```text
협박 메시지는 미성년 아들에게 갔다
졸업 공연장에도 K씨는 나타났다
황정민에게 온 문자만 500건을 넘겼다
*정당화할 수 없는 스토킹이라고 했다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: her tightly controlled face, jaw set and lips pressed, lit only from below. Recurring subject B — a Korean woman in her early 40s with shoulder-length dark hair tied back, slim build, wearing a muted beige knit top — sits alone in a dark room at night, holding a smartphone up close with both hands, her head bent over it. The phone screen glows blank and featureless against her face, and her eyes stay locked on it. No other person is present in the room.
Camera: medium close-up, chest-up framing, facial emotion, slight body context from high angle shot, looking down, vulnerable subject, small, observed, shot on 85mm portrait lens, flattering face, soft background separation, elegant focus
Lighting/mood: cold blue dim interior light, heavy and suffocating, faint trembling tension
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), film-noir low-key lighting, deep shadows
Korean setting: Korean faces and physique, Korean interior conventions.
Text handling: the phone screen shows only light and blurred shapes, never readable characters; no garbled or fake script, no meaningless letters, no random characters, no dense text.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the dim interior wall) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
스토킹 문자메시지 협박
```

### [카드 4]
**텍스트**
```text
반대편에는 단둘의 술자리가 있었다
연락을 먼저 건 쪽은 황정민이었다
*"안아보고 싶지 나도" 녹취가 남았다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: a fleeting micro-expression flashing across his otherwise composed face, one mouth corner lifting for an instant. Recurring subject B — a Korean woman in her early 40s with shoulder-length dark hair tied back, slim build, wearing a muted beige knit top — is present only as an out-of-focus shoulder at the near edge of the frame. Filling the frame in profile is a Korean man in his early 50s with close-cropped greying hair and a plain dark jacket, seated at a small bar table with his own phone lying face-up beside his hand, his gaze angled down toward it. Two glasses stand between the two figures and the bar around them falls away into blackness.
Camera: tight close-up, face fills frame, intense emotion, intimate pressure from profile shot, side view, clear silhouette, directional movement, shot on 135mm telephoto lens, strong compression, elegant portrait separation, cinematic depth
Lighting/mood: single pool of hard light isolating the figure in surrounding blackness, claustrophobic loneliness
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), film-noir low-key lighting, deep shadows
Korean setting: Korean faces and physique, Korean bar interior conventions.
Text handling: no labels on glasses or on the phone; no garbled or fake script, no meaningless letters, no random characters, no dense text.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the darkened bar wall) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
황정민 통화 녹취 공개
```

### [카드 5]
**텍스트**
```text
이진호는 다시 선을 그었다
가장 큰 실수는 사적인 연락이었다
*그래도 스토킹이 정당화되진 않는다*
황정민 측은 법적 대응을 이어간다
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: his flat open palm held out in the air, cutting a hard line between two sides. Recurring subject A — a Korean man in his late 30s with short cropped black hair and thick black-framed glasses, wearing a dark charcoal zip-up hoodie — stands in a dark studio space, chest-up in frame, his other hand resting on the back of a chair, his eyes lowered toward where his palm falls. The empty studio wall stretches behind him with nothing else in view.
Camera: medium close-up, chest-up framing, facial emotion, slight body context from low angle shot, looking up, dramatic presence, shot on 70mm short telephoto, gentle background compression, subject isolation
Lighting/mood: single hard side-light cutting across the subject, deep chiaroscuro shadows, tense atmosphere
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), film-noir low-key lighting, deep shadows
Korean setting: Korean faces and physique, Korean interior conventions.
Text handling: keep the wall bare and unlettered; no garbled or fake script, no meaningless letters, no random characters, no dense text.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the studio wall) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
황정민 소속사 법적대응
```

### [카드 6]
**텍스트**
```text
'100대 0'이라는 말은 늘 위험하다
가해의 크기 대신 피해자를 따진다
'15살 연하'가 폭로자의 첫 소개였다
*그 사이 아들은 이야기에서 사라진다*
```
**이미지 프롬프트**
```text
korean manhwa style serious drama illustration, sharp black ink outlines with varying line weight, precise anatomical rendering, screentone shading, cel-shaded color with defined edges, high contrast chiaroscuro, muted desaturated palette with selective color accents, heavy atmosphere
Scene: Emotional focal point: one empty seat in the front row with a folded program left behind on it. A Korean school auditorium after everyone has gone, rows of identical empty seats receding evenly toward a dark stage, viewed straight on from the center aisle. A single shaft of pale light from a high side window falls across that one seat. No people are present anywhere in the frame.
Camera: wide shot, full body scale of the room, surrounding environment, spatial context from eye-level shot, neutral perspective, front-on shot, symmetrical composition, shot on 35mm lens, natural documentary perspective, minimal distortion
Lighting/mood: warm soft morning light, gentle and quiet, faint melancholy
Accent: monochrome desaturated base with a single color accent (neon green #0FFD02), muted daylight contrast
Korean setting: Korean school auditorium interior conventions.
Text handling: the folded program stays blank and unlettered; no garbled or fake script, no meaningless letters, no random characters, no dense text.
Aspect ratio: 4:5 vertical portrait, full bleed single image filling the entire frame edge to edge with no inner border, no outer frame, no rectangular outline, no white margin around the image.
MANDATORY: This is ONE single seamless illustration on ONE continuous surface. The entire canvas shows ONE continuous scene without any horizontal division, without any line cutting the image, without any frame inside the frame. The whole image is one unified visual flowing edge to edge.
Composition: ONE continuous surface (the auditorium floor and seating) extending edge to edge from top to bottom of the frame. The main subject is anchored in the upper-center area on this same surface. No other surface, no transition between two distinct surfaces anywhere in the frame.
NEGATIVE — strictly avoid:
- no comic panel layout, no split panel, no panel division, no horizontal divider line cutting the image, no upper and lower separate scenes, no two stacked frames, no boxed sections, no inset, no second view of the same subject, no duplicate elements
- no letterbox, no black bands at top or bottom, no padding, no empty black areas, no UI overlay, no caption space rendered as a solid color block
- no border, no frame, no panel border, no inner outline, no outer rectangular outline, no white margin around the image, no thick black outline framing the scene, no comic page border, no painted picture frame, no canvas border, no matted edge
- no main subject in the lower portion, no key figure in the bottom area, no face placed in the bottom of the frame, no central focal point in the bottom third
- no long sentences rendered, no paragraphs of text, no full newspaper headlines, no document body text, no long signage text, no English text, no garbled letters, no fake script, no dense text covering the image; minimal Korean text only if essential (a few characters max)
```
**검색어**
```text
학교 강당 졸업 공연장
```
