#!/usr/bin/env python3
"""
build.py — 생활인프라 편리성 GIS 분석 결과 → 정적 HTML 대시보드

사용법:  python build.py
출력:    dashboard.html  (브라우저에서 바로 열 수 있는 단일 파일)
"""

import geopandas as gpd
import pandas as pd
import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
OUT  = os.path.join(BASE, 'dashboard.html')

# ── 데이터 처리 ──────────────────────────────────────────────────────────────

def load():
    print('[1/5] Shapefile 로딩...')
    comp = gpd.read_file(os.path.join(DATA, 'composite_index.shp'))
    sup  = gpd.read_file(os.path.join(DATA, 'supply_index.shp'))
    pop  = gpd.read_file(os.path.join(DATA, 'service_pop_index.shp'))
    acc  = gpd.read_file(os.path.join(DATA, 'access_index.shp'))

    print('[2/5] CRS 변환 + 단순화...')
    comp = comp.to_crs(epsg=4326)
    comp['geometry'] = comp['geometry'].simplify(0.001)

    sup_df = (sup[['sgg_cd','edu_avg','care_avg','cult_avg','med_avg','safe_avg']]
              .rename(columns={'edu_avg':'edu_sup','care_avg':'care_sup',
                               'cult_avg':'cult_sup','med_avg':'med_sup','safe_avg':'safe_sup'}))

    pop_df = (pop[['sgg_cd','edu_avg','care_avg','cult_avg','med_avg','safe_avg']]
              .rename(columns={'edu_avg':'edu_pop','care_avg':'care_pop',
                               'cult_avg':'cult_pop','med_avg':'med_pop','safe_avg':'safe_pop'}))

    acc_df = (acc[['sgg_cd','edu_std','care_std','cult_std','med_std','safe_std']]
              .rename(columns={'edu_std':'edu_acc','care_std':'care_acc',
                               'cult_std':'cult_acc','med_std':'med_acc','safe_std':'safe_acc'}))

    print('[3/5] 데이터 병합...')
    gdf = comp.merge(sup_df, on='sgg_cd', how='left')
    gdf = gdf.merge(pop_df, on='sgg_cd', how='left')
    gdf = gdf.merge(acc_df, on='sgg_cd', how='left')
    return gdf


def to_geojson(gdf):
    NUM = ['infra_idx',
           'edu_conv','care_conv','med_conv','safe_conv','cult_conv',
           'edu_sup','care_sup','med_sup','safe_sup','cult_sup',
           'edu_pop','care_pop','med_pop','safe_pop','cult_pop',
           'edu_acc','care_acc','med_acc','safe_acc','cult_acc']
    sub = gdf[['sgg_cd','sgg_nm_k','sido_nm_k'] + NUM + ['geometry']].copy()
    for c in NUM:
        sub[c] = sub[c].round(4)
    return json.loads(sub.to_json())


def to_records(gdf):
    NUM = ['infra_idx',
           'edu_conv','care_conv','med_conv','safe_conv','cult_conv',
           'edu_sup','care_sup','med_sup','safe_sup','cult_sup',
           'edu_pop','care_pop','med_pop','safe_pop','cult_pop',
           'edu_acc','care_acc','med_acc','safe_acc','cult_acc']
    df = gdf[['sgg_cd','sgg_nm_k','sido_nm_k'] + NUM].copy()
    for c in NUM:
        df[c] = df[c].round(4)
    return df.to_dict(orient='records')


