// 발사 레이트리밋 공용 헬퍼(260711 · 평의회 권고 후보9) — 러너 무료분 남용 방지.
// 해당 워크플로의 queued+in_progress 런 수가 캡 이상이면 429 정직 거절(뷰어 연타·중복 발사 차단).
// 원칙: ① 업로드 *전*에 게이트(업로드 후 거절 = up-<id> 고아 브랜치·낭비) ② 조회 실패/예외 = fail-open(null 반환 —
//   레이트리밋은 남용 방지지 가용성 게이트가 아님 · GH API 장애가 발사를 막으면 안 됨) ③ GH 콜 2회 = 발사 시에만(폴링 무관).
// 사용: const rl = await rateGate(GH, env.GH_TOKEN, 'edit-make.yml'); if (rl) return json({ error: rl.error }, 429);
export async function rateGate(GH, token, wf, cap = 3) {
  try {
    let n = 0;
    for (const st of ['queued', 'in_progress']) {
      const r = await GH(token, `actions/workflows/${wf}/runs?status=${st}&per_page=1`, 'GET');
      if (r.status !== 200) return null;   // 조회 실패 = fail-open
      n += Number((await r.json()).total_count) || 0;
    }
    if (n >= cap) return { error: `이미 작업 ${n}개가 돌고 있어 — 끝나면 다시 걸어줘`, n };
    return null;
  } catch { return null; }
}
