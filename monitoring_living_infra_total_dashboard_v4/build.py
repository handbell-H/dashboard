#!/usr/bin/env python3
"""
build.py — 생활인프라 편리성 GIS 분석 결과 → 정적 HTML 대시보드 v4 (시계열)

사용법:  python build.py
출력:    dashboard.html  (브라우저에서 바로 열 수 있는 단일 파일)

v4 변경사항 (v3 기반):
  - 입력을 생활인프라_시계열데이터/{연도}/output_test/ 자동 스캔으로 변경
    (연도 폴더를 추가하면 대시보드에 자동 반영)
  - geometry는 1회만 embed, 연도별 속성은 YEARS 사전으로 분리 embed
  - 전역 연도 셀렉터: 요약·지도·상세·비교·분포 탭이 선택 연도로 렌더
  - 신규 "변화분석" 탭: 연도 간 T점수 증감 지도 + 순위변화 상승/하락 표
  - 상세 탭에 연도별 추이 차트 + 순위변화 배지
  - AI 챗봇: 연도 파라미터 지원 + 연도 간 비교(compare_years) 도구

주의: 모든 지수는 연도별 T점수(상대 표준화)라 연도 간 차이는
      '절대 수준 변화'가 아니라 '전국 내 상대적 위치 변화'를 뜻한다.
"""

import geopandas as gpd
import pandas as pd
import json, os, sys

BASE   = os.path.dirname(os.path.abspath(__file__))
TSDATA = os.path.join(BASE, '..', '생활인프라_시계열데이터')
OUT    = os.path.join(BASE, 'dashboard.html')

# 시계열 원본 스키마 → v3 대시보드 스키마
RENAME = {'SIGUNGU_CD': 'sgg_cd', 'SIGUNGU_NM': 'sgg_nm_k', 'SIDO_NM': 'sido_nm_k'}

# ── 데이터 처리 ──────────────────────────────────────────────────────────────

NUM = ['infra_idx','infra_sum',
       'edu_conv','care_conv','med_conv','safe_conv','cult_conv',
       'edu_sup','care_sup','med_sup','safe_sup','cult_sup',
       'edu_pop','care_pop','med_pop','safe_pop','cult_pop',
       'edu_acc','care_acc','med_acc','safe_acc','cult_acc']


def scan_years():
    years = sorted(d for d in os.listdir(TSDATA)
                   if d.isdigit() and os.path.isdir(os.path.join(TSDATA, d, 'output_test')))
    if not years:
        sys.exit(f'연도 폴더를 찾을 수 없습니다: {TSDATA}')
    return years


def load_year(year):
    d = os.path.join(TSDATA, year, 'output_test')
    comp = gpd.read_file(os.path.join(d, 'composite_index.shp')).rename(columns=RENAME)
    sup  = gpd.read_file(os.path.join(d, 'supply_index.shp')).rename(columns=RENAME)
    pop  = gpd.read_file(os.path.join(d, 'service_pop_index.shp')).rename(columns=RENAME)
    acc  = gpd.read_file(os.path.join(d, 'access_index.shp')).rename(columns=RENAME)

    # 종합지수 = 부문별 T점수 평균 (v3 방식)
    comp['infra_idx'] = comp['infra_avg'] if 'infra_avg' in comp.columns else comp['infra_sum']

    sup_df = (sup[['sgg_cd','popall','edu_avg','care_avg','cult_avg','med_avg','safe_avg']]
              .rename(columns={'edu_avg':'edu_sup','care_avg':'care_sup',
                               'cult_avg':'cult_sup','med_avg':'med_sup','safe_avg':'safe_sup'}))
    sup_df['popall'] = sup_df['popall'].round(0).astype('Int64')

    pop_df = (pop[['sgg_cd','edu_avg','care_avg','cult_avg','med_avg','safe_avg']]
              .rename(columns={'edu_avg':'edu_pop','care_avg':'care_pop',
                               'cult_avg':'cult_pop','med_avg':'med_pop','safe_avg':'safe_pop'}))

    acc_df = (acc[['sgg_cd','edu_std','care_std','cult_std','med_std','safe_std']]
              .rename(columns={'edu_std':'edu_acc','care_std':'care_acc',
                               'cult_std':'cult_acc','med_std':'med_acc','safe_std':'safe_acc'}))

    gdf = comp.merge(sup_df, on='sgg_cd', how='left')
    gdf = gdf.merge(pop_df, on='sgg_cd', how='left')
    gdf = gdf.merge(acc_df, on='sgg_cd', how='left')
    # 면적(km²): EPSG:5179 미터 좌표계 geometry에서 직접 계산
    gdf['area'] = (gdf.geometry.area / 1e6).round(2)
    return gdf


def to_geojson(gdf):
    sub = gdf[['sgg_cd','sgg_nm_k','sido_nm_k','popall','area'] + NUM + ['geometry']].copy()
    sub = sub.to_crs(epsg=4326)
    sub['geometry'] = sub['geometry'].simplify(0.001)
    for c in NUM:
        sub[c] = sub[c].round(4)
    return json.loads(sub.to_json())


def to_records(gdf):
    df = pd.DataFrame(gdf[['sgg_cd','sgg_nm_k','sido_nm_k','popall','area'] + NUM]).copy()
    for c in NUM:
        df[c] = df[c].round(4)
    return df.to_dict(orient='records')


# ── HTML 템플릿 ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>생활인프라 편리성 모니터링 대시보드 v4 (시계열)</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://unpkg.com/deck.gl@8.9.35/dist.min.js"></script>
<script>
/* 레이어 등록 부트스트랩 — 본문 스크립트가 waiter 포함 버전으로 교체한다 */
window.LAYER_CACHE = {};
window.__LAYER = function (k, d) { window.LAYER_CACHE[k] = d; };
</script>
<script src="layers/__ACCESS_LATEST__"></script>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chroma-js@2.4.2/chroma.min.js"></script>
<script src="ai_config.js"></script>
<style>
/* ── 디자인 토큰 (거점지도 대시보드 톤) ─────────────────────────────── */
:root {
  --bg:        #ebedef;   /* 페이지 배경 */
  --surface:   #ffffff;   /* 카드 배경 */
  --header:    #3c4b64;   /* 헤더/다크 면 */
  --header-bd: #2c3a55;
  --ink:       #3c4b64;   /* 본문 텍스트 */
  --ink-2:     #768192;   /* 보조 텍스트 */
  --ink-3:     #adb5bd;   /* 흐린 텍스트 */
  --line:      #d8dbe0;   /* 테두리 */
  --line-2:    #ebedef;   /* 옅은 구분선 */
  --soft:      #f8f9fa;   /* 옅은 배경(헤더셀 등) */
  --accent:    #2563EB;   /* 강조(파랑) */
  --accent-sb: rgba(37,99,235,0.08);  /* 강조 옅은 배경 */
  --accent-bd: rgba(37,99,235,0.3);
  --radius:    8px;
  --shadow:    0 1px 4px rgba(0,0,0,.07);
  --shadow-h:  0 4px 12px rgba(0,0,0,.12);
}
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--ink); margin: 0;
       font-family: -apple-system,BlinkMacSystemFont,'Segoe UI','Apple SD Gothic Neo','Malgun Gothic',sans-serif; }

/* ── 헤더 ──────────────────────────────────────────────────────────── */
.navbar { background: var(--header); padding: 0 20px; height: 56px; display: flex; align-items: center;
          gap: 10px; border-bottom: 1px solid var(--header-bd); box-shadow: 0 2px 8px rgba(0,0,0,.2); }
