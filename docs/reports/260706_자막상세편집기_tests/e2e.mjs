// ly.html 상세 편집기 E2E — 실제 STT 산출물(segments.json)+실제 오디오를 라우트로 물려 전 플로우 검증.
import { chromium } from 'playwright';
import { readFileSync, existsSync, mkdirSync } from 'fs';
import { execSync } from 'child_process';

const SCRATCH = new URL('.', import.meta.url).pathname;
const OUTDIR = SCRATCH + 'e2e/';
mkdirSync(OUTDIR, { recursive: true });
const SEG_PATH = SCRATCH + 'stt_out/ko.segments.json';
const WAV_PATH = SCRATCH + 'stt_out/ko.wav';
if (!existsSync(SEG_PATH) || !existsSync(WAV_PATH)) { console.error('실물 STT 산출물 없음 — stt_multi_test 먼저'); process.exit(2); }
const SEGJ = JSON.parse(readFileSync(SEG_PATH, 'utf8'));
const MD = ['# 자막 테스트', '## ⓪ 개요', '- 내용: 자막 편집기 소개 · 화자 1명 · ' + Math.round(SEGJ.dur) + 's · 한국어 원본 모드 · 조각 ' + SEGJ.segs.length + '개', '## ① 전체 표', '| # | 시간 | 자막 |', '|---|---|---|',
  ...SEGJ.segs.slice(0, 3).map((s, i) => `| ${i + 1} | 0:0${i} | ${s.t.slice(0, 12)} |`), '---', '## ② 조각별 복사 블록', '(1/3) 0:00', '```text', SEGJ.segs[0].t.slice(0, 14), '```'].join('\n');

// 정적 서버(viewer 루트) — tokens.css·nm-svg.js 실물 로드
try { execSync('pkill -f "http.server 8737" 2>/dev/null'); } catch {}
const srv = execSync('cd /home/user/nomute-editor/viewer && (python3 -m http.server 8737 >/dev/null 2>&1 & echo $!)').toString().trim();
await new Promise(r => setTimeout(r, 900));

let pass = 0, fail = 0; const bad = [];
const ok = (c, label) => { if (c) pass++; else { fail++; bad.push(label); console.log('✗ ' + label); } };

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--autoplay-policy=no-user-gesture-required', '--mute-audio'] });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
page.on('pageerror', e => { fail++; bad.push('pageerror: ' + e.message); console.log('✗ pageerror', e.message); });
await page.route('**/api/ly', r => r.fulfill({ json: { ok: true, id: 'e2e1', out: 'ly_out/e2e1/subs.md' } }));
await page.route('**/ly_out/e2e1/subs.md*', r => r.fulfill({ contentType: 'text/markdown; charset=utf-8', body: MD }));
await page.route('**/ly_out/e2e1/segments.json*', r => r.fulfill({ contentType: 'application/json', body: JSON.stringify(SEGJ) }));
await page.route('**/ly_out/e2e1/error.log*', r => r.fulfill({ status: 404, body: '' }));

await page.goto('http://127.0.0.1:8737/ly.html');
ok(await page.locator('#go').isVisible(), '폼 로드');

// 1) 파일 첨부(오디오) → 배지 + 미리보기
await page.setInputFiles('#file', WAV_PATH);
await page.waitForFunction(() => document.querySelector('#fileLab').classList.contains('has'), null, { timeout: 20000 });
ok(await page.locator('#lyPv').isVisible(), '미리보기 등장(objectURL)');
ok(!(await page.locator('#lyCap').isVisible()), '생성 전 캡션바 미노출([hidden] 가드 · 평의회5)');
ok((await page.locator('#fileTxt .ftype').textContent()) === '음성', '음성 배지');

