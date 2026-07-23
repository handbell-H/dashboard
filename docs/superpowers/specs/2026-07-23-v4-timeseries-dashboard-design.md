# v4 시계열 대시보드 설계 (2026-07-23)

## 목적
생활인프라 편리성 대시보드(v3)를 시계열 데이터 기반으로 확장한 v4 신규 버전.
연도별 지수 비교·변화 분석 가능하게.

## 입력 데이터
- `생활인프라_시계열데이터/{YEAR}/output_test/` — 연도 폴더 자동 스캔 (현재 2023, 2024)
- 각 연도: composite_index / supply_index / service_pop_index / access_index shapefile + integrated_meta.json
- 확인 사항:
  - 두 연도 시군구 229개, `SIGUNGU_CD` 동일, geometry 완전 동일 (EPSG:5179)
  - `popall` supply_index에 포함 → 별도 인구 shapefile 불필요, 면적은 geometry에서 계산
  - 원본 스키마 `SIGUNGU_CD`/`SIGUNGU_NM`/`SIDO_NM` — v3의 `sgg_cd`/`sgg_nm_k`/`sido_nm_k`로 rename 어댑터
  - 부문 컬럼: composite `*_conv`+`infra_sum`(+`infra_avg`), supply/pop `*_avg`, access `*_std`

## 산출물
`monitoring_living_infra_total_dashboard_v4/` — build.py → dashboard.html (단일 파일, v3 방식)

## 아키텍처
### build.py
1. 연도 폴더 스캔 → 연도별 4개 shapefile 로드, rename 어댑터, v3 병합 로직 재사용
2. embed 구조 분리:
   - `GEO`: geometry(simplify 0.001, EPSG:4326) + sgg_cd/이름 — 1회만
   - `YEARS`: `{year: {sgg_cd: {infra_idx, edu_conv…, edu_sup…, edu_pop…, edu_acc…, popall}}}`
   - `RANKS`: 연도별 종합+5부문 순위 사전계산
3. 크기: geometry ~3.5MB 고정, 연도당 속성 ~150KB

### UI (v3 디자인톤 유지)
- 헤더 전역 연도 셀렉터(세그먼트 버튼, 연도 자동 확장) — 지도·상세·비교 탭 전부 선택 연도로 렌더
- 상세 패널: 연도별 추이 미니라인차트 + 순위변화 배지
- 신규 "변화분석" 탭:
  - 증감 지도: 최신−이전 T점수 차이, diverging 색상, "상대적 위치 변화" 캡션 명시
  - 순위변화 상승/하락 TOP 테이블, 지표 필터(종합+5부문)
- 챗봇: v3 하네스 이식, 시계열 구조·T점수 상대성 주의 프롬프트, 도구에 연도 파라미터
- DRT 탭 제외. access_grids.js(500m 격자)는 시계열 아님 — v3 것 그대로 복사(최신 시점 표기)

## 지수 비교 원칙
T점수는 연도별 상대 표준화 → 절대 비교 불가. 증감은 T점수 차이로 표시하되
"상대적 위치 변화"임을 UI에 명시하고 순위변화 병기. 재표준화 안 함.

## 검증
- 연도 수×229 레코드, null 검사, v3 값과 spot check (2024)
- 브라우저 로드, 연도 전환, 변화탭 렌더 확인