.navbar-title { color: #fff; font-weight: 700; font-size: .95rem; letter-spacing: -.3px; }
.badge-cnt { background: var(--accent-sb); color: var(--accent); font-size: .86rem;
             font-weight: 700; padding: 5px 12px; border-radius: 100px; border: 1px solid var(--accent-bd); }

/* ── 연도쌍 배지 (Y1 vs Y2 비교 대시보드) ──────────────────────────── */
.year-pair-badge { display: inline-flex; align-items: center; gap: 7px; margin-left: 12px;
                   padding: 5px 14px; background: rgba(255,255,255,.1);
                   border: 1px solid rgba(255,255,255,.22); border-radius: 100px;
                   font-size: .82rem; font-weight: 700; color: #fff; }
.year-pair-badge .y1 { color: rgba(255,255,255,.62); }
.year-pair-badge .vs { font-size: .7rem; color: rgba(255,255,255,.45); font-weight: 400; }

/* ── 듀얼 맵 ───────────────────────────────────────────────────────── */
.map-dual { flex: 1; min-height: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.map-dual.single { grid-template-columns: 1fr; }
.map-dual.single .map-cell:not(.latest) { display: none; }
.map-cell { position: relative; overflow: hidden; }
.map-cell .map-year-chip { position: absolute; left: 10px; top: 10px; z-index: 6;
  background: rgba(60,75,100,.92); color: #fff; font-size: .78rem; font-weight: 700;
  padding: 4px 12px; border-radius: 100px; pointer-events: none; }
.map-cell.latest .map-year-chip { background: var(--accent); }
#map, #map1 { position: absolute; inset: 0; }
@media(max-width:900px){ .map-dual { grid-template-columns: 1fr; } }

/* ── 연도 오버레이 공통 ────────────────────────────────────────────── */
.yr1-chip { display:inline-block; padding:1px 7px; border-radius:100px; background:#EEF2F7; color:#64748B; font-size:.7rem; font-weight:700; }
.yr2-chip { display:inline-block; padding:1px 7px; border-radius:100px; background:var(--accent-sb); color:var(--accent); font-size:.7rem; font-weight:700; }

/* ── 탭 내부 연도 셀렉터 (상세·비교) ───────────────────────────────── */
.year-seg-local { display: inline-flex; gap: 2px; padding: 3px; background: var(--soft);
                  border: 1px solid var(--line); border-radius: 100px; }
.year-seg-local button { padding: 4px 14px; border: none; background: none; border-radius: 100px;
                         cursor: pointer; font-size: .8rem; font-weight: 700; color: var(--ink-2); transition: all .15s; }
.year-seg-local button:hover:not(.active) { color: var(--ink); }
.year-seg-local button.active { background: var(--accent); color: #fff; }

/* ── 요약 TOP 표 펼치기 ────────────────────────────────────────────── */
.mini-table-wrap.expanded { max-height: 460px; overflow-y: auto; }
.expand-btn { display: block; width: 100%; margin-top: 8px; padding: 6px 0; border: 1px dashed var(--line);
              background: var(--soft); border-radius: 6px; cursor: pointer; font-size: .76rem;
              font-weight: 700; color: var(--ink-2); transition: all .15s; }
.expand-btn:hover { background: var(--accent-sb); color: var(--accent); border-color: var(--accent-bd); }

/* ── 변화분석 탭 ───────────────────────────────────────────────────── */
.chg-layout { display: grid; grid-template-columns: 1fr 390px; gap: 14px; align-items: start; }
#chg-map { height: calc(100vh - 265px); min-height: 460px; position: relative; }
.chg-side { display: flex; flex-direction: column; gap: 14px; max-height: calc(100vh - 265px); overflow-y: auto; }
.chg-note { font-size: .74rem; color: var(--ink-2); background: #FFF7ED; border: 1px solid #FED7AA;
            border-radius: 6px; padding: 6px 10px; }
.chg-legend { position: absolute; right: 12px; top: 12px; z-index: 5; background: rgba(255,255,255,.95);
              border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow);
              padding: 10px 12px; font-size: .74rem; width: 168px; }
.rank-delta-up   { color: #DC2626; font-weight: 700; }
.rank-delta-down { color: #1D4ED8; font-weight: 700; }
.rank-delta-flat { color: #94A3B8; }
@media (max-width: 1100px) { .chg-layout { grid-template-columns: 1fr; } .chg-side { max-height: none; } }

/* ── 도움말 버튼 / 설명 모달 ───────────────────────────────────────── */
.navbar-spacer { flex: 1; }
.help-btn { background: rgba(255,255,255,.12); color: #fff; border: 1px solid rgba(255,255,255,.25);
            font-size: .82rem; font-weight: 600; padding: 6px 13px; border-radius: 100px; cursor: pointer;
            display: flex; align-items: center; gap: 5px; transition: background .15s; }
.help-btn:hover { background: rgba(255,255,255,.22); }

/* ── AI 챗봇 ───────────────────────────────────────────────────────── */
#chat-toggle-btn { background: rgba(255,255,255,.12); color: #fff; border: 1px solid rgba(255,255,255,.25);
                   font-size: .82rem; font-weight: 600; padding: 6px 13px; border-radius: 100px; cursor: pointer;
                   transition: background .15s; white-space: nowrap; }
#chat-toggle-btn:hover { background: rgba(255,255,255,.22); }
#chat-toggle-btn.open { background: rgba(37,99,235,.5); border-color: rgba(37,99,235,.8); }
#chat-panel { display: none; position: fixed; top: 72px; right: 24px; width: 420px; height: 78vh; max-height: 760px;
              background: var(--surface); border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,.28); z-index: 1100;
              flex-direction: column; overflow: hidden; animation: chatPop .22s cubic-bezier(.4,0,.2,1); }
#chat-panel.open { display: flex; }
@keyframes chatPop { from { opacity: 0; transform: translateY(14px) scale(.98); } to { opacity: 1; transform: none; } }
#chat-panel-header { display: flex; align-items: center; padding: 0 14px; height: 56px; background: var(--header);
                     color: #fff; flex-shrink: 0; border-bottom: 1px solid var(--header-bd); cursor: move; user-select: none; }
#chat-panel-title { font-size: 13px; font-weight: 700; flex: 1; }
#chat-panel-close { background: none; border: none; color: rgba(255,255,255,.6); font-size: 22px; line-height: 1; cursor: pointer; padding: 0 2px; }
#chat-panel-close:hover { color: #fff; }
#chat-apikey-section { padding: 12px 14px; background: var(--soft); border-bottom: 1px solid var(--line-2); flex-shrink: 0; }
#chat-apikey-label { font-size: 11px; font-weight: 700; color: var(--ink-2); text-transform: uppercase; letter-spacing: .5px; margin-bottom: 6px; }
#chat-apikey-row { display: flex; gap: 6px; }
#chat-apikey-input { flex: 1; padding: 7px 10px; border: 1px solid var(--line); border-radius: 6px; font-size: 12px; outline: none; color: var(--ink); background: #fff; }
#chat-apikey-input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(37,99,235,.12); }
#chat-apikey-save { padding: 7px 14px; background: var(--accent); color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 700; white-space: nowrap; }
#chat-apikey-save:hover { background: #1d4ed8; }
#chat-apikey-hint { font-size: 11px; color: var(--ink-3); margin-top: 5px; }
#chat-quick-btns { display: flex; flex-wrap: wrap; gap: 5px; padding: 10px 14px; border-bottom: 1px solid var(--line-2); flex-shrink: 0; }
.chat-quick-btn { padding: 5px 10px; background: var(--soft); border: 1px solid var(--line); border-radius: 100px; cursor: pointer; font-size: 11px; font-weight: 600; color: var(--ink); transition: all .15s; }
.chat-quick-btn:hover { background: var(--accent-sb); border-color: var(--accent-bd); color: var(--accent); }
#chat-messages { flex: 1; overflow-y: auto; padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }
#chat-empty { text-align: center; padding: 30px 10px; color: var(--ink-3); font-size: 12px; line-height: 1.7; }
.chat-msg { display: flex; flex-direction: column; max-width: 92%; }
.chat-msg.user { align-self: flex-end; align-items: flex-end; }
.chat-msg.assistant { align-self: flex-start; align-items: flex-start; }
.chat-bubble { padding: 9px 12px; border-radius: 10px; font-size: 12px; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }
.chat-msg.user .chat-bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 3px; }
.chat-msg.assistant .chat-bubble { background: #f1f5f9; color: var(--ink); border-bottom-left-radius: 3px; border: 1px solid #e2e8f0; }
.chat-bubble.loading { color: var(--ink-3); font-style: italic; }
#chat-input-area { padding: 10px 14px; border-top: 1px solid var(--line-2); flex-shrink: 0; background: #fff; }
#chat-model-row { display: inline-flex; margin-bottom: 8px; gap: 2px; padding: 2px; background: var(--soft); border: 1px solid var(--line); border-radius: 100px; }
.model-seg-btn { padding: 4px 11px; border: none; background: none; border-radius: 100px; cursor: pointer; font-size: 11px; font-weight: 600; color: var(--ink-2); transition: all .15s; }
.model-seg-btn:hover:not(.active) { color: var(--ink); }
.model-seg-btn.active { background: var(--accent); color: #fff; }
#chat-input-row { display: flex; gap: 6px; align-items: flex-end; }
#chat-input { flex: 1; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; font-size: 13px; outline: none; color: var(--ink); background: #fff; resize: none; min-height: 40px; max-height: 120px; font-family: inherit; line-height: 1.5; }
#chat-input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(37,99,235,.12); }
#chat-send-btn { padding: 8px 14px; background: var(--accent); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 700; white-space: nowrap; align-self: flex-end; min-height: 40px; }
#chat-send-btn:hover { background: #1d4ed8; }
#chat-send-btn:disabled { background: var(--ink-3); cursor: not-allowed; }
.modal-overlay { position: fixed; inset: 0; background: rgba(28,37,55,.55); z-index: 1000;
                 display: none; align-items: center; justify-content: center; padding: 24px 16px; }
.modal-overlay.open { display: flex; }
.modal-box { background: var(--surface); border-radius: 12px; box-shadow: 0 12px 40px rgba(0,0,0,.3);
         max-width: 760px; width: 100%; max-height: 85vh; display: flex; flex-direction: column;
         animation: modalIn .18s ease; }
@keyframes modalIn { from { opacity: 0; transform: translateY(-12px); } to { opacity: 1; transform: none; } }
.modal-head { display: flex; align-items: center; justify-content: space-between; padding: 18px 24px;
              border-bottom: 1px solid var(--line); background: var(--surface); flex-shrink: 0;
              border-radius: 12px 12px 0 0; }
.modal-head h2 { margin: 0; font-size: 1.05rem; color: var(--ink); letter-spacing: -.3px; }
.modal-close { background: none; border: none; font-size: 1.5rem; line-height: 1; color: var(--ink-2);
               cursor: pointer; padding: 0 4px; }
.modal-close:hover { color: var(--ink); }
.modal-cont { padding: 20px 24px 28px; font-size: .86rem; line-height: 1.65; color: var(--ink);
              overflow-y: auto; flex: 1; }
.modal-cont h3 { font-size: .92rem; color: var(--accent); margin: 22px 0 8px; letter-spacing: -.2px; }
.modal-cont h3:first-child { margin-top: 0; }
.modal-cont p { margin: 6px 0; color: var(--ink-2); }
.modal-cont ul { margin: 6px 0; padding-left: 20px; }
.modal-cont li { margin: 3px 0; }
.modal-cont table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: .82rem; }
.modal-cont th, .modal-cont td { border: 1px solid var(--line); padding: 7px 10px; text-align: left; vertical-align: top; }
.modal-cont th { background: var(--soft); color: var(--ink-2); font-weight: 700; }
.modal-cont code { background: var(--soft); padding: 1px 5px; border-radius: 4px; font-size: .8rem; color: var(--accent); }
.modal-flow { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 12px 0; }
.modal-flow .step { background: var(--accent-sb); border: 1px solid var(--accent-bd); color: var(--accent);
                    padding: 5px 11px; border-radius: 6px; font-weight: 600; font-size: .8rem; }
.modal-flow .arr { color: var(--ink-3); font-weight: 700; }
.modal-note { background: #FFF7ED; border: 1px solid #FED7AA; border-radius: 6px; padding: 10px 13px;
              margin: 14px 0 0; font-size: .82rem; color: #9A3412; line-height: 1.55; }
.modal-foot { border-top: 1px solid var(--line); padding: 12px 24px; font-size: .76rem; color: var(--ink-3); flex-shrink: 0; }

/* ── 탭 바 ─────────────────────────────────────────────────────────── */
.tab-bar { background: var(--surface); border-bottom: 1px solid var(--line); padding: 0 20px;
           display: flex; gap: 2px; }
.tab-btn { border: none; background: none; padding: 12px 16px; font-size: .85rem; color: var(--ink-2);
           cursor: pointer; border-bottom: 2px solid transparent; font-weight: 500; white-space: nowrap;
           transition: color .15s, border-color .15s; }
.tab-btn:hover { color: var(--ink); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 700; }
.content { padding: 18px 20px; }
.tab-pane { display: none; }
.tab-pane.active { display: block; }

/* ── 카드 ──────────────────────────────────────────────────────────── */
.card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
        box-shadow: var(--shadow); }
.card-p { padding: 16px 18px; }
.card-h { font-size: .8rem; font-weight: 700; color: var(--ink-2); margin-bottom: 12px;
          letter-spacing: .2px; }

/* ── 요약 KPI 카드 ─────────────────────────────────────────────────── */
.stat-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-bottom: 14px; }
.stat-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
             padding: 16px 18px; box-shadow: var(--shadow); position: relative; overflow: hidden;
             transition: transform .15s, box-shadow .15s; }
.stat-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-h); }
.stat-card::after { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
                    background: linear-gradient(90deg,#6B7280,#2563EB,#059669); }
.stat-label { font-size: .72rem; color: var(--ink-2); font-weight: 600; margin-bottom: 6px;
              letter-spacing: .3px; }
.stat-val { font-size: 1.4rem; font-weight: 700; color: var(--ink); line-height: 1.2; letter-spacing: -.3px; }
.stat-sub { font-size: .72rem; color: var(--ink-2); margin-top: 3px; }

/* ── 부문 카드 ─────────────────────────────────────────────────────── */
.sector-grid { display: grid; grid-template-columns: repeat(5,1fr); gap: 12px; margin-bottom: 14px; }
@media(max-width:900px){ .sector-grid { grid-template-columns: repeat(3,1fr); } }
.sector-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
               padding: 14px 16px; box-shadow: var(--shadow); }
.sector-chip { display: inline-block; padding: 2px 10px; border-radius: 100px;
               font-size: .72rem; font-weight: 700; color: #fff; margin-bottom: 8px; }
.sector-val { font-size: 1.3rem; font-weight: 700; color: var(--ink); letter-spacing: -.3px; }
.sector-sub { font-size: .72rem; color: var(--ink-2); }
.bar-bg { background: var(--line-2); border-radius: 4px; height: 5px; margin-top: 6px; }
.bar-fill { border-radius: 4px; height: 5px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media(max-width:700px){ .two-col { grid-template-columns: 1fr; } }

/* ── 미니 테이블 ───────────────────────────────────────────────────── */
.mini-table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.mini-table th { padding: 6px 8px; background: var(--soft); color: var(--ink-2); font-weight: 700;
                  border-bottom: 1px solid var(--line); text-align: left; }
.mini-table td { padding: 5px 8px; border-bottom: 1px solid var(--line-2); }
.mini-table tr:hover td { background: var(--soft); }

/* ── 지도 탭 (풀높이, 무스크롤) ─────────────────────────────────────── */
.map-layout { display: grid; grid-template-columns: 230px 1fr; gap: 12px;
              height: calc(100vh - 138px); }
@media(max-width:768px){ .map-layout { grid-template-columns: 1fr; height: auto; } }
.map-left, .map-right { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.metric-card { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.map-card { flex: 1; min-height: 0; }
#map { height: 100%; border-radius: var(--radius); position: relative; overflow: hidden; background: #eaf0f4; }
#map canvas { border-radius: var(--radius); }
.map-overlay-right { position: absolute; top: 12px; right: 12px; z-index: 2; pointer-events: none;
              display: flex; flex-direction: column; align-items: flex-end; gap: 8px;
              max-height: calc(100% - 24px); }
.map-legend { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
              box-shadow: var(--shadow); padding: 9px 11px; font-size: .73rem; min-width: 132px;
              max-height: 300px; overflow-y: auto; }
#map-grid-detail, #map-svc-detail { display: none; background: var(--surface); border: 1px solid var(--line);
              border-radius: var(--radius); box-shadow: var(--shadow); padding: 10px 12px 22px;
              font-size: .72rem; width: 252px; flex: 0 1 auto; min-height: 0; overflow-y: auto; }
#map-svc-detail { padding-bottom: 10px; pointer-events: auto; }
.svc-row:hover { background: var(--soft); }
/* 지역 상세 하단 시트 (슬라이드업 팝업) */
.map-sheet { position: absolute; left: 12px; right: 12px; bottom: 0; z-index: 5;
             background: var(--surface); border: 1px solid var(--line);
             border-top-left-radius: 12px; border-top-right-radius: 12px;
             box-shadow: 0 -6px 24px rgba(0,0,0,.18); padding: 15px 18px 17px;
             transform: translateY(115%); transition: transform .32s cubic-bezier(.4,0,.2,1);
             max-height: 56%; overflow-y: auto; }
.map-sheet.open { transform: translateY(0); }
.map-sheet-close { position: absolute; top: 9px; right: 13px; background: none; border: none;
                   font-size: 20px; line-height: 1; color: var(--ink-3); cursor: pointer; padding: 0; }
.map-sheet-close:hover { color: var(--ink); }
.map-legend .leg-title { font-weight: 700; margin-bottom: 6px; color: var(--ink); }
.map-legend .leg-row { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; color: var(--ink-2); }
.map-legend .leg-dot { width: 13px; height: 13px; border-radius: 3px; flex-shrink: 0; }
.deck-tooltip { background: rgba(60,75,100,.96) !important; color: #fff !important; font-size: 12px !important;
                padding: 8px 11px !important; border-radius: 6px !important; box-shadow: var(--shadow-h) !important;
                line-height: 1.5 !important; }
.deck-tooltip-grid { max-width: 340px !important; font-size: 11.5px !important; }
/* 격자 토글 옆 ⓘ 호버 설명 */
.info-hint { position: relative; display: inline-flex; }
.info-hint-pop { position: absolute; top: calc(100% + 8px); right: 0; z-index: 30; width: 288px;
  background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: 8px;
  box-shadow: var(--shadow-h); padding: 11px 13px; font-size: .73rem; line-height: 1.55; font-weight: 400;
  text-align: left; opacity: 0; visibility: hidden; transform: translateY(-4px);
  transition: opacity .15s, transform .15s; pointer-events: none; }
.info-hint:hover .info-hint-pop { opacity: 1; visibility: visible; transform: translateY(0); }
.info-hint-pop b { color: var(--accent); }
.metric-list { list-style: none; padding: 0; margin: 0; overflow-y: auto; flex: 1; min-height: 0; }
.metric-list li { margin-bottom: 1px; }
.metric-list label { display: block; padding: 3px 8px; border-radius: 5px; cursor: pointer;
                      font-size: .76rem; color: var(--ink); transition: background .12s; }
.metric-list input[type=radio] { display: none; }
.metric-list input:checked + label { background: var(--accent-sb); color: var(--accent); font-weight: 700; }
.metric-list label:hover { background: var(--soft); }
.stat-box { background: var(--soft); border: 1px solid var(--line-2); border-radius: var(--radius);
            padding: 10px 12px; font-size: .8rem; }
.stat-row { display: flex; justify-content: space-between; padding: 2px 0; }
.stat-row .sk { color: var(--ink-2); }
.stat-row .sv { font-weight: 700; color: var(--ink); }
/* 지역 선택 버튼 */
.sido-btn { background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
            padding: 4px 10px; font-size: .76rem; cursor: pointer; color: var(--ink);
            transition: all .12s; white-space: nowrap; }
.sido-btn:hover { background: var(--accent-sb); color: var(--accent); border-color: var(--accent-bd); }

/* ── 상세 탭 ───────────────────────────────────────────────────────── */
.detail-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
@media(max-width:768px){ .detail-layout { grid-template-columns: 1fr; } }

/* 좌측 지역 선택 패널 (상세 탭 / 비교 탭 공용) */
.detail-tab-layout { display: grid; grid-template-columns: 268px 1fr; gap: 12px; align-items: start; }
@media(max-width:768px){ .detail-tab-layout { grid-template-columns: 1fr; } }
.region-panel { padding: 12px; display: flex; flex-direction: column; height: 736px; }
.region-search { width: 100%; padding: 7px 11px; border: 1px solid var(--line); border-radius: 6px;
                 font-size: .85rem; outline: none; color: var(--ink); background: #fff; margin-bottom: 8px; }
.region-search:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-sb); }
.region-search::placeholder { color: var(--ink-3); }
.region-list { flex: 1; min-height: 0; overflow-y: auto; margin: 0 -4px; }
.sido-header { display: flex; align-items: center; gap: 6px; padding: 6px 6px; border-radius: 6px;
               cursor: pointer; user-select: none; }
.sido-header:hover { background: var(--soft); }
.sido-toggle { font-size: 10px; color: var(--ink-3); width: 12px; flex: none; transition: transform .2s; }
.sido-toggle.open { transform: rotate(90deg); }
.sido-name { flex: 1; font-size: .85rem; font-weight: 600; color: var(--ink); }
.sido-cnt { font-size: .7rem; color: var(--ink-3); }
.sgg-list { display: none; padding: 2px 0 4px 22px; }
.sgg-list.open { display: block; }
.sgg-item { display: flex; align-items: center; gap: 6px; padding: 5px 8px; border-radius: 6px;
            cursor: pointer; font-size: .8rem; color: var(--ink-2); }
.sgg-item:hover { background: var(--accent-sb); }
.sgg-item.selected { background: var(--accent-sb); color: var(--accent); font-weight: 700; }
.sgg-check { margin-left: auto; font-size: 11px; color: var(--accent); opacity: 0; }
.sgg-item.selected .sgg-check { opacity: 1; }

/* ── 비교 탭 ───────────────────────────────────────────────────────── */
.cmp-tab-layout { display: grid; grid-template-columns: 268px 1fr; gap: 12px; align-items: start; }
@media(max-width:900px){ .cmp-tab-layout { grid-template-columns: 1fr; } }
.cmp-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
@media(max-width:900px){ .cmp-charts { grid-template-columns: 1fr; } }
.cmp-chips { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; min-height: 4px; }
.cmp-chip { display: inline-flex; align-items: center; gap: 5px; padding: 3px 6px 3px 9px;
            border-radius: 100px; font-size: .76rem; font-weight: 700; color: #fff; }
.cmp-chip .chip-x { cursor: pointer; font-size: .9rem; line-height: 1; opacity: .85; }
.cmp-chip .chip-x:hover { opacity: 1; }
.cmp-layout { display: grid; grid-template-columns: 230px 1.4fr 1fr; gap: 12px; align-items: stretch; }
@media(max-width:1000px){ .cmp-layout { grid-template-columns: 1fr; } }
.score-badge { display: inline-block; padding: 1px 8px; border-radius: 100px;
               font-weight: 700; font-size: .8rem; }
.cmp-side-label { font-size: .72rem; color: var(--ink-2); margin-bottom: 3px; font-weight: 700; }
.cmp-mode-bar { display: flex; gap: 4px; margin-bottom: 10px; }
.cmp-mode-btn { flex: 1; border: 1px solid var(--line); background: var(--surface); border-radius: 6px;
                padding: 5px 2px; font-size: .73rem; cursor: pointer; color: var(--ink-2);
                white-space: nowrap; transition: all .12s; }
.cmp-mode-btn.active { background: var(--accent-sb); color: var(--accent); border-color: var(--accent-bd);
                       font-weight: 700; }

/* ── 분포 탭 ───────────────────────────────────────────────────────── */
.dist-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
@media(max-width:768px){ .dist-layout { grid-template-columns: 1fr; } }
select.form-select-sm { font-size: .82rem; }
.form-select-sm, .form-control-sm { border-color: var(--line); color: var(--ink); }
.form-select-sm:focus, .form-control-sm:focus { border-color: var(--accent);
            box-shadow: 0 0 0 2px var(--accent-sb); }
</style>
</head>
<body>

<!-- ── Navbar ─────────────────────────────────────────────────────────────── -->
<div class="navbar">
  <span class="navbar-title">🗺 생활인프라 편리성 모니터링 대시보드 <span style="opacity:.65;font-weight:400">시계열</span></span>
  <span class="year-pair-badge" id="year-pair-badge"></span>
  <span class="navbar-spacer"></span>
  <button id="chat-toggle-btn" onclick="toggleChatPanel()"></button>
  <button class="help-btn" id="helpBtn">ℹ️ 산출 방법</button>
</div>

<!-- ── Tabs ───────────────────────────────────────────────────────────────── -->
<div class="tab-bar">
  <button class="tab-btn active" data-tab="overview">📊 요약</button>
  <button class="tab-btn" data-tab="map">🗺 지도</button>
  <button class="tab-btn" data-tab="detail">🔍 지역별 상세</button>
  <button class="tab-btn" data-tab="ranking">🏆 지역별 비교</button>
  <button class="tab-btn" data-tab="dist">📈 분포 분석</button>
  <button class="tab-btn" data-tab="change">🕒 변화분석</button>
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
      <div class="card-h">🏆 상위 10개 지역 (종합지수 · 최신연도 기준)</div>
      <div id="top10"></div>
    </div>
    <div class="card card-p">
      <div class="card-h">⚠️ 하위 10개 지역 (종합지수 · 최신연도 기준)</div>
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
    <div class="map-left">
      <div class="card card-p" style="padding-bottom:10px">
        <div class="card-h" style="margin-bottom:8px">🎨 색상 분류</div>
        <div style="display:flex;gap:5px;flex-wrap:wrap">
          <label style="display:flex;align-items:center;gap:4px;font-size:.8rem;cursor:pointer;padding:4px 8px;border-radius:6px;border:1px solid var(--line);flex:1;justify-content:center;min-width:56px" id="lbl-equal">
            <input type="radio" name="classify" value="equal" style="display:none">
            <span>등간격</span>
          </label>
          <label style="display:flex;align-items:center;gap:4px;font-size:.8rem;cursor:pointer;padding:4px 8px;border-radius:6px;border:1px solid var(--line);flex:1;justify-content:center;min-width:56px" id="lbl-quantile">
            <input type="radio" name="classify" value="quantile" style="display:none">
            <span>분위수</span>
          </label>
          <label style="display:flex;align-items:center;gap:4px;font-size:.8rem;cursor:pointer;padding:4px 8px;border-radius:6px;border:1px solid var(--line);flex:1;justify-content:center;min-width:56px" id="lbl-decile">
            <input type="radio" name="classify" value="decile" checked style="display:none">
            <span>10등급</span>
          </label>
        </div>
      </div>
      <div class="card card-p metric-card">
        <div class="card-h">📌 지표 선택</div>
        <ul class="metric-list" id="metric-list"></ul>
      </div>
    </div>
    <!-- Map -->
    <div class="map-right">
      <!-- 시도 → 시군구 연동 선택 -->
      <div class="card card-p" style="padding:10px 14px">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <div class="year-seg-local" id="map-mode-seg">
            <button data-m="compare" class="active">🆚 연도 비교</button>
            <button data-m="detail">🔎 상세보기</button>
          </div>
          <span style="font-size:.75rem;color:var(--ink-2);font-weight:700">📍 지역 선택</span>
          <select id="map-sido-sel" class="form-select form-select-sm" style="width:auto;min-width:130px"><option value="">시도 전체</option></select>
          <select id="map-sgg-sel" class="form-select form-select-sm" style="width:auto;min-width:150px" disabled><option value="">시군구</option></select>
          <button id="map-region-reset" type="button" class="sido-btn" style="display:none">↺ 전체보기</button>
          <span id="layer-chips" style="display:none;align-items:center;gap:6px;flex-wrap:wrap;margin-left:auto">
            <span style="font-size:.72rem;color:var(--ink-2);font-weight:700">레이어</span>
            <button id="lyr-poi-btn" type="button" class="sido-btn">📍 시설 POI</button>
            <button id="lyr-svc-btn" type="button" class="sido-btn">👥 서비스권역 인구</button>
            <select id="lyr-fac-sel" class="form-select form-select-sm" style="width:auto;display:none"></select>
          </span>
          <button id="grid-toggle-btn" type="button" class="sido-btn" style="display:none">📊 충족격자</button>
          <span id="grid-info-wrap" class="info-hint" style="display:none">
            <button id="grid-info-btn" type="button" title="시설별 기준 및 산출 방식" style="width:26px;height:26px;border-radius:50%;border:1.5px solid var(--accent-bd);background:var(--accent-sb);color:var(--accent);font-size:.78rem;font-weight:800;cursor:pointer;line-height:1;padding:0;flex-shrink:0">ⓘ</button>
            <span class="info-hint-pop">
              <b>🏘️ 마을시설 (생활밀착형 · 1km)</b><br>
              도보·자전거로 접근하는 마을 단위 시설<br>
              <span style="color:var(--ink-2)">어린이집·초등학교·의원·약국·경로당·생활권공원 등</span><br><br>
              <b>🏛️ 거점시설 (광역거점형 · 5km)</b><br>
              차량 등으로 접근하는 거점 단위 시설<br>
              <span style="color:var(--ink-2)">종합병원·경찰서·소방서·종합사회복지관·공공체육시설 등</span><br><br>
              <span style="color:var(--ink-3)">ⓘ 클릭 시 시설별 기준·산출 방식 전체가 열립니다.</span>
            </span>
          </span>
          <span id="grid-color-ctrl" style="display:none;align-items:center;gap:4px;font-size:.72rem;color:var(--ink-2);font-weight:700">
            격자 색상
            <span class="year-seg-local" style="padding:2px">
              <button id="gcm-score" class="active" style="padding:2px 9px;font-size:.72rem">충족점수</button>
              <button id="gcm-pop" style="padding:2px 9px;font-size:.72rem">인구</button>
            </span>
          </span>
          <span id="grid-opacity-ctrl" style="display:none;align-items:center;gap:6px;font-size:.72rem;color:var(--ink-2);font-weight:700">
            격자 투명도
            <input id="grid-opacity-slider" type="range" min="0" max="100" value="90" style="width:96px;vertical-align:middle">
          </span>
        </div>
      </div>
      <div class="map-dual">
        <div class="card map-cell">
          <span class="map-year-chip" id="map-chip-y1"></span>
          <div id="map1"></div>
        </div>
        <div class="card map-cell latest">
          <span class="map-year-chip" id="map-chip-y2"></span>
          <div id="map"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════
     TAB 3 : 시군구 상세
══════════════════════════════════════════════════════════════════════════ -->
<div id="tab-detail" class="tab-pane">
  <div class="detail-tab-layout">
    <!-- 좌측: 검색 + 시도 접이식 시군구 목록 -->
    <div class="card region-panel">
      <input type="text" id="region-search" class="region-search" placeholder="시도 / 시군구 검색...">
      <div id="region-list" class="region-list"></div>
    </div>
    <!-- 우측: 선택 지역 분석 결과 -->
    <div class="region-main">
      <div style="margin-bottom:14px;min-height:32px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <div class="year-seg-local" id="detail-year-seg"></div>
        <span class="badge-cnt" id="detail-rank-badge" style="display:none"></span>
      </div>
      <div id="detail-content" style="display:none">
        <div class="detail-layout">
          <div class="card card-p">
            <div class="card-h">5개 부문 편리성 — 연도 비교</div>
            <div id="radar-chart" style="height:320px"></div>
          </div>
          <div class="card card-p">
            <div class="card-h">공급 · 향유 · 충족 수준 — 연도 비교</div>
            <div id="bar-chart" style="height:320px"></div>
          </div>
        </div>
        <div class="card card-p">
          <div class="card-h">부문별 상세 지표</div>
          <div id="detail-table"></div>
        </div>
      </div>
      <div id="detail-placeholder" style="color:#94A3B8;font-size:.875rem;padding:40px 0;text-align:center">
        왼쪽 목록에서 시군구를 선택하면 분석 결과가 표시됩니다.
      </div>
    </div>
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════
     TAB 4 : 지역별 비교
══════════════════════════════════════════════════════════════════════════ -->
<div id="tab-ranking" class="tab-pane">
  <div class="cmp-tab-layout">
    <!-- 좌측: 검색 + 시도 접이식 목록 -->
    <div class="card region-panel">
      <div style="display:flex;justify-content:center;margin-bottom:8px">
        <div class="year-seg-local" id="cmp-year-seg"></div>
      </div>
      <div class="cmp-mode-bar">
        <button class="cmp-mode-btn active" data-mode="direct">직접선택</button>
        <button class="cmp-mode-btn" data-mode="pop">인구유사</button>
        <button class="cmp-mode-btn" data-mode="area">면적유사</button>
      </div>
      <div class="cmp-side-label" id="cmp-sel-hint">시군구를 선택하세요 (최대 2곳 비교)</div>
      <div class="cmp-chips" id="cmp-chips"></div>
      <input type="text" id="cmp-region-search" class="region-search" placeholder="시도 / 시군구 검색...">
      <div id="cmp-region-list" class="region-list"></div>
    </div>
    <!-- 우측: 레이더 + 막대 + 비교표 -->
    <div class="cmp-main">
      <div id="cmp-content" style="display:none">
        <div class="cmp-charts">
          <div class="card card-p">
            <div class="card-h">5개 부문 편리성 비교 (레이더)</div>
            <div id="cmp-radar" style="height:clamp(240px,34vh,400px)"></div>
          </div>
          <div class="card card-p">
            <div class="card-h">5개 부문 편리성 비교 (막대)</div>
            <div id="cmp-bar" style="height:clamp(240px,34vh,400px)"></div>
          </div>
        </div>
        <div class="card card-p">
          <div class="card-h">부문별 비교표</div>
          <div id="cmp-table"></div>
        </div>
      </div>
      <div id="cmp-placeholder" style="color:#94A3B8;font-size:.875rem;padding:40px 0;text-align:center">
        왼쪽에서 비교 방식을 고르고 시군구를 선택하면 비교 결과가 표시됩니다.
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

<!-- ══════════════════════════════════════════════════════════════════════════
     TAB 6 : 변화분석 (시계열)
══════════════════════════════════════════════════════════════════════════ -->
<div id="tab-change" class="tab-pane">
  <div class="card card-p" style="margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span style="font-size:.78rem;font-weight:700;color:var(--ink-2)">📌 지표</span>
      <select id="chg-metric" class="form-select form-select-sm" style="width:220px"></select>
      <span style="font-size:.78rem;font-weight:700;color:var(--ink-2)">🕒 기간</span>
      <select id="chg-y1" class="form-select form-select-sm" style="width:96px"></select>
      <span style="color:var(--ink-3)">→</span>
      <select id="chg-y2" class="form-select form-select-sm" style="width:96px"></select>
      <span class="chg-note">⚠️ 지수는 연도별 T점수(상대 표준화)라 증감은 절대 수준 변화가 아니라 <b>전국 내 상대적 위치 변화</b>입니다. 순위 변화를 함께 확인하세요.</span>
    </div>
  </div>
  <div class="chg-layout">
    <div class="card" style="overflow:hidden;position:relative">
      <div id="chg-map"></div>
    </div>
    <div class="chg-side">
      <div class="card card-p">
        <div class="card-h">📈 상대적 상승 TOP 10 <span style="font-weight:400;color:var(--ink-3);font-size:.72rem">(순위 상승 기준)</span></div>
        <div id="chg-up"></div>
      </div>
      <div class="card card-p">
        <div class="card-h">📉 상대적 하락 TOP 10 <span style="font-weight:400;color:var(--ink-3);font-size:.72rem">(순위 하락 기준)</span></div>
        <div id="chg-down"></div>
      </div>
    </div>
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
// 연도쌍 상태 (시계열 비교) — 대시보드 전체가 Y1 vs Y2 대비 구조
// ══════════════════════════════════════════════════════════════════════════════
const Y1 = YEAR_LIST[0];                       // 비교 기준(이전) 연도
const Y2 = YEAR_LIST[YEAR_LIST.length - 1];    // 최신 연도
const CUR_YEAR = Y2;                           // 챗봇 등 "기본 연도" = 최신
const RECORDS  = YEARS[Y2];                    // 목록·순위 등 기준 레코드 = 최신 연도
let detailSelCd = null;                        // 상세 탭 선택 시군구

function recsOf(year) { return YEARS[String(year)] || []; }
function findIn(recs, cd) { return recs.find(r => String(r.sgg_cd) === String(cd)); }
function rankIn(recs, key, value) {
  const vals = recs.map(r => r[key]).filter(v => v != null && !isNaN(+v)).sort((a, b) => b - a);
  return vals.findIndex(v => v <= value) + 1;
}
function meanIn(recs, key) {
  const vals = recs.map(r => r[key]).filter(v => v != null && !isNaN(+v));
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}
// 특정 연도에서 시군구(cd)의 전국 순위
function rankOf(year, key, cd) {
  const recs = recsOf(year);
  const r = findIn(recs, cd);
  if (!r || r[key] == null) return null;
  return rankIn(recs, key, r[key]);
}

// 연도별 sgg_cd → record 색인
const BYCD = {};
YEAR_LIST.forEach(y => {
  BYCD[y] = {};
  YEARS[y].forEach(r => { BYCD[y][String(r.sgg_cd)] = r; });
});
function valOf(year, cd, key) {
  const r = BYCD[String(year)] && BYCD[String(year)][String(cd)];
  return r ? r[key] : null;
}

// Δ 표시 헬퍼: +2.1 / -0.3 색상 span
function deltaHtml(d, digits = 1) {
  if (d == null || isNaN(+d)) return '<span style="color:#94A3B8">-</span>';
  const col = d > 0 ? '#DC2626' : d < 0 ? '#1D4ED8' : '#94A3B8';
  const s = (d > 0 ? '+' : '') + (+d).toFixed(digits);
  return `<span style="color:${col};font-weight:700">${s}</span>`;
}
function rankDeltaHtml(r1, r2) {
  if (r1 == null || r2 == null) return '';
  const d = r1 - r2;   // +면 순위 상승
  const cls = d > 0 ? 'rank-delta-up' : d < 0 ? 'rank-delta-down' : 'rank-delta-flat';
  const arrow = d > 0 ? `▲${d}` : d < 0 ? `▼${-d}` : '—';
  return `<span class="${cls}">${arrow}</span>`;
}

// ══════════════════════════════════════════════════════════════════════════════
// UTILS
// ══════════════════════════════════════════════════════════════════════════════
const f1 = v => (v == null || isNaN(+v)) ? '-' : (+v).toFixed(1);
const f3 = v => (v == null || isNaN(+v)) ? '-' : (+v).toFixed(3);
const fAuto = (v, key) => f1(v); // 모든 지표 T점수 스케일 → 소수점 1자리 통일

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
let changeInited = false;

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    document.getElementById('tab-' + tab).classList.add('active');

    if (tab === 'map' && !mapInited)     { initMap(); mapInited = true; }
    else if (tab === 'map' && deckMap)   { setTimeout(() => deckMap.redraw(true), 60); }
    if (tab === 'ranking' && !rankInited){ initRanking(); rankInited = true; }
    if (tab === 'dist' && !distInited)   { initDist(); distInited = true; }
    if (tab === 'change' && !changeInited) { initChange(); changeInited = true; }
    else if (tab === 'change' && deckChg)  { setTimeout(() => deckChg.redraw(true), 60); }
  });
});

