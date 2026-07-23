#!/usr/bin/env python3
"""
make_map_layers.py — 지도 탭 온디맨드 레이어 파일 생성 (v4)

생성물:
  - layers/poi_{시설코드}_{연도}.js : window.__LAYER('poi_daycar_2024', {sgg_cd: [[lon,lat], ...]})
  - layers/svc_ratios.js           : window.__LAYER('svc_ratios',
        {연도: {시설코드: {label: '영유아인구비율(1.0km)', rows: {sgg_cd: 비율}}}})

주의: servicepop shapefile 의 geometry 는 시군구 경계와 동일(권역 모양 아님)이라
      값(value_r)만 추출한다. dashboard 는 POI 파일을 시설·연도 조합별 lazy-load,
      svc_ratios 는 1회 lazy-load 한다. POI 좌표 4자리 반올림(≈11m).
"""

import geopandas as gpd
import json, os, sys, glob, re
from shapely.ops import transform

BASE   = os.path.dirname(os.path.abspath(__file__))
TSDATA = os.path.join(BASE, '..', '생활인프라_시계열데이터')
OUTDIR = os.path.join(BASE, 'layers')

# 시설코드 ↔ 한글명 (dashboard FACILITIES 와 동일)
FAC = {
    '어린이집': 'daycar', '유치원': 'kinder', '초등학교': 'elem', '작은도서관': 'smlib',
    '온종일돌봄센터': 'allday', '종합사회복지관': 'welfar', '노인여가복지시설': 'snrlei', '경로당': 'snrctr',
    '종합병원': 'hosp', '보건기관': 'health', '의원': 'clinic', '약국': 'pharma',
    '지진옥외대피소': 'eqshlt', '응급의료시설': 'emerg', '경찰서': 'police', '소방서': 'fire',
    '생활권공원': 'lfpark', '주제공원': 'thpark', '공연문화시설': 'cultur', '공공체육시설': 'sports',
}

def rnd(geom, nd=4):
    return transform(lambda x, y: (round(x, nd), round(y, nd)), geom)

def kor_of(fname):
    """파일명에서 시설 한글명 추출 (가장 긴 매칭 우선). 공백 변형 흡수."""
    squeezed = fname.replace(' ', '')
    hits = [k for k in FAC if k in squeezed]
    return max(hits, key=len) if hits else None

def write_js(path, key, obj):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"window.__LAYER('{key}', ")
        f.write(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
        f.write(');\n')

_SGG_CACHE = {}
def sgg_boundary(year):
    """sgg_cd 누락 파일용 공간조인 경계 (EPSG:5179)."""
    if year not in _SGG_CACHE:
        b = gpd.read_file(os.path.join(TSDATA, year, 'output_test', 'composite_index.shp'))
        _SGG_CACHE[year] = b[['SIGUNGU_CD', 'geometry']].rename(columns={'SIGUNGU_CD': 'sgg_cd'})
    return _SGG_CACHE[year]

def ensure_sgg_cd(g, year, fname):
    # sgg_cd 가 없거나 대부분 null 이면 시군구 경계와 공간조인으로 부여
    if 'sgg_cd' in g.columns and g['sgg_cd'].notna().mean() >= 0.9:
        return g
    print(f'  [정보] sgg_cd 없음/결측 → 공간조인: {fname}')
    if 'sgg_cd' in g.columns:
        g = g.drop(columns=['sgg_cd'])
    j = gpd.sjoin(g, sgg_boundary(year), how='left', predicate='within')
    j = j.dropna(subset=['sgg_cd'])
    j['sgg_cd'] = j['sgg_cd'].astype(str).str.replace(r'\.0$', '', regex=True)
    return j

def build_poi(year):
    files = glob.glob(os.path.join(TSDATA, year, 'point', '*.shp'))
    done = set()
    for fp in files:
        kor = kor_of(os.path.basename(fp))
        if not kor:
            print(f'  [경고] 시설 매칭 실패: {os.path.basename(fp)}'); continue
        code = FAC[kor]
        g = gpd.read_file(fp)
        g = ensure_sgg_cd(g, year, os.path.basename(fp))
        g = g[['sgg_cd', 'geometry']].to_crs(4326)
        out = {}
        for cd, grp in g.groupby('sgg_cd'):
            out[str(cd)] = [[round(p.x, 4), round(p.y, 4)] for p in grp.geometry if p is not None]
        write_js(os.path.join(OUTDIR, f'poi_{code}_{year}.js'), f'poi_{code}_{year}', out)
        done.add(code)
        print(f'  poi_{code}_{year}: {sum(len(v) for v in out.values())}점')
    missing = set(FAC.values()) - done
    if missing: print(f'  [경고] {year} POI 누락 시설: {missing}')

def build_svc(year, acc):
    """value_r 만 추출 (geometry 는 시군구 경계라 미사용). acc[year][code] 에 누적."""
    files = glob.glob(os.path.join(TSDATA, year, 'servicepop', '*.shp'))
    done = set()
    acc[year] = {}
    for fp in files:
        base = os.path.basename(fp)
        kor = kor_of(base)
        if not kor:
            print(f'  [경고] 시설 매칭 실패: {base}'); continue
        code = FAC[kor]
        m = re.search(r'내\s*(.+?비율)\((.+?)\)', base)
        label = (m.group(1) + '(' + m.group(2) + ')') if m else '인구비율'
        # servicepop 은 행정코드(252개) 기준 → 대표점 공간조인으로 통계청 229개 코드에 매핑,
        # 한 통계청 시군구에 여러 행정구가 속하면 value_r 평균
        g = gpd.read_file(fp)[['value_r', 'geometry']]
        g = g[g.value_r.notna()].copy()
        g['geometry'] = g.geometry.representative_point()
        j = gpd.sjoin(g, sgg_boundary(year), how='inner', predicate='within')
        agg = j.groupby('sgg_cd')['value_r'].mean()
        rows = {str(cd): round(float(v), 1) for cd, v in agg.items()}
        acc[year][code] = {'label': label, 'rows': rows}
        done.add(code)
        print(f'  svc {code} {year}: {len(rows)}개 시군구 ({label})')
    missing = set(FAC.values()) - done
    if missing: print(f'  [경고] {year} 서비스권역 누락 시설: {missing}')

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    # 이전 실행의 svc_{fac}_{year}.js 잔재 정리
    for f in glob.glob(os.path.join(OUTDIR, 'svc_*_*.js')):
        os.remove(f)
    years = sorted(d for d in os.listdir(TSDATA)
                   if d.isdigit() and os.path.isdir(os.path.join(TSDATA, d)))
    svc_acc = {}
    for y in years:
        print(f'[{y}] POI...')
        build_poi(y)
        print(f'[{y}] 서비스권역 비율...')
        build_svc(y, svc_acc)
    write_js(os.path.join(OUTDIR, 'svc_ratios.js'), 'svc_ratios', svc_acc)
    total = sum(os.path.getsize(os.path.join(OUTDIR, f)) for f in os.listdir(OUTDIR))
    print(f'[완료] layers/ 총 {total/1024/1024:.1f}MB')

if __name__ == '__main__':
    main()
