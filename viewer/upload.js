// R2 직업로드 공용(편집기 edit.html · 변환 conv.html) — 32MB 균일 조각 멀티파트(api/upload 계약).
// window.nmUpArm() → 가용 여부(세션 1회 핑 캐시 · 바인딩 없으면 false = 각 폼이 기존 30MB base64 경로 폴백 = 회귀 0)
// window.nmUpload(file, onPct) → Promise<{key,size}> (진행률 0~100 콜백 · 실패 시 abort 후 throw)
// XHR 사용 이유 = fetch는 업로드 진행 이벤트가 없음(조각별 %가 UX 핵심). 조각당 1회 재시도 = 일시 네트워크 흔들림 흡수.
(function () {
  let armed = null;
  window.nmUpArm = async function () {
    if (armed !== null) return armed;
    try { const r = await fetch('api/upload'); const j = await r.json(); armed = !!(r.ok && j.ok); }
    catch (e) { armed = false; }
    return armed;
  };

  function putPart(url, blob, onLoaded) {
    return new Promise((res, rej) => {
      const x = new XMLHttpRequest();
      x.open('PUT', url);
      x.timeout = 180000;   // 조각당 3분(32MB) — 느린 회선도 조각 단위로만 실패 = 전체 재시작 방지
      x.upload.onprogress = e => { if (e.lengthComputable && onLoaded) onLoaded(e.loaded); };
      x.onload = () => {
        try { const j = JSON.parse(x.responseText || '{}'); (x.status === 200 && j.etag) ? res(j) : rej(new Error(j.error || ('HTTP ' + x.status))); }
        catch (e) { rej(new Error('HTTP ' + x.status)); }
      };
      x.onerror = () => rej(new Error('네트워크 오류'));
      x.ontimeout = () => rej(new Error('조각 시간 초과'));
      x.send(blob);
    });
  }

  window.nmUpload = async function (f, onPct) {
    const r0 = await fetch('api/upload', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ action: 'create', name: f.name, size: f.size }) });
    const c = await r0.json();
    if (!r0.ok || !c.key) throw new Error(c.error || '업로드 시작 실패');
    const part = c.part || 33554432, total = f.size, parts = [];
    let done = 0;
    const pct = extra => { if (onPct) onPct(Math.min(99, Math.round((done + (extra || 0)) / total * 100))); };
    try {
      for (let i = 0, n = 1; i < total; i += part, n++) {
        const blob = f.slice(i, Math.min(i + part, total));
        let p = null, err = null;
        for (let t = 0; t < 2; t++) {
          try { p = await putPart('api/upload?key=' + encodeURIComponent(c.key) + '&uploadId=' + encodeURIComponent(c.uploadId) + '&n=' + n, blob, pct); err = null; break; }
          catch (e) { err = e; }
        }
        if (err) throw err;
        parts.push({ n, etag: p.etag });
        done += blob.size;
        pct(0);
      }
      const r2 = await fetch('api/upload', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ action: 'complete', key: c.key, uploadId: c.uploadId, parts }) });
      const j2 = await r2.json();
      if (!r2.ok || !j2.ok) throw new Error(j2.error || '업로드 마무리 실패');
      if (onPct) onPct(100);
      return { key: c.key, size: j2.size };
    } catch (e) {
      try { fetch('api/upload', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ action: 'abort', key: c.key, uploadId: c.uploadId }) }); } catch (e2) { /* 정리 실패 = 무해(멀티파트 잔재는 R2가 자체 수명 관리) */ }
      throw e;
    }
  };
})();