// ══════════════════════════════════════════════════════════════════════════════
// TAB 1 : 개요
// ══════════════════════════════════════════════════════════════════════════════
function renderOverview() {
  const sorted = [...RECORDS].sort((a, b) => (b.infra_idx || 0) - (a.infra_idx || 0));
  const top = sorted[0], bot = sorted[sorted.length - 1];
  const chg = computeChangeRows('infra_idx', Y1, Y2);
  const bestUp    = [...chg].sort((a, b) => b.dr - a.dr || b.dv - a.dv)[0];
  const worstDown = [...chg].sort((a, b) => a.dr - b.dr || a.dv - b.dv)[0];

  // KPI 카드: 지역명 + 한 줄 요약만 (간결)
  const regionCard = (label, rec, color) => {
    const v1 = valOf(Y1, rec.sgg_cd, 'infra_idx');
    const r1 = rankOf(Y1, 'infra_idx', rec.sgg_cd);
    const r2 = rankIn(RECORDS, 'infra_idx', rec.infra_idx);
    return `<div class="stat-card">
      <div class="stat-label">${label}</div>
      <div class="stat-val" style="font-size:1rem">${rec.sido_nm_k} ${rec.sgg_nm_k}</div>
      <div class="stat-sub" style="color:${color}">${f1(rec.infra_idx)}점 ${deltaHtml(v1 != null ? rec.infra_idx - v1 : null)} ${rankDeltaHtml(r1, r2)}</div>
    </div>`;
  };
  const moveCard = (label, m, color) => m ? `<div class="stat-card">
      <div class="stat-label">${label}</div>
      <div class="stat-val" style="font-size:1rem">${m.sido} ${m.sgg}</div>
      <div class="stat-sub" style="color:${color}">${m.rank1}위 → ${m.rank2}위 ${rankDeltaHtml(m.rank1, m.rank2)}</div>
    </div>` : '';

  document.getElementById('summary-stats').innerHTML =
    regionCard(`최고 지역 🥇 (${Y2})`, top, '#16A34A') +
    regionCard(`최저 지역 ⚠️ (${Y2})`, bot, '#DC2626') +
    moveCard('최대 상승 🚀', bestUp, '#DC2626') +
    moveCard('최대 하락 📉', worstDown, '#1D4ED8');

  // Sector cards — 최고·최저(최신연도 값)와 순위 상승 1위만
  document.getElementById('sector-cards').innerHTML = Object.entries(SEC).map(([k, s]) => {
    const key = k + '_conv';
    const recs = RECORDS.filter(r => r[key] != null);
    const sortedRecs = [...recs].sort((a, b) => b[key] - a[key]);
    const topRec = sortedRecs[0];
    const botRec = sortedRecs[sortedRecs.length - 1];
    const secChg = computeChangeRows(key, Y1, Y2);
    const secUp = [...secChg].sort((a, b) => b.dr - a.dr || b.dv - a.dv)[0];
    const row = (icon, name, valueHtml) => `<div style="display:flex;justify-content:space-between;align-items:center">
      <span style="color:#94A3B8;white-space:nowrap">${icon}</span>
      <span style="text-align:right"><strong style="color:#1E293B">${name}</strong> ${valueHtml}</span>
    </div>`;
    return `<div class="sector-card">
      <span class="sector-chip" style="background:${s.color}">${s.label}</span>
      <div style="font-size:.7rem;border-top:1px solid #F1F5F9;margin-top:10px;padding-top:8px;display:flex;flex-direction:column;gap:5px">
        ${row('🥇 최고', topRec.sgg_nm_k, `<span style="color:${s.color};font-weight:600">${f1(topRec[key])}</span>`)}
        ${row('⬇ 최저', botRec.sgg_nm_k, `<span style="color:#94A3B8;font-weight:600">${f1(botRec[key])}</span>`)}
        ${secUp ? row('🚀 상승1위', secUp.sgg, rankDeltaHtml(secUp.rank1, secUp.rank2)) : ''}
      </div>
    </div>`;
  }).join('');

  // Top / Bottom 표 — 컬럼 축소(최신 점수·Δ·순위변화) + 펼치기
  const rankRow = (r, i) => {
    const c = colorFor(r.infra_idx, ...getRange('infra_idx'));
    const v1 = valOf(Y1, r.sgg_cd, 'infra_idx');
    const r1 = rankOf(Y1, 'infra_idx', r.sgg_cd);
    const r2 = rankIn(RECORDS, 'infra_idx', r.infra_idx);
    return `<tr>
      <td style="color:#94A3B8">${i + 1}</td>
      <td>${r.sido_nm_k}</td>
      <td><strong>${r.sgg_nm_k}</strong></td>
      <td><span class="score-badge" style="background:${c}22;color:${c}">${f1(r.infra_idx)}</span></td>
      <td>${deltaHtml(v1 != null ? r.infra_idx - v1 : null)}</td>
      <td style="white-space:nowrap">${rankDeltaHtml(r1, r2)}</td>
    </tr>`;
  };
  const miniTable = (rows, expanded) => `
    <div class="mini-table-wrap${expanded ? ' expanded' : ''}">
      <table class="mini-table">
        <thead><tr><th>#</th><th>시도</th><th>시군구</th><th>${Y2}년</th><th>Δ</th><th>순위변화</th></tr></thead>
        <tbody>${rows.slice(0, expanded ? rows.length : 10).map(rankRow).join('')}</tbody>
      </table>
    </div>
    <button class="expand-btn">${expanded ? '접기 ▲' : `전체 ${rows.length}개 펼치기 ▼`}</button>`;

  const renderRankTable = (elId, rows) => {
    const el = document.getElementById(elId);
    let expanded = false;
    const draw = () => {
      el.innerHTML = miniTable(rows, expanded);
      el.querySelector('.expand-btn').addEventListener('click', () => { expanded = !expanded; draw(); });
    };
    draw();
  };
  renderRankTable('top10', sorted);
  renderRankTable('bot10', [...sorted].reverse());
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 2 : 지도
// ══════════════════════════════════════════════════════════════════════════════
let deckMap = null;    // 최신연도(Y2) 지도
let deckMap1 = null;   // 이전연도(Y1) 지도
let _vsSyncing = false; // 듀얼 맵 뷰 동기화 재진입 가드
let curMetric = 'infra_idx';
let curClassify = 'decile'; // 'equal' | 'quantile' | 'decile' (기본: 10등급)
let curSidoFilter = null;
let highlightSggCd = null;   // 검색으로 강조된 시군구
let decileBreaks = [], decileColors = [];
let mapViewState = { longitude: 127.8, latitude: 36.2, zoom: 6.1, pitch: 0, bearing: 0 };
const VWORLD_KEY = '6D2A7A4B-CB1D-3574-8FD8-331C8254D8F9';
let _colorScale = null, _qBreaks = [], _mn = 0, _mx = 1; // 색상 분류 상태

// ── 충족격자(access) ─────────────────────────────────────────────────────────
let mapMode = 'compare';        // 'compare'(듀얼 연도 비교) | 'detail'(단일 최신연도 상세)
let gridLayerOn = false;
let gridOpacity = 0.9;
let gridColorMode = 'score';    // 'score'(충족점수) | 'pop'(격자 인구)
let _gridPopMax = 1;            // 현재 시군구 격자 인구 스케일 상한 (95분위)
const POP_SCALE = chroma.scale(['#BFDBFE', '#60A5FA', '#2563EB', '#1E3A8A']);
// (컬럼키, 한글명, 부문)  비트 i = 인덱스 (make_access_grids.py와 동일 순서 필수)
const FACILITIES = [
  ['daycar','어린이집','edu'],['kinder','유치원','edu'],['elem','초등학교','edu'],['smlib','작은도서관','edu'],
  ['allday','온종일돌봄센터','care'],['welfar','종합사회복지관','care'],['snrlei','노인여가복지시설','care'],['snrctr','경로당','care'],
  ['hosp','종합병원','med'],['health','보건기관','med'],['clinic','의원','med'],['pharma','약국','med'],
  ['eqshlt','지진옥외대피소','safe'],['emerg','응급의료시설','safe'],['police','경찰서','safe'],['fire','소방서','safe'],
  ['lfpark','생활권공원','cult'],['thpark','주제공원','cult'],['cultur','공연문화시설','cult'],['sports','공공체육시설','cult'],
];
const SECTOR_ORDER = ['edu','care','med','safe','cult'];
const GRID_SCALE = chroma.scale(['#d73027','#fdae61','#fee08b','#a6d96a','#1a9850']).domain([1, 20]); // 1빨강~20초록

// ── 온디맨드 오버레이 레이어 (POI · 서비스권역 인구) ─────────────────────────
// layers/{kind}_{fac}_{year}.js 파일을 시설·연도 조합별로 lazy-load 한다.
let poiOn = false, svcOn = false;
let layerFac = 'daycar';   // 선택 시설 코드
const LAYER_CACHE = window.LAYER_CACHE;   // head 부트스트랩에서 생성 (access_최신연도 포함)
const _layerWaiters = {};
window.__LAYER = (k, d) => {
  LAYER_CACHE[k] = d;
  (_layerWaiters[k] || []).forEach(fn => fn(d));
  delete _layerWaiters[k];
};
function loadLayerKey(k) {
  if (LAYER_CACHE[k]) return Promise.resolve(LAYER_CACHE[k]);
  return new Promise((resolve, reject) => {
    (_layerWaiters[k] || (_layerWaiters[k] = [])).push(resolve);
    if (_layerWaiters[k].length > 1) return;   // 이미 로딩 중
    const s = document.createElement('script');
    s.src = 'layers/' + k + '.js';
    s.onerror = () => { delete _layerWaiters[k]; reject(new Error('레이어 로드 실패: ' + k)); };
    document.head.appendChild(s);
  });
}
function facEntry(code) { return FACILITIES.find(f => f[0] === code); }
function facColorRgb(code) {
  const e = facEntry(code);
  const c = chroma(SEC[e ? e[2] : 'edu'].color).rgb();
  return [c[0], c[1], c[2]];
}
// 켜진 레이어에 필요한 파일들을 로드한 뒤 지도 재렌더
async function refreshOverlayLayers() {
  if (highlightSggCd != null && (poiOn || svcOn || gridLayerOn)) {
    const jobs = [];
    if (poiOn || svcOn) {
      // 서비스권역도 반경 원을 그리려면 시설 좌표(POI)가 필요
      [Y1, Y2].forEach(y => jobs.push(loadLayerKey(`poi_${layerFac}_${y}`).catch(() => null)));
    }
    if (svcOn) jobs.push(loadLayerKey('svc_ratios').catch(() => null));
    if (gridLayerOn) [Y1, Y2].forEach(y => jobs.push(loadLayerKey(`access_${y}`).catch(() => null)));
    await Promise.all(jobs);
  }
  renderChoropleth();
}

// 선택 시설의 서비스권역 반경(m) — svc_ratios label 의 "(1.0km)" 등에서 파싱
function svcRadiusM(year) {
  const S = LAYER_CACHE['svc_ratios'];
  const meta = S && S[year] && S[year][layerFac];
  if (!meta) return 1000;
  const m = (meta.label || '').match(/\(([\d.]+)\s*km\)/);
  return m ? parseFloat(m[1]) * 1000 : 1000;
}

// 서비스권역 인구비율 패널 — 시설별 미니 바(Y1·Y2) + 행 클릭으로 시설 선택
function updateSvcPanel() {
  const div = document.getElementById('map-svc-detail');
  if (!div) return;
  const S = LAYER_CACHE['svc_ratios'];
  if (!svcOn || highlightSggCd == null || !S) { div.style.display = 'none'; div.innerHTML = ''; return; }
  const cd = String(highlightSggCd);
  const selMeta = (S[Y2] && S[Y2][layerFac]) || (S[Y1] && S[Y1][layerFac]) || {};
  let html = `<div class="leg-title" style="margin-bottom:2px">서비스권역 내 인구비율 (%)</div>
    <div style="font-size:.64rem;color:var(--ink-3);margin-bottom:7px;line-height:1.5">
      시설 반경 안에 사는 <b>대상인구 비율</b>.<br>지도의 <span style="color:#059669">초록 원</span> = 선택 시설의 권역.<br>행을 클릭하면 그 시설로 전환.</div>`;
  SECTOR_ORDER.forEach(sk => {
    FACILITIES.filter(f => f[2] === sk).forEach(f => {
      const e1 = S[Y1] && S[Y1][f[0]], e2 = S[Y2] && S[Y2][f[0]];
      const r1 = e1 ? e1.rows[cd] : null, r2 = e2 ? e2.rows[cd] : null;
      const d = (r1 != null && r2 != null) ? r2 - r1 : null;
      const label = (e2 || e1 || {}).label || '';
      const sel = f[0] === layerFac;
      const bar = (v, color, op) => `<div style="height:5px;border-radius:3px;background:var(--line-2);margin-top:2px">
        <div style="height:100%;width:${v == null ? 0 : Math.min(100, Math.max(0, v))}%;border-radius:3px;background:${color};opacity:${op}"></div></div>`;
      html += `<div class="svc-row" data-fac="${f[0]}" title="${label}"
        style="padding:5px 6px;margin:0 -6px;border-radius:6px;cursor:pointer;${sel ? 'background:var(--accent-sb);outline:1px solid var(--accent-bd);' : ''}">
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:6px">
          <span style="white-space:nowrap;font-weight:${sel ? 700 : 400}"><span style="color:${SEC[sk].color}">●</span> ${f[1]}</span>
          <span style="white-space:nowrap;font-size:.68rem"><span style="color:var(--ink-3)">${r1 ?? '-'}</span> → <b>${r2 ?? '-'}</b> ${d == null ? '' : deltaHtml(d)}</span>
        </div>
        ${bar(r1, '#94A3B8', .55)}
        ${bar(r2, SEC[sk].color, .9)}
      </div>`;
    });
  });
  div.innerHTML = html;
  div.style.display = 'block';
}
function popcount(m) { let c = 0; while (m) { c += m & 1; m >>>= 1; } return c; }

function getDecileGrade(v) {
  // Grade 1 = 최고(top 10%), Grade 10 = 최저(bottom 10%)
  if (v == null || decileBreaks.length < 11) return null;
  let bin = 0;
  for (let i = 1; i <= 9; i++) { if (v >= decileBreaks[i]) bin = i; }
  return 10 - bin; // bin 9 → grade 1, bin 0 → grade 10
}

// 피처 경계 [minLon,minLat,maxLon,maxLat]
function featureBounds(ft) {
  let mnx=Infinity,mny=Infinity,mxx=-Infinity,mxy=-Infinity;
  const collect = arr => {
    if (!arr.length) return;
    if (typeof arr[0][0] === 'number') arr.forEach(c => { if(c[0]<mnx)mnx=c[0]; if(c[0]>mxx)mxx=c[0]; if(c[1]<mny)mny=c[1]; if(c[1]>mxy)mxy=c[1]; });
    else arr.forEach(a => collect(a));
  };
  collect(ft.geometry.coordinates);
  return [mnx, mny, mxx, mxy];
}

// 경계로 부드럽게 이동
function flyToBounds(b, maxZoom, vShiftFrac) {
  const cLon = (b[0]+b[2])/2, cLat = (b[1]+b[3])/2;
  const maxDelta = Math.max(b[2]-b[0]||0.02, (b[3]-b[1]||0.02)*1.3);
  const zoom = Math.min(Math.max(Math.log2(3.5/maxDelta)+7, 6), maxZoom||11);
  // vShiftFrac>0 이면 중심을 남쪽으로 내려, 대상이 화면 상단에 보이도록(하단 시트에 안 가리게)
  const latShift = vShiftFrac ? maxDelta * vShiftFrac : 0;
  mapViewState = { longitude:cLon, latitude:cLat - latShift, zoom, pitch:0, bearing:0, transitionDuration:600 };
  if (deckMap)  deckMap.setProps({ initialViewState: { ...mapViewState } });
  if (deckMap1) deckMap1.setProps({ initialViewState: { ...mapViewState } });
}

// ── 색상 분류 ────────────────────────────────────────────────────────────────
const MAP_PALETTE = ['#1D4ED8','#93C5FD','#FCA5A5','#DC2626'];

// 두 연도 값을 합친 풀 — 색상 등급을 공유해 좌우 지도가 같은 잣대로 비교되게 함
function getValsBoth(key) {
  const out = [];
  [Y1, Y2].forEach(y => recsOf(y).forEach(r => {
    const v = r[key];
    if (v != null && !isNaN(+v)) out.push(+v);
  }));
  return out;
}

function computeColorState() {
  const allVals = getValsBoth(curMetric);
  _mn = Math.min(...allVals); _mx = Math.max(...allVals);
  if (curClassify === 'quantile') {
    _qBreaks = chroma.limits(allVals, 'q', 5);
    _colorScale = chroma.scale(MAP_PALETTE).classes(_qBreaks);
  } else if (curClassify === 'decile') {
    const sorted = [...allVals].sort((a,b)=>a-b); const n = sorted.length;
    decileBreaks = Array.from({length:11}, (_,i)=> i<10 ? sorted[Math.floor(i*n/10)] : sorted[n-1]);
    decileColors = chroma.scale(MAP_PALETTE).colors(10);
  } else {
    _colorScale = chroma.scale(MAP_PALETTE).domain([_mn, _mx]);
  }
}

function fillColorFor(v) {
  if (v == null || isNaN(+v)) return [206, 212, 218, 130];
  let hex;
  if (curClassify === 'decile') hex = decileColors[getDecileGrade(v)-1] || '#cccccc';
  else hex = _colorScale(v).hex();
  const c = chroma(hex).rgb();
  return [c[0], c[1], c[2], 195];
}

// ── deck.gl 레이어 ───────────────────────────────────────────────────────────
function makeTileLayer() {
  return new deck.TileLayer({
    id: 'vworld-base',
    data: 'https://api.vworld.kr/req/wmts/1.0.0/' + VWORLD_KEY + '/Base/{z}/{y}/{x}.png',
    minZoom: 0, maxZoom: 19, tileSize: 256,
    renderSubLayers: props => {
      const { bbox: { west, south, east, north } } = props.tile;
      return new deck.BitmapLayer(props, { data: null, image: props.data, bounds: [west, south, east, north] });
    }
  });
}

function buildMapLayers(year) {
  const feats = curSidoFilter
    ? GEOJSON.features.filter(f => f.properties.sido_nm_k === curSidoFilter)
    : GEOJSON.features;
  const showGrid = gridLayerOn;   // 격자는 연도별 데이터 → 좌우 지도 각각 표시
  const layers = [
    makeTileLayer(),
    new deck.GeoJsonLayer({
      id: 'sgg-fill-' + year,
      data: { type: 'FeatureCollection', features: feats },
      filled: true, stroked: true, opacity: 1,
      getFillColor: f => (showGrid && f.properties.sgg_cd === highlightSggCd)
        ? [148, 163, 184, 235]
        : fillColorFor(valOf(year, f.properties.sgg_cd, curMetric)),
      getLineColor: [255, 255, 255, 230], lineWidthUnits: 'pixels', getLineWidth: 0.8, lineWidthMinPixels: 0.5,
      pickable: true, autoHighlight: true, highlightColor: [37, 99, 235, 90],
      updateTriggers: { getFillColor: [curMetric, curClassify, gridLayerOn, highlightSggCd, year] }
    })
  ];
  if (highlightSggCd != null) {
    const hf = GEOJSON.features.find(f => f.properties.sgg_cd === highlightSggCd);
    if (hf) layers.push(new deck.GeoJsonLayer({
      id: 'sgg-highlight-' + year, data: { type: 'FeatureCollection', features: [hf] },
      filled: false, stroked: true, getLineColor: [37, 99, 235, 255],
      lineWidthUnits: 'pixels', getLineWidth: 3, lineWidthMinPixels: 2.5, pickable: false
    }));
  }
  if (showGrid && highlightSggCd != null && LAYER_CACHE['access_' + year]) {
    const raw = LAYER_CACHE['access_' + year][String(highlightSggCd)] || [];
    const gdata = raw.map(a => ({ position: [a[0], a[1]], mask: a[2], score: popcount(a[2]), pop: a[3] || 0, year }));
    layers.push(new deck.ScatterplotLayer({
      id: 'access-grids-' + year, data: gdata, getPosition: d => d.position, opacity: gridOpacity,
      getRadius: 230, radiusUnits: 'meters', radiusMinPixels: 2, radiusMaxPixels: 16,
      getFillColor: d => {
        if (gridColorMode === 'pop') {
          if (!d.pop) return [203, 213, 225, 140];
          const c = POP_SCALE(Math.min(1, d.pop / _gridPopMax)).rgb();
          return [c[0], c[1], c[2], 235];
        }
        const c = GRID_SCALE(d.score).rgb(); return [c[0], c[1], c[2], 235];
      },
      stroked: true, getLineColor: [255, 255, 255, 150], lineWidthMinPixels: 0.3,
      pickable: true, updateTriggers: { getFillColor: [highlightSggCd, gridColorMode] }
    }));
  }

  // ── 서비스권역 반경 원 (선택 시설 POI 주변, 연도별) ──
  if (svcOn && highlightSggCd != null) {
    const pts = LAYER_CACHE[`poi_${layerFac}_${year}`];
    const arr = (pts && pts[String(highlightSggCd)]) || [];
    const radM = svcRadiusM(year);
    layers.push(new deck.ScatterplotLayer({
      id: `svc-radius-${year}`,
      data: arr, getPosition: d => d,
      getRadius: radM, radiusUnits: 'meters',
      getFillColor: [16, 185, 129, 34],
      stroked: true, getLineColor: [5, 150, 105, 130], lineWidthMinPixels: 1,
      pickable: false,
      updateTriggers: { getPosition: [layerFac, highlightSggCd], getRadius: [layerFac] }
    }));
  }

  // ── 시설 POI 점 (POI 켬 또는 서비스권역 켬 → 시설 위치 필요) ──
  if ((poiOn || svcOn) && highlightSggCd != null) {
    const pts = LAYER_CACHE[`poi_${layerFac}_${year}`];
    const arr = (pts && pts[String(highlightSggCd)]) || [];
    const col = facColorRgb(layerFac);
    layers.push(new deck.ScatterplotLayer({
      id: `poi-${year}`,
      data: arr, getPosition: d => d,
      getRadius: 45, radiusUnits: 'meters', radiusMinPixels: 3.5, radiusMaxPixels: 9,
      getFillColor: [col[0], col[1], col[2], 235],
      stroked: true, getLineColor: [255, 255, 255, 230], lineWidthMinPixels: 1,
      pickable: true,
      updateTriggers: { getFillColor: [layerFac], getPosition: [layerFac, highlightSggCd] }
    }));
  }
  return layers;
}

// 격자 호버 시 범례 하단 패널에 표 형태로 표시
function updateGridDetail(d) {
  const div = document.getElementById('map-grid-detail');
  if (!div) return;
  if (!d) { div.style.display = 'none'; div.innerHTML = ''; return; }
  const bySec = { edu: [], care: [], med: [], safe: [], cult: [] };
  FACILITIES.forEach((f, i) => { bySec[f[2]].push({ kor: f[1], on: (d.mask >> i) & 1 }); });
  let html = `<div class="leg-title" style="margin-bottom:2px">
    선택 격자 (${d.year || Y2}년) · 충족 <span style="color:var(--ink)">${d.score}</span>/20</div>
    <div style="font-size:.72rem;color:var(--ink-2);margin-bottom:6px">👥 격자 인구: <b style="color:var(--ink)">${(d.pop || 0).toLocaleString()}명</b></div>`;
  SECTOR_ORDER.forEach((sk, idx) => {
    const s = SEC[sk];
    const onCnt = bySec[sk].filter(it => it.on).length;
    const tags = bySec[sk].map(it =>
      `<span style="padding:1px 4px;border-radius:3px;font-size:.9em;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border:1px solid ` +
      (it.on
        ? `var(--ink);background:var(--ink);color:#fff">${it.kor} ✓`
        : `var(--line);background:var(--soft);color:var(--ink-3)">${it.kor} ✕`) +
      `</span>`
    ).join('');
    html += `<div style="padding-top:6px;${idx ? 'border-top:1px solid var(--line);margin-top:6px' : ''}">
      <div style="font-weight:700;color:var(--ink);margin-bottom:3px">${s.label} <span style="font-weight:400;color:var(--ink-3);font-size:.9em">${onCnt}/${bySec[sk].length}</span></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">${tags}</div>
    </div>`;
  });
  div.innerHTML = html;
  div.style.display = 'block';
}

// 연도별 툴팁: 해당 연도 값 + 반대 연도 값 + Δ 병기
function mapTooltipFor(year) {
  return ({ object }) => {
    if (!object) return null;
    if (object.mask !== undefined) return null; // 격자 정보는 범례 하단 패널(updateGridDetail)에 표시
    if (Array.isArray(object)) {                // POI 점
      const e = facEntry(layerFac);
      return { html: `<b>${e ? e[1] : layerFac}</b> (${year}년 시설 위치)`, className: 'deck-tooltip' };
    }
    if (!object.properties) return null;
    const p = object.properties;
    const ml = METRIC_DEFS.find(m => m.key === curMetric)?.label || curMetric;
    const other = year === Y2 ? Y1 : Y2;
    const v  = valOf(year,  p.sgg_cd, curMetric);
    const vo = valOf(other, p.sgg_cd, curMetric);
    const d  = (v != null && vo != null) ? (year === Y2 ? v - vo : vo - v) : null;
    const dStr = d == null ? '' : `<br>Δ(${Y1}→${Y2}): <b>${(d > 0 ? '+' : '') + d.toFixed(1)}</b>`;
    const gradeStr = curClassify === 'decile' && v != null ? `<br>${year} 등급: <b>${getDecileGrade(v)}등급</b>` : '';
    return {
      html: `<b>${p.sido_nm_k} ${p.sgg_nm_k}</b><br>${ml}<br>` +
            `${year}: <b>${fAuto(v, curMetric)}</b> · ${other}: <b>${fAuto(vo, curMetric)}</b>${dStr}${gradeStr}`,
      className: 'deck-tooltip'
    };
  };
}

function initMap() {
  // 색상 분류 토글
  function updateClassifyUI() {
    ['equal','quantile','decile'].forEach(v => {
      const el = document.getElementById('lbl-' + v);
      if (!el) return;
      const on = curClassify === v;
      el.style.cssText += on ? ';background:var(--accent-sb);color:var(--accent);border-color:var(--accent-bd);font-weight:700'
                             : ';background:#fff;color:var(--ink);border-color:var(--line);font-weight:400';
    });
  }
  updateClassifyUI();
  document.querySelectorAll('input[name="classify"]').forEach(inp => {
    inp.addEventListener('change', () => {
      curClassify = inp.value; updateClassifyUI(); renderChoropleth();
    });
  });

  // 지표 라디오 목록
  let curGroup = '';
  document.getElementById('metric-list').innerHTML = METRIC_DEFS.map(m => {
    let groupHtml = '';
    if (m.group !== curGroup) {
      curGroup = m.group;
      groupHtml = `<li style="padding:6px 4px 2px;font-size:.7rem;color:var(--ink-2);font-weight:700;letter-spacing:.04em">${m.group}</li>`;
    }
    return `${groupHtml}<li>
      <input type="radio" name="metric" id="m_${m.key}" value="${m.key}" ${m.key === curMetric ? 'checked' : ''}>
      <label for="m_${m.key}">${m.label}</label>
    </li>`;
  }).join('');

  document.querySelectorAll('#metric-list input').forEach(inp => {
    inp.addEventListener('change', () => {
      curMetric = inp.value; renderChoropleth();
    });
  });

  // ── 시도 → 시군구 연동 선택 ──────────────────────────────────────────────
  const sidoBoundsMap = {};
  const hier = {};   // sido → [{sgg, cd}]
  GEOJSON.features.forEach(ft => {
    const sido = ft.properties.sido_nm_k, sgg = ft.properties.sgg_nm_k, cd = ft.properties.sgg_cd;
    const b = featureBounds(ft);
    if (!sidoBoundsMap[sido]) sidoBoundsMap[sido] = b.slice();
    else { const m = sidoBoundsMap[sido];
      m[0]=Math.min(m[0],b[0]); m[1]=Math.min(m[1],b[1]); m[2]=Math.max(m[2],b[2]); m[3]=Math.max(m[3],b[3]); }
    (hier[sido] || (hier[sido] = [])).push({ sgg, cd });
  });
  Object.values(hier).forEach(arr => arr.sort((a, b) => a.sgg.localeCompare(b.sgg, 'ko')));

  const sidoSel = document.getElementById('map-sido-sel');
  const sggSel  = document.getElementById('map-sgg-sel');
  const regionReset = document.getElementById('map-region-reset');
  sidoSel.innerHTML = '<option value="">시도 전체</option>' +
    Object.keys(hier).sort((a, b) => a.localeCompare(b, 'ko')).map(s => `<option value="${s}">${s}</option>`).join('');

  // 충족격자 토글 버튼 + POI·서비스권역 레이어 칩
  const gridToggleBtn = document.getElementById('grid-toggle-btn');
  const gridOpacityCtrl = document.getElementById('grid-opacity-ctrl');
  const gridOpacitySlider = document.getElementById('grid-opacity-slider');
  const layerChips = document.getElementById('layer-chips');
  const poiBtn = document.getElementById('lyr-poi-btn');
  const svcBtn = document.getElementById('lyr-svc-btn');
  const facSel = document.getElementById('lyr-fac-sel');
  facSel.innerHTML = SECTOR_ORDER.map(sk =>
    `<optgroup label="${SEC[sk].label}">${FACILITIES.filter(f => f[2] === sk)
      .map(f => `<option value="${f[0]}">${f[1]}</option>`).join('')}</optgroup>`).join('');
  facSel.value = layerFac;

  function chipStyle(btn, on) {
    btn.style.background  = on ? 'var(--accent-sb)' : '';
    btn.style.color       = on ? 'var(--accent)' : '';
    btn.style.borderColor = on ? 'var(--accent-bd)' : '';
    btn.style.fontWeight  = on ? '700' : '';
  }
  const gridColorCtrl = document.getElementById('grid-color-ctrl');
  function updateGridBtnUI() {
    gridToggleBtn.textContent = '📊 충족격자';
    chipStyle(gridToggleBtn, gridLayerOn);
    gridOpacityCtrl.style.display = gridLayerOn ? 'inline-flex' : 'none';
    gridColorCtrl.style.display = gridLayerOn ? 'inline-flex' : 'none';
    if (!gridLayerOn) updateGridDetail(null);
  }
  function updateLayerChipUI() {
    chipStyle(poiBtn, poiOn);
    chipStyle(svcBtn, svcOn);
    facSel.style.display = (poiOn || svcOn) ? '' : 'none';   // POI·서비스권역 공용 시설 선택
  }
  const gridInfoWrap = document.getElementById('grid-info-wrap');
  // 레이어 칩은 상세보기 모드 + 시군구 선택 시에만 노출
  function showGridToggle(on) {
    on = on && mapMode === 'detail';
    if (!on) {
      gridLayerOn = false; updateGridBtnUI();
      poiOn = false; svcOn = false; updateLayerChipUI();
    }
    gridToggleBtn.style.display = on ? '' : 'none';
    gridInfoWrap.style.display = on ? 'inline-flex' : 'none';
    layerChips.style.display = on ? 'inline-flex' : 'none';
  }
  // 상세보기 모드에서 시군구 선택 → 격자·서비스권역 자동 활성화
  function autoEnableDetailLayers() {
    if (mapMode !== 'detail' || highlightSggCd == null) return;
    gridLayerOn = true; svcOn = true;
    updateGridBtnUI(); updateLayerChipUI();
    refreshOverlayLayers();
  }
  gridToggleBtn.addEventListener('click', () => {
    if (highlightSggCd == null) return;
    gridLayerOn = !gridLayerOn; updateGridBtnUI(); refreshOverlayLayers();
  });
  document.getElementById('gcm-score').addEventListener('click', () => {
    gridColorMode = 'score';
    document.getElementById('gcm-score').classList.add('active');
    document.getElementById('gcm-pop').classList.remove('active');
    renderChoropleth();
  });
  document.getElementById('gcm-pop').addEventListener('click', () => {
    gridColorMode = 'pop';
    document.getElementById('gcm-pop').classList.add('active');
    document.getElementById('gcm-score').classList.remove('active');
    renderChoropleth();
  });

  // ── 지도 모드 전환 (연도 비교 ↔ 상세보기) ──
  const modeSeg = document.getElementById('map-mode-seg');
  function setMapMode(m) {
    if (m === mapMode) return;
    mapMode = m;
    modeSeg.querySelectorAll('button').forEach(b => b.classList.toggle('active', b.dataset.m === m));
    if (m === 'compare') {
      showGridToggle(false);
      renderChoropleth();
    } else {
      showGridToggle(highlightSggCd != null);
      if (highlightSggCd != null) autoEnableDetailLayers();
      else renderChoropleth();
    }
    setTimeout(() => { deckMap && deckMap.redraw(true); deckMap1 && deckMap1.redraw(true); }, 90);
  }
  modeSeg.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (b) setMapMode(b.dataset.m);
  });
  poiBtn.addEventListener('click', () => {
    if (highlightSggCd == null) return;
    poiOn = !poiOn; updateLayerChipUI(); refreshOverlayLayers();
  });
  svcBtn.addEventListener('click', () => {
    if (highlightSggCd == null) return;
    svcOn = !svcOn; updateLayerChipUI(); refreshOverlayLayers();
  });
  facSel.addEventListener('change', () => {
    layerFac = facSel.value;
    refreshOverlayLayers();
  });
  gridOpacitySlider.addEventListener('input', () => {
    gridOpacity = +gridOpacitySlider.value / 100;
    if (gridLayerOn) renderChoropleth();
  });

  function resetRegion() {
    sidoSel.value = ''; sggSel.innerHTML = '<option value="">시군구</option>'; sggSel.disabled = true;
    curSidoFilter = null; highlightSggCd = null; regionReset.style.display = 'none';
    showGridToggle(false); closeMapSheet();
    renderChoropleth();
    mapViewState = { longitude: 127.8, latitude: 36.2, zoom: 6.1, pitch: 0, bearing: 0, transitionDuration: 600 };
    deckMap.setProps({ initialViewState: { ...mapViewState } });
    if (deckMap1) deckMap1.setProps({ initialViewState: { ...mapViewState } });
  }

  sidoSel.addEventListener('change', () => {
    const sido = sidoSel.value;
    highlightSggCd = null;
    if (!sido) { resetRegion(); return; }
    curSidoFilter = sido;
    sggSel.disabled = false;
    sggSel.innerHTML = '<option value="">시군구 전체</option>' +
      hier[sido].map(o => `<option value="${o.cd}">${o.sgg}</option>`).join('');
    regionReset.style.display = '';
    showGridToggle(false);   // 시군구 미선택 → 격자 숨김
    renderChoropleth();
    flyToBounds(sidoBoundsMap[sido], 10);
  });

  sggSel.addEventListener('change', () => {
    const cd = sggSel.value;
    if (!cd) {
      highlightSggCd = null; showGridToggle(false); closeMapSheet(); renderChoropleth();
      if (curSidoFilter) flyToBounds(sidoBoundsMap[curSidoFilter], 10);
      return;
    }
    const ft = GEOJSON.features.find(f => String(f.properties.sgg_cd) === String(cd));
    if (!ft) return;
    highlightSggCd = ft.properties.sgg_cd;
    showGridToggle(true);    // 시군구 선택 → 레이어 칩 노출 (상세보기 모드)
    renderChoropleth();
    autoEnableDetailLayers();
    flyToBounds(featureBounds(ft), 11, 0.05);
    showMapInfo(ft.properties);
  });

  // 지도 클릭 = 드롭다운 시군구 선택과 동일 동작 (격자 토글 노출 포함)
  function pickSgg(ft) {
    if (!ft || !ft.properties || ft.properties.sgg_cd == null) return;
    const sido = ft.properties.sido_nm_k, cd = ft.properties.sgg_cd;
    if (sidoSel.value !== sido) {
      sidoSel.value = sido; curSidoFilter = sido; sggSel.disabled = false;
      sggSel.innerHTML = '<option value="">시군구 전체</option>' +
        hier[sido].map(o => `<option value="${o.cd}">${o.sgg}</option>`).join('');
    }
    sggSel.value = String(cd);
    curSidoFilter = sido; highlightSggCd = cd;
    regionReset.style.display = ''; showGridToggle(true);
    renderChoropleth();
    autoEnableDetailLayers();
    flyToBounds(featureBounds(ft), 11, 0.05);
    showMapInfo(ft.properties);
  }

  regionReset.addEventListener('click', resetRegion);

  // 범례 + 격자 상세 오버레이 (우측 세로 컬럼)
  const overlayRight = document.createElement('div');
  overlayRight.className = 'map-overlay-right';
  const legendDiv = document.createElement('div');
  legendDiv.className = 'map-legend'; legendDiv.id = 'map-legend';
  const svcDetailDiv = document.createElement('div');
  svcDetailDiv.id = 'map-svc-detail';
  svcDetailDiv.addEventListener('click', e => {
    const row = e.target.closest('.svc-row');
    if (!row || row.dataset.fac === layerFac) return;
    layerFac = row.dataset.fac;
    const sel = document.getElementById('lyr-fac-sel');
    if (sel) sel.value = layerFac;
    refreshOverlayLayers();
  });
  const gridDetailDiv = document.createElement('div');
  gridDetailDiv.id = 'map-grid-detail';
  overlayRight.appendChild(legendDiv);
  overlayRight.appendChild(svcDetailDiv);
  overlayRight.appendChild(gridDetailDiv);
  document.getElementById('map').appendChild(overlayRight);

  // 지역 상세 하단 시트
  const sheet = document.createElement('div');
  sheet.className = 'map-sheet'; sheet.id = 'map-sheet';
  sheet.innerHTML = '<button class="map-sheet-close" title="닫기">×</button><div id="map-sheet-body"></div>';
  document.getElementById('map').appendChild(sheet);
  sheet.querySelector('.map-sheet-close').addEventListener('click', closeMapSheet);

  // 연도 칩 라벨
  document.getElementById('map-chip-y1').textContent = Y1 + '년';
  document.getElementById('map-chip-y2').textContent = Y2 + '년';

  // deck.gl 초기화 (V-World 베이스맵) — 듀얼 맵, 뷰 상태 동기화
  function syncedView(self, other) {
    return ({ viewState }) => {
      mapViewState = viewState;
      if (_vsSyncing) return;
      _vsSyncing = true;
      other().setProps({ initialViewState: { ...viewState, transitionDuration: 0 } });
      _vsSyncing = false;
    };
  }
  deckMap = new deck.DeckGL({
    container: document.getElementById('map'),
    initialViewState: { ...mapViewState },
    controller: true,
    layers: [],
    getTooltip: mapTooltipFor(Y2),
    onHover: info => updateGridDetail(info && info.object && info.object.mask !== undefined ? info.object : null),
    onViewStateChange: syncedView(() => deckMap, () => deckMap1),
    onClick: info => {
      if (info && info.object && info.object.properties) pickSgg(info.object);
    }
  });
  deckMap1 = new deck.DeckGL({
    container: document.getElementById('map1'),
    initialViewState: { ...mapViewState },
    controller: true,
    layers: [],
    getTooltip: mapTooltipFor(Y1),
    onHover: info => updateGridDetail(info && info.object && info.object.mask !== undefined ? info.object : null),
    onViewStateChange: syncedView(() => deckMap1, () => deckMap),
    onClick: info => {
      if (info && info.object && info.object.properties) pickSgg(info.object);
    }
  });

  renderChoropleth();
}

