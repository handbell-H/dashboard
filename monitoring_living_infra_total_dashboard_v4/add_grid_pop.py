#!/usr/bin/env python3
"""
add_grid_pop.py — access_grids.js 격자에 최신연도 500m 인구를 붙인다

각 격자 항목 [lon, lat, mask] → [lon, lat, mask, pop]
popall_500 (EPSG:5179 폴리곤) 중심점과 최근접 결합 (500m 격자라 350m 이내 매칭).
인구 없음/미매칭은 0.
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import json, os, re
from scipy.spatial import cKDTree

BASE   = os.path.dirname(os.path.abspath(__file__))
TSDATA = os.path.join(BASE, '..', '생활인프라_시계열데이터')
SRC    = os.path.join(BASE, 'access_grids.js')

def main():
    years = sorted(d for d in os.listdir(TSDATA) if d.isdigit())
    latest = years[-1]
    pop_fp = os.path.join(TSDATA, latest, 'pop', 'popall_500.shp')
    if not os.path.exists(pop_fp):
        cands = [f for f in os.listdir(os.path.join(TSDATA, latest, 'pop')) if f.startswith('popall') and f.endswith('.shp')]
        pop_fp = os.path.join(TSDATA, latest, 'pop', cands[0])
    print(f'인구 격자: {pop_fp}')
    pg = gpd.read_file(pop_fp)[['VAL', 'geometry']]
    pg = pg[pg.VAL.notna() & (pg.VAL > 0)]
    cent = pg.geometry.centroid
    cent4326 = gpd.GeoSeries(cent, crs=pg.crs).to_crs(4326)
    tree_pts = np.c_[cent.x.values, cent.y.values]          # EPSG:5179 (m)
    tree = cKDTree(tree_pts)
    vals = pg.VAL.values

    txt = open(SRC, encoding='utf-8').read()
    m = re.search(r'ACCESS_GRIDS\s*=\s*(\{.*\});?\s*$', txt, re.S)
    data = json.loads(m.group(1))
    all_pts = [(cd, i, e[0], e[1]) for cd, arr in data.items() for i, e in enumerate(arr)]
    print(f'격자 점 {len(all_pts)}개')

    g = gpd.GeoDataFrame(geometry=gpd.points_from_xy([p[2] for p in all_pts], [p[3] for p in all_pts]), crs=4326).to_crs(pg.crs)
    q = np.c_[g.geometry.x.values, g.geometry.y.values]
    dist, idx = tree.query(q, k=1)
    matched = dist <= 350
    print(f'인구 매칭 {matched.sum()}개 / 미매칭 {(~matched).sum()}개 (0 처리)')

    for (cd, i, _, _), d_ok, j in zip(all_pts, matched, idx):
        pop = int(round(float(vals[j]))) if d_ok else 0
        e = data[cd][i]
        if len(e) >= 4: e[3] = pop
        else: e.append(pop)

    with open(SRC, 'w', encoding='utf-8') as f:
        f.write('var ACCESS_GRIDS = ')
        f.write(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
        f.write(f';\nvar ACCESS_GRIDS_POP_YEAR = "{latest}";\n')
    print(f'완료: {os.path.getsize(SRC)/1024/1024:.1f}MB (인구 연도 {latest})')

if __name__ == '__main__':
    main()
