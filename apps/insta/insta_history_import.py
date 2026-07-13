#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""인스타 과거 일별 시계열 임포트 — 프로페셔널 대시보드 CSV 내보내기(zip) → data/insta_history.json.

배경(운영자 260713): API 인사이트는 연결 시점부터 누적이라 과거 소급 불가였는데, 운영자가 대시보드에서
일별 CSV(2025-11~2026-07 · 8개월)를 내보내 레포에 넣음(Shared.zip) → 이걸 과거 시드로 변환해
일일 추이 시계열을 소급한다. 봇(insta-fetch) 수집분과의 병합은 insta_signals._daily_timeseries 몫.

사용: python3 apps/insta/insta_history_import.py [zip경로=Shared.zip]
규칙:
- Instagram 축만 — 라벨에 'Facebook' = 제외 · 무라벨 동일범위 쌍(조회수·상호작용) = 합계 큰 쪽 = Instagram
  {근거 = 라벨 실측 패턴: 방문·팔로우의 Instagram(대)↔Facebook(소) 쌍과 값 스케일 동형 · notes에 가정 기록}.
- 내보낸 날(파일 내 최대 날짜) = 부분일 → 제외(cut_after) · 겹침 = 값 동일 검증(불일치 = 카운트·큰 범위 우선).
- 결측 날짜 = 키 없음(gap 유지 — 차트가 선을 끊어 정직 표시).
- 제외 = 링크클릭(유효값 4건) · 타겟(인구통계 = audience.json 축) · 조회계정(정체 모호 · 2025-11~12만).
CSV 형식 실측: UTF-16 · line1 'sep=,' · line2 지표명 · line3 헤더("날짜","Primary") · 이후 "ISO일시","값".
"""
import datetime
import json
import os
import re
import sys
import zipfile
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
KST = ZoneInfo('Asia/Seoul')

# 파일명 접두 → 출력 지표 키 (없는 접두 = 스킵)
METRIC_OF = {'조회수': 'views', '도달': 'reach', '방문': 'profile_views', '상호 작용': 'interactions', '팔로우': 'follows'}


def parse_csv(raw):
    """UTF-16 대시보드 CSV → (지표라벨, {date: value})."""
    txt = raw.decode('utf-16', 'replace')
    lines = [l.strip() for l in txt.splitlines() if l.strip() and l.strip() != 'sep=,']
    if len(lines) < 3:
        return '', {}
    label = lines[0].replace('"', '').strip()
    series = {}
    for ln in lines[2:]:
        parts = [p.strip().strip('"') for p in ln.split(',')]
        if len(parts) < 2 or not re.match(r'\d{4}-\d{2}-\d{2}', parts[0]):
            continue
        try:
            v = float(parts[1])
        except ValueError:
            continue
        series[parts[0][:10]] = int(v) if v == int(v) else v
    return label, series


def main():
    zpath = sys.argv[1] if len(sys.argv) > 1 else 'Shared.zip'
    if not os.path.exists(zpath):
        print(f'zip 없음: {zpath}')
        return 1
    z = zipfile.ZipFile(zpath)
    # 지표별 후보 시리즈 수집
    cand = {}   # metric -> [(fname, label, series)]
    skipped = []
    for n in z.namelist():
        try:
            fname = n.encode('cp437').decode('euc-kr')
        except Exception:
            fname = n
        stem = os.path.basename(fname)
        mkey = next((v for k, v in METRIC_OF.items() if stem.startswith(k)), None)
        if not mkey:
            skipped.append(stem)
            continue
        label, series = parse_csv(z.read(n))
        if not series:
            skipped.append(stem + ' (빈 시계열)')
            continue
        if 'Facebook' in label:
            skipped.append(stem + ' (Facebook 축)')
            continue
        cand.setdefault(mkey, []).append((stem, label, series))

    # 무라벨 동일범위 쌍 판별: 같은 (시작,끝) 범위에 2개면 합계 큰 쪽 = Instagram
    notes, mism = [], 0
    merged = {}   # metric -> {date: val}
    for mkey, lst in cand.items():
        bygroup = {}
        for fname, label, series in lst:
            key = (min(series), max(series))
            bygroup.setdefault(key, []).append((fname, label, series))
        keep = []
        for rng, group in bygroup.items():
            if len(group) > 1 and not any('Instagram' in g[1] for g in group):
                group.sort(key=lambda g: -sum(v for v in g[2].values()))
                keep.append(group[0])
                notes.append(f'{mkey} {rng[0]}~{rng[1]}: 무라벨 {len(group)}개 → 합계 큰 {group[0][0]} = Instagram 판정(나머지 제외)')
            else:
                for g in group:
                    keep.append(g)
        out = {}
        for fname, label, series in keep:
            for d, v in series.items():
                if d in out and out[d] != v:
                    mism += 1
                else:
                    out[d] = v
        merged[mkey] = out

    # 부분일 컷: 전 파일의 최대 날짜 = 내보낸 날 = 진행 중 → 제외
    all_dates = [d for s in merged.values() for d in s]
    cut = max(all_dates)
    for mkey in merged:
        merged[mkey] = {d: v for d, v in merged[mkey].items() if d < cut}

    # 날짜 통합 행
    dates = sorted({d for s in merged.values() for d in s})
    daily = []
    for d in dates:
        row = {'date': d}
        for mkey in ('views', 'reach', 'profile_views', 'interactions', 'follows'):
            if d in merged.get(mkey, {}):
                row[mkey] = merged[mkey][d]
        daily.append(row)

    meta = {m: {'from': min(s), 'to': max(s), 'n': len(s)} for m, s in merged.items() if s}
    doc = {'source': 'instagram_professional_dashboard_csv(Shared.zip · 운영자 수동 내보내기)',
           'imported_kst': datetime.datetime.now(KST).isoformat(timespec='seconds'),
           'cut_partial_day': cut, 'value_mismatch_overlap': mism,
           'metrics': meta, 'notes': notes, 'skipped': skipped, 'daily': daily}
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, 'insta_history.json'), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f'OK → data/insta_history.json · 일수 {len(daily)} ({dates[0]}~{dates[-1]}) · 부분일 컷 {cut} · 겹침 불일치 {mism}')
    for m, i in meta.items():
        print(f'  {m:<14} {i["from"]}~{i["to"]} n={i["n"]}')
    for n in notes:
        print('  ⚠', n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