function renderChoropleth() {
  if (!deckMap) return;
  computeColorState();   // 등급은 두 연도 통합 전국 기준 (시도 필터와 무관)
  // 격자 인구 색상 상한: 두 연도 합산 95분위 → 좌우 지도가 같은 스케일
  if (gridLayerOn && highlightSggCd != null) {
    const cd = String(highlightSggCd);
    const pops = [];
    [Y1, Y2].forEach(y => {
      const AG = LAYER_CACHE['access_' + y];
      ((AG && AG[cd]) || []).forEach(a => { if (a[3] > 0) pops.push(a[3]); });
    });
    pops.sort((x, y) => x - y);
    _gridPopMax = pops.length ? Math.max(1, pops[Math.floor(pops.length * 0.95)]) : 1;
  }
  deckMap.setProps({ layers: buildMapLayers(Y2) });
  if (deckMap1) deckMap1.setProps({ layers: buildMapLayers(Y1) });
  updateMapLegend();
  updateSvcPanel();
}

// POI·서비스권역 범례 블록 (켜져 있을 때만; 비율 수치는 별도 패널)
function overlayLegendHtml() {
  if ((!poiOn && !svcOn) || highlightSggCd == null) return '';
  const e = facEntry(layerFac);
  let html = `<div style="border-top:1px solid var(--line);margin-top:7px;padding-top:6px">
    <div class="leg-row"><div class="leg-dot" style="background:${SEC[e[2]].color};border-radius:50%"></div><span>${e[1]} 위치 (좌 ${Y1} · 우 ${Y2})</span></div>`;
  if (svcOn) {
    const km = (svcRadiusM(Y2) / 1000).toFixed(1).replace(/\.0$/, '');
    html += `<div class="leg-row"><div class="leg-dot" style="background:rgba(16,185,129,.35);border:1px solid #059669;border-radius:50%"></div><span>서비스권역 (반경 ${km}km)</span></div>`;
  }
  return html + '</div>';
}

