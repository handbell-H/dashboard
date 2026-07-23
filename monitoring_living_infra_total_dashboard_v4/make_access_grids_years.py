#!/usr/bin/env python3
"""
make_access_grids_years.py — 연도별 500m 충족격자 + 격자 인구 레이어 생성

입력: 생활인프라_시계열데이터/{연도}/access/*.shp (시설별 격자 접근성 거리 km)
      생활인프라_시계열데이터/{연도}/pop/popall_500*.shp (격자 인구)
출력: layers/access_{연도}.js
      window.__LAYER('access_2024', {sgg_cd: [[lon,lat,mask,pop], ...]})

- 충족: 접근성 거리 <= 시설별 기준(생활밀착 1km / 광역거점 5km), 결측=미충족
- 비트 순서 = 대시보드 FACILITIES 인덱스와 동일 (필수)
- 시군구 키: 격자 중심점을 통계청 229개 경계에 공간조인
- 포함 격자: 충족 1개 이상 또는 인구 > 0
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import json, os, glob, re
from scipy.spatial import cKDTree

BASE   = os.path.dirname(os.path.abspath(__file__))
TSDATA = os.path.join(BASE, '..', '생활인프라_시계열데이터')
OUTDIR = os.path.join(BASE, 'layers')

# (코드, 한글명, 거리기준 km) — 순서 = 대시보드 FACILITIES 비트 인덱스
FACILITIES = [
    ('daycar', '어린이집', 1), ('kinder', '유치원', 1), ('elem', '초등학교', 1), ('smlib', '작은도서관', 1),
    ('allday', '온종일돌봄센터', 1), ('welfar', '종합사회복지관', 5), ('snrlei', '노인여가복지시설', 5), ('snrctr', '경로당', 1),
    ('hosp', '종합병원', 5), ('health', '보건기관', 5), ('clinic', '의원', 1), ('pharma', '약국', 1),
    ('eqshlt', '지진옥외대피소', 1), ('emerg', '응급의료시설', 5), ('police', '경찰서', 5), ('fire', '소방서', 5),
    ('lfpark', '생활권공원', 1), ('thpark', '주제공원', 5), ('cultur', '공연문화시설', 5), ('sports', '공공체육시설', 5),
]

def find_file(year, kor):
    squeeze = lambda s: s.replace(' ', '')
    for fp in glob.glob(os.path.join(TSDATA, year, 'access', '*.shp')):
        if kor in squeeze(os.path.basename(fp)):
            return fp
    return None

def pop_file(year):
    cands = sorted(glob.glob(os.path.join(TSDATA, year, 'pop', 'popall_500*.shp')))
    return cands[0] if cands else None

def build_year(year):
    print(f'[{year}] 접근성 격자 결합...')
    base_fp = find_file(year, FACILITIES[0][1])
    g0 = gpd.read_file(base_fp)[['gid', 'geometry']]
    df = pd.DataFrame({'gid': g0.gid.values})
    mask = np.zeros(len(df), dtype=np.int64)

    for i, (code, kor, thr) in enumerate(FACILITIES):
        fp = find_file(year, kor)
        if not fp:
            print(f'  [경고] {kor} 파일 없음 — 비트 {i} 전부 0'); continue
        a = gpd.read_file(fp, ignore_geometry=True)[['gid', 'value']]
        a = df.merge(a, on='gid', how='left')
        ok = (a['value'].notna() & (a['value'] <= thr)).values.astype(np.int64)
        mask |= (ok << i)
        print(f'  {kor}: 충족 {int(ok.sum()):,} / {len(ok):,} (기준 {thr}km)')

    # 중심점 + 통계청 시군구 조인
    cent = g0.geometry.centroid
    b = gpd.read_file(os.path.join(TSDATA, year, 'output_test', 'composite_index.shp'))
    b = b[['SIGUNGU_CD', 'geometry']].rename(columns={'SIGUNGU_CD': 'sgg_cd'})
    cg = gpd.GeoDataFrame({'idx': np.arange(len(g0))}, geometry=cent, crs=g0.crs)
    j = gpd.sjoin(cg, b, how='left', predicate='within')
    j = j[~j.index.duplicated(keep='first')]
    sgg = np.full(len(g0), None, dtype=object)
    sgg[j['idx'].values] = j['sgg_cd'].values

    # 격자 인구 (최근접 350m)
    pop = np.zeros(len(g0), dtype=np.int64)
    pfp = pop_file(year)
    if pfp:
        pg = gpd.read_file(pfp)[['VAL', 'geometry']]
        pg = pg[pg.VAL.notna() & (pg.VAL > 0)]
        pc = pg.geometry.centroid
        tree = cKDTree(np.c_[pc.x.values, pc.y.values])
        dist, idx = tree.query(np.c_[cent.x.values, cent.y.values], k=1)
        hit = dist <= 350
        pop[hit] = np.round(pg.VAL.values[idx[hit]]).astype(np.int64)
        print(f'  인구 매칭 {int(hit.sum()):,}개 ({os.path.basename(pfp)})')
    else:
        print('  [경고] 인구 파일 없음')

    cent4326 = gpd.GeoSeries(cent, crs=g0.crs).to_crs(4326)
    lon = cent4326.x.round(5).values
    lat = cent4326.y.round(5).values
    score = np.array([bin(int(m)).count('1') for m in mask])

    keep = (sgg != None) & ((score > 0) | (pop > 0))
    out = {}
    for k in np.where(keep)[0]:
        out.setdefault(str(sgg[k]), []).append([float(lon[k]), float(lat[k]), int(mask[k]), int(pop[k])])

    path = os.path.join(OUTDIR, f'access_{year}.js')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"window.__LAYER('access_{year}', ")
        f.write(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
        f.write(');\n')
    print(f'  access_{year}.js: 격자 {int(keep.sum()):,}개, {os.path.getsize(path)/1024/1024:.1f}MB')

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    years = sorted(d for d in os.listdir(TSDATA)
                   if d.isdigit() and os.path.isdir(os.path.join(TSDATA, d, 'access')))
    for y in years:
        build_year(y)
    print('[완료]')

if __name__ == '__main__':
    main()
