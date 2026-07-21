// GET /api/linkgrab/ytstat?id=… — 변환 상태({ready,asset|parts,size} | {failed} | {ready:false}) · 릴리스 자산 조회 기반
import { json, lgYtRel, lgYtLookup } from './_lib.js';

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const id = String(url.searchParams.get('id') || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 20);
  if (!id) return json({ error: 'id가 필요해요' }, 400);
  const hit = lgYtLookup(await lgYtRel(env), id);
  return json(hit || { ready: false });
}