function updateMapLegend() {
  const div = document.getElementById('map-legend');
  if (!div) return;
  if (gridLayerOn) {
    let gl;
    if (gridColorMode === 'pop') {
      gl = `<div class="leg-title">격자 인구 (명)</div>
        <div style="display:flex;height:11px;border-radius:3px;overflow:hidden;margin-bottom:4px">${
          [0,.2,.4,.6,.8,1].map(t => `<div style="flex:1;background:${POP_SCALE(t).hex()}"></div>`).join('')
        }</div>
        <div style="display:flex;justify-content:space-between;font-size:.68rem;color:var(--ink-2)"><span>0</span><span>${Math.round(_gridPopMax/2).toLocaleString()}</span><span>${Math.round(_gridPopMax).toLocaleString()}+</span></div>
        <div style="font-size:.66rem;color:var(--ink-3);margin-top:4px">회색 = 인구 0 격자</div>`;
    } else {
      gl = `<div class="leg-title">충족 점수 (1~20)</div>
        <div style="display:flex;height:11px;border-radius:3px;overflow:hidden;margin-bottom:4px">${
          [1,4,7,10,13,16,20].map(s => `<div style="flex:1;background:${GRID_SCALE(s).hex()}"></div>`).join('')
        }</div>
        <div style="display:flex;justify-content:space-between;font-size:.68rem;color:var(--ink-2)"><span>1</span><span>10</span><span>20</span></div>
        <div style="font-size:.66rem;color:var(--ink-3);margin-top:4px">좌 ${Y1}년 · 우 ${Y2}년 격자 (0점·무인구 격자는 제외)</div>`;
    }
    div.innerHTML = gl + overlayLegendHtml();
    return;
  }
  const metricLabel = METRIC_DEFS.find(m => m.key === curMetric)?.label || curMetric;
  let html = `<div class="leg-title">${metricLabel}</div>
    <div style="font-size:.64rem;color:var(--ink-3);margin-bottom:5px">${Y1}·${Y2} 공통 등급 (통합 분포 기준)</div>`;
  if (curClassify === 'decile') {
    for (let g = 1; g <= 10; g++) {
      const lo = decileBreaks[10 - g];
      const hi = g === 1 ? decileBreaks[10] : decileBreaks[10 - g + 1];
      html += `<div class="leg-row"><div class="leg-dot" style="background:${decileColors[g-1]}"></div><span>${g}등급 ${fAuto(lo, curMetric)}–${fAuto(hi, curMetric)}</span></div>`;
    }
  } else if (curClassify === 'quantile') {
    for (let i = _qBreaks.length - 2; i >= 0; i--) {
      const mid = (_qBreaks[i] + _qBreaks[i+1]) / 2;
      html += `<div class="leg-row"><div class="leg-dot" style="background:${_colorScale(mid).hex()}"></div><span>${fAuto(_qBreaks[i], curMetric)} – ${fAuto(_qBreaks[i+1], curMetric)}</span></div>`;
    }
  } else {
    const steps = 5;
    for (let i = steps; i >= 0; i--) {
      const v = _mn + (_mx - _mn) * (i / steps);
      html += `<div class="leg-row"><div class="leg-dot" style="background:${_colorScale(v).hex()}"></div><span>${fAuto(v, curMetric)}</span></div>`;
    }
  }
  div.innerHTML = html + overlayLegendHtml();
}

function showMapInfo(p) {
  const label = METRIC_DEFS.find(m => m.key === curMetric)?.label || curMetric;
  const cd = p.sgg_cd;
  const v1 = valOf(Y1, cd, curMetric), v2 = valOf(Y2, cd, curMetric);
  const r1 = rankOf(Y1, curMetric, cd), r2 = rankOf(Y2, curMetric, cd);
  const body = document.getElementById('map-sheet-body');
  if (!body) return;

  const yearBlock = (y, v, r, latest) => `
    <div style="display:flex;flex-direction:column;gap:1px;${latest ? '' : 'opacity:.75'}">
      <span class="${latest ? 'yr2-chip' : 'yr1-chip'}" style="align-self:flex-start">${y}</span>
      <span style="font-size:1.55rem;font-weight:700;letter-spacing:-.5px;color:${v != null ? colorFor(v, _mn, _mx) : '#999'}">${fAuto(v, curMetric)}</span>
      ${r ? `<span style="font-size:.72rem;color:var(--ink-2)">전국 ${r}위 / ${RECORDS.length}</span>` : ''}
    </div>`;

  body.innerHTML = `
    <div style="display:flex;align-items:center;gap:22px;flex-wrap:wrap">
      <div style="min-width:150px">
        <div style="font-weight:700;font-size:1.02rem;margin-bottom:2px">${p.sido_nm_k} ${p.sgg_nm_k}</div>
        <div style="font-size:.74rem;color:var(--ink-2)">${label}</div>
      </div>
      ${yearBlock(Y1, v1, r1, false)}
      <div style="font-size:1.1rem;color:var(--ink-3)">→</div>
      ${yearBlock(Y2, v2, r2, true)}
      <div style="display:flex;flex-direction:column;gap:2px">
        <span style="font-size:.7rem;color:var(--ink-2);font-weight:700">Δ / 순위변화</span>
        <span style="font-size:1.05rem">${deltaHtml(v1 != null && v2 != null ? v2 - v1 : null)} ${rankDeltaHtml(r1, r2)}</span>
      </div>
      <div style="margin-left:auto;display:flex;flex-direction:column;gap:6px;min-width:230px">
        <div style="font-size:.74rem;font-weight:700;color:var(--ink-2)">종합지수 ${Y2}년
          <span style="color:var(--ink);font-size:.92rem">${f1(valOf(Y2, cd, 'infra_idx'))}점</span>
          ${deltaHtml((valOf(Y2, cd, 'infra_idx') ?? 0) - (valOf(Y1, cd, 'infra_idx') ?? 0))}</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          ${Object.entries(SEC).map(([k, s]) =>
            `<span class="score-badge" style="background:${s.color}22;color:${s.color}">${s.label} ${f1(valOf(Y2, cd, k + '_conv'))}</span>`
          ).join('')}
        </div>
      </div>
    </div>`;
  document.getElementById('map-sheet').classList.add('open');
}

function closeMapSheet() {
  const s = document.getElementById('map-sheet');
  if (s) s.classList.remove('open');
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 3 : 시군구 상세
// ══════════════════════════════════════════════════════════════════════════════
let radarChart = null, barChart = null;
let detailYear = String(Y2);   // 상세 탭 표시 연도

function renderDetailYearSeg() {
  const seg = document.getElementById('detail-year-seg');
  seg.innerHTML = YEAR_LIST.map(y =>
    `<button class="${y === detailYear ? 'active' : ''}" data-y="${y}">${y}년</button>`).join('');
}

function initDetail() {
  renderDetailYearSeg();
  document.getElementById('detail-year-seg').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b || b.dataset.y === detailYear) return;
    detailYear = b.dataset.y;
    renderDetailYearSeg();
    if (detailSelCd != null) {
      const r = findIn(recsOf(detailYear), detailSelCd);
      if (r) renderDetail(r);
    }
  });

  const hier = {};
  RECORDS.forEach(r => { (hier[r.sido_nm_k] = hier[r.sido_nm_k] || []).push(r); });
  Object.values(hier).forEach(arr => arr.sort((a, b) => a.sgg_nm_k.localeCompare(b.sgg_nm_k, 'ko')));

  const listEl = document.getElementById('region-list');
  listEl.innerHTML = Object.keys(hier).sort((a, b) => a.localeCompare(b, 'ko')).map(sido =>
    `<div class="sido-item" data-sido="${sido}">
      <div class="sido-header"><span class="sido-toggle">▶</span><span class="sido-name">${sido}</span><span class="sido-cnt">${hier[sido].length}</span></div>
      <div class="sgg-list">${hier[sido].map(r =>
        `<div class="sgg-item" data-cd="${r.sgg_cd}"><span class="sgg-nm">${r.sgg_nm_k}</span><span class="sgg-check">✓</span></div>`
      ).join('')}</div>
    </div>`
  ).join('');

  listEl.addEventListener('click', e => {
    const sgg = e.target.closest('.sgg-item');
    if (sgg) {
      listEl.querySelectorAll('.sgg-item.selected').forEach(el => el.classList.remove('selected'));
      sgg.classList.add('selected');
      const rec = RECORDS.find(r => String(r.sgg_cd) === sgg.dataset.cd);
      if (rec) renderDetail(rec);
      return;
    }
    const header = e.target.closest('.sido-header');
    if (header) {
      header.querySelector('.sido-toggle').classList.toggle('open');
      header.parentElement.querySelector('.sgg-list').classList.toggle('open');
    }
  });

  document.getElementById('region-search').addEventListener('input', e => filterDetailRegions(e.target.value));
}

function filterDetailRegions(q) {
  q = q.trim().toLowerCase();
  document.querySelectorAll('#region-list .sido-item').forEach(div => {
    const sido = div.dataset.sido.toLowerCase();
    let any = false;
    div.querySelectorAll('.sgg-item').forEach(si => {
      const m = !q || sido.includes(q) || si.querySelector('.sgg-nm').textContent.toLowerCase().includes(q);
      si.style.display = m ? '' : 'none';
      if (m) any = true;
    });
    div.style.display = (!q || sido.includes(q) || any) ? '' : 'none';
    if (q && any) {
      div.querySelector('.sgg-list').classList.add('open');
      div.querySelector('.sido-toggle').classList.add('open');
    }
  });
}