# ── HTML 템플릿 ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>생활인프라 편리성 모니터링 대시보드</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chroma-js@2.4.2/chroma.min.js"></script>
<style>
* { box-sizing: border-box; }
body { background: #F1F5F9; font-family: 'Apple SD Gothic Neo','Malgun Gothic',sans-serif; margin: 0; }
.navbar { background: #1E293B; padding: 10px 20px; display: flex; align-items: center; gap: 10px; }
.navbar-title { color: #F8FAFC; font-weight: 700; font-size: 1rem; }
.badge-cnt { background: #334155; color: #94A3B8; font-size: .75rem; padding: 3px 8px; border-radius: 20px; }
.tab-bar { background: #fff; border-bottom: 1px solid #E2E8F0; padding: 0 20px; display: flex; gap: 4px; }
.tab-btn { border: none; background: none; padding: 12px 16px; font-size: .875rem; color: #64748B;
           cursor: pointer; border-bottom: 2px solid transparent; font-weight: 500; white-space: nowrap; }
.tab-btn:hover { color: #334155; }
.tab-btn.active { color: #2563EB; border-bottom-color: #2563EB; font-weight: 600; }
.content { padding: 20px; }
.tab-pane { display: none; }
.tab-pane.active { display: block; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.08); border: none; }
.card-p { padding: 16px 20px; }
.card-h { font-size: .875rem; font-weight: 600; color: #374151; margin-bottom: 12px; }
.stat-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { background: #fff; border-radius: 10px; padding: 14px 18px;
             box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.stat-label { font-size: .75rem; color: #94A3B8; margin-bottom: 4px; }
.stat-val { font-size: 1.4rem; font-weight: 700; color: #1E293B; line-height: 1.2; }
.stat-sub { font-size: .72rem; color: #94A3B8; margin-top: 2px; }
.sector-grid { display: grid; grid-template-columns: repeat(5,1fr); gap: 12px; margin-bottom: 16px; }
@media(max-width:900px){ .sector-grid { grid-template-columns: repeat(3,1fr); } }
.sector-card { background: #fff; border-radius: 10px; padding: 14px 16px;
               box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.sector-chip { display: inline-block; padding: 2px 10px; border-radius: 20px;
               font-size: .75rem; font-weight: 600; color: #fff; margin-bottom: 8px; }
.sector-val { font-size: 1.3rem; font-weight: 700; color: #1E293B; }
.sector-sub { font-size: .72rem; color: #94A3B8; }
.bar-bg { background: #F1F5F9; border-radius: 4px; height: 5px; margin-top: 6px; }
.bar-fill { border-radius: 4px; height: 5px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media(max-width:700px){ .two-col { grid-template-columns: 1fr; } }
.mini-table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.mini-table th { padding: 6px 8px; background: #F8FAFC; color: #64748B; font-weight: 600;
                  border-bottom: 1px solid #E2E8F0; text-align: left; }
.mini-table td { padding: 5px 8px; border-bottom: 1px solid #F1F5F9; }
.mini-table tr:hover td { background: #F8FAFC; }
/* Map tab */
.map-layout { display: grid; grid-template-columns: 240px 1fr; gap: 12px; }
@media(max-width:768px){ .map-layout { grid-template-columns: 1fr; } }
#map { height: 520px; border-radius: 10px; }
.metric-list { list-style: none; padding: 0; margin: 0; }
.metric-list li { margin-bottom: 2px; }
.metric-list label { display: block; padding: 5px 8px; border-radius: 6px; cursor: pointer;
                      font-size: .82rem; color: #374151; }
.metric-list input[type=radio] { display: none; }
.metric-list input:checked + label { background: #EFF6FF; color: #2563EB; font-weight: 600; }
.metric-list label:hover { background: #F8FAFC; }
.stat-box { background: #F8FAFC; border-radius: 8px; padding: 10px 12px; font-size: .8rem; }
.stat-row { display: flex; justify-content: space-between; padding: 2px 0; }
.stat-row .sk { color: #94A3B8; }
.stat-row .sv { font-weight: 600; color: #1E293B; }
/* Detail tab */
.detail-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
@media(max-width:768px){ .detail-layout { grid-template-columns: 1fr; } }
/* Ranking tab */
.rank-layout { display: grid; grid-template-columns: 1fr 380px; gap: 12px; }
@media(max-width:900px){ .rank-layout { grid-template-columns: 1fr; } }
.rank-table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.rank-table th { padding: 7px 8px; background: #F8FAFC; color: #64748B; font-weight: 600;
                  border-bottom: 2px solid #E2E8F0; text-align: left; cursor: pointer;
                  user-select: none; white-space: nowrap; position: sticky; top: 0; }
.rank-table th:hover { background: #EFF6FF; }
.rank-table th.sort-asc::after { content: ' ▲'; color: #2563EB; }
.rank-table th.sort-desc::after { content: ' ▼'; color: #2563EB; }
.rank-table td { padding: 5px 8px; border-bottom: 1px solid #F1F5F9; }
.rank-table tr:hover td { background: #F8FAFC; }
.table-wrap { max-height: 560px; overflow-y: auto; border-radius: 8px; border: 1px solid #E2E8F0; }
.score-badge { display: inline-block; padding: 1px 7px; border-radius: 10px;
               font-weight: 600; font-size: .8rem; }
/* Dist tab */
.dist-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
@media(max-width:768px){ .dist-layout { grid-template-columns: 1fr; } }
select.form-select-sm { font-size: .82rem; }
</style>
</head>
<body>

<!-- ── Navbar ─────────────────────────────────────────────────────────────── -->
<div class="navbar">
  <span class="navbar-title">🗺 생활인프라 편리성 모니터링 대시보드</span>
  <span class="badge-cnt" id="data-badge">로딩 중...</span>
</div>

<!-- ── Tabs ───────────────────────────────────────────────────────────────── -->
<div class="tab-bar">
  <button class="tab-btn active" data-tab="overview">📊 요약</button>
  <button class="tab-btn" data-tab="map">🗺 지도</button>
  <button class="tab-btn" data-tab="detail">🔍 시군구 상세</button>
  <button class="tab-btn" data-tab="ranking">🏆 순위 비교</button>
  <button class="tab-btn" data-tab="dist">📈 분포 분석</button>
</div>

<div class="content">

<!-- ══════════════════════════════════════════════════════════════════════════
     TAB 1 : 개요
══════════════════════════════════════════════════════════════════════════ -->
<div id="tab-overview" class="tab-pane active">
  <div class="stat-grid" id="summary-stats"></div>
  <div class="sector-grid" id="sector-cards"></div>
  <div class="two-col">
    <div class="card card-p">
      <div class="card-h">🏆 상위 10개 지역 (종합지수)</div>
      <div id="top10"></div>
    </div>
    <div class="card card-p">
      <div class="card-h">⚠️ 하위 10개 지역 (종합지수)</div>
      <div id="bot10"></div>
    </div>
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════
     TAB 2 : 지도
══════════════════════════════════════════════════════════════════════════ -->
<div id="tab-map" class="tab-pane">
  <div class="map-layout">
    <!-- Left panel -->
    <div>
      <div class="card card-p mb-3" style="padding-bottom:10px">
        <div class="card-h" style="margin-bottom:8px">🎨 색상 분류</div>
        <div style="display:flex;gap:6px">
          <label style="display:flex;align-items:center;gap:4px;font-size:.8rem;cursor:pointer;padding:4px 10px;border-radius:6px;border:1px solid #E2E8F0;flex:1;justify-content:center" id="lbl-equal">
            <input type="radio" name="classify" value="equal" checked style="display:none">
            <span>등간격</span>
          </label>
          <label style="display:flex;align-items:center;gap:4px;font-size:.8rem;cursor:pointer;padding:4px 10px;border-radius:6px;border:1px solid #E2E8F0;flex:1;justify-content:center" id="lbl-quantile">
            <input type="radio" name="classify" value="quantile" style="display:none">
            <span>분위수</span>
          </label>
        </div>
      </div>
      <div class="card card-p mb-3">
        <div class="card-h">📌 지표 선택</div>
        <ul class="metric-list" id="metric-list"></ul>
      </div>
      <div class="card card-p" id="map-info-card">
        <div style="color:#94A3B8;font-size:.82rem">지도에서 시군구를 클릭하면 상세 정보가 표시됩니다.</div>
      </div>
    </div>
    <!-- Map + Table -->
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="card" style="overflow:hidden">
        <div id="map"></div>
      </div>
      <div class="card card-p">
        <div class="card-h" id="map-table-title">상위 20개 지역</div>
        <div id="map-top20" style="max-height:220px;overflow-y:auto"></div>
      </div>
    </div>
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════
     TAB 3 : 시군구 상세
══════════════════════════════════════════════════════════════════════════ -->
<div id="tab-detail" class="tab-pane">
  <div style="display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap">
    <select class="form-select form-select-sm" id="sido-sel" style="width:auto">
      <option value="">— 시도 선택 —</option>
    </select>
    <select class="form-select form-select-sm" id="sgg-sel" style="width:auto" disabled>
      <option value="">— 시군구 선택 —</option>
    </select>
    <span class="badge-cnt" id="detail-rank-badge" style="display:none"></span>
  </div>
  <div id="detail-content" style="display:none">
    <div class="detail-layout">
      <div class="card card-p">
        <div class="card-h">5개 부문 편리성 vs 전국 평균</div>
        <div id="radar-chart" style="height:320px"></div>
      </div>
      <div class="card card-p">
        <div class="card-h">공급 · 향유 · 충족 수준 비교</div>
        <div id="bar-chart" style="height:320px"></div>
      </div>
    </div>
    <div class="card card-p">
      <div class="card-h">부문별 상세 지표</div>
      <div id="detail-table"></div>
    </div>
  </div>
  <div id="detail-placeholder" style="color:#94A3B8;font-size:.875rem;padding:40px 0;text-align:center">
    시도 → 시군구 순서로 선택하면 분석 결과가 표시됩니다.
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════
     TAB 4 : 순위 비교
══════════════════════════════════════════════════════════════════════════ -->
<div id="tab-ranking" class="tab-pane">
  <div class="rank-layout">
    <!-- Table -->
    <div class="card card-p">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap">
        <input class="form-control form-control-sm" id="rank-search"
               placeholder="시군구 검색..." style="width:160px">
        <span class="badge-cnt" id="rank-count"></span>
      </div>
      <div class="table-wrap">
        <table class="rank-table" id="rank-table">
          <thead id="rank-thead"></thead>
          <tbody id="rank-tbody"></tbody>
        </table>
      </div>
    </div>
    <!-- Compare panel -->
    <div>
      <div class="card card-p mb-3">
        <div class="card-h">지역 비교 (레이더)</div>
        <div style="display:flex;gap:6px;margin-bottom:10px">
          <select class="form-select form-select-sm" id="cmp-a" style="flex:1"></select>
          <select class="form-select form-select-sm" id="cmp-b" style="flex:1"></select>
        </div>
        <div id="cmp-radar" style="height:260px"></div>
      </div>
      <div class="card card-p">
        <div id="cmp-table"></div>
      </div>
    </div>
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════
     TAB 5 : 분포 분석
══════════════════════════════════════════════════════════════════════════ -->
<div id="tab-dist" class="tab-pane">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap">
    <label style="font-size:.82rem;color:#64748B">지표:</label>
    <select class="form-select form-select-sm" id="dist-metric" style="width:220px"></select>
  </div>
  <div class="dist-layout">
    <div class="card card-p">
      <div class="card-h">히스토그램</div>
      <div id="hist-chart" style="height:280px"></div>
    </div>
    <div class="card card-p">
      <div class="card-h">시도별 박스플롯</div>
      <div id="box-chart" style="height:280px"></div>
    </div>
  </div>
  <div class="card card-p">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap">
      <div style="display:flex;align-items:center;gap:6px">
        <label style="font-size:.82rem;color:#64748B">X축:</label>
        <select class="form-select form-select-sm" id="sc-x" style="width:200px"></select>
      </div>
      <div style="display:flex;align-items:center;gap:6px">
        <label style="font-size:.82rem;color:#64748B">Y축:</label>
        <select class="form-select form-select-sm" id="sc-y" style="width:200px"></select>
      </div>
    </div>
    <div class="card-h">산점도</div>
    <div id="scatter-chart" style="height:340px"></div>
  </div>
</div>

</div><!-- /content -->

<!-- ── 임베드 데이터 ───────────────────────────────────────────────────────── -->
<script>
/* __DATA__ */
</script>

<!-- ── 앱 로직 ───────────────────────────────────────────────────────────── -->
<script>
// ══════════════════════════════════════════════════════════════════════════════
// CONFIG
// ══════════════════════════════════════════════════════════════════════════════
const SEC = {
  edu:  { label: '교육학습', color: '#4472C4' },
  care: { label: '돌봄복지', color: '#ED7D31' },
  med:  { label: '보건의료', color: '#70AD47' },
  safe: { label: '안전치안', color: '#E84040' },
  cult: { label: '체육문화', color: '#7030A0' },
};

const METRIC_DEFS = [
  { key: 'infra_idx',  label: '종합 편리성 지수',  group: '종합' },
  { key: 'edu_conv',   label: '교육학습 편리성',   group: '부문 편리성' },
  { key: 'care_conv',  label: '돌봄복지 편리성',   group: '부문 편리성' },
  { key: 'med_conv',   label: '보건의료 편리성',   group: '부문 편리성' },
  { key: 'safe_conv',  label: '안전치안 편리성',   group: '부문 편리성' },
  { key: 'cult_conv',  label: '체육문화 편리성',   group: '부문 편리성' },
  { key: 'edu_sup',    label: '교육학습 공급수준', group: '공급수준' },
  { key: 'care_sup',   label: '돌봄복지 공급수준', group: '공급수준' },
  { key: 'med_sup',    label: '보건의료 공급수준', group: '공급수준' },
  { key: 'safe_sup',   label: '안전치안 공급수준', group: '공급수준' },
  { key: 'cult_sup',   label: '체육문화 공급수준', group: '공급수준' },
  { key: 'edu_pop',    label: '교육학습 향유수준', group: '향유수준' },
  { key: 'care_pop',   label: '돌봄복지 향유수준', group: '향유수준' },
  { key: 'med_pop',    label: '보건의료 향유수준', group: '향유수준' },
  { key: 'safe_pop',   label: '안전치안 향유수준', group: '향유수준' },
  { key: 'cult_pop',   label: '체육문화 향유수준', group: '향유수준' },
  { key: 'edu_acc',    label: '교육학습 충족수준', group: '충족수준' },
  { key: 'care_acc',   label: '돌봄복지 충족수준', group: '충족수준' },
  { key: 'med_acc',    label: '보건의료 충족수준', group: '충족수준' },
  { key: 'safe_acc',   label: '안전치안 충족수준', group: '충족수준' },
  { key: 'cult_acc',   label: '체육문화 충족수준', group: '충족수준' },
];

// ══════════════════════════════════════════════════════════════════════════════
// UTILS
// ══════════════════════════════════════════════════════════════════════════════
const f1 = v => (v == null || isNaN(+v)) ? '-' : (+v).toFixed(1);
const f3 = v => (v == null || isNaN(+v)) ? '-' : (+v).toFixed(3);
const fAuto = (v, key) => key === 'infra_idx' ? f1(v) : f3(v);

function getVals(key) {
  return RECORDS.map(r => r[key]).filter(v => v != null && !isNaN(+v));
}

function getRange(key) {
  const vals = getVals(key);
  return [Math.min(...vals), Math.max(...vals)];
}

function getMean(key) {
  const vals = getVals(key);
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

// 상위 백분위 (높을수록 좋음) — "상위 X%"
function upperPct(key, value) {
  const vals = getVals(key).sort((a, b) => a - b);
  const below = vals.filter(v => v < value).length;
  return Math.round((1 - below / vals.length) * 100);
}

// 전국 순위 (1위 = 최고)
function natRank(key, value) {
  const vals = getVals(key).sort((a, b) => b - a);
  return vals.findIndex(v => v <= value) + 1;
}

function colorFor(val, min, max) {
  return chroma.scale(['#1D4ED8','#93C5FD','#FCA5A5','#DC2626']).domain([min, max])(val).hex();
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB ROUTING
// ══════════════════════════════════════════════════════════════════════════════
let mapInited = false;
let rankInited = false;
let distInited = false;

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    document.getElementById('tab-' + tab).classList.add('active');

    if (tab === 'map' && !mapInited)     { initMap(); mapInited = true; }
    if (tab === 'ranking' && !rankInited){ initRanking(); rankInited = true; }
    if (tab === 'dist' && !distInited)   { initDist(); distInited = true; }
  });
});

// ══════════════════════════════════════════════════════════════════════════════
// TAB 1 : 개요
// ══════════════════════════════════════════════════════════════════════════════
function renderOverview() {
  const sorted = [...RECORDS].sort((a, b) => (b.infra_idx || 0) - (a.infra_idx || 0));
  const avg = getMean('infra_idx');
  const top = sorted[0], bot = sorted[sorted.length - 1];

  document.getElementById('data-badge').textContent = RECORDS.length + '개 시군구';

  // Summary stats
  document.getElementById('summary-stats').innerHTML = `
    <div class="stat-card">
      <div class="stat-label">분석 시군구</div>
      <div class="stat-val">${RECORDS.length}</div>
      <div class="stat-sub">개 행정구역</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">전국 평균 편리성 지수</div>
      <div class="stat-val" style="color:#2563EB">${f1(avg)}</div>
      <div class="stat-sub">점 (0 ~ 100)</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">최고 지역 🥇</div>
      <div class="stat-val" style="font-size:1rem">${top.sido_nm_k} ${top.sgg_nm_k}</div>
      <div class="stat-sub" style="color:#16A34A">${f1(top.infra_idx)}점</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">최저 지역 ⚠️</div>
      <div class="stat-val" style="font-size:1rem">${bot.sido_nm_k} ${bot.sgg_nm_k}</div>
      <div class="stat-sub" style="color:#DC2626">${f1(bot.infra_idx)}점</div>
    </div>`;

  // Sector cards
  document.getElementById('sector-cards').innerHTML = Object.entries(SEC).map(([k, s]) => {
    const vals = getVals(k + '_conv');
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    const mn = Math.min(...vals), mx = Math.max(...vals);
    const pct = (avg - mn) / (mx - mn) * 100;
    return `<div class="sector-card">
      <span class="sector-chip" style="background:${s.color}">${s.label}</span>
      <div class="sector-val">${f3(avg)}</div>
      <div class="sector-sub">전국 평균 (0~1)</div>
      <div class="bar-bg"><div class="bar-fill" style="width:${pct}%;background:${s.color}"></div></div>
      <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:.7rem;color:#94A3B8">
        <span>최소 ${f3(mn)}</span><span>최대 ${f3(mx)}</span>
      </div>
    </div>`;
  }).join('');

  // Top / Bottom 10
  function miniTable(rows) {
    return `<table class="mini-table">
      <thead><tr><th>#</th><th>시도</th><th>시군구</th><th>종합지수</th></tr></thead>
      <tbody>${rows.slice(0, 10).map((r, i) => {
        const c = colorFor(r.infra_idx, 0, 100);
        return `<tr>
          <td style="color:#94A3B8">${i + 1}</td>
          <td>${r.sido_nm_k}</td>
          <td><strong>${r.sgg_nm_k}</strong></td>
          <td><span class="score-badge" style="background:${c}22;color:${c}">${f1(r.infra_idx)}</span></td>
        </tr>`;
      }).join('')}</tbody>
    </table>`;
  }
  document.getElementById('top10').innerHTML = miniTable(sorted);
  document.getElementById('bot10').innerHTML = miniTable([...sorted].reverse());
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 2 : 지도
// ══════════════════════════════════════════════════════════════════════════════
let leafMap = null, geoLayer = null, legendCtrl = null;
let curMetric = 'infra_idx';
let curClassify = 'equal'; // 'equal' | 'quantile'

function initMap() {
  // Classify toggle
  function updateClassifyUI() {
    document.getElementById('lbl-equal').style.cssText    += curClassify === 'equal'    ? ';background:#EFF6FF;color:#2563EB;border-color:#93C5FD;font-weight:600' : ';background:#fff;color:#374151;border-color:#E2E8F0;font-weight:400';
    document.getElementById('lbl-quantile').style.cssText += curClassify === 'quantile' ? ';background:#EFF6FF;color:#2563EB;border-color:#93C5FD;font-weight:600' : ';background:#fff;color:#374151;border-color:#E2E8F0;font-weight:400';
  }
  updateClassifyUI();
  document.querySelectorAll('input[name="classify"]').forEach(inp => {
    inp.addEventListener('change', () => {
      curClassify = inp.value;
      updateClassifyUI();
      renderChoropleth();
    });
  });

  // Metric radio list
  let curGroup = '';
  document.getElementById('metric-list').innerHTML = METRIC_DEFS.map(m => {
    let groupHtml = '';
    if (m.group !== curGroup) {
      curGroup = m.group;
      groupHtml = `<li style="padding:6px 4px 2px;font-size:.7rem;color:#94A3B8;font-weight:600;letter-spacing:.05em">${m.group.toUpperCase()}</li>`;
    }
    return `${groupHtml}<li>
      <input type="radio" name="metric" id="m_${m.key}" value="${m.key}" ${m.key === curMetric ? 'checked' : ''}>
      <label for="m_${m.key}">${m.label}</label>
    </li>`;
  }).join('');

  document.querySelectorAll('#metric-list input').forEach(inp => {
    inp.addEventListener('change', () => {
      curMetric = inp.value;
      renderChoropleth();
      renderMapTable();
    });
  });

  leafMap = L.map('map', { preferCanvas: true }).setView([36.5, 127.8], 7);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CartoDB',
    subdomains: 'abcd', maxZoom: 19
  }).addTo(leafMap);

  renderChoropleth();
  renderMapTable();
}

function renderChoropleth() {
  if (!leafMap) return;
  if (geoLayer)   { geoLayer.remove();   geoLayer = null; }
  if (legendCtrl) { legendCtrl.remove(); legendCtrl = null; }

  const PALETTE = ['#1D4ED8','#93C5FD','#FCA5A5','#DC2626'];
  const allVals = getVals(curMetric);
  const [mn, mx] = [Math.min(...allVals), Math.max(...allVals)];

  let scale, breaks;
  if (curClassify === 'quantile') {
    breaks = chroma.limits(allVals, 'q', 5);
    scale  = chroma.scale(PALETTE).classes(breaks);
  } else {
    scale  = chroma.scale(PALETTE).domain([mn, mx]);
  }

  geoLayer = L.geoJSON(GEOJSON, {
    style: ft => {
      const v = ft.properties[curMetric];
      return {
        fillColor:   v != null ? scale(v).hex() : '#ccc',
        fillOpacity: 0.75,
        color: '#fff',
        weight: 0.6,
      };
    },
    onEachFeature: (ft, layer) => {
      const p = ft.properties;
      const label = METRIC_DEFS.find(m => m.key === curMetric)?.label || curMetric;
      layer.bindTooltip(
        `<strong>${p.sido_nm_k} ${p.sgg_nm_k}</strong><br>${label}: <b>${fAuto(p[curMetric], curMetric)}</b>`,
        { sticky: true, direction: 'top' }
      );
      layer.on('click', () => showMapInfo(p));
    }
  }).addTo(leafMap);

  // Legend
  legendCtrl = L.control({ position: 'bottomright' });
  legendCtrl.onAdd = () => {
    const div = L.DomUtil.create('div');
    div.style.cssText = 'background:#fff;padding:10px 12px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.15);font-size:.75rem;min-width:130px';
    const label = METRIC_DEFS.find(m => m.key === curMetric)?.label || curMetric;
    let html = `<div style="font-weight:600;margin-bottom:6px;color:#374151">${label}</div>`;
    if (curClassify === 'quantile') {
      // 분위수: breaks 구간별 표시
      for (let i = breaks.length - 2; i >= 0; i--) {
        const mid = (breaks[i] + breaks[i+1]) / 2;
        html += `<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
          <div style="width:14px;height:14px;border-radius:3px;background:${scale(mid).hex()}"></div>
          <span>${fAuto(breaks[i], curMetric)} – ${fAuto(breaks[i+1], curMetric)}</span>
        </div>`;
      }
    } else {
      const steps = 5;
      for (let i = steps; i >= 0; i--) {
        const v = mn + (mx - mn) * (i / steps);
        html += `<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
          <div style="width:14px;height:14px;border-radius:3px;background:${scale(v).hex()}"></div>
          <span>${fAuto(v, curMetric)}</span>
        </div>`;
      }
    }
    div.innerHTML = html;
    return div;
  };
  legendCtrl.addTo(leafMap);
}

function showMapInfo(p) {
  const [mn, mx] = getRange(curMetric);
  const label = METRIC_DEFS.find(m => m.key === curMetric)?.label || curMetric;
  const val = p[curMetric];
  const rank = val != null ? natRank(curMetric, val) : null;

  document.getElementById('map-info-card').innerHTML = `
    <div style="font-weight:700;font-size:.95rem;margin-bottom:4px">${p.sido_nm_k} ${p.sgg_nm_k}</div>
    <div style="font-size:.75rem;color:#94A3B8;margin-bottom:8px">${label}</div>
    <div style="font-size:1.5rem;font-weight:700;color:${val != null ? colorFor(val, mn, mx) : '#999'}">
      ${fAuto(val, curMetric)}
    </div>
    ${rank ? `<div style="font-size:.75rem;color:#64748B;margin-top:2px">전국 ${rank}위 / ${RECORDS.length}</div>` : ''}
    <hr style="margin:10px 0;border-color:#F1F5F9">
    <div style="font-size:.75rem;font-weight:600;margin-bottom:6px;color:#64748B">종합지수 <span style="color:#1E293B;font-size:.9rem">${f1(p.infra_idx)}점</span></div>
    <div style="display:flex;flex-wrap:wrap;gap:4px">
      ${Object.entries(SEC).map(([k, s]) =>
        `<span class="score-badge" style="background:${s.color}22;color:${s.color}">${s.label} ${f3(p[k + '_conv'])}</span>`
      ).join('')}
    </div>`;
}

function renderMapTable() {
  const label = METRIC_DEFS.find(m => m.key === curMetric)?.label || curMetric;
  document.getElementById('map-table-title').textContent = `상위 20개 지역 — ${label}`;
  const sorted = [...RECORDS].filter(r => r[curMetric] != null)
    .sort((a, b) => b[curMetric] - a[curMetric]);
  const [mn, mx] = getRange(curMetric);
  const rows = sorted.slice(0, 20).map((r, i) => {
    const c = colorFor(r[curMetric], mn, mx);
    return `<tr>
      <td style="color:#94A3B8">${i + 1}</td>
      <td>${r.sido_nm_k}</td>
      <td><strong>${r.sgg_nm_k}</strong></td>
      <td><span class="score-badge" style="background:${c}22;color:${c}">${fAuto(r[curMetric], curMetric)}</span></td>
      <td>${f1(r.infra_idx)}</td>
    </tr>`;
  }).join('');
  document.getElementById('map-top20').innerHTML = `
    <table class="mini-table">
      <thead><tr><th>#</th><th>시도</th><th>시군구</th><th>${label}</th><th>종합지수</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 3 : 시군구 상세
// ══════════════════════════════════════════════════════════════════════════════
let radarChart = null, barChart = null;

function initDetail() {
  const sidos = [...new Set(RECORDS.map(r => r.sido_nm_k))].sort();
  const sidoSel = document.getElementById('sido-sel');
  sidos.forEach(s => sidoSel.innerHTML += `<option value="${s}">${s}</option>`);

  sidoSel.addEventListener('change', () => {
    const sido = sidoSel.value;
    const sggSel = document.getElementById('sgg-sel');
    sggSel.innerHTML = '<option value="">— 시군구 선택 —</option>';
    sggSel.disabled = !sido;
    if (sido) {
      RECORDS.filter(r => r.sido_nm_k === sido)
        .sort((a, b) => a.sgg_nm_k.localeCompare(b.sgg_nm_k))
        .forEach(r => { sggSel.innerHTML += `<option value="${r.sgg_cd}">${r.sgg_nm_k}</option>`; });
    }
    document.getElementById('detail-content').style.display = 'none';
    document.getElementById('detail-placeholder').style.display = 'block';
  });

  document.getElementById('sgg-sel').addEventListener('change', function () {
    const rec = RECORDS.find(r => r.sgg_cd === this.value);
    if (rec) renderDetail(rec);
  });
}

function renderDetail(rec) {
  document.getElementById('detail-content').style.display = 'block';
  document.getElementById('detail-placeholder').style.display = 'none';

  const rank = natRank('infra_idx', rec.infra_idx);
  const pct  = upperPct('infra_idx', rec.infra_idx);
  document.getElementById('detail-rank-badge').style.display = 'inline-block';
  document.getElementById('detail-rank-badge').textContent =
    `종합지수 ${f1(rec.infra_idx)}점 | 전국 ${rank}위 / ${RECORDS.length} (상위 ${pct}%)`;

  const secKeys = Object.keys(SEC);
  const secLabels = secKeys.map(k => SEC[k].label);
  const natAvg = secKeys.map(k => +getMean(k + '_conv').toFixed(3));
  const recConv = secKeys.map(k => +(rec[k + '_conv'] || 0).toFixed(3));

  // Radar
  if (!radarChart) radarChart = echarts.init(document.getElementById('radar-chart'));
  radarChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { data: ['선택 지역', '전국 평균'], bottom: 0, textStyle: { fontSize: 11 } },
    radar: {
      indicator: secLabels.map(name => ({ name, max: 1 })),
      radius: '60%',
      axisName: { fontSize: 11 }
    },
    series: [{
      type: 'radar',
      data: [
        { value: recConv,  name: '선택 지역',
          lineStyle: { color: '#2563EB' }, itemStyle: { color: '#2563EB' }, areaStyle: { opacity: .15 } },
        { value: natAvg, name: '전국 평균',
          lineStyle: { color: '#94A3B8', type: 'dashed' }, itemStyle: { color: '#94A3B8' }, areaStyle: { opacity: .05 } },
      ]
    }]
  }, true);

  // Bar
  if (!barChart) barChart = echarts.init(document.getElementById('bar-chart'));
  const dims = [
    { sfx: 'sup', label: '공급수준', color: '#60A5FA' },
    { sfx: 'pop', label: '향유수준', color: '#34D399' },
    { sfx: 'acc', label: '충족수준', color: '#F472B6' },
  ];
  barChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: dims.map(d => d.label), bottom: 0, textStyle: { fontSize: 11 } },
    xAxis: { data: secLabels, axisLabel: { interval: 0, fontSize: 11 } },
    yAxis: { type: 'value', max: 1, min: 0, axisLabel: { fontSize: 10 } },
    grid: { bottom: 50 },
    series: dims.map(d => ({
      name: d.label, type: 'bar', barGap: '10%',
      itemStyle: { color: d.color },
      data: secKeys.map(k => +(rec[k + '_' + d.sfx] || 0).toFixed(3)),
    }))
  }, true);

  // Detail table
  const [mnI, mxI] = getRange('infra_idx');
  const tableRows = secKeys.map(k => {
    const s = SEC[k];
    const cv = rec[k + '_conv'];
    const r = natRank(k + '_conv', cv);
    const p = upperPct(k + '_conv', cv);
    const [mn, mx] = getRange(k + '_conv');
    const c = colorFor(cv, mn, mx);
    return `<tr>
      <td><span class="sector-chip" style="background:${s.color}">${s.label}</span></td>
      <td><span class="score-badge" style="background:${c}22;color:${c}">${f3(cv)}</span></td>
      <td style="color:#64748B;font-size:.8rem">${r}위 (상위 ${p}%)</td>
      <td>${f3(rec[k + '_sup'])}</td>
      <td>${f3(rec[k + '_pop'])}</td>
      <td>${f3(rec[k + '_acc'])}</td>
    </tr>`;
  }).join('');

  document.getElementById('detail-table').innerHTML = `
    <table class="mini-table">
      <thead><tr>
        <th>부문</th><th>편리성 지수</th><th>전국 순위</th>
        <th>공급수준</th><th>향유수준</th><th>충족수준</th>
      </tr></thead>
      <tbody>${tableRows}</tbody>
    </table>`;
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 4 : 순위 비교
// ══════════════════════════════════════════════════════════════════════════════
let rankSort = { key: 'infra_idx', dir: -1 };
let cmpChart = null;

const RANK_COLS = [
  { key: 'infra_idx', label: '종합지수' },
  { key: 'edu_conv',  label: '교육학습' },
  { key: 'care_conv', label: '돌봄복지' },
  { key: 'med_conv',  label: '보건의료' },
  { key: 'safe_conv', label: '안전치안' },
  { key: 'cult_conv', label: '체육문화' },
];

function initRanking() {
  // Populate compare dropdowns
  const optHtml = RECORDS.map(r =>
    `<option value="${r.sgg_cd}">${r.sido_nm_k} ${r.sgg_nm_k}</option>`
  ).join('');
  document.getElementById('cmp-a').innerHTML = '<option value="">A 선택</option>' + optHtml;
  document.getElementById('cmp-b').innerHTML = '<option value="">B 선택</option>' + optHtml;
  ['cmp-a', 'cmp-b'].forEach(id =>
    document.getElementById(id).addEventListener('change', renderComparison)
  );

  renderRankTable();

  document.getElementById('rank-search').addEventListener('input', () => {
    rankSort = { key: 'infra_idx', dir: -1 };
    renderRankTable();
  });
}

function renderRankTable() {
  const q = document.getElementById('rank-search').value.toLowerCase();
  const filtered = RECORDS.filter(r =>
    !q || r.sgg_nm_k.includes(q) || r.sido_nm_k.includes(q)
  ).sort((a, b) => rankSort.dir * ((b[rankSort.key] || 0) - (a[rankSort.key] || 0)));

  document.getElementById('rank-count').textContent = filtered.length + '개';

  const thHtml = RANK_COLS.map(c => {
    const cls = c.key === rankSort.key ? (rankSort.dir < 0 ? 'sort-desc' : 'sort-asc') : '';
    return `<th class="${cls}" data-key="${c.key}">${c.label}</th>`;
  }).join('');

  document.getElementById('rank-thead').innerHTML =
    `<tr><th>#</th><th>시도</th><th>시군구</th>${thHtml}</tr>`;

  const rows = filtered.slice(0, 300).map((r, i) => {
    const cells = RANK_COLS.map(c => {
      const v = r[c.key];
      const [mn, mx] = getRange(c.key);
      const col = v != null ? colorFor(v, mn, mx) : '#999';
      return `<td><span style="color:${col};font-weight:600">${fAuto(v, c.key)}</span></td>`;
    }).join('');
    return `<tr><td style="color:#94A3B8">${i + 1}</td><td>${r.sido_nm_k}</td><td><strong>${r.sgg_nm_k}</strong></td>${cells}</tr>`;
  }).join('');
  document.getElementById('rank-tbody').innerHTML = rows;

  // Sort click
  document.querySelectorAll('#rank-thead th[data-key]').forEach(th => {
    th.addEventListener('click', () => {
      if (rankSort.key === th.dataset.key) rankSort.dir *= -1;
      else { rankSort.key = th.dataset.key; rankSort.dir = -1; }
      renderRankTable();
    });
  });
}

function renderComparison() {
  const a = RECORDS.find(r => r.sgg_cd === document.getElementById('cmp-a').value);
  const b = RECORDS.find(r => r.sgg_cd === document.getElementById('cmp-b').value);
  if (!a && !b) return;

  const secKeys = Object.keys(SEC);
  const secLabels = secKeys.map(k => SEC[k].label);
  const series = [];
  if (a) series.push({
    value: secKeys.map(k => +(a[k + '_conv'] || 0).toFixed(3)),
    name: `${a.sgg_nm_k}`,
    lineStyle: { color: '#2563EB' }, itemStyle: { color: '#2563EB' }, areaStyle: { opacity: .15 }
  });
  if (b) series.push({
    value: secKeys.map(k => +(b[k + '_conv'] || 0).toFixed(3)),
    name: `${b.sgg_nm_k}`,
    lineStyle: { color: '#EF4444' }, itemStyle: { color: '#EF4444' }, areaStyle: { opacity: .15 }
  });

  if (!cmpChart) cmpChart = echarts.init(document.getElementById('cmp-radar'));
  cmpChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { data: series.map(s => s.name), bottom: 0, textStyle: { fontSize: 11 } },
    radar: {
      indicator: secLabels.map(name => ({ name, max: 1 })),
      radius: '55%', axisName: { fontSize: 11 }
    },
    series: [{ type: 'radar', data: series }]
  }, true);

  if (a && b) {
    const rows = secKeys.map(k => {
      const s = SEC[k];
      const av = a[k + '_conv'], bv = b[k + '_conv'];
      const diff = ((av || 0) - (bv || 0)).toFixed(3);
      const col = +diff > 0 ? '#16A34A' : +diff < 0 ? '#DC2626' : '#94A3B8';
      return `<tr>
        <td><span class="sector-chip" style="background:${s.color}">${s.label}</span></td>
        <td>${f3(av)}</td><td>${f3(bv)}</td>
        <td style="color:${col};font-weight:600">${+diff > 0 ? '+' : ''}${diff}</td>
      </tr>`;
    }).join('');
    document.getElementById('cmp-table').innerHTML = `
      <table class="mini-table">
        <thead><tr><th>부문</th><th>${a.sgg_nm_k}</th><th>${b.sgg_nm_k}</th><th>차이(A-B)</th></tr></thead>
        <tbody>${rows}</tbody>
        <tfoot><tr style="background:#F8FAFC;font-weight:700">
          <td>종합지수</td>
          <td>${f1(a.infra_idx)}</td><td>${f1(b.infra_idx)}</td>
          <td style="color:${a.infra_idx > b.infra_idx ? '#16A34A' : '#DC2626'}">
            ${a.infra_idx > b.infra_idx ? '+' : ''}${(a.infra_idx - b.infra_idx).toFixed(1)}
          </td>
        </tr></tfoot>
      </table>`;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 5 : 분포 분석
// ══════════════════════════════════════════════════════════════════════════════
let histChart = null, boxChart = null, scatterChart = null;

const DIST_METRICS = METRIC_DEFS; // 종합·편리성·공급·향유·충족 전체

function initDist() {
  const optHtml = DIST_METRICS.map(m => `<option value="${m.key}">${m.label}</option>`).join('');
  document.getElementById('dist-metric').innerHTML = optHtml;
  document.getElementById('sc-x').innerHTML = optHtml;
  document.getElementById('sc-y').innerHTML = optHtml;
  document.getElementById('sc-y').selectedIndex = 1;

  document.getElementById('dist-metric').addEventListener('change', () => renderDistCharts());
  document.getElementById('sc-x').addEventListener('change', () => renderScatter());
  document.getElementById('sc-y').addEventListener('change', () => renderScatter());

  renderDistCharts();
  renderScatter();
}

function renderDistCharts() {
  const key   = document.getElementById('dist-metric').value;
  const label = DIST_METRICS.find(m => m.key === key)?.label || key;
  const vals  = getVals(key).sort((a, b) => a - b);
  const mn = vals[0], mx = vals[vals.length - 1];

  // Histogram
  const BINS = 20;
  const step = (mx - mn) / BINS;
  const counts = new Array(BINS).fill(0);
  vals.forEach(v => { const i = Math.min(Math.floor((v - mn) / step), BINS - 1); counts[i]++; });
  const xLabels = Array.from({ length: BINS }, (_, i) => (mn + i * step + step / 2).toFixed(key === 'infra_idx' ? 1 : 3));

  if (!histChart) histChart = echarts.init(document.getElementById('hist-chart'));
  histChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: xLabels, axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value', name: '빈도' },
    series: [{ type: 'bar', data: counts, itemStyle: { color: '#60A5FA' }, barWidth: '90%' }]
  }, true);

  // Boxplot by 시도
  const sidos = [...new Set(RECORDS.map(r => r.sido_nm_k))].sort();
  const boxData = sidos.map(sido => {
    const sv = RECORDS.filter(r => r.sido_nm_k === sido).map(r => r[key])
               .filter(v => v != null).sort((a, b) => a - b);
    if (sv.length < 4) return null;
    const q1 = sv[Math.floor(sv.length * .25)];
    const med = sv[Math.floor(sv.length * .5)];
    const q3 = sv[Math.floor(sv.length * .75)];
    return [sv[0], q1, med, q3, sv[sv.length - 1]];
  });
  const validSidos = sidos.filter((_, i) => boxData[i] != null);
  const validBox   = boxData.filter(v => v != null);

  if (!boxChart) boxChart = echarts.init(document.getElementById('box-chart'));
  boxChart.setOption({
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: validSidos, axisLabel: { rotate: 45, fontSize: 9 } },
    yAxis: { type: 'value' },
    grid: { bottom: 70 },
    series: [{ type: 'boxplot', data: validBox, itemStyle: { color: '#34D399', borderColor: '#059669' } }]
  }, true);
}

function linReg(pts) {
  const n = pts.length;
  if (n < 2) return null;
  let sx=0, sy=0, sxy=0, sxx=0, syy=0;
  pts.forEach(([x,y]) => { sx+=x; sy+=y; sxy+=x*y; sxx+=x*x; syy+=y*y; });
  const denom = n*sxx - sx*sx;
  if (Math.abs(denom) < 1e-12) return null;
  const slope = (n*sxy - sx*sy) / denom;
  const intercept = (sy - slope*sx) / n;
  const yMean = sy/n;
  const ssTot = syy - n*yMean*yMean;
  const ssRes = pts.reduce((acc,[x,y]) => acc + Math.pow(y-(slope*x+intercept),2), 0);
  const r2 = ssTot > 1e-12 ? 1 - ssRes/ssTot : 0;
  return { slope, intercept, r2 };
}

function renderScatter() {
  const xKey   = document.getElementById('sc-x').value;
  const yKey   = document.getElementById('sc-y').value;
  const xLabel = DIST_METRICS.find(m => m.key === xKey)?.label || xKey;
  const yLabel = DIST_METRICS.find(m => m.key === yKey)?.label || yKey;

  const data = RECORDS
    .filter(r => r[xKey] != null && r[yKey] != null)
    .map(r => [r[xKey], r[yKey], r.sido_nm_k + ' ' + r.sgg_nm_k]);

  // 회귀선 계산
  const reg = linReg(data.map(d => [d[0], d[1]]));
  const xVals = data.map(d => d[0]);
  const xMin = Math.min(...xVals), xMax = Math.max(...xVals);
  const regLine = reg ? [[xMin, reg.slope*xMin+reg.intercept], [xMax, reg.slope*xMax+reg.intercept]] : [];
  const regLabel = reg ? `y = ${reg.slope.toFixed(3)}x + ${reg.intercept.toFixed(3)}  (R² = ${reg.r2.toFixed(3)})` : '';

  if (!scatterChart) scatterChart = echarts.init(document.getElementById('scatter-chart'));
  scatterChart.setOption({
    tooltip: {
      formatter: p => p.seriesIndex === 0
        ? `${p.data[2]}<br>${xLabel}: ${p.data[0]}<br>${yLabel}: ${p.data[1]}`
        : regLabel
    },
    xAxis: { name: xLabel, nameLocation: 'middle', nameGap: 28, type: 'value', axisLabel: { fontSize: 10 } },
    yAxis: { name: yLabel, nameLocation: 'middle', nameGap: 40, type: 'value', axisLabel: { fontSize: 10 } },
    graphic: reg ? [{
      type: 'text', left: 'center', top: 8,
      style: { text: regLabel, font: '11px sans-serif', fill: '#EF4444', textAlign: 'center' }
    }] : [],
    series: [
      {
        type: 'scatter',
        data,
        symbolSize: 6,
        itemStyle: { color: '#60A5FA', opacity: .65 }
      },
      {
        type: 'line',
        data: regLine,
        showSymbol: false,
        lineStyle: { color: '#EF4444', width: 1.5, type: 'dashed' },
        tooltip: { show: false },
        z: 2
      }
    ]
  }, true);
}

// ══════════════════════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════════════════════
renderOverview();
initDetail();
</script>
</body>
</html>
"""

# ── 메인 ────────────────────────────────────────────────────────────────────

def main():
    gdf = load()

    print('[4/5] GeoJSON 생성...')
    geojson = to_geojson(gdf)

    print('[5/5] 레코드 + HTML 생성...')
    records = to_records(gdf)

    print('       HTML 인젝션...')
    data_js = (
        f'const GEOJSON = {json.dumps(geojson, ensure_ascii=False)};\n'
        f'const RECORDS = {json.dumps(records, ensure_ascii=False)};\n'
    )
    html = HTML_TEMPLATE.replace('/* __DATA__ */', data_js)

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)

    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f'[완료] {OUT}  ({size_mb:.1f} MB)')
    print('   브라우저에서 파일을 바로 열면 됩니다.')

if __name__ == '__main__':
    main()