// 2) 생성 → 편집기 렌더(기본 = 상세)
await page.click('#go');
await page.waitForSelector('.lytabs.show', { timeout: 20000 });
ok(await page.locator('#out').isVisible() && !(await page.locator('#lydet').isVisible()), '기본 탭 = 개요(다듬은 자막 첫인상 · 평의회8)');
ok((await page.locator('#lyTabOv').getAttribute('aria-selected')) === 'true', '탭 aria-selected 동기');
await page.click('#lyTabDet');
ok(await page.locator('#lydet').isVisible(), '상세 탭 전환');
const cardN = await page.locator('.lyseg').count();
ok(cardN === SEGJ.segs.length, `조각 카드 수 = segments(${SEGJ.segs.length}) — 실측 ${cardN}`);
ok((await page.locator('#lyStats').textContent()).includes('조각'), '통계 표시');
ok(await page.locator('#lyPvRow').isVisible(), '미리보기 컨트롤 행(컷스킵·속도·자막크기)');

// 3) 칩 제외 토글(탭 디바운스 200ms 대기)
const chip0 = page.locator('.lyseg[data-i="0"] .ed-chip').first();
const chipTxt = await chip0.textContent();
await chip0.click(); await page.waitForTimeout(320);
ok(await chip0.evaluate(el => el.classList.contains('off')), '칩 탭 = 제외(off)');
ok((await page.locator('#lyStats').textContent()).includes('뺀 단어') && (await page.locator('#lyStats').innerHTML()).includes('뺀 단어 <b>1</b>'), '통계 뺀 단어 1 반영');
await chip0.click(); await page.waitForTimeout(320);
ok(!(await chip0.evaluate(el => el.classList.contains('off'))), '재탭 = 복원');

// 4) 칩 더블탭 수정(Enter 확정)
await chip0.dblclick();
ok(await chip0.evaluate(el => el.isContentEditable), '더블탭 = 편집 진입');
await chip0.evaluate(el => { el.textContent = '테스트어'; });
await chip0.press('Enter');
await page.waitForTimeout(150);
ok((await page.locator('.lyseg[data-i="0"] .ed-chip').first().textContent()) === '테스트어', '수정 확정(Enter→blur)');

// 5) 스페이스 분열(칩 +1)
const before = await page.locator('.lyseg[data-i="0"] .ed-chip').count();
const c0 = page.locator('.lyseg[data-i="0"] .ed-chip').first();
await c0.dblclick();
await c0.evaluate(el => { el.textContent = '테스 트어'; el.dispatchEvent(new InputEvent('input', { bubbles: true })); });
await page.waitForTimeout(200);
const after = await page.locator('.lyseg[data-i="0"] .ed-chip').count();
ok(after === before + 1, `스페이스 분열 칩 +1 (${before}→${after})`);
await page.keyboard.press('Enter'); await page.waitForTimeout(120);

// 6) 찾아 바꾸기
await page.click('#lyFindTg');
ok(await page.locator('#lyFind').isVisible(), '찾아바꾸기 바 열림');
await page.fill('#lyFindQ', '테스');
await page.waitForTimeout(260);
ok(parseInt((await page.locator('#lyFindN').textContent()) || '0') >= 1, '매치 카운트 표시');
ok((await page.locator('.ed-chip.hit').count()) >= 1, '매치 칩 하이라이트');
await page.fill('#lyFindR', '체크');
await page.click('#lyFindGo');
await page.waitForTimeout(200);
ok((await page.locator('.lyseg[data-i="0"] .ed-chip').first().textContent()).includes('체크'), '모두 바꾸기 반영');

// 7) 선택(개별→전체) + 카운터
await page.locator('.lyseg[data-i="0"] .lyseg-h .dl-full').click();   // 실사용 제스처 = label 탭(투명 input은 cbox가 덮음)
await page.waitForTimeout(120);
ok((await page.locator('#lyStats').innerHTML()).includes('선택'), '선택 카운터');
await page.locator('#lydet .lytool .dl-full').click();
await page.waitForTimeout(120);
const selAll = await page.evaluate(() => LY_SEGS.filter(s => !s.del && s.sel).length === LY_SEGS.filter(s => !s.del).length);
ok(selAll, '전체 선택(라벨 탭)');
await page.locator('#lydet .lytool .dl-full').click();
await page.waitForTimeout(120);