function renderDetail(rec) {
  document.getElementById('detail-content').style.display = 'block';
  document.getElementById('detail-placeholder').style.display = 'none';

  detailSelCd = rec.sgg_cd;
  // 선택 연도 레코드 기준으로 표시
  const R = recsOf(detailYear);
  const ry = findIn(R, rec.sgg_cd) || rec;

  const rank = rankIn(R, 'infra_idx', ry.infra_idx);
  const pct  = _pctIn(R, 'infra_idx', ry.infra_idx);
  document.getElementById('detail-rank-badge').style.display = 'inline-block';
  document.getElementById('detail-rank-badge').innerHTML =
    `${ry.sido_nm_k} ${ry.sgg_nm_k} · ${detailYear}년 종합지수 ${f1(ry.infra_idx)}점 | 전국 ${rank}위 / ${R.length} (상위 ${pct}%)`;

  const secKeys = Object.keys(SEC);
  const secLabels = secKeys.map(k => SEC[k].label);
  // 레이더 부문 순서: 시계방향이 표 순서(교육→돌봄→보건→안전→체육)가 되도록 꼬리 역순
  const radarKeys = [secKeys[0], ...secKeys.slice(1).reverse()];
  const radarLabels = radarKeys.map(k => SEC[k].label);
  const recConv = radarKeys.map(k => +(ry[k + '_conv'] || 0).toFixed(3));

  // 시도 평균 (선택 연도 기준)
  const sidoPeers = R.filter(r => r.sido_nm_k === ry.sido_nm_k);
  const sidoAvg = radarKeys.map(k => {
    const vals = sidoPeers.map(r => r[k + '_conv']).filter(v => v != null);
    return +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(3);
  });

  // 레이더 축 범위: 실제 그려지는 값에 타이트하게 + 여백 35%
  const drawnVals = [...recConv, ...sidoAvg];
  const _mnC = Math.min(...drawnVals), _mxC = Math.max(...drawnVals);
  const _pad = Math.max((_mxC - _mnC) * 0.35, 3);
  const radarMin = Math.floor(_mnC - _pad);
  const radarMax = Math.ceil(_mxC + _pad);

  // Radar — 선택 지역 vs 시도 평균 (선택 연도)
  if (!radarChart) radarChart = echarts.init(document.getElementById('radar-chart'));
  radarChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { data: ['선택 지역', `${ry.sido_nm_k} 평균`], bottom: 0, textStyle: { fontSize: 11 } },
    radar: {
      indicator: radarLabels.map(name => ({ name, max: radarMax, min: radarMin })),
      radius: '62%',
      axisName: { fontSize: 11 },
      splitArea: { areaStyle: { color: ['#FAFAFA', '#F1F5F9'] } }
    },
    series: [{
      type: 'radar',
      data: [
        { value: recConv, name: '선택 지역',
          lineStyle: { color: '#2563EB', width: 2 }, itemStyle: { color: '#2563EB' }, areaStyle: { color: 'rgba(37,99,235,.18)' } },
        { value: sidoAvg, name: `${ry.sido_nm_k} 평균`,
          lineStyle: { color: '#F59E0B', width: 1.5, type: 'dashed' }, itemStyle: { color: '#F59E0B' }, areaStyle: { color: 'rgba(245,158,11,.1)' } },
      ]
    }]
  }, true);

  // Bar — 공급·향유·충족 (선택 연도)
  if (!barChart) barChart = echarts.init(document.getElementById('bar-chart'));
  const dims = [
    { sfx: 'sup', label: '공급수준', color: '#60A5FA' },
    { sfx: 'pop', label: '향유수준', color: '#34D399' },
    { sfx: 'acc', label: '충족수준', color: '#F472B6' },
  ];
  barChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: {
      data: dims.map(d => d.label),
      bottom: 0, textStyle: { fontSize: 10 }, itemWidth: 12, itemHeight: 10,
    },
    xAxis: { data: secLabels, axisLabel: { interval: 0, fontSize: 11 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
    grid: { bottom: 40 },
    series: dims.map(d => ({
      name: d.label, type: 'bar', barGap: '10%',
      itemStyle: { color: d.color },
      data: secKeys.map(k => +(ry[k + '_' + d.sfx] || 0).toFixed(3)),
    }))
  }, true);

  // Detail table — 선택 연도 값
  const tableRows = secKeys.map(k => {
    const s = SEC[k];
    const key = k + '_conv';
    const cv = ry[key];
    const rk = rankIn(R, key, cv);
    const p = _pctIn(R, key, cv);
    const vals = R.map(r => r[key]).filter(v => v != null && !isNaN(+v));
    const c = colorFor(cv, Math.min(...vals), Math.max(...vals));
    return `<tr>
      <td><span class="sector-chip" style="background:${s.color}">${s.label}</span></td>
      <td><span class="score-badge" style="background:${c}22;color:${c}">${f1(cv)}</span></td>
      <td style="color:#64748B;font-size:.8rem">${rk}위 (상위 ${p}%)</td>
      <td>${f1(ry[k + '_sup'])}</td>
      <td>${f1(ry[k + '_pop'])}</td>
      <td>${f1(ry[k + '_acc'])}</td>
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
let cmpChart = null, cmpBarChart = null;
let cmpMode = 'direct'; // 'direct' | 'pop' | 'area'
let cmpSel = [];        // 선택된 시군구 sgg_cd 목록 (직접:최대2, 유사:1)
let cmpYear = String(Y2);   // 비교 탭 표시 연도

function renderCmpYearSeg() {
  const seg = document.getElementById('cmp-year-seg');
  seg.innerHTML = YEAR_LIST.map(y =>
    `<button class="${y === cmpYear ? 'active' : ''}" data-y="${y}">${y}년</button>`).join('');
}
const CMP_COLORS = ['#2563EB', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6'];

// 시도→시군구 접이식 목록 HTML (상세/비교 공용 구조)
function regionListHtml() {
  const hier = {};
  RECORDS.forEach(r => { (hier[r.sido_nm_k] = hier[r.sido_nm_k] || []).push(r); });
  Object.values(hier).forEach(arr => arr.sort((a, b) => a.sgg_nm_k.localeCompare(b.sgg_nm_k, 'ko')));
  return Object.keys(hier).sort((a, b) => a.localeCompare(b, 'ko')).map(sido =>
    `<div class="sido-item" data-sido="${sido}">
      <div class="sido-header"><span class="sido-toggle">▶</span><span class="sido-name">${sido}</span><span class="sido-cnt">${hier[sido].length}</span></div>
      <div class="sgg-list">${hier[sido].map(r =>
        `<div class="sgg-item" data-cd="${r.sgg_cd}"><span class="sgg-nm">${r.sgg_nm_k}</span><span class="sgg-check">✓</span></div>`
      ).join('')}</div>
    </div>`
  ).join('');
}

// 접이식 목록 검색 필터 (root: #region-list 또는 #cmp-region-list)
function filterRegionTree(root, q) {
  q = q.trim().toLowerCase();
  root.querySelectorAll('.sido-item').forEach(div => {
    const sido = div.dataset.sido.toLowerCase();
    let any = false;
    div.querySelectorAll('.sgg-item').forEach(si => {
      const m = !q || sido.includes(q) || si.querySelector('.sgg-nm').textContent.toLowerCase().includes(q);
      si.style.display = m ? '' : 'none';
      if (m) any = true;
    });
    div.style.display = (!q || sido.includes(q) || any) ? '' : 'none';
    if (q && any) {
      div.querySelector('.sgg-list').classList.add('open');
      div.querySelector('.sido-toggle').classList.add('open');
    }
  });
}

function initRanking() {
  renderCmpYearSeg();
  document.getElementById('cmp-year-seg').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b || b.dataset.y === cmpYear) return;
    cmpYear = b.dataset.y;
    renderCmpYearSeg();
    renderComparison();
  });

  const listEl = document.getElementById('cmp-region-list');
  listEl.innerHTML = regionListHtml();

  listEl.addEventListener('click', e => {
    const sgg = e.target.closest('.sgg-item');
    if (sgg) { cmpToggleSel(sgg.dataset.cd); return; }
    const header = e.target.closest('.sido-header');
    if (header) {
      header.querySelector('.sido-toggle').classList.toggle('open');
      header.parentElement.querySelector('.sgg-list').classList.toggle('open');
    }
  });

  document.getElementById('cmp-region-search')
    .addEventListener('input', e => filterRegionTree(listEl, e.target.value));

  // 칩 제거
  document.getElementById('cmp-chips').addEventListener('click', e => {
    const x = e.target.closest('.chip-x');
    if (!x) return;
    const cd = x.parentElement.dataset.cd;
    const i = cmpSel.indexOf(cd);
    if (i >= 0) cmpSel.splice(i, 1);
    cmpSyncUI();
  });

  // 비교 방식 토글
  document.querySelectorAll('#tab-ranking .cmp-mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      cmpMode = btn.dataset.mode;
      document.querySelectorAll('#tab-ranking .cmp-mode-btn').forEach(b => b.classList.toggle('active', b === btn));
      if (cmpMode !== 'direct' && cmpSel.length > 1) cmpSel = cmpSel.slice(0, 1);
      document.getElementById('cmp-sel-hint').textContent =
        cmpMode === 'direct' ? '시군구를 선택하세요 (최대 2곳 비교)'
        : cmpMode === 'pop'  ? '기준 시군구 1개를 선택하세요 (인구 유사 4곳 자동)'
                             : '기준 시군구 1개를 선택하세요 (면적 유사 4곳 자동)';
      cmpSyncUI();
    });
  });
}

// 목록 선택 토글 (직접:최대2 FIFO, 유사:1)
function cmpToggleSel(cd) {
  const i = cmpSel.indexOf(cd);
  if (i >= 0) { cmpSel.splice(i, 1); }
  else {
    const cap = cmpMode === 'direct' ? 2 : 1;
    cmpSel.push(cd);
    while (cmpSel.length > cap) cmpSel.shift();
  }
  cmpSyncUI();
}

function cmpSyncUI() {
  document.querySelectorAll('#cmp-region-list .sgg-item')
    .forEach(el => el.classList.toggle('selected', cmpSel.includes(el.dataset.cd)));
  const wrap = document.getElementById('cmp-chips');
  wrap.innerHTML = cmpSel.map((cd, i) => {
    const r = RECORDS.find(x => String(x.sgg_cd) === cd);
    return r ? `<span class="cmp-chip" style="background:${CMP_COLORS[i]}" data-cd="${cd}">${r.sido_nm_k} ${r.sgg_nm_k}<span class="chip-x">×</span></span>` : '';
  }).join('');
  renderComparison();
}

// 유사 지역 찾기 (key: 'popall' or 'area', n: 개수, recs: 대상 연도 레코드)
function findSimilar(base, key, n = 4, recs) {
  return (recs || RECORDS)
    .filter(r => r.sgg_cd !== base.sgg_cd && r[key] != null)
    .map(r => ({ ...r, _diff: Math.abs((r[key] || 0) - (base[key] || 0)) }))
    .sort((a, b) => a._diff - b._diff)
    .slice(0, n);
}

function fNum(v) {
  if (v == null) return '-';
  return v >= 10000 ? (v / 10000).toFixed(1) + '만' : Math.round(v).toLocaleString();
}

function renderComparison() {
  const content = document.getElementById('cmp-content');
  const ph = document.getElementById('cmp-placeholder');
  const R = recsOf(cmpYear);   // 선택 연도 레코드
  const base = cmpSel.length ? R.find(r => String(r.sgg_cd) === cmpSel[0]) : null;
  const ready = !!base;   // 1곳만 선택해도 바로 펼쳐 보여주고, 2번째를 더하면 비교가 된다
  if (!ready) {
    content.style.display = 'none';
    ph.style.display = 'block';
    ph.textContent = '왼쪽 목록에서 시군구를 선택하면 분석 결과가 표시됩니다.';
    document.querySelector('#tab-ranking .region-panel').style.height = ''; // 기본 736px
    return;
  }
  content.style.display = 'block';
  ph.style.display = 'none';

  const secKeys = Object.keys(SEC);
  const secLabels = secKeys.map(k => SEC[k].label);
  // 레이더가 시계방향으로 표와 같은 순서(교육→돌봄→보건→안전→체육)가 되도록 꼬리를 역순
  const radarKeys = [secKeys[0], ...secKeys.slice(1).reverse()];
  const radarLabels = radarKeys.map(k => SEC[k].label);

  const COLORS = CMP_COLORS;

  let compareList = []; // 비교할 지역 목록 (base 제외)
  if (cmpMode === 'direct') {
    const b = R.find(r => String(r.sgg_cd) === cmpSel[1]);
    if (b) compareList = [b];
  } else {
    const simKey = cmpMode === 'pop' ? 'popall' : 'area';
    compareList = findSimilar(base, simKey, 4, R);
  }

  // 지역 표시명: 시도 + 시군구 (중복 이름 구분)
  const rName = r => r.sido_nm_k + ' ' + r.sgg_nm_k;

  const allRegions = [base, ...compareList];
  // 축 범위: 비교 지역들의 실제 값에 타이트하게 + 여백 35%
  const drawnVals = allRegions.flatMap(r => secKeys.map(k => r[k + '_conv']).filter(v => v != null));
  const _mnC = Math.min(...drawnVals), _mxC = Math.max(...drawnVals);
  const _pad = Math.max((_mxC - _mnC) * 0.35, 3);
  const radarMin = Math.floor(_mnC - _pad);
  const radarMax = Math.ceil(_mxC + _pad);

  // ── 레이더 차트 (선택 연도) ──
  const radarData = allRegions.map((r, i) => ({
    value: radarKeys.map(k => +(r[k + '_conv'] || 0).toFixed(3)),
    name: rName(r),
    lineStyle: { color: COLORS[i] },
    itemStyle: { color: COLORS[i] },
    areaStyle: { opacity: i === 0 ? .2 : .07 }
  }));

  if (!cmpChart) cmpChart = echarts.init(document.getElementById('cmp-radar'));
  cmpChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { data: radarData.map(d => d.name), bottom: 0, textStyle: { fontSize: 10 }, itemWidth: 10 },
    radar: {
      indicator: radarLabels.map(name => ({ name, max: radarMax, min: radarMin })),
      radius: '68%', center: ['50%', '48%'], axisName: { fontSize: 11 },
      splitArea: { areaStyle: { color: ['#FAFAFA', '#F1F5F9'] } }
    },
    series: [{ type: 'radar', data: radarData }]
  }, true);

  // ── 막대 차트 (5개 부문, 선택 연도) ──
  if (!cmpBarChart) cmpBarChart = echarts.init(document.getElementById('cmp-bar'));
  cmpBarChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: allRegions.map(rName), bottom: 0, textStyle: { fontSize: 10 }, itemWidth: 10 },
    grid: { left: 44, right: 14, top: 18, bottom: 54 },
    xAxis: { type: 'category', data: secLabels, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', min: radarMin, max: radarMax },
    series: allRegions.map((r, i) => ({
      name: rName(r), type: 'bar',
      data: secKeys.map(k => +(r[k + '_conv'] || 0).toFixed(1)),
      itemStyle: { color: COLORS[i] }
    }))
  }, true);

  // 비교 테이블
  const simKey = cmpMode === 'pop' ? 'popall' : cmpMode === 'area' ? 'area' : null;
  const simLabel = cmpMode === 'pop' ? '인구' : cmpMode === 'area' ? '면적(km²)' : null;

  const headerCells = allRegions.map((r, i) =>
    `<th style="color:${COLORS[i]}">${rName(r)}</th>`).join('');

  // 유사도 행 (직접 선택 아닐 때)
  let simRow = '';
  if (simKey && compareList.length) {
    const simVals = allRegions.map(r => {
      const v = r[simKey];
      return simKey === 'popall' ? fNum(v) : (v ? v.toFixed(1) : '-');
    });
    simRow = `<tr style="background:#F8FAFC">
      <td style="color:#94A3B8;font-size:.78rem">${simLabel}</td>
      ${simVals.map(v => `<td style="font-size:.8rem">${v}</td>`).join('')}
    </tr>`;
  }

  const sectorRows = secKeys.map(k => {
    const s = SEC[k];
    const vals = allRegions.map(r => r[k + '_conv']);
    const cells = vals.map((v, i) => {
      const diff = i === 0 ? '' : (() => {
        const d = ((v || 0) - (vals[0] || 0));
        const col = d > 0 ? '#16A34A' : d < 0 ? '#DC2626' : '#94A3B8';
        return `<span style="font-size:.72rem;color:${col};margin-left:3px">${d > 0 ? '+' : ''}${d.toFixed(1)}</span>`;
      })();
      return `<td>${f1(v)}${diff}</td>`;
    }).join('');
    return `<tr>
      <td><span class="sector-chip" style="background:${s.color}">${s.label}</span></td>
      ${cells}
    </tr>`;
  }).join('');

  const totalRow = (() => {
    const vals = allRegions.map(r => r.infra_idx);
    const cells = vals.map((v, i) => {
      const diff = i === 0 ? '' : (() => {
        const d = ((v || 0) - (vals[0] || 0));
        const col = d > 0 ? '#16A34A' : d < 0 ? '#DC2626' : '#94A3B8';
        return `<span style="font-size:.72rem;color:${col};margin-left:3px">${d > 0 ? '+' : ''}${d.toFixed(1)}</span>`;
      })();
      return `<td style="font-weight:700">${f1(v)}${diff}</td>`;
    }).join('');
    return `<tr style="background:#F8FAFC"><td style="font-weight:700">종합지수</td>${cells}</tr>`;
  })();

  document.getElementById('cmp-table').innerHTML = `
    <table class="mini-table">
      <thead><tr><th>부문</th>${headerCells}</tr></thead>
      <tbody>${simRow}${sectorRows}</tbody>
      <tfoot>${totalRow}</tfoot>
    </table>`;

  // 좌측 패널 높이를 우측 정보 카드(레이더+막대+표) 총 높이에 맞춤
  document.querySelector('#tab-ranking .region-panel').style.height =
    document.querySelector('.cmp-main').offsetHeight + 'px';
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 5 : 분포 분석
// ══════════════════════════════════════════════════════════════════════════════
let histChart = null, boxChart = null, scatterChart = null;

const DIST_METRICS = METRIC_DEFS;

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
  // 두 연도 공통 bin (통합 범위 기준)
  const allVals = getValsBoth(key);
  const mn = Math.min(...allVals), mx = Math.max(...allVals);
  const BINS = 20;
  const step = (mx - mn) / BINS;
  const xLabels = Array.from({ length: BINS }, (_, i) => (mn + i * step + step / 2).toFixed(1));
  const countsOf = y => {
    const counts = new Array(BINS).fill(0);
    recsOf(y).forEach(r => {
      const v = r[key];
      if (v == null || isNaN(+v)) return;
      const i = Math.min(Math.floor((v - mn) / step), BINS - 1);
      counts[i]++;
    });
    return counts;
  };

  if (!histChart) histChart = echarts.init(document.getElementById('hist-chart'));
  histChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [String(Y1), String(Y2)], top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'category', data: xLabels, axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value', name: '빈도' },
    grid: { top: 34 },
    series: [
      { name: String(Y1), type: 'bar', data: countsOf(Y1), barGap: '-100%', barWidth: '90%',
        itemStyle: { color: '#94A3B8', opacity: .45 } },
      { name: String(Y2), type: 'bar', data: countsOf(Y2), barWidth: '90%',
        itemStyle: { color: '#60A5FA', opacity: .75 } },
    ]
  }, true);

  // Boxplot by 시도 — 연도쌍 (Y1 회색 · Y2 초록)
  const sidos = [...new Set(RECORDS.map(r => r.sido_nm_k))].sort();
  const boxOf = y => sidos.map(sido => {
    const sv = recsOf(y).filter(r => r.sido_nm_k === sido).map(r => r[key])
               .filter(v => v != null).sort((a, b) => a - b);
    if (sv.length < 4) return null;
    const q1 = sv[Math.floor(sv.length * .25)];
    const med = sv[Math.floor(sv.length * .5)];
    const q3 = sv[Math.floor(sv.length * .75)];
    return [sv[0], q1, med, q3, sv[sv.length - 1]];
  });
  const box1 = boxOf(Y1), box2 = boxOf(Y2);
  const validIdx = sidos.map((_, i) => i).filter(i => box1[i] != null && box2[i] != null);
  const validSidos = validIdx.map(i => sidos[i]);

  if (!boxChart) boxChart = echarts.init(document.getElementById('box-chart'));
  boxChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { data: [String(Y1), String(Y2)], top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'category', data: validSidos, axisLabel: { rotate: 45, fontSize: 9 } },
    yAxis: { type: 'value' },
    grid: { bottom: 70, top: 34 },
    series: [
      { name: String(Y1), type: 'boxplot', data: validIdx.map(i => box1[i]),
        itemStyle: { color: '#F1F5F9', borderColor: '#94A3B8' }, boxWidth: [6, 18] },
      { name: String(Y2), type: 'boxplot', data: validIdx.map(i => box2[i]),
        itemStyle: { color: '#D1FAE5', borderColor: '#059669' }, boxWidth: [6, 18] },
    ]
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

  const dataOf = y => recsOf(y)
    .filter(r => r[xKey] != null && r[yKey] != null)
    .map(r => [r[xKey], r[yKey], r.sido_nm_k + ' ' + r.sgg_nm_k]);
  const data1 = dataOf(Y1), data2 = dataOf(Y2);

  // 회귀선은 최신연도(Y2) 기준
  const reg = linReg(data2.map(d => [d[0], d[1]]));
  const xVals = [...data1, ...data2].map(d => d[0]);
  const xMin = Math.min(...xVals), xMax = Math.max(...xVals);
  const regLine = reg ? [[xMin, reg.slope*xMin+reg.intercept], [xMax, reg.slope*xMax+reg.intercept]] : [];
  const regLabel = reg ? `${Y2}: y = ${reg.slope.toFixed(3)}x + ${reg.intercept.toFixed(3)}  (R² = ${reg.r2.toFixed(3)})` : '';

  if (!scatterChart) scatterChart = echarts.init(document.getElementById('scatter-chart'));
  scatterChart.setOption({
    tooltip: {
      formatter: p => p.seriesName === 'reg' ? regLabel
        : `${p.data[2]} (${p.seriesName})<br>${xLabel}: ${p.data[0]}<br>${yLabel}: ${p.data[1]}`
    },
    legend: { data: [String(Y1), String(Y2)], top: 0, right: 10, textStyle: { fontSize: 10 } },
    xAxis: { name: xLabel, nameLocation: 'middle', nameGap: 28, type: 'value', scale: true, axisLabel: { fontSize: 10 } },
    yAxis: { name: yLabel, nameLocation: 'middle', nameGap: 40, type: 'value', scale: true, axisLabel: { fontSize: 10 } },
    graphic: reg ? [{
      type: 'text', left: 'center', top: 8,
      style: { text: regLabel, font: '11px sans-serif', fill: '#EF4444', textAlign: 'center' }
    }] : [],
    series: [
      { name: String(Y1), type: 'scatter', data: data1, symbolSize: 5,
        itemStyle: { color: '#94A3B8', opacity: .45 } },
      { name: String(Y2), type: 'scatter', data: data2, symbolSize: 6,
        itemStyle: { color: '#60A5FA', opacity: .75 } },
      { name: 'reg', type: 'line', data: regLine, showSymbol: false,
        lineStyle: { color: '#EF4444', width: 1.5, type: 'dashed' },
        tooltip: { show: false }, z: 2 }
    ]
  }, true);
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 6 : 변화분석 (시계열)
// ══════════════════════════════════════════════════════════════════════════════
let deckChg = null;
let _chgState = { byCd: {}, y1: null, y2: null, label: '' };   // 툴팁·테이블 공유 상태

function computeChangeRows(metric, y1, y2) {
  const r1 = recsOf(y1), r2 = recsOf(y2);
  const by1 = {};
  r1.forEach(r => { by1[String(r.sgg_cd)] = r; });
  return r2.map(b => {
    const a = by1[String(b.sgg_cd)];
    if (!a || a[metric] == null || b[metric] == null) return null;
    const rank1 = rankIn(r1, metric, a[metric]);
    const rank2 = rankIn(r2, metric, b[metric]);
    return {
      cd: b.sgg_cd, sido: b.sido_nm_k, sgg: b.sgg_nm_k,
      v1: a[metric], v2: b[metric], dv: b[metric] - a[metric],
      rank1, rank2, dr: rank1 - rank2   // +면 순위 상승
    };
  }).filter(Boolean);
}

function chgTooltip({ object }) {
  if (!object || !object.properties) return null;
  const r = _chgState.byCd[String(object.properties.sgg_cd)];
  if (!r) return null;
  const dvStr = (r.dv > 0 ? '+' : '') + r.dv.toFixed(1);
  const drStr = r.dr > 0 ? `▲${r.dr}` : r.dr < 0 ? `▼${-r.dr}` : '—';
  return {
    html: `<b>${r.sido} ${r.sgg}</b><br>${_chgState.label}<br>` +
          `${_chgState.y1}: <b>${f1(r.v1)}</b> (${r.rank1}위) → ${_chgState.y2}: <b>${f1(r.v2)}</b> (${r.rank2}위)<br>` +
          `ΔT점수 <b>${dvStr}</b> · 순위 <b>${drStr}</b>`,
    className: 'deck-tooltip'
  };
}

function chgRankTable(rows) {
  if (!rows.length) return '<div style="color:var(--ink-3);font-size:.8rem;padding:12px 0;text-align:center">해당 없음</div>';
  return `<table class="mini-table">
    <thead><tr><th>#</th><th>지역</th><th>순위</th><th>ΔT점수</th></tr></thead>
    <tbody>${rows.map((r, i) => {
      const cls = r.dr > 0 ? 'rank-delta-up' : r.dr < 0 ? 'rank-delta-down' : 'rank-delta-flat';
      const arrow = r.dr > 0 ? `▲${r.dr}` : r.dr < 0 ? `▼${-r.dr}` : '—';
      const dvStr = (r.dv > 0 ? '+' : '') + r.dv.toFixed(1);
      return `<tr>
        <td style="color:#94A3B8">${i + 1}</td>
        <td>${r.sido} <strong>${r.sgg}</strong></td>
        <td style="white-space:nowrap">${r.rank1}→${r.rank2}위 <span class="${cls}">${arrow}</span></td>
        <td style="color:#64748B">${dvStr}</td>
      </tr>`;
    }).join('')}</tbody>
  </table>`;
}

function renderChangeTab() {
  if (!deckChg) return;
  const metric = document.getElementById('chg-metric').value;
  const y1 = document.getElementById('chg-y1').value;
  const y2 = document.getElementById('chg-y2').value;
  const label = METRIC_DEFS.find(m => m.key === metric)?.label || metric;
  const rows = computeChangeRows(metric, y1, y2);
  const byCd = {};
  rows.forEach(r => { byCd[String(r.cd)] = r; });
  _chgState = { byCd, y1, y2, label };

  const maxAbs = Math.max(0.5, ...rows.map(r => Math.abs(r.dv)));
  const scale = chroma.scale(['#1D4ED8', '#F1F5F9', '#DC2626']).domain([-maxAbs, 0, maxAbs]);

  deckChg.setProps({
    layers: [
      makeTileLayer(),
      new deck.GeoJsonLayer({
        id: 'chg-fill',
        data: GEOJSON,
        filled: true, stroked: true, opacity: 1,
        getFillColor: f => {
          const r = byCd[String(f.properties.sgg_cd)];
          if (!r) return [206, 212, 218, 130];
          const c = scale(r.dv).rgb();
          return [c[0], c[1], c[2], 195];
        },
        getLineColor: [255, 255, 255, 230], lineWidthUnits: 'pixels', getLineWidth: 0.8, lineWidthMinPixels: 0.5,
        pickable: true, autoHighlight: true, highlightColor: [37, 99, 235, 90],
        updateTriggers: { getFillColor: [metric, y1, y2] }
      })
    ]
  });

  // 범례 (diverging)
  const leg = document.getElementById('chg-legend');
  if (leg) {
    leg.innerHTML = `<div class="leg-title">${label}<br>${y1} → ${y2} ΔT점수</div>
      <div style="display:flex;height:11px;border-radius:3px;overflow:hidden;margin:6px 0 4px">${
        [-1, -0.6, -0.25, 0, 0.25, 0.6, 1].map(t => `<div style="flex:1;background:${scale(t * maxAbs).hex()}"></div>`).join('')
      }</div>
      <div style="display:flex;justify-content:space-between;font-size:.68rem;color:var(--ink-2)">
        <span>-${maxAbs.toFixed(1)}</span><span>0</span><span>+${maxAbs.toFixed(1)}</span>
      </div>
      <div style="font-size:.66rem;color:var(--ink-3);margin-top:5px">파랑=상대적 하락 · 빨강=상대적 상승</div>`;
  }

  // 순위변화 TOP 10 (동률은 ΔT점수 큰 순)
  const up   = [...rows].sort((a, b) => b.dr - a.dr || b.dv - a.dv).filter(r => r.dr > 0).slice(0, 10);
  const down = [...rows].sort((a, b) => a.dr - b.dr || a.dv - b.dv).filter(r => r.dr < 0).slice(0, 10);
  document.getElementById('chg-up').innerHTML = chgRankTable(up);
  document.getElementById('chg-down').innerHTML = chgRankTable(down);
}

function initChange() {
  const metricSel = document.getElementById('chg-metric');
  metricSel.innerHTML = METRIC_DEFS.map(m => `<option value="${m.key}">${m.label}</option>`).join('');
  const y1Sel = document.getElementById('chg-y1');
  const y2Sel = document.getElementById('chg-y2');
  y1Sel.innerHTML = YEAR_LIST.map(y => `<option value="${y}">${y}</option>`).join('');
  y2Sel.innerHTML = YEAR_LIST.map(y => `<option value="${y}">${y}</option>`).join('');
  y1Sel.value = YEAR_LIST[0];
  y2Sel.value = YEAR_LIST[YEAR_LIST.length - 1];

  [metricSel, y1Sel, y2Sel].forEach(el => el.addEventListener('change', renderChangeTab));

  const legend = document.createElement('div');
  legend.className = 'chg-legend'; legend.id = 'chg-legend';
  document.getElementById('chg-map').appendChild(legend);

  deckChg = new deck.DeckGL({
    container: document.getElementById('chg-map'),
    initialViewState: { longitude: 127.8, latitude: 36.2, zoom: 6.1, pitch: 0, bearing: 0 },
    controller: true,
    layers: [],
    getTooltip: chgTooltip
  });

  renderChangeTab();
}

// ══════════════════════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════════════════════
document.getElementById('year-pair-badge').innerHTML =
  `<span class="y1">${Y1}</span><span class="vs">vs</span><span>${Y2}</span>`;
renderOverview();
initDetail();

// ── 산출 방법 설명 모달 ──────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('helpModal');
  const open  = () => modal.classList.add('open');
  const close = () => modal.classList.remove('open');
  document.getElementById('helpBtn').addEventListener('click', open);
  document.getElementById('helpClose').addEventListener('click', close);
  modal.addEventListener('click', e => { if (e.target === modal) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
});
</script>

<!-- ── 산출 방법 설명 모달 ──────────────────────────────────────────────── -->
<div class="modal-overlay" id="helpModal">
  <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="helpTitle">
    <div class="modal-head">
      <h2 id="helpTitle">📖 생활인프라 편리성 지수 산출 방법</h2>
      <button class="modal-close" id="helpClose" aria-label="닫기">&times;</button>
    </div>
    <div class="modal-cont">
      <h3>① 5개 평가 부문</h3>
      <p>교육학습 · 돌봄복지 · 보건의료 · 안전치안 · 체육문화 — 부문별 주요 공공시설(도서관·어린이집·병원·경찰서·공원 등)을 모니터링합니다.</p>

      <h3>② 3개 세부지수</h3>
      <p>각 부문마다 다음 3개 지수를 산출합니다.</p>
      <table>
        <thead><tr><th>세부지수</th><th>의미</th></tr></thead>
        <tbody>
          <tr><td><strong>공급수준</strong> <code>_sup</code></td><td>1천인당 시설 수 (시설 포인트 ↔ 인구 공간결합)</td></tr>
          <tr><td><strong>향유수준</strong> <code>_pop</code></td><td>서비스권역 내 인구 비율</td></tr>
          <tr><td><strong>충족수준</strong> <code>_acc</code></td><td>접근성 기반 격자 충족도 (거리기준 이하 = 1, 초과·NoData = 0)</td></tr>
        </tbody>
      </table>

      <h3>③ 표준화 처리</h3>
      <p>각 지표는 다음 3단계를 거쳐 부문별로 평균화됩니다.</p>
      <div class="modal-flow">
        <span class="step">원값</span><span class="arr">→</span>
        <span class="step">로그 변환</span><span class="arr">→</span>
        <span class="step">T점수 표준화</span><span class="arr">→</span>
        <span class="step">부문 평균화</span>
      </div>
      <ul>
        <li>로그 변환: 왜도(skewness)로 자동 권장 — <code>|skew| &gt; 2</code> → log₁₀, <code>|skew| &gt; 1</code> → ln</li>
        <li>표준화: <strong>T점수 = 50 + 10·Z</strong> (전국 평균 50 기준, 상대적 위치를 직관적으로 해석)</li>
      </ul>

      <h3>④ 종합지수 (<code>infra_idx</code>)</h3>
      <p>부문별 <strong>T점수 편리성 지수의 가중 평균</strong>으로 산출합니다.</p>
      <ul>
        <li>전국 평균 ≈ <strong>50</strong>, 실제 범위 약 <strong>39 ~ 74</strong></li>
        <li>점수가 50보다 높으면 전국 평균 이상, 낮으면 평균 이하를 의미합니다.</li>
        <li>지도 색상은 고정 0~100이 아닌 <strong>데이터 실제 범위 기반 동적 색상</strong>을 사용합니다.</li>
      </ul>
      <div class="modal-note">
        ⚠️ v3에서 종합지수 산출 방식이 <strong>0~100 리스케일 → T점수 평균(평균 50)</strong>으로 변경되었습니다.
      </div>

      <h3>⑤ 시계열(연도 간) 해석 주의</h3>
      <p>v4는 두 연도의 분석 결과를 <strong>모든 탭에서 나란히 비교</strong>하는 구조입니다. 지도는 좌(이전연도)·우(최신연도) 듀얼 맵으로, 차트·표는 연도 겹침·Δ 병기로 표시합니다.</p>
      <ul>
        <li>T점수는 <strong>해당 연도 전국 분포 안에서의 상대 표준화</strong>입니다. 연도 간 점수 차이는 시설의 절대적 증감이 아니라 <strong>전국 내 상대적 위치의 변화</strong>를 뜻합니다.</li>
        <li>따라서 모든 Δ 표시에는 <strong>순위 변화를 병기</strong>해 상대적 이동을 함께 보여줍니다.</li>
        <li>듀얼 맵의 색상 등급은 <strong>두 연도 통합 분포 기준</strong>으로 계산해 좌우 지도가 같은 잣대로 비교됩니다.</li>
        <li>지도 탭 <strong>상세보기 모드</strong>에서 시군구를 선택하면 좌(이전연도)·우(최신연도) 지도에 각 연도의 500m 격자(충족점수·격자 인구)와 시설 서비스권역이 표시되고, 서비스권역 인구비율 패널이 함께 열립니다. 시설 POI는 on/off 할 수 있습니다.</li>
      </ul>
    </div>
    <div class="modal-foot">
      출처 · 국토연구원 국토모니터링연구센터 — 생활인프라 편리성 모니터링 QGIS 플러그인 (제작: 손종혁)
    </div>
  </div>
</div>

<!-- ── 시설별 기준 · 산출 방식 모달 ──────────────────────────────────────── -->
<div class="modal-overlay" id="gridInfoModal">
  <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="gridInfoTitle" style="max-width:820px">
    <div class="modal-head">
      <h2 id="gridInfoTitle">📐 국토생활인프라 시설별 기준 및 산출 방식</h2>
      <button class="modal-close" id="gridInfoClose" aria-label="닫기">&times;</button>
    </div>
    <div class="modal-cont">

      <h3>① 개념도: 격자 충족도 산출 흐름</h3>
      <div class="modal-flow" style="justify-content:center;margin:16px 0 20px">
        <span class="step">500m 격자</span><span class="arr">→</span>
        <span class="step">시설별 최근접 거리 계산</span><span class="arr">→</span>
        <span class="step">거리기준 이하 = 충족(1)</span><span class="arr">→</span>
        <span class="step">20개 시설 합산<br><small>(0~20점)</small></span>
      </div>
      <p>각 500m 격자에서 20개 시설까지의 최근접 거리를 측정하고, 시설별 <strong>거리 기준</strong> 이하이면 <strong>충족(1)</strong>, 초과 또는 결측이면 <strong>미충족(0)</strong>으로 이진화합니다. 충족 시설 수의 합계(0~20)가 해당 격자의 점수입니다.</p>

      <h3>② 시설별 거리 기준</h3>
      <p>시설 특성에 따라 <strong>생활밀착형(1km)</strong>과 <strong>광역거점형(5km)</strong> 두 가지 기준을 적용합니다.</p>
      <table>
        <thead><tr><th>부문</th><th>시설명</th><th>거리 기준</th><th>유형</th></tr></thead>
        <tbody>
          <tr><td rowspan="4" style="font-weight:700;color:var(--accent);vertical-align:middle">교육학습</td>
              <td>어린이집</td><td><strong>1 km</strong></td><td>생활밀착</td></tr>
          <tr><td>유치원</td><td><strong>1 km</strong></td><td>생활밀착</td></tr>
          <tr><td>초등학교</td><td><strong>1 km</strong></td><td>생활밀착</td></tr>
          <tr><td>작은도서관</td><td><strong>1 km</strong></td><td>생활밀착</td></tr>

          <tr><td rowspan="4" style="font-weight:700;color:var(--accent);vertical-align:middle">돌봄복지</td>
              <td>온종일돌봄센터</td><td><strong>1 km</strong></td><td>생활밀착</td></tr>
          <tr><td>종합사회복지관</td><td><strong>5 km</strong></td><td>광역거점</td></tr>
          <tr><td>노인여가복지시설</td><td><strong>5 km</strong></td><td>광역거점</td></tr>
          <tr><td>경로당</td><td><strong>1 km</strong></td><td>생활밀착</td></tr>

          <tr><td rowspan="4" style="font-weight:700;color:var(--accent);vertical-align:middle">보건의료</td>
              <td>종합병원</td><td><strong>5 km</strong></td><td>광역거점</td></tr>
          <tr><td>보건기관</td><td><strong>5 km</strong></td><td>광역거점</td></tr>
          <tr><td>의원</td><td><strong>1 km</strong></td><td>생활밀착</td></tr>
          <tr><td>약국</td><td><strong>1 km</strong></td><td>생활밀착</td></tr>

          <tr><td rowspan="4" style="font-weight:700;color:var(--accent);vertical-align:middle">안전치안</td>
              <td>지진옥외대피소</td><td><strong>1 km</strong></td><td>생활밀착</td></tr>
          <tr><td>응급의료시설</td><td><strong>5 km</strong></td><td>광역거점</td></tr>
          <tr><td>경찰서</td><td><strong>5 km</strong></td><td>광역거점</td></tr>
          <tr><td>소방서</td><td><strong>5 km</strong></td><td>광역거점</td></tr>

          <tr><td rowspan="4" style="font-weight:700;color:var(--accent);vertical-align:middle">체육문화</td>
              <td>생활권공원</td><td><strong>1 km</strong></td><td>생활밀착</td></tr>
          <tr><td>주제공원</td><td><strong>5 km</strong></td><td>광역거점</td></tr>
          <tr><td>공연문화시설</td><td><strong>5 km</strong></td><td>광역거점</td></tr>
          <tr><td>공공체육시설</td><td><strong>5 km</strong></td><td>광역거점</td></tr>
        </tbody>
      </table>

      <h3>③ 점수 해석</h3>
      <div style="display:flex;gap:0;margin:10px 0 14px">
        <span style="flex:1;text-align:center;padding:10px 4px;background:#fce4ec;border:1px solid #ef9a9a;color:#c62828;font-size:.8rem;font-weight:600;border-radius:6px 0 0 6px">1~4점<br><small>매우 취약</small></span>
        <span style="flex:1;text-align:center;padding:10px 4px;background:#fff3e0;border:1px solid #ffcc80;border-left:none;color:#e65100;font-size:.8rem;font-weight:600">5~8점<br><small>취약</small></span>
        <span style="flex:1;text-align:center;padding:10px 4px;background:#fffde7;border:1px solid #fff176;border-left:none;color:#f57f17;font-size:.8rem;font-weight:600">9~12점<br><small>보통</small></span>
        <span style="flex:1;text-align:center;padding:10px 4px;background:#e8f5e9;border:1px solid #a5d6a7;border-left:none;color:#2e7d32;font-size:.8rem;font-weight:600">13~16점<br><small>양호</small></span>
        <span style="flex:1;text-align:center;padding:10px 4px;background:#e0f2f1;border:1px solid #80cbc4;border-left:none;color:#00695c;font-size:.8rem;font-weight:600;border-radius:0 6px 6px 0">17~20점<br><small>매우 양호</small></span>
      </div>
      <p>지도 위 격자 색상은 <strong>빨강(1점) → 초록(20점)</strong>으로 표시되며, 충족 시설이 많을수록 생활인프라가 잘 갖추어진 지역입니다.</p>

      <div class="modal-note">
        💡 <strong>생활밀착형(1km)</strong>은 도보·자전거로 접근 가능한 마을 단위 시설, <strong>광역거점형(5km)</strong>은 차량 등으로 접근하는 거점 단위 시설을 기준으로 합니다.
      </div>
    </div>
    <div class="modal-foot">
      출처 · 국토연구원 국토모니터링연구센터 — 생활인프라 편리성 모니터링
    </div>
  </div>
</div>
<script>
window.addEventListener('DOMContentLoaded', function() {
  const m = document.getElementById('gridInfoModal');
  const open  = () => m.classList.add('open');
  const close = () => m.classList.remove('open');
  document.getElementById('grid-info-btn').addEventListener('click', open);
  document.getElementById('gridInfoClose').addEventListener('click', close);
  m.addEventListener('click', e => { if (e.target === m) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && m.classList.contains('open')) close(); });
});
</script>

<!-- ── AI 챗봇 패널 ──────────────────────────────────────────────────────── -->
<div id="chat-panel">
  <div id="chat-panel-header">
    <span id="chat-panel-title"></span>
    <button id="chat-panel-close" onclick="toggleChatPanel()">×</button>
  </div>
  <div id="chat-apikey-section" style="display:none">
    <div id="chat-apikey-label">Claude API 키</div>
    <div id="chat-apikey-row">
      <input id="chat-apikey-input" type="password" placeholder="sk-ant-..." autocomplete="off">
      <button id="chat-apikey-save" onclick="saveChatApiKey()">저장</button>
    </div>
    <div id="chat-apikey-hint">키는 브라우저 로컬에만 저장됩니다.</div>
  </div>
  <div id="chat-quick-btns"></div>
  <div id="chat-messages">
    <div id="chat-empty"></div>
  </div>
  <div id="chat-input-area">
    <div id="chat-model-row">
      <button class="model-seg-btn active" id="model-seg-basic" onclick="setChatModel(false)"></button>
      <button class="model-seg-btn" id="model-seg-adv" onclick="setChatModel(true)"></button>
    </div>
    <div id="chat-input-row">
      <textarea id="chat-input" rows="1" placeholder=""></textarea>
      <button id="chat-send-btn" onclick="sendChat()">전송</button>
    </div>
  </div>
</div>

<script>
/* ===== AI 챗봇 ===== */
const AI_CONFIG = window.AI_CONFIG;
let _chatOpen = false;
let _chatApiKey = localStorage.getItem('chat_apikey') || '';
let _chatHistory = [];   // {role, content}[]
let _chatMsgId = 0;
let _advancedOn = false; // false=기본 모델, true=고급 모델
const _chatTools = AI_CONFIG.tools || [];
const _WEB_SEARCH_TOOL = { type: 'web_search_20250305', name: 'web_search' };

function _activeModel() { return _advancedOn ? AI_CONFIG.advancedModel : AI_CONFIG.basicModel; }

function _renderModelSeg() {
  const basic = document.getElementById('model-seg-basic');
  const adv = document.getElementById('model-seg-adv');
  if (!basic || !adv) return;
  basic.textContent = '⚡ 기본 · ' + AI_CONFIG.basicLabel;
  adv.textContent = '🚀 고급 · ' + AI_CONFIG.advancedLabel + ' 🌐';
  basic.title = '대시보드 데이터만 사용 (빠름)';
  adv.title = '고급 모델 + 외부 웹 검색 (검색 결과는 출처와 함께 표기)';
  basic.classList.toggle('active', !_advancedOn);
  adv.classList.toggle('active', _advancedOn);
}
function setChatModel(advanced) {
  _advancedOn = advanced;
  _renderModelSeg();
}

function toggleChatPanel() {
  _chatOpen = !_chatOpen;
  document.getElementById('chat-panel').classList.toggle('open', _chatOpen);
  document.getElementById('chat-toggle-btn').classList.toggle('open', _chatOpen);
  document.getElementById('chat-toggle-btn').textContent = _chatOpen ? AI_CONFIG.ui.toggleOpen : AI_CONFIG.ui.toggleClosed;
  if (_chatOpen) {
    document.getElementById('chat-apikey-section').style.display = _chatApiKey ? 'none' : 'block';
    document.getElementById('chat-input').focus();
  }
}

/* 채팅 팝업 창을 헤더로 드래그해 이동 */
(function() {
  let dragging = false, sx = 0, sy = 0, ox = 0, oy = 0;
  document.addEventListener('mousedown', function(e) {
    const h = e.target.closest('#chat-panel-header');
    if (!h || e.target.closest('#chat-panel-close')) return;
    const p = document.getElementById('chat-panel');
    const r = p.getBoundingClientRect();
    p.style.left = r.left + 'px'; p.style.top = r.top + 'px'; p.style.right = 'auto';
    dragging = true; sx = e.clientX; sy = e.clientY; ox = r.left; oy = r.top;
    e.preventDefault();
  });
  document.addEventListener('mousemove', function(e) {
    if (!dragging) return;
    const p = document.getElementById('chat-panel');
    let nx = ox + (e.clientX - sx), ny = oy + (e.clientY - sy);
    nx = Math.max(0, Math.min(nx, window.innerWidth - p.offsetWidth));
    ny = Math.max(0, Math.min(ny, window.innerHeight - p.offsetHeight));
    p.style.left = nx + 'px'; p.style.top = ny + 'px';
  });
  document.addEventListener('mouseup', function() { dragging = false; });
})();

function saveChatApiKey() {
  const v = document.getElementById('chat-apikey-input').value.trim();
  if (!v) return;
  _chatApiKey = v;
  localStorage.setItem('chat_apikey', v);
  document.getElementById('chat-apikey-section').style.display = 'none';
  document.getElementById('chat-input').focus();
}

// 현재 화면 상태를 system 동적 블록으로 주입한다. (구체 수치는 도구로 조회)
function _buildDashboardContext() {
  const activeBtn = document.querySelector('.tab-btn.active');
  const tab = activeBtn ? activeBtn.textContent.trim() : '-';
  const mean = k => _round(getMean(k), 1);
  let ctx = '[현재 대시보드 상태]\\n';
  ctx += `활성 탭: ${tab}\\n`;
  ctx += `데이터 연도: ${YEAR_LIST.join(', ')} — 이 대시보드는 ${Y1} vs ${Y2} 두 연도를 나란히 비교하는 구조 (모든 탭 2연도 병기, 수치 기본값은 최신 ${Y2}년)\\n`;
  ctx += `전체 시군구: ${RECORDS.length}개 (전국 17개 시도)\\n`;
  ctx += `전국 평균(T점수, 50 기준) — 종합 ${mean('infra_idx')} / 교육 ${mean('edu_conv')} 돌봄 ${mean('care_conv')} 보건 ${mean('med_conv')} 안전 ${mean('safe_conv')} 체육 ${mean('cult_conv')}\\n`;
  const byIdx = RECORDS.filter(r => r.infra_idx != null).slice().sort((a, b) => b.infra_idx - a.infra_idx);
  if (byIdx.length) {
    const t = byIdx[0], b = byIdx[byIdx.length - 1];
    ctx += `종합지수 최고 ${t.sido_nm_k} ${t.sgg_nm_k} ${_round(t.infra_idx, 1)} / 최저 ${b.sido_nm_k} ${b.sgg_nm_k} ${_round(b.infra_idx, 1)}\\n`;
  }
  if (typeof cmpSel !== 'undefined' && cmpSel.length) {
    const names = cmpSel.map(cd => { const r = RECORDS.find(x => String(x.sgg_cd) === String(cd)); return r ? r.sgg_nm_k : cd; });
    ctx += `[비교 탭 선택] ${names.join(', ')}\\n`;
  }
  if (typeof curMetric !== 'undefined') {
    ctx += `[지도] 표시 지표: ${_MLABEL[curMetric] || curMetric}`;
    if (typeof curSidoFilter !== 'undefined' && curSidoFilter) ctx += `, 시도필터: ${curSidoFilter}`;
    if (typeof highlightSggCd !== 'undefined' && highlightSggCd) {
      const r = RECORDS.find(x => String(x.sgg_cd) === String(highlightSggCd));
      if (r) ctx += `, 선택: ${r.sgg_nm_k}`;
    }
    ctx += '\\n';
  }
  return ctx;
}

function _addChatBubble(role, text, id) {
  const msgsEl = document.getElementById('chat-messages');
  const emptyEl = document.getElementById('chat-empty');
  if (emptyEl) emptyEl.style.display = 'none';
  const div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  if (id) div.dataset.msgid = id;
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble' + (text === '...' ? ' loading' : '');
  bubble.textContent = text;
  div.appendChild(bubble);
  msgsEl.appendChild(div);
  msgsEl.scrollTop = msgsEl.scrollHeight;
  return div;
}

function _updateChatBubble(id, text) {
  const div = document.querySelector(`[data-msgid="${id}"]`);
  if (!div) return;
  const bubble = div.querySelector('.chat-bubble');
  bubble.className = 'chat-bubble';
  bubble.textContent = text;
  document.getElementById('chat-messages').scrollTop = 9999;
}

function quickChat(prompt) {
  document.getElementById('chat-input').value = prompt;
  sendChat();
}

// ===== AI 도구 실행: 이 대시보드 데이터(RECORDS·ACCESS_GRIDS) 직접 조회 =====
const _MLABEL = Object.fromEntries(METRIC_DEFS.map(m => [m.key, m.label]));
const _METRIC_KEYS = METRIC_DEFS.map(m => m.key);
const _SECTORS = { edu: '교육학습', care: '돌봄복지', med: '보건의료', safe: '안전치안', cult: '체육문화' };
function _round(v, d) { if (v == null || isNaN(+v)) return null; const m = Math.pow(10, d); return Math.round(+v * m) / m; }
function _findRec(name, recs) {
  const R = recs || RECORDS;
  const n = (name || '').trim();
  if (!n) return null;
  return R.find(r => r.sgg_nm_k === n)
    || R.find(r => r.sgg_nm_k.replace(/\\s/g, '') === n.replace(/\\s/g, ''))
    || R.find(r => (r.sido_nm_k + ' ' + r.sgg_nm_k).replace(/\\s/g, '') === n.replace(/\\s/g, ''));
}

// 도구 입력의 year 파라미터 해석: 없으면 현재 선택 연도, 잘못되면 현재 연도로 폴백
function _recsForTool(input) {
  const y = input && input.year != null ? String(input.year) : CUR_YEAR;
  if (YEARS[y]) return { recs: YEARS[y], year: y };
  return { recs: RECORDS, year: CUR_YEAR,
           note: `요청한 연도(${input.year})의 데이터가 없어 ${CUR_YEAR}년 데이터로 답합니다. 보유 연도: ${YEAR_LIST.join(', ')}` };
}

function _pctIn(recs, key, value) {
  const vals = recs.map(r => r[key]).filter(v => v != null && !isNaN(+v)).sort((a, b) => a - b);
  const below = vals.filter(v => v < value).length;
  return Math.round((1 - below / vals.length) * 100);
}

function _toolQueryIndex(input) {
  const { recs: R, year, note } = _recsForTool(input);
  const mode = input.mode;
  const level = input.level === 'sido' ? 'sido' : 'sgg';
  if (mode === 'detail') {
    const rec = _findRec(input.sgg_nm, R);
    if (!rec) return { error: `'${input.sgg_nm || ''}' 시군구를 찾을 수 없습니다.` };
    const out = { year, note, region: `${rec.sido_nm_k} ${rec.sgg_nm_k}`, sgg_cd: rec.sgg_cd, popall: rec.popall, area: rec.area, metrics: {} };
    _METRIC_KEYS.forEach(k => {
      const v = rec[k];
      if (v == null) return;
      out.metrics[_MLABEL[k]] = { value: _round(v, 1), national_rank: rankIn(R, k, v), of_total: R.length, top_pct: _pctIn(R, k, v) };
    });
    return out;
  }
  const metric = input.metric;
  if (!metric || !_MLABEL[metric]) return { error: 'metric 지표 키가 필요합니다 (예: infra_idx, med_sup).' };
  let rows;
  if (level === 'sido') {
    const g = {};
    R.forEach(r => { if (r[metric] == null) return; (g[r.sido_nm_k] || (g[r.sido_nm_k] = [])).push(r[metric]); });
    rows = Object.keys(g).map(s => ({ name: s, value: g[s].reduce((a, b) => a + b, 0) / g[s].length, n_sgg: g[s].length }));
  } else {
    rows = R.filter(r => r[metric] != null && (!input.sido_nm || r.sido_nm_k === input.sido_nm))
      .map(r => ({ name: `${r.sido_nm_k} ${r.sgg_nm_k}`, sgg_cd: r.sgg_cd, value: r[metric] }));
    if (input.sido_nm && !rows.length) return { error: `'${input.sido_nm}' 시도에 데이터가 없습니다. 정확한 시도명인지 확인하세요.` };
  }
  if (mode === 'filter') {
    if (input.min != null) rows = rows.filter(r => r.value >= input.min);
    if (input.max != null) rows = rows.filter(r => r.value <= input.max);
  }
  const ord = input.order === 'asc' ? 1 : -1;
  rows.sort((a, b) => (a.value - b.value) * ord);
  const topN = Math.min(Math.max(input.top_n || 10, 1), 50);
  return {
    year, note,
    metric: _MLABEL[metric], level: level,
    order: ord < 0 ? '높은순' : '낮은순',
    scope: input.sido_nm || '전국',
    national_mean: level === 'sgg' ? _round(meanIn(R, metric), 1) : undefined,
    matched: rows.length,
    rows: rows.slice(0, topN).map((r, i) => ({ rank: i + 1, ...r, value: _round(r.value, 1) }))
  };
}

function _toolCompareRegions(input) {
  const { recs: R, year, note } = _recsForTool(input);
  const defaults = ['infra_idx', 'edu_conv', 'care_conv', 'med_conv', 'safe_conv', 'cult_conv'];
  let metrics = (input.metrics && input.metrics.length ? input.metrics : defaults).filter(k => _MLABEL[k]);
  if (!metrics.length) metrics = defaults;
  let recs = [];
  if (input.base_sgg) {
    const base = _findRec(input.base_sgg, R);
    if (!base) return { error: `'${input.base_sgg}' 시군구를 찾을 수 없습니다.` };
    const key = (input.similar_by && (_MLABEL[input.similar_by] || ['popall', 'area'].includes(input.similar_by))) ? input.similar_by : 'infra_idx';
    recs = [base, ...findSimilar(base, key, 4, R)];
  } else {
    const names = input.sgg_names || [];
    if (names.length < 2) return { error: '비교할 시군구명을 2개 이상 sgg_names로 주거나, base_sgg로 유사지역을 찾으세요.' };
    for (const nm of names) { const r = _findRec(nm, R); if (!r) return { error: `'${nm}' 시군구를 찾을 수 없습니다.` }; recs.push(r); }
  }
  return {
    year, note,
    metrics: metrics.map(k => _MLABEL[k]),
    regions: recs.map(r => ({
      region: `${r.sido_nm_k} ${r.sgg_nm_k}`, sgg_cd: r.sgg_cd, popall: r.popall, area: r.area,
      values: Object.fromEntries(metrics.map(k => [_MLABEL[k], _round(r[k], 1)]))
    }))
  };
}

// 연도 간 비교: 특정 시군구의 연도별 값·순위, 또는 전국 순위변화 상위/하위
function _toolCompareYears(input) {
  const metric = (input.metric && _MLABEL[input.metric]) ? input.metric : 'infra_idx';
  const fromY = input.from_year != null && YEARS[String(input.from_year)] ? String(input.from_year) : YEAR_LIST[0];
  const toY   = input.to_year   != null && YEARS[String(input.to_year)]   ? String(input.to_year)   : YEAR_LIST[YEAR_LIST.length - 1];
  const caveat = 'T점수는 연도별 상대 표준화 지표라 증감은 절대 수준 변화가 아니라 전국 내 상대적 위치 변화를 뜻함. 순위 변화를 함께 해석할 것.';

  if (input.sgg_nm) {
    const base = _findRec(input.sgg_nm, recsOf(toY)) || _findRec(input.sgg_nm);
    if (!base) return { error: `'${input.sgg_nm}' 시군구를 찾을 수 없습니다.` };
    const defaults = ['infra_idx', 'edu_conv', 'care_conv', 'med_conv', 'safe_conv', 'cult_conv'];
    const metrics = (input.metric && _MLABEL[input.metric]) ? [input.metric] : defaults;
    const byYear = {};
    YEAR_LIST.forEach(y => {
      const r = findIn(recsOf(y), base.sgg_cd);
      if (!r) return;
      byYear[y] = Object.fromEntries(metrics.map(k => [_MLABEL[k],
        { value: _round(r[k], 1), national_rank: rankIn(recsOf(y), k, r[k]), of_total: recsOf(y).length }]));
    });
    return { region: `${base.sido_nm_k} ${base.sgg_nm_k}`, years: byYear, caveat };
  }

  const rows = computeChangeRows(metric, fromY, toY);
  const topN = Math.min(Math.max(input.top_n || 10, 1), 30);
  const fmt = r => ({
    region: `${r.sido} ${r.sgg}`,
    [`value_${fromY}`]: _round(r.v1, 1), [`value_${toY}`]: _round(r.v2, 1),
    delta_tscore: _round(r.dv, 1),
    [`rank_${fromY}`]: r.rank1, [`rank_${toY}`]: r.rank2, rank_change: r.dr
  });
  return {
    metric: _MLABEL[metric], from_year: fromY, to_year: toY, caveat,
    top_rank_up:   [...rows].sort((a, b) => b.dr - a.dr || b.dv - a.dv).filter(r => r.dr > 0).slice(0, topN).map(fmt),
    top_rank_down: [...rows].sort((a, b) => a.dr - b.dr || a.dv - b.dv).filter(r => r.dr < 0).slice(0, topN).map(fmt)
  };
}

function _toolQueryAccessGrids(input) {
  const y = input.year != null && YEARS[String(input.year)] ? String(input.year) : CUR_YEAR;
  const AG = LAYER_CACHE['access_' + y];
  if (!AG) return { error: `격자 데이터(access_${y})가 아직 로드되지 않았습니다. 잠시 후 다시 시도하세요.` };
  const rec = _findRec(input.sgg_nm);
  if (!rec) return { error: `'${input.sgg_nm || ''}' 시군구를 찾을 수 없습니다.` };
  const grids = AG[String(rec.sgg_cd)];
  const region = `${rec.sido_nm_k} ${rec.sgg_nm_k}`;
  if (!grids || !grids.length) return { region, grid_count: 0, note: '충족 격자 데이터가 없습니다(전 시설 미충족 격자는 제외됨).' };
  const n = grids.length;
  let facIdx = null;
  if (input.facility) { facIdx = FACILITIES.findIndex(f => f[0] === input.facility); if (facIdx < 0) return { error: `알 수 없는 시설 코드: ${input.facility}` }; }
  const facStats = FACILITIES.map((f, bit) => {
    let cnt = 0; for (let i = 0; i < n; i++) { if (grids[i][2] & (1 << bit)) cnt++; }
    return { code: f[0], name: f[1], sector: _SECTORS[f[2]], met_grids: cnt, met_pct: _round(cnt / n * 100, 1) };
  });
  let facilities = facStats;
  if (facIdx != null) facilities = [facStats[facIdx]];
  else if (input.sector) facilities = facStats.filter((s, i) => FACILITIES[i][2] === input.sector);
  const secAvg = {};
  ['edu', 'care', 'med', 'safe', 'cult'].forEach(s => {
    const bits = []; FACILITIES.forEach((f, b) => { if (f[2] === s) bits.push(b); });
    let sum = 0; for (let i = 0; i < n; i++) { let c = 0; bits.forEach(b => { if (grids[i][2] & (1 << b)) c++; }); sum += c; }
    secAvg[_SECTORS[s]] = `${_round(sum / n, 2)} / ${bits.length}`;
  });
  let totalMet = 0; for (let i = 0; i < n; i++) totalMet += popcount(grids[i][2]);
  return {
    region, year: y, grid_count: n,
    note: '충족 시설이 있거나 인구가 있는 500m 격자 기준 수치입니다 (무인구·전 시설 미충족 격자 제외). year 파라미터로 연도 지정 가능.',
    avg_met_facilities: `${_round(totalMet / n, 2)} / 20`,
    sector_avg_met: secAvg,
    facilities
  };
}

function _toolFocusMap(input) {
  const rec = _findRec(input.sgg_nm);
  if (!rec) return { error: `'${input.sgg_nm || ''}' 시군구를 찾을 수 없습니다.` };
  const mapBtn = document.querySelector('.tab-btn[data-tab="map"]');
  if (mapBtn) mapBtn.click();
  setTimeout(() => {
    const sidoSel = document.getElementById('map-sido-sel');
    const sggSel = document.getElementById('map-sgg-sel');
    if (!sidoSel || !sggSel) return;
    sidoSel.value = rec.sido_nm_k; sidoSel.dispatchEvent(new Event('change'));
    sggSel.value = String(rec.sgg_cd); sggSel.dispatchEvent(new Event('change'));
  }, 80);
  return { ok: true, focused: `${rec.sido_nm_k} ${rec.sgg_nm_k}`, sgg_cd: rec.sgg_cd };
}

function _runChatTool(name, input) {
  try {
    if (name === 'query_index') return _toolQueryIndex(input);
    if (name === 'compare_regions') return _toolCompareRegions(input);
    if (name === 'compare_years') return _toolCompareYears(input);
    if (name === 'query_access_grids') return _toolQueryAccessGrids(input);
    if (name === 'focus_map') return _toolFocusMap(input);
    return { error: '알 수 없는 도구: ' + name };
  } catch (e) { return { error: String(e && e.message || e) }; }
}

// Messages API를 stream:true로 호출하고 SSE를 파싱해 assistant content 블록을 재구성한다.
async function _streamMessage(reqBody, onText) {
  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': _chatApiKey,
      'anthropic-version': AI_CONFIG.anthropicVersion,
      'anthropic-dangerous-direct-browser-access': 'true'
    },
    body: JSON.stringify({ ...reqBody, stream: true })
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    return { error: err.error?.message || ('HTTP ' + resp.status) };
  }
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  const blocks = [];   // index -> content block
  const jsonAcc = {};  // index -> tool_use 입력 partial JSON 누적
  const searchResults = [];  // web_search 가 실제로 가져온 결과 {url,title}
  const citations = [];      // 모델이 본문에서 인용한 출처 {url,title}
  let stopReason = null, text = '', buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf('\\n')) >= 0) {
      const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1);
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (!payload || payload === '[DONE]') continue;
      let ev; try { ev = JSON.parse(payload); } catch { continue; }
      if (ev.type === 'content_block_start') {
        blocks[ev.index] = JSON.parse(JSON.stringify(ev.content_block));
        const t = blocks[ev.index].type;
        if (t === 'tool_use' || t === 'server_tool_use') jsonAcc[ev.index] = '';
        if (t === 'web_search_tool_result' && Array.isArray(blocks[ev.index].content)) {
          blocks[ev.index].content.forEach(r => { if (r && r.url) searchResults.push({ url: r.url, title: r.title || r.url }); });
        }
      } else if (ev.type === 'content_block_delta') {
        const d = ev.delta;
        if (d.type === 'text_delta') { if (blocks[ev.index]) blocks[ev.index].text += d.text; text += d.text; onText && onText(text); }
        else if (d.type === 'input_json_delta') { jsonAcc[ev.index] = (jsonAcc[ev.index] || '') + d.partial_json; }
        else if (d.type === 'citations_delta' && d.citation && d.citation.url) { citations.push({ url: d.citation.url, title: d.citation.title || d.citation.url }); }
      } else if (ev.type === 'content_block_stop') {
        if (jsonAcc[ev.index] !== undefined && blocks[ev.index]) {
          try { blocks[ev.index].input = jsonAcc[ev.index] ? JSON.parse(jsonAcc[ev.index]) : {}; } catch { blocks[ev.index].input = {}; }
        }
      } else if (ev.type === 'message_delta') {
        if (ev.delta && ev.delta.stop_reason) stopReason = ev.delta.stop_reason;
      } else if (ev.type === 'error') {
        return { error: ev.error?.message || '스트리밍 오류' };
      }
    }
  }
  return { content: blocks.filter(Boolean), stop_reason: stopReason, text, searchResults, citations };
}

// 외부 검색 출처 강제 표기: 본문에 누락된 URL이 있으면 검증된 출처 목록을 덧붙인다.
function _appendSources(text, sources, heading) {
  const seen = new Set(), list = [];
  sources.forEach(s => { if (s.url && !seen.has(s.url)) { seen.add(s.url); list.push(s); } });
  if (!list.length) return text;
  if (list.every(s => text.indexOf(s.url) >= 0)) return text; // 모델이 이미 모든 URL을 본문에 표기함
  const lines = list.slice(0, 8).map((s, i) => `${i + 1}. ${s.title} — ${s.url}`).join('\\n');
  return text + `\\n\\n— ${heading} —\\n` + lines;
}

async function sendChat() {
  const inputEl = document.getElementById('chat-input');
  const userText = inputEl.value.trim();
  if (!userText) return;
  if (!_chatApiKey) {
    document.getElementById('chat-apikey-section').style.display = 'block';
    return;
  }

  inputEl.value = '';
  inputEl.style.height = '';
  document.getElementById('chat-send-btn').disabled = true;

  _addChatBubble('user', userText);

  const msgId = 'ai-' + (++_chatMsgId);
  _addChatBubble('assistant', '...', msgId);

  // system 2블록: (1) 정적 규칙(캐싱), (2) 매턴 변동 화면 상태.
  const system = [
    { type: 'text', text: AI_CONFIG.systemPrompt, cache_control: { type: 'ephemeral' } },
    { type: 'text', text: '[아래는 현재 화면 상태이며 참고용입니다.]\\n' + _buildDashboardContext() }
  ];

  const convo = [..._chatHistory.slice(-8).map(m => ({ role: m.role, content: m.content })), { role: 'user', content: userText }];
  const model = _activeModel();
  const tools = _advancedOn ? [..._chatTools, _WEB_SEARCH_TOOL] : _chatTools;

  try {
    let finalText = '(응답 없음)';
    let completed = false;
    let webResults = [], webCites = [];
    for (let iter = 0; iter < 6; iter++) {
      const data = await _streamMessage(
        { model: model, max_tokens: AI_CONFIG.maxTokens, system: system, tools: tools, messages: convo },
        (t) => _updateChatBubble(msgId, t));
      if (data.error) {
        _updateChatBubble(msgId, '오류: ' + data.error);
        completed = true;
        break;
      }
      if (data.searchResults && data.searchResults.length) webResults.push(...data.searchResults);
      if (data.citations && data.citations.length) webCites.push(...data.citations);
      convo.push({ role: 'assistant', content: data.content });
      if (data.stop_reason === 'tool_use') {
        const toolResults = [];
        for (const block of data.content) {
          if (block.type === 'tool_use') {
            _updateChatBubble(msgId, '🔧 데이터 조회 중… (' + block.name + ')');
            const result = _runChatTool(block.name, block.input);
            toolResults.push({ type: 'tool_result', tool_use_id: block.id, content: JSON.stringify(result) });
          }
        }
        convo.push({ role: 'user', content: toolResults });
        continue;
      }
      if (data.stop_reason === 'pause_turn') {
        // 서버사이드 도구(웹 검색) 루프가 길어 일시중단됨 → 그대로 재요청해 이어서 진행
        _updateChatBubble(msgId, '🌐 외부 검색 중…');
        continue;
      }
      finalText = (data.text && data.text.trim())
        || (data.content || []).filter(b => b.type === 'text').map(b => b.text).join('\\n').trim()
        || '(응답 없음)';
      // 외부 검색을 썼다면 출처를 강제로 표기 (인용 우선, 없으면 검색 결과)
      if (webCites.length) finalText = _appendSources(finalText, webCites, '출처');
      else if (webResults.length) finalText = _appendSources(finalText, webResults, '참고한 외부 검색 결과');
      _updateChatBubble(msgId, finalText);
      _chatHistory.push({ role: 'user', content: userText }, { role: 'assistant', content: finalText });
      if (_chatHistory.length > 20) _chatHistory = _chatHistory.slice(-20);
      completed = true;
      break;
    }
    if (!completed) _updateChatBubble(msgId, '응답이 너무 길어 완료하지 못했습니다. 질문을 더 구체적으로 나눠서 다시 시도해 주세요.');
  } catch (e) {
    _updateChatBubble(msgId, '네트워크 오류: ' + e.message);
  }
  document.getElementById('chat-send-btn').disabled = false;
  inputEl.focus();
}

document.addEventListener('DOMContentLoaded', () => {
  const _ui = AI_CONFIG.ui;
  document.getElementById('chat-panel-title').textContent = _ui.panelTitle;
  document.getElementById('chat-toggle-btn').textContent = _ui.toggleClosed;
  document.getElementById('chat-empty').innerHTML = _ui.emptyHint;
  _renderModelSeg();
  const _qb = document.getElementById('chat-quick-btns');
  if (_qb) AI_CONFIG.quickQuestions.forEach(q => {
    const b = document.createElement('button');
    b.className = 'chat-quick-btn'; b.textContent = q.label;
    b.addEventListener('click', () => quickChat(q.prompt));
    _qb.appendChild(b);
  });
  const inp = document.getElementById('chat-input');
  if (inp) {
    inp.placeholder = _ui.inputPlaceholder;
    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
    });
    inp.addEventListener('input', () => { inp.style.height = ''; inp.style.height = Math.min(inp.scrollHeight, 120) + 'px'; });
  }
});
</script>
</body>
</html>
"""

# ── 메인 ────────────────────────────────────────────────────────────────────

def main():
    years = scan_years()
    print(f'[1/4] 연도 스캔: {", ".join(years)}')

    gdfs = {}
    for y in years:
        print(f'[2/4] {y} Shapefile 로딩·병합...')
        gdfs[y] = load_year(y)

    latest = years[-1]
    print(f'[3/4] GeoJSON 생성 (geometry는 {latest} 기준 1회)...')
    geojson = to_geojson(gdfs[latest])
    years_records = {y: to_records(gdfs[y]) for y in years}

    print('[4/4] HTML 인젝션...')
    data_js = (
        f'const GEOJSON = {json.dumps(geojson, ensure_ascii=False)};\n'
        f'const YEAR_LIST = {json.dumps(years)};\n'
        f'const YEARS = {json.dumps(years_records, ensure_ascii=False)};\n'
    )
    html = HTML_TEMPLATE.replace('/* __DATA__ */', data_js)
    html = html.replace('__ACCESS_LATEST__', f'access_{latest}.js')

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)

    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f'[완료] {OUT}  ({size_mb:.1f} MB)')
    print('   브라우저에서 파일을 바로 열면 됩니다.')

if __name__ == '__main__':
    main()
