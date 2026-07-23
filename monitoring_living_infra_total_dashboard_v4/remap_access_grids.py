#!/usr/bin/env python3
"""
remap_access_grids.py — v3 access_grids.js 의 시군구 키를 v4 코드체계로 변환

v3 파일은 행정코드(252개, 예: 11110) 키인데 v4 대시보드는 통계청코드(229개,
예: 11010)를 쓴다. 격자 점을 통계청 시군구 경계에 공간조인해 재키잉하고
같은 파일(access_grids.js)을 덮어쓴다. (마스크 값은 그대로 유지)
"""

import geopandas as gpd
import pandas as pd
import json, os, re

BASE   = os.path.dirname(os.path.abspath(__file__))
TSDATA = os.path.join(BASE, '..', '생활인프라_시계열데이터')
SRC    = os.path.join(BASE, 'access_grids.js')

def main():
    txt = open(SRC, encoding='utf-8').read()
    m = re.search(r'ACCESS_GRIDS\s*=\s*(\{.*\});?\s*$', txt, re.S)
    if not m:
        raise SystemExit('ACCESS_GRIDS 파싱 실패')
    data = json.loads(m.group(1))
    pts = [(lon, lat, mask) for arr in data.values() for lon, lat, mask in arr]
    print(f'격자 점 {len(pts)}개 (기존 키 {len(data)}개)')

    years = sorted(d for d in os.listdir(TSDATA) if d.isdigit())
    b = gpd.read_file(os.path.join(TSDATA, years[-1], 'output_test', 'composite_index.shp'))
    b = b[['SIGUNGU_CD', 'geometry']].rename(columns={'SIGUNGU_CD': 'sgg_cd'}).to_crs(4326)

    g = gpd.GeoDataFrame(
        pd.DataFrame(pts, columns=['lon', 'lat', 'mask']),
        geometry=gpd.points_from_xy([p[0] for p in pts], [p[1] for p in pts]), crs=4326)
    j = gpd.sjoin(g, b, how='inner', predicate='within')
    print(f'조인 성공 {len(j)}개 / 유실 {len(g) - len(j)}개')

    out = {}
    for r in j.itertuples():
        out.setdefault(str(r.sgg_cd), []).append([round(r.lon, 5), round(r.lat, 5), int(r.mask)])

    with open(SRC, 'w', encoding='utf-8') as f:
        f.write('var ACCESS_GRIDS = ')
        f.write(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
        f.write(';\n')
    print(f'재키잉 완료: {len(out)}개 시군구, {os.path.getsize(SRC)/1024/1024:.1f}MB')

if __name__ == '__main__':
    main()