// 8) SRT 다운로드(내용 검증 — CapCut 규격: UTF-8 무BOM·쉼표 ms·번호)
const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#lySrt')]);
const srtPath = OUTDIR + 'e2e.srt';
await dl.saveAs(srtPath);
const srtBuf = readFileSync(srtPath);
const srtTxt = srtBuf.toString('utf8');
ok(!(srtBuf[0] === 0xEF && srtBuf[1] === 0xBB), 'SRT BOM 없음');
ok(/^1\r\n\d\d:\d\d:\d\d,\d\d\d --> /.test(srtTxt), 'SRT 헤더 규격(번호·CRLF·쉼표 ms — 프리미어 호환)');
const aliveN = await page.evaluate(() => LY_SEGS.filter(s => !s.del && s.w.some(w => w.on)).length);
ok((srtTxt.match(/ --> /g) || []).length === aliveN, `SRT 큐 수 = 생존 조각(${aliveN})`);
ok(await page.locator('#lySrt').evaluate(el => el.classList.contains('dl-done')), 'SRT 받음 표식(dl-done 흰색)');
await page.screenshot({ path: OUTDIR + '1_상세편집기.png', fullPage: true });

// 9) 병합(카드 -1) / 삭제·복원
const n1 = await page.locator('.lyseg').count();
await page.locator('.lyseg[data-i="1"] .lyseg-a[aria-label="위 조각과 합치기"]').click();
await page.waitForTimeout(150);
ok((await page.locator('.lyseg').count()) === n1 - 1, '병합 = 카드 -1');
await page.locator('.lyseg[data-i="0"] .lyseg-a[aria-label="조각 삭제"]').click();
await page.waitForTimeout(150);
ok(await page.locator('.lyseg[data-i="0"]').evaluate(el => el.classList.contains('del')), '삭제 = 흐림');
await page.locator('.lyseg[data-i="0"] .lyseg-a[aria-label="조각 복원"]').click();
await page.waitForTimeout(150);
ok(!(await page.locator('.lyseg[data-i="0"]').evaluate(el => el.classList.contains('del'))), '복원');

// 10) 미리보기 싱크(시크→캡션·cur 하이라이트) + 자막 크기 슬라이더
const seg1 = await page.evaluate(() => ({ s: LY_SEGS[1].s, e: LY_SEGS[1].e, t: LY_SEGS[1].w.filter(w => w.on).map(w => w.t).join(' ') }));
await page.evaluate(mid => { const v = document.querySelector('#lyVid'); v.muted = true; v.currentTime = mid; }, (seg1.s + seg1.e) / 2);
await page.waitForTimeout(700);
ok((await page.locator('#lyCap').textContent()).length > 0, '캡션 표시(시크 싱크)');
ok(await page.locator('.lyseg[data-i="1"]').evaluate(el => el.classList.contains('cur')), '현재 조각 하이라이트');
await page.locator('.lyseg[data-i="2"] .lyseg-t').click();
await page.waitForTimeout(500);
const ct = await page.evaluate(() => document.querySelector('#lyVid').currentTime);
const seg2s = await page.evaluate(() => LY_SEGS[2].s);
ok(Math.abs(ct - seg2s) < 0.6, `타임스탬프 탭 = 시크(${ct.toFixed(2)}≈${seg2s})`);
await page.locator('#lyFs').evaluate(el => { el.value = 26; el.dispatchEvent(new Event('input', { bubbles: true })); });
ok((await page.locator('#lyCap').evaluate(el => el.style.fontSize)) === '26px', '자막 크기 슬라이더');
await page.click('#lyRate');
ok((await page.evaluate(() => document.querySelector('#lyVid').playbackRate)) === 1.5, '재생 속도 1.5x');

// 11) 컷 스킵 — 조각0 삭제 후 그 구간 재생 → 다음 조각으로 점프
await page.locator('.lyseg[data-i="0"] .lyseg-a[aria-label="조각 삭제"]').click();
await page.waitForTimeout(150);
const jump = await page.evaluate(async () => {
  const v = document.querySelector('#lyVid'); v.muted = true;
  const s0 = LY_SEGS[0], next = LY_SEGS.find(s => !s.del && s.s != null);
  v.currentTime = s0.s + 0.15; await v.play();
  await new Promise(r => setTimeout(r, 1300)); v.pause();
  return { t: v.currentTime, want: next.s };
});
ok(jump.t >= jump.want - 0.3, `컷 스킵 점프(${jump.t.toFixed(2)} ≥ ${jump.want})`);
await page.locator('.lyseg[data-i="0"] .lyseg-a[aria-label="조각 복원"]').click();

// 12) 개요 탭(기존 산출 그대로) ↔ 상세
await page.click('#lyTabOv');
ok(await page.locator('#out table').isVisible(), '개요 = 기존 subs.md 렌더(표)');
ok(await page.locator('#out .code button').first().isVisible(), '개요 복사 블록 버튼');
await page.screenshot({ path: OUTDIR + '2_개요탭.png', fullPage: true });
await page.click('#lyTabDet');

// 13) 리로드 → 자동 복원(편집 유지·미리보기는 세션 한정이라 없음)
await page.reload();
await page.waitForSelector('.lytabs.show', { timeout: 15000 });
ok((await page.locator('#status').textContent()).includes('이전 결과 복원'), '복원 배너');
ok((await page.locator('.lyseg[data-i="0"] .ed-chip').first().textContent()).includes('체크'), '편집 내용 복원(localStorage)');
ok(!(await page.locator('#lyPv').isVisible()), '미리보기는 세션 한정(리로드 후 없음 = 의도)');
ok(await page.locator('#out').isVisible(), '복원도 개요 기본(일관)');
await page.click('#lyTabDet');
await page.screenshot({ path: OUTDIR + '3_복원.png', fullPage: true });

// 14) 편집 초기화 → 원본 복귀
await page.click('#lyReset');
await page.waitForTimeout(200);
ok(!(await page.locator('.lyseg[data-i="0"] .ed-chip').first().textContent()).includes('체크'), '편집 초기화 = 원본 전사 복귀');

// 14b) 칩 키보드 온리(Space=토글·Enter=수정 — 평의회9 P0)
const kchip = page.locator('.lyseg[data-i="1"] .ed-chip').first();
await kchip.focus();
await page.keyboard.press('Space');
ok(await kchip.evaluate(el => el.classList.contains('off')), '키보드 Space = 빼기 토글');
ok((await kchip.getAttribute('aria-pressed')) === 'true', 'aria-pressed 동기');
await page.keyboard.press('Space');
await page.keyboard.press('Enter');
ok(await kchip.evaluate(el => el.isContentEditable), '키보드 Enter = 수정 진입');
await page.keyboard.press('Escape');
await kchip.evaluate(el => el.blur());
await page.waitForTimeout(120);

// 14c) 모두 바꾸기 빈칸 = 재확인 어포던스(평의회8)
const firstWord = await page.locator('.lyseg[data-i="0"] .ed-chip').first().textContent();
await page.click('#lyFindTg').catch(() => {});
if (await page.locator('#lyFind').isHidden()) await page.click('#lyFindTg');
await page.fill('#lyFindQ', firstWord);
await page.fill('#lyFindR', '');
await page.click('#lyFindGo');
ok((await page.locator('#lyFindGo').textContent()).includes('한 번 더'), '빈 바꾸기 1탭 = 재확인 arm');
await page.click('#lyFindGo');
await page.waitForTimeout(200);
ok((await page.locator('.lyseg[data-i="0"] .ed-chip').first().textContent()) !== firstWord, '재확인 2탭 = 단어 지움 실행');

// 15) TXT 파일 = 편집기 미등장(종전 경로 그대로) — 회귀 가드
await page.evaluate(() => localStorage.clear());
await page.reload();
await page.setInputFiles('#file', { name: 'note.txt', mimeType: 'text/plain', buffer: Buffer.from('타임코드 없는 그냥 텍스트') });
await page.waitForTimeout(400);
ok(!(await page.locator('.lytabs').evaluate(el => el.classList.contains('show'))), 'TXT = 탭 없음(종전 경로)');

console.log(`\nE2E 결과: ${pass} 통과 · ${fail} 실패${fail ? ' — ' + bad.join(' / ') : ''}`);
await browser.close();
try { execSync('kill ' + srv); } catch {}
process.exit(fail ? 1 : 0);
