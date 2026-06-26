(function(){
  "use strict";

  var tools = [
    {
      id:"extract_candidates", group:"center", name:"1. 중심지 후보 추출", alg:"krihs_cnt_classifier:extract_candidates",
      summary:"격자 원자료에서 중심지 후보가 될 만한 공간 덩어리를 만든다. 결과는 아직 중심지로 확정된 것이 아니라 후보 폴리곤이다.",
      inputShape:"grid", outputShape:"candidate",
      inputTitle:"국토공간거점지도 격자",
      inputRows:[["gid","G_001"],["type","중심지Ⅰ"],["pop_r","420.5"],["geometry","500m grid polygon"]],
      outputTitle:"통합 중심지 후보 폴리곤",
      outputRows:[["중심지후보id","1"],["중심지후보이름","서초"],["구분","중심지후보그룹1"],["geometry","multi-polygon"]],
      steps:[
        {title:"격자 분류", action:"type이 중심지Ⅰ·Ⅱ이면 그룹1, 아니면 pop_r 임계값 이상을 그룹2 예비군으로 둔다.", artifact:"그룹1: G_001,G_002 / 그룹2 예비: G_021,G_022"},
        {title:"버퍼·디졸브", action:"각 후보군에 양의 버퍼, unaryUnion, 음의 버퍼를 차례로 적용해 격자를 하나의 면으로 묶는다.", artifact:"격자 12개 → 후보 폴리곤 2개"},
        {title:"거리 필터", action:"그룹2는 그룹1 후보의 1km 버퍼와 겹치면 제외한다.", artifact:"그룹2 예비 8개 → 유지 3개"},
        {title:"이름·중복 정리", action:"읍면동 교차 면적이 가장 큰 이름을 붙이고, 옵션에 따라 읍면동별 1개만 남긴다.", artifact:"서초동 → 서초, 중복명은 서초_2"}
      ],
      note:"버퍼 거리는 m 단위라 투영 좌표계에서 쓰는 것이 적합하다.",
      next:"이 후보 폴리곤이 다음 도구의 중심지 후보 레이어가 된다."
    },
    {
      id:"extract_center_attributes", group:"center", name:"2. 중심지 후보 속성 추출", alg:"krihs_cnt_classifier:extract_center_attributes",
      summary:"후보 폴리곤 안에 들어오는 격자를 모아 인구, 중심성, 생활인프라 지표를 계산한다.",
      inputShape:"attribute", outputShape:"attribute",
      inputTitle:"후보 폴리곤 + 격자 지표",
      inputRows:[["후보","중심지후보id=1"],["geojeom","pop_r, pop_w, pc_in, pc_out"],["infra","마을시설 열, 거점시설 열"],["포함 기준","격자 centroid in polygon"]],
      outputTitle:"속성 포함 후보 레이어",
      outputRows:[["res_pop_sum","52,400"],["wor_pop_sum","48,100"],["total_fac_avg","6.2"],["base_fac_avg","5.1"]],
      steps:[
        {title:"공간 인덱스", action:"국토공간거점지도와 생활인프라 격자에 spatial index를 만든다.", artifact:"geojeom index, infra index 생성"},
        {title:"포함 격자 수집", action:"후보 폴리곤별로 중심점이 내부에 있는 격자만 가져온다.", artifact:"후보 1번 내부 격자 43개"},
        {title:"인구·중심성 통계", action:"sum, max, min, avg, density 또는 중심성 avg 계열을 계산한다.", artifact:"res_pop_sum=52,400 / inflow_avg=0.63"},
        {title:"인프라 통계", action:"마을시설과 거점시설 열을 합산해 total_fac, vill_fac, base_fac 필드를 만든다.", artifact:"base_fac_avg=5.1 / total_fac_avg_ratio=0.31"}
      ],
      note:"코드의 마을시설 접두어는 village_fac가 아니라 vill_fac다.",
      next:"계산된 필드가 중심지 위계 분류 조건식의 입력이 된다."
    },
    {
      id:"classify_centers", group:"center", name:"3. 중심지 및 위계 설정", alg:"krihs_cnt_classifier:classify_centers",
      summary:"속성값에 조건식을 적용해 후보를 생활중심지, 지역중심지, 광역중심지로 올려 보낸다.",
      inputShape:"attribute", outputShape:"classified",
      inputTitle:"속성 포함 후보 레코드",
      inputRows:[["중심지후보id","1"],["total_fac_avg","6.2"],["base_fac_avg","5.1"],["res_pop_sum / wor_pop_sum","52,400 / 48,100"]],
      outputTitle:"분류 결과",
      outputRows:[["중심지후보id","1"],["분류","지역중심지"],["geometry","candidate polygon"],["제외","첫 조건 실패 후보"]],
      steps:[
        {title:"조건식 준비", action:"활성화된 유형의 QGIS 표현식을 위계값 순서로 정렬한다.", artifact:"생활 → 지역 → 광역"},
        {title:"생활 조건", action:"첫 조건을 평가한다. 실패하면 결과 레이어에 쓰지 않는다.", artifact:"total_fac_avg=6.2 → 통과"},
        {title:"지역 조건", action:"앞 조건을 통과한 피처만 두 번째 조건을 평가한다.", artifact:"base_fac_avg=5.1 → 지역중심지"},
        {title:"광역 조건", action:"세 번째 조건까지 통과하면 광역중심지로 갱신한다.", artifact:"wor_pop_sum=48,100 → 광역 미통과"}
      ],
      note:"현재 코드 기본 조건은 ratio가 아니라 total_fac_avg, base_fac_avg 수량 기준이다.",
      next:"분류 결과는 대표점 추출과 상위중심지 선별의 기준 레이어가 된다."
    },
    {
      id:"od_matrix_region_assign", group:"region", name:"1. 거리 행렬 기반 기초생활권 할당", alg:"krihs_cnt_classifier:od_matrix_region_assign",
      summary:"격자에서 각 중심지까지의 비용 행렬을 보고, 격자마다 가장 가까운 중심지를 배정한다.",
      inputShape:"od", outputShape:"zonegrid",
      inputTitle:"OD Matrix CSV + 격자 + 중심점",
      inputRows:[["origin_id","G_101"],["destination_id","C_03"],["total_cost","12.8"],["center","gid=C_03, cent_nm=서초"]],
      outputTitle:"격자 권역할당",
      outputRows:[["gid","G_101"],["destination_id","C_03"],["total_cost_updated","12.8"],["cent_id / cent_nm","C_03 / 서초"]],
      steps:[
        {title:"OD CSV 읽기", action:"레이어 source 경로에서 origin_id, destination_id, total_cost 열을 pandas로 읽는다.", artifact:"G_101 → C_01=21.0, C_03=12.8"},
        {title:"자기 연결 보정", action:"origin과 destination이 같으면 비용을 0.1로 둬 자기 권역을 우선한다.", artifact:"G_102 → G_102 cost 0.1"},
        {title:"최소 비용 선택", action:"origin_id별 total_cost_updated 최솟값 행을 고른다.", artifact:"G_101의 목적지 C_03 선택"},
        {title:"격자에 조인", action:"destination_id를 중심점 gid와 매칭해 cent_id, cent_nm을 격자 속성에 붙인다.", artifact:"G_101.cent_nm = 서초"}
      ],
      note:"UI에서 필드를 고르지만 내부 일부 계산은 origin_id, destination_id, total_cost 이름을 직접 참조한다.",
      next:"권역할당 격자는 스무딩의 입력이 된다."
    },
    {
      id:"region_smoothing", group:"region", name:"2. 기초생활권 스무딩", alg:"krihs_cnt_classifier:region_smoothing",
      summary:"권역 경계의 작은 튐을 이웃 격자 투표로 정리한다. 반복할수록 고립 셀이 주변 권역으로 흡수된다.",
      inputShape:"zonegrid", outputShape:"smooth",
      inputTitle:"권역할당 격자",
      inputRows:[["gid","G_101"],["cent_id","C_03"],["cent_nm","서초"],["geometry","grid polygon"]],
      outputTitle:"스무딩 결과",
      outputRows:[["cent_id_smoothed_1","C_03"],["cent_id_smoothed_2","C_04"],["cent_id_smoothed_final","방배"],["layer","smoothing_result"]],
      steps:[
        {title:"GeoDataFrame 로드", action:"입력 레이어를 geopandas로 읽고 cent_id를 문자열로 정리한다.", artifact:"격자 12,540개 로드"},
        {title:"이웃 계산", action:"공간 인덱스와 geometry.touches로 각 격자의 이웃 목록을 만든다.", artifact:"G_101 이웃: G_096,G_100,G_102"},
        {title:"반복 투표", action:"이웃 권역값의 최빈값을 다음 iteration 필드에 쓴다. 동률이면 seed 기반 랜덤 선택한다.", artifact:"C_03,C_04,C_04 → C_04"},
        {title:"최종 이름 매핑", action:"마지막 iteration의 cent_id를 cent_nm으로 바꿔 최종 표시 필드를 만든다.", artifact:"C_04 → 방배"}
      ],
      note:"최종 이름 매핑에 cent_nm 필드를 직접 사용한다.",
      next:"스무딩 결과는 하위생활권 격자 레이어로 재사용된다."
    },
    {
      id:"pop_weighted_centroid", group:"region", name:"3. 인구가중 중심지 대표점 추출", alg:"krihs_cnt_classifier:pop_weighted_centroid",
      summary:"중심지 폴리곤의 단순 중심이 아니라, 인구가 많은 격자 쪽으로 대표점을 이동시킨다.",
      inputShape:"classified", outputShape:"point",
      inputTitle:"중심지 폴리곤 + 인구 격자",
      inputRows:[["center","cent_id=C_03, 분류=지역중심지"],["grid","G_101 pop_r=850"],["grid centroid","x=205320, y=445210"],["weight","pop_r"]],
      outputTitle:"인구가중 중심점",
      outputRows:[["cent_id","C_03"],["geometry","POINT(205410 445180)"],["속성","중심지 원본 필드 유지"],["fallback","인구합 0이면 polygon centroid"]],
      steps:[
        {title:"내부 격자 찾기", action:"중심지 폴리곤 안에 centroid가 들어오는 격자를 찾는다.", artifact:"C_03 내부 격자 18개"},
        {title:"가중 좌표 합산", action:"각 격자 centroid 좌표에 인구값을 곱해 합산한다.", artifact:"Σpop*x, Σpop*y 계산"},
        {title:"가중 평균점", action:"좌표 합계를 총 인구로 나눠 대표점 좌표를 만든다.", artifact:"x=205410, y=445180"},
        {title:"포인트 출력", action:"필요하면 좌표계를 원래 중심지 CRS로 되돌리고 포인트를 쓴다.", artifact:"C_03 대표점 생성"}
      ],
      note:"폴리곤 내부 인구 합계가 0이면 단순 centroid를 대신 사용한다.",
      next:"대표점은 도로망 기반 중심지 간 거리 행렬 계산에 들어간다."
    },
    {
      id:"od_matrix_road_distance", group:"region", name:"4. 중심지-중심지 거리(도로) 행렬 산출", alg:"krihs_cnt_classifier:od_matrix_road_distance",
      summary:"대표점끼리의 직선거리가 아니라 도로망을 따라 이동하는 최단거리 행렬을 만든다.",
      inputShape:"road", outputShape:"od",
      inputTitle:"대표점 + 도로망",
      inputRows:[["center point","C_03, 분류=지역중심지"],["network","road line layer"],["ONEWAY","0 또는 1"],["from/to type","생활중심지 → 광역중심지"]],
      outputTitle:"도로거리 OD 행렬",
      outputRows:[["from_id","C_03"],["to_id","M_01"],["total_cost","18420.6"],["geometry","straight OD line"]],
      steps:[
        {title:"도로망 검증", action:"네트워크 레이어에 ONEWAY 필드가 있는지 확인한다.", artifact:"ONEWAY 필드 확인"},
        {title:"기점 필터", action:"선택한 기점 중심지 유형만 임시 포인트 레이어로 만든다.", artifact:"생활중심지 37개"},
        {title:"종점 필터", action:"선택한 종점 중심지 유형만 임시 포인트 레이어로 만든다.", artifact:"광역중심지 5개"},
        {title:"QNEAT3 실행", action:"OdMatrixFromLayersAsLines를 shortest path distance 전략으로 호출한다.", artifact:"37 × 5 거리 행렬"}
      ],
      note:"QNEAT3 플러그인과 ONEWAY 필드가 필수다.",
      next:"거리 행렬은 매력도 기반 상위생활권 도출에 연결된다."
    },
    {
      id:"mobility_matrix", group:"region", name:"5. 하위생활권-상위중심지 이동량 행렬 산출", alg:"krihs_cnt_classifier:mobility_matrix",
      summary:"격자 단위 모바일 통행량을 하위생활권과 상위중심지 쌍으로 묶어 유입·유출 표로 바꾼다.",
      inputShape:"mobility", outputShape:"mobility",
      inputTitle:"하위생활권 격자 + 통행 CSV",
      inputRows:[["from_id","G_101"],["to_id","G_902"],["trip","34.7"],["grid mapping","G_101 → 하위생활권 C_03"]],
      outputTitle:"생활권-상위중심지 이동량 CSV",
      outputRows:[["하위생활권ID","C_03"],["상위중심지ID","M_01"],["유입통행량","1,248.5"],["유출통행량","932.0"]],
      steps:[
        {title:"격자 매핑", action:"하위생활권 격자의 grid_id를 zone_id로 매핑한다.", artifact:"G_101 → C_03"},
        {title:"상위중심 격자", action:"상위중심지 폴리곤 안에 들어오는 격자 ID 집합을 만든다.", artifact:"M_01 내부 격자 42개"},
        {title:"CSV 단일 패스", action:"통행 CSV를 한 줄씩 읽으며 from/to 격자를 확인한다.", artifact:"500,000행마다 진행 로그"},
        {title:"양방향 누적", action:"하위→상위는 유입, 상위→하위는 유출로 누적한다.", artifact:"(C_03,M_01) = 1,248.5 / 932.0"}
      ],
      note:"CSV 파일은 utf-8-sig, utf-8, cp949 순서로 열기를 시도한다.",
      next:"이동량 표는 매력도 계산의 중간 검증 자료로 쓸 수 있다."
    },
    {
      id:"attractiveness_upper_zone", group:"region", name:"6. 매력도 기반 상위생활권 도출", alg:"krihs_cnt_classifier:attractiveness_upper_zone",
      summary:"통행량이 많고 거리가 가까운 상위중심지를 선택해 하위생활권을 상위생활권으로 묶는다.",
      inputShape:"zone", outputShape:"zone",
      inputTitle:"상위중심지 + 하위생활권 + 거리",
      inputRows:[["mobility","C_03 → M_01, 유입+유출=2,180.5"],["distance","C_03 → M_01, 18.4km"],["formula","(inflow+outflow)/dist²"],["upper type","광역중심지"]],
      outputTitle:"상위생활권 권역",
      outputRows:[["하위생활권ID","C_03"],["상위중심지ID","M_01"],["매력도점수","6.44"],["dissolve","M_01 권역 격자수 320"]],
      steps:[
        {title:"통행량 집계", action:"하위생활권과 상위중심지 쌍별 유입·유출 이동량을 만든다.", artifact:"C_03-M_01 총 2,180.5"},
        {title:"거리 결합", action:"중심지 간 거리 행렬을 읽고 필요하면 m를 km로 변환한다.", artifact:"18,420m → 18.42km"},
        {title:"매력도 계산", action:"score = (유입 + 유출) / 거리²를 계산한다.", artifact:"2,180.5 / 18.42² = 6.44"},
        {title:"할당·합역", action:"점수가 가장 큰 상위중심지 ID를 격자에 붙이고 상위 ID별로 dissolve한다.", artifact:"C_03 → M_01, 권역 폴리곤 생성"}
      ],
      note:"거리값이 없거나 0 이하인 쌍은 매력도 후보에서 제외된다.",
      next:"최종 산출물은 상위생활권 경계 지도와 매력도 점수 CSV다."
    },
    {
      id:"policy_interest_area", group:"m01", name:"1. 정책관심구역 산출", alg:"simulation_toolbox:policy_interest_area",
      summary:"국토공간거점지도의 거점 유형과 생활인프라 충족도를 합집합해 1km 격자를 유도구역/주변으로 구분한다.",
      inputShape:"grid", outputShape:"zonegrid",
      inputTitle:"거점지도 + 생활인프라 격자",
      inputRows:[["거점지도","gid, type"],["인프라","GRID_1K_CD, Me_CI_1, Me_CI_2"],["거점유형","중심지Ⅰ·Ⅱ·Ⅲ 선택"],["충족도 임계","Me_CI ≥ 3.0"]],
      outputTitle:"정책관심구역 격자",
      outputRows:[["gid","다바05"],["type","중심지Ⅰ"],["zone","유도구역"],["SOURCE","TYPE+CI"]],
      steps:[
        {title:"거점 유형 필터", action:"거점지도에서 선택한 type(중심지Ⅰ·Ⅱ 등)에 해당하는 gid를 모은다.", artifact:"type_gids 12,340개"},
        {title:"충족도 기준", action:"인프라 격자에서 Me_CI_1 또는 Me_CI_2가 임계값 이상인 GRID_1K_CD를 모은다(OR).", artifact:"ci_gids 8,902개"},
        {title:"합집합", action:"두 집합을 합쳐 유도구역 대상 격자를 만든다(TYPE·CI·교집합 구분).", artifact:"유도구역 15,210 / 주변 4,790"},
        {title:"zone 부여 출력", action:"전체 격자를 다시 쓰며 대상이면 zone=유도구역, 아니면 주변을 부여한다.", artifact:"{gid:다바05, zone:유도구역}"}
      ],
      note:"거점지도는 gid, 인프라는 GRID_1K_CD로 격자 키 필드명이 달라 두 코드체계가 일치해야 하며, 충족도는 AND가 아닌 OR 결합이다.",
      next:"zone(유도구역/주변)은 장래인구 배분의 거점 가중치 판별 입력이 된다."
    },
    {
      id:"pop_grid_allocate", group:"m02", name:"1. 장래인구 격자 배분", alg:"simulation_toolbox:pop_grid_allocate",
      summary:"시군구 단위 장래인구 추계를 zone(거점/비거점)별 지수가중으로 1km 격자에 재배분해 연도별 인구를 산출한다.",
      inputShape:"zonegrid", outputShape:"popgrid",
      inputTitle:"격자 장래인구(BAU) + zone",
      inputRows:[["격자","gid, sgg_cd_h, zone"],["기준인구","pop_r_21"],["추계","T_25 ~ T_40"],["지수","a1.1 b0.9 c0.9 d1.1"]],
      outputTitle:"연도별 격자 인구",
      outputRows:[["gid","다바05"],["pop_2025","142.3"],["pop_2035","135.0"],["pop_2040","131.0"]],
      steps:[
        {title:"zone 적용·그룹화", action:"(연결 시) zone 레이어로 zone을 덮어쓰고, 시군구(sgg_cd_h)별로 격자를 묶는다.", artifact:"sgg_groups[43111]=12격자"},
        {title:"초기 ratio", action:"시군구 평균 대비 격자 pop_r_21 비율로 ratio를 초기화한다(평균 0이면 1.0).", artifact:"다바05 ratio=1.42"},
        {title:"연도별 지수배분", action:"T_25→T_40 순으로 거점/비거점·ratio 구간별 가중치(r^a~r^d)로 시군구 인구를 비례 배분한다.", artifact:"2025 다바05=142.3명"},
        {title:"ratio 연쇄·출력", action:"배분 결과로 ratio를 갱신해 다음 연도로 넘기고 pop_2025~2040을 기록한다.", artifact:"new_ratio=1.38 → 2030 입력"}
      ],
      note:"시군구 총인구를 보존하며 ratio가 연도 간 연쇄되므로 연도 처리 순서가 결과에 영향을 준다.",
      next:"pop_2025~2040은 생활여건 향유도·관리대상 시설 탐색의 인구 격자 입력이 된다."
    },
    {
      id:"living_condition", group:"m03", name:"1. 생활여건 향유도 산출", alg:"simulation_toolbox:living_condition",
      summary:"POI 서비스권역(버퍼) 안 인구를 시군구 전체 인구로 나눠 시설별·시점별 향유도를 산출한다.",
      inputShape:"poibuffer", outputShape:"yeartable",
      inputTitle:"격자 인구 + POI 폴더",
      inputRows:[["격자인구","T_25~T_40, pop_2025~2040"],["POI","폴더 내 시설별 파일"],["반경","기본 500m"],["시설표","시설명·약어·반경"]],
      outputTitle:"시설별 향유도 표",
      outputRows:[["시설명","의원 / clinic"],["sgg_cd_h","43111"],["_b25 (BAU)","0.645"],["_s40 (SN1)","0.712"]],
      steps:[
        {title:"격자 중심점", action:"격자별 중심점과 8개 인구 컬럼을 저장하고 sgg_cd_h를 모은다.", artifact:"grid[다바05]={sgg:43111, T_25:120}"},
        {title:"시군구 인구·인덱스", action:"시군구별 8시점 총인구를 합산하고 격자 중심점으로 공간 인덱스를 만든다.", artifact:"sgg_tot[43111][T_25]=15,200"},
        {title:"서비스권 분석", action:"각 POI를 반경 버퍼로 확장해 내부 격자 중심점 인구를 시군구별로 합산한다.", artifact:"clinic 커버 1,820격자"},
        {title:"향유도 산출", action:"서비스권 인구 / 시군구 전체 인구로 시점별 향유도를 계산한다.", artifact:"(clinic,43111) _b25=0.645"}
      ],
      note:"인구 8개 컬럼(T_25~T_40, pop_2025~2040)이 모두 있어야 하고, 격자 포함은 폴리곤 교차가 아닌 버퍼가 격자 중심점을 포함하는지로 판정한다.",
      next:"향유도 지표는 KPI 진단모형(설계 예정)의 입력으로 쓰인다."
    },
    {
      id:"infra_mgmt", group:"m03", name:"2. 관리대상 생활인프라시설 탐색", alg:"simulation_toolbox:infra_mgmt",
      summary:"각 POI 서비스반경 내 배후인구가 최소 기준 미만인 시점을 관리대상(1)으로 분류한다.",
      inputShape:"poibuffer", outputShape:"facflag",
      inputTitle:"격자 인구 + POI 폴더",
      inputRows:[["격자인구","T_25~T_40, pop_2025~2040"],["POI","폴더 내 시설별 파일"],["반경","기본 500m"],["최소 배후인구","기본 2,000"]],
      outputTitle:"시설별 관리대상 GPKG",
      outputRows:[["POI 원본","유지"],["_b25","1 (관리대상)"],["_s40","0 (유지)"],["파일","clinic_mgmt.gpkg"]],
      steps:[
        {title:"격자 인덱스", action:"격자 중심점과 8개 인구 컬럼을 저장하며 공간 인덱스를 만든다.", artifact:"grid[1024]={T_25:120}"},
        {title:"출력 파일 준비", action:"시설마다 {약어}_mgmt.gpkg를 만들고 POI 필드 + 8시점 정수 컬럼을 둔다.", artifact:"clinic_mgmt.gpkg 생성"},
        {title:"배후인구 판별", action:"POI 버퍼 내 격자 중심점 인구를 시점별로 합산해 최소 기준 미만이면 1을 부여한다.", artifact:"POI#7 T_25=1,800<2,000 → 1"},
        {title:"저장·자동로드", action:"관리 여부를 기록해 GPKG로 저장하고 QGIS에 추가한다.", artifact:"관리대상(_b25) 34/210"}
      ],
      note:"관리대상 판정은 '미만(<)' 기준이며, 진행 로그의 관리대상 수는 _b25(BAU 2025) 한 시점만 집계한다.",
      next:"시점별 관리대상 플래그는 KPI 진단·인프라 관리 의사결정에 쓰인다."
    },
    {
      id:"pop_plan_step1", group:"m02", name:"2. 신규 건축물량 계산", alg:"pop_plan_alloc:step1",
      summary:"사업지구의 연도별 신규 건축호수를 겹치는 시군구에 균등 분배하고 기준 주택호수에 누적해 시군구별 기존/신규 호수를 만든다.",
      inputShape:"grid", outputShape:"yeartable",
      inputTitle:"격자 + 사업지구 + 주택호수",
      inputRows:[["격자","gid, sgg_cd_h, sd_sgg_nm"],["사업지구","zoneName, newHouse25~40"],["주택호수 Excel","시도·시군구·호수"],["기준연도","2022 누적 시작"]],
      outputTitle:"시군구 연도별 호수 CSV",
      outputRows:[["sgg_cd_h","41461"],["기존호수_2025","420,000"],["신규호수_2025","500"],["기존호수_2030","420,500"]],
      steps:[
        {title:"공간 중첩", action:"격자 공간 인덱스로 각 사업지구와 실제 교차하는 시군구 집합을 구한다.", artifact:"광교지구 → {41461,41463} n=2"},
        {title:"신규호수 분배", action:"사업지구 newHouseYY를 겹치는 시군구 수 n으로 균등 분할해 누적한다.", artifact:"1000 / 2 → 각 +500"},
        {title:"기준호수 로드", action:"주택호수 Excel을 시도+시군구명 키로 읽어 기준(2022) 호수를 만든다.", artifact:"'경기도 수원시'=420,000"},
        {title:"연도별 누적", action:"기존호수_t = 기준 + 이전연도 신규 합, 신규호수_t = 해당연도 신규로 계산한다.", artifact:"2025 기존=420,000 / 신규=500"}
      ],
      note:"기존호수는 해당 연도 신규를 더하기 전 값이며, 신규호수는 겹치는 시군구 수로 균등 분배된다.",
      next:"기존/신규 호수 CSV는 2단계에서 KOTI 인구를 개발/비개발로 나누는 비율이 된다."
    },
    {
      id:"pop_plan_step2", group:"m02", name:"3. 개발·비개발 인구 배분", alg:"pop_plan_alloc:step2",
      summary:"연도별 KOTI 장래인구를 신규/기존 호수 비율로 나눠 시군구별 개발지구·비개발지구 인구로 배분한다.",
      inputShape:"yeartable", outputShape:"yeartable",
      inputTitle:"1단계 CSV + KOTI 인구",
      inputRows:[["1단계","기존호수·신규호수_YYYY"],["KOTI Excel","시도·시군구·KOTI_2025~2040"],["공식","개발=KOTI×신규/전체"],["키","시도+시군구명"]],
      outputTitle:"개발/비개발 인구 CSV",
      outputRows:[["sgg_cd_h","41461"],["개발_2025","1,415"],["비개발_2025","1,188,585"],["…","연도별 반복"]],
      steps:[
        {title:"1단계 로드", action:"1단계 CSV에서 시군구별 기존/신규 호수를 복원한다.", artifact:"41461 기존420,000 신규500"},
        {title:"KOTI 로드", action:"KOTI Excel을 시도+시군구명 키로 읽어 연도별 장래인구를 만든다.", artifact:"수원시 2025=1,190,000"},
        {title:"개발/비개발 배분", action:"개발=KOTI×신규/전체, 비개발=KOTI×기존/전체로 나눈다.", artifact:"개발≈1,415 / 비개발≈1,188,585"},
        {title:"CSV 저장", action:"연도별 개발·비개발 컬럼을 넓은 표로 저장한다.", artifact:"개발_2025 … 비개발_2040"}
      ],
      note:"신규호수=0(또는 전체=0)인 연도는 개발=0·비개발=KOTI 전액으로 처리하고, KOTI 미매칭 시군구는 결과에서 제외한다.",
      next:"개발/비개발 인구는 3단계 격자 배분의 시군구별 배분 총량이 된다."
    },
    {
      id:"pop_plan_step3", group:"m02", name:"4. 인구 격자 배분", alg:"pop_plan_alloc:step3",
      summary:"비개발 인구는 거점 가중 지수배분으로 전체 격자에, 개발 인구는 개발격자에 균등 추가해 연도순으로 격자 인구를 만든다.",
      inputShape:"yeartable", outputShape:"popgrid",
      inputTitle:"격자 + 정책관심구역 + 2단계 CSV",
      inputRows:[["격자","gid, sgg_cd_h, pop_r_21"],["정책관심구역","GRID_1K_CD (거점)"],["사업지구","newHouse25~40"],["2단계","개발·비개발_YYYY"]],
      outputTitle:"연도별 격자 인구 SHP",
      outputRows:[["gid","다바3344"],["pop_2025","707.5"],["pop_2035","690.0"],["pop_2040","672.0"]],
      steps:[
        {title:"ratio 초기화", action:"시군구 평균 대비 격자 pop_r_21 비율로 ratio를 초기화한다.", artifact:"다바3344 ratio=1.5"},
        {title:"개발격자 식별", action:"연도별 newHouseYY>0 사업지구와 교차하는 격자를 모은다.", artifact:"2025 개발격자 {다바3344,…}"},
        {title:"지수 배분", action:"비개발은 거점/비거점·ratio 구간 가중치(r^a~r^d)로 전체 격자에, 개발은 개발격자에 균등 추가한다.", artifact:"개발 1,415 → 2격자 각 +707.5"},
        {title:"ratio 갱신·거점 편입", action:"배분 결과로 ratio를 갱신하고 개발격자를 다음 연도 거점으로 편입해 SHP를 저장한다.", artifact:"2025 개발격자 → 2030 거점"}
      ],
      note:"비개발 인구는 개발격자 포함 전체 격자에 배분돼 기존 인구를 유지하고, 거점/비거점 가중치는 a1.1 b0.9 c0.9 d1.1이 기본이다.",
      next:"pop_2025~2040 격자 인구는 4단계 폐업 시뮬레이션의 배후인구 산출 입력이 된다."
    },
    {
      id:"pop_plan_step4", group:"m02", name:"5. 폐업 시뮬레이션", alg:"pop_plan_alloc:step4",
      summary:"POI 서비스반경 버퍼 내 격자 인구를 합산해 배후인구를 구하고, 최소 기준 미만 시점을 관리대상(폐업위험)으로 표시한다.",
      inputShape:"poibuffer", outputShape:"facflag",
      inputTitle:"3단계 격자 인구 + POI",
      inputRows:[["격자","pop_2025~2040"],["POI","시설 포인트 SHP"],["반경","기본 500m"],["최소 배후인구","기본 2,000"]],
      outputTitle:"POI 배후인구·폐업위험 GPKG",
      outputRows:[["POI 원본","유지"],["pop_2025","1,850"],["mgmt_2025","1 (위험)"],["mgmt_2040","0"]],
      steps:[
        {title:"격자 중심점 인덱스", action:"3단계 격자의 중심점을 점으로 인덱싱하고 fid→gid를 매핑한다.", artifact:"다바3344 중심점 pop_2025=707.5"},
        {title:"POI 버퍼", action:"각 POI를 서비스반경(기본 500m) 버퍼로 확장한다.", artifact:"약국#12 반경 500m"},
        {title:"배후인구 합산", action:"버퍼 안에 중심점이 포함되는 격자의 연도별 인구를 합산한다.", artifact:"포함 8격자 → 2025 합 1,850"},
        {title:"관리대상 판정", action:"배후인구 < 최소 기준이면 mgmt=1을 부여하고 GPKG로 저장한다.", artifact:"2025 1,850<2,000 → mgmt_2025=1"}
      ],
      note:"배후인구는 격자 폴리곤 교차가 아닌 격자 중심점이 버퍼에 포함되는지로 합산하며, 판정은 '미만(<)' 기준이다.",
      next:"최종 산출물은 연도별 배후인구·폐업위험 플래그가 부착된 POI GPKG로, 지도/대시보드 시각화에 쓰인다."
    }
  ];

  // ── 폴더 구조(트리) 순서로 정렬 (그룹 내 상대 순서는 유지) ──
  var GROUP_ORDER = ["m01", "m02", "m03", "center", "region"];
  tools.sort(function(a, b){ return GROUP_ORDER.indexOf(a.group) - GROUP_ORDER.indexOf(b.group); });

  var index = 0;
  var toolWindow = document.getElementById("toolWindow");
  var counter = document.getElementById("counter");
  var crumb = document.getElementById("crumb");
  var progress = document.getElementById("progress");
  var dots = document.getElementById("dots");
  var prevBtn = document.getElementById("prevBtn");
  var nextBtn = document.getElementById("nextBtn");

  function escapeHtml(value){
    return String(value).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\"/g,"&quot;").replace(/'/g,"&#039;");
  }
  function pad(n){ return n < 10 ? "0" + n : String(n); }
  var GROUP_LABELS = {
    m01:    "01. 공간정책 투입모형",
    m02:    "02. 장래인구 배분모형",
    m03:    "03. 생활여건 변화모형",
    center: "04. 중심지 분석",
    region: "05. 중심지-생활권 경계 도출"
  };
  function groupLabel(tool){ return GROUP_LABELS[tool.group] || tool.group; }

  // ── 샘플 일러스트 공통 자원 ─────────────────────────────────────────
  var SHAPE_DEFS = '<defs>' +
    '<linearGradient id="gBlue" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#eef4ff"/><stop offset="1" stop-color="#cdddff"/></linearGradient>' +
    '<linearGradient id="gGreen" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e7f7f0"/><stop offset="1" stop-color="#c3ecdc"/></linearGradient>' +
    '<linearGradient id="gAmber" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fdf1de"/><stop offset="1" stop-color="#f6dcaf"/></linearGradient>' +
    '<linearGradient id="gPurple" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f1e9ff"/><stop offset="1" stop-color="#dbc8ff"/></linearGradient>' +
    '<filter id="softShadow" x="-25%" y="-25%" width="150%" height="150%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#1f2937" flood-opacity="0.16"/></filter>' +
    '</defs>';
  var SHAPE_FRAME = '<rect x="6" y="6" width="248" height="138" rx="12" fill="#fcfdff" stroke="#e7e9ee"/>';

  // 셀 색상 (연한 면)
  var C_N = "#e6eaf1", C_B = "#bcd2ff", C_G = "#b6e6d2", C_A = "#f4d6a6", C_P = "#d3bdff";

  function _svg(inner){
    return '<svg viewBox="0 0 260 150" preserveAspectRatio="xMidYMid meet" aria-hidden="true">' + SHAPE_DEFS + SHAPE_FRAME + inner + '</svg>';
  }
  // 색 지정 텍스트: CSS class가 fill 속성을 덮어쓰므로 색은 inline style로 적용
  function _t(x, y, txt, color, cls){
    return '<text x="' + x + '" y="' + y + '" class="' + (cls || "shape-mono") + '"' + (color ? ' style="fill:' + color + '"' : '') + '>' + txt + '</text>';
  }
  function _grid(ox, oy, cols, rows, pitch, size, colors){
    var html = "";
    for(var r=0;r<rows;r++){
      for(var c=0;c<cols;c++){
        var f = colors[r*cols+c] || C_N;
        html += '<rect x="' + (ox+c*pitch) + '" y="' + (oy+r*pitch) + '" width="' + size + '" height="' + size + '" rx="3" fill="' + f + '" stroke="#fff" stroke-width="2"/>';
      }
    }
    return html;
  }
  function _chip(x, y, fill, label, stroke){
    return '<rect x="' + x + '" y="' + (y-9) + '" width="12" height="12" rx="3" fill="' + fill + '"' + (stroke ? ' stroke="' + stroke + '" stroke-width="1.3"' : '') + '/>' +
           _t(x+17, y+1, label);
  }
  function _star(cx, cy, fill){
    return '<path transform="translate(' + cx + ' ' + cy + ')" d="M0 -9 L2.6 -2.8 L9 -2.8 L3.7 1.4 L5.6 8 L0 3.8 L-5.6 8 L-3.7 1.4 L-9 -2.8 L-2.6 -2.8 Z" fill="' + fill + '" stroke="#fff" stroke-width="1.2"/>';
  }

  // 깔끔한 가로 화살표 (오른쪽/왼쪽). dir: "r" 또는 "l"
  function _arrow(x1, x2, y, color, dir){
    var line = '<line x1="' + x1 + '" y1="' + y + '" x2="' + x2 + '" y2="' + y + '" stroke="' + color + '" stroke-width="2.6"/>';
    var head = (dir === "l")
      ? '<path d="M' + (x2+7) + ' ' + (y-5) + ' L' + x2 + ' ' + y + ' L' + (x2+7) + ' ' + (y+5) + ' Z" fill="' + color + '"/>'
      : '<path d="M' + (x2-7) + ' ' + (y-5) + ' L' + x2 + ' ' + y + ' L' + (x2-7) + ' ' + (y+5) + ' Z" fill="' + color + '"/>';
    return line + head;
  }

  function shapeSvg(type){
    // 1) 격자 원자료 — 색칠된 셀 몇 개 + 범례
    if(type === "grid"){
      return _svg(
        _t(20, 28, "국토공간거점지도 격자", null, "shape-title") +
        _grid(64, 44, 6, 3, 23, 19, [
          C_N,C_N,C_B,C_B,C_N,C_N,
          C_N,C_B,C_B,C_P,C_N,C_N,
          C_N,C_N,C_B,C_N,C_N,C_N
        ]) +
        _chip(60, 134, C_B, "중심지Ⅰ·Ⅱ", "#2563eb") +
        _chip(150, 134, C_N, "일반 격자", "#d6dbe2")
      );
    }
    // 2) 격자 → 후보 면 (작은 격자 → 화살표 → 면)
    if(type === "candidate"){
      // 출력 = 격자 셀이 버퍼·디졸브로 뭉친 멀티폴리곤. 셀 덩어리 + 외곽선으로 표현
      return _svg(
        _t(20, 28, "격자 → 중심지 후보 면", null, "shape-title") +
        _grid(38, 64, 2, 2, 21, 18, [C_B,C_B, C_B,C_B]) +
        _arrow(92, 128, 84, "#9aa1ac", "r") +
        [[1,0],[2,0],[3,0],[0,1],[1,1],[2,1],[3,1],[4,1],[0,2],[1,2],[2,2],[3,2],[4,2],[1,3],[2,3],[3,3]].map(function(c){
          return '<rect x="' + (150+c[0]*15) + '" y="' + (56+c[1]*15) + '" width="15" height="15" fill="#cdddff" stroke="#fff" stroke-width="1.5"/>';
        }).join("") +
        '<path d="M165 56 L210 56 L210 71 L225 71 L225 101 L210 101 L210 116 L165 116 L165 101 L150 101 L150 71 L165 71 Z" fill="none" stroke="#2563eb" stroke-width="2.6" stroke-linejoin="round"/>' +
        _t(150, 134, "격자가 뭉친 후보 폴리곤", null, "shape-label")
      );
    }
    // 3) 후보 면 → 집계 통계 3종
    if(type === "attribute"){
      return _svg(
        _t(20, 28, "후보 면 + 격자 집계", null, "shape-title") +
        '<ellipse cx="64" cy="84" rx="36" ry="30" fill="url(#gBlue)" stroke="#2563eb" stroke-width="2"/>' +
        '<g fill="#0f9d6f"><circle cx="52" cy="80" r="4"/><circle cx="72" cy="76" r="4"/><circle cx="64" cy="94" r="4"/></g>' +
        _t(44, 130, "후보 면", null, "shape-label") +
        _arrow(106, 134, 84, "#9aa1ac", "r") +
        '<g transform="translate(146 54)">' +
          '<rect x="0" y="0" width="98" height="20" rx="6" fill="#eff4ff" stroke="#cfe0ff"/>' + _t(9, 14, "인구  res_pop") +
          '<rect x="0" y="26" width="98" height="20" rx="6" fill="#e8f7f1" stroke="#c7eedf"/>' + _t(9, 40, "중심성  pc_in") +
          '<rect x="0" y="52" width="98" height="20" rx="6" fill="#fdf3e3" stroke="#f3e2c2"/>' + _t(9, 66, "인프라  fac") +
        '</g>'
      );
    }
    // 4) 위계 분류 — 분리된 면 3개
    if(type === "classified"){
      return _svg(
        _t(20, 28, "위계 분류 결과", null, "shape-title") +
        '<ellipse cx="66" cy="78" rx="26" ry="24" fill="url(#gGreen)" stroke="#0f9d6f" stroke-width="2"/>' +
        '<ellipse cx="130" cy="78" rx="26" ry="24" fill="url(#gAmber)" stroke="#c2780a" stroke-width="2"/>' +
        '<ellipse cx="194" cy="78" rx="26" ry="24" fill="#f7c6c6" stroke="#8c0000" stroke-width="2"/>' +
        _t(48, 120, "생활중심지", null, "shape-label") +
        _t(112, 120, "지역중심지", null, "shape-label") +
        _t(176, 120, "광역중심지", null, "shape-label")
      );
    }
    // 5) OD 비용 행렬 — 최소 비용 행 강조
    if(type === "od"){
      return _svg(
        _t(20, 28, "OD 비용 행렬", null, "shape-title") +
        '<g transform="translate(26 40)">' +
          '<rect x="0" y="0" width="208" height="22" rx="6" fill="#eef0f3"/>' +
          _t(10, 15, "origin") + _t(80, 15, "destination") + _t(170, 15, "cost") +
          '<rect x="0" y="27" width="208" height="20" rx="5" fill="#fff" stroke="#eef0f3"/>' +
          _t(10, 41, "G101") + _t(80, 41, "C01") + _t(170, 41, "21.0") +
          '<rect x="0" y="51" width="208" height="20" rx="5" fill="#e8f7f1" stroke="#0f9d6f" stroke-width="1.5"/>' +
          _t(10, 65, "G101") + _t(80, 65, "C03") + _t(170, 65, "12.8") +
        '</g>' +
        _t(26, 132, "↑ origin별 최소 비용 행 → 권역 배정", "#0f9d6f")
      );
    }
    // 6) 권역 배정 격자 — 색으로 영역 구분
    if(type === "zonegrid"){
      return _svg(
        _t(20, 28, "권역 배정 격자", null, "shape-title") +
        _grid(64, 40, 7, 4, 18, 15, [
          C_B,C_B,C_B,C_A,C_A,C_A,C_A,
          C_B,C_B,C_B,C_A,C_A,C_A,C_A,
          C_B,C_B,C_A,C_A,C_G,C_G,C_G,
          C_B,C_B,C_A,C_A,C_G,C_G,C_G
        ]) +
        _chip(40, 136, C_B, "서초", "#2563eb") + _chip(104, 136, C_A, "방배", "#c2780a") + _chip(168, 136, C_G, "양재", "#0f9d6f")
      );
    }
    // 7) 권역 경계 스무딩 (before → after)
    if(type === "smooth"){
      return _svg(
        _t(20, 28, "권역 경계 정리", null, "shape-title") +
        _t(40, 50, "before", null, "shape-label") +
        _grid(28, 56, 3, 3, 18, 15, [C_B,C_B,C_B, C_B,C_A,C_B, C_B,C_B,C_B]) +
        '<rect x="45" y="73" width="18" height="18" rx="3" fill="none" stroke="#e11d48" stroke-width="2.4"/>' +
        _arrow(112, 144, 92, "#9aa1ac", "r") +
        _t(176, 50, "after", null, "shape-label") +
        _grid(164, 56, 3, 3, 18, 15, [C_B,C_B,C_B, C_B,C_B,C_B, C_B,C_B,C_B]) +
        _t(34, 134, "고립 셀이 이웃 권역 최빈값으로 흡수")
      );
    }
    // 8) 인구가중 대표점 — 단순 중심 → 가중 중심
    if(type === "point"){
      return _svg(
        _t(20, 28, "인구가중 대표점", null, "shape-title") +
        '<ellipse cx="104" cy="82" rx="52" ry="32" fill="url(#gBlue)" stroke="#2563eb" stroke-width="2"/>' +
        '<g fill="#0f9d6f"><circle cx="124" cy="72" r="4.5"/><circle cx="136" cy="84" r="4.5"/><circle cx="126" cy="94" r="4.5"/></g>' +
        '<circle cx="82" cy="82" r="6.5" fill="#fff" stroke="#9aa1ac" stroke-width="2"/>' +
        '<line x1="90" y1="82" x2="100" y2="82" stroke="#e11d48" stroke-width="2"/><path d="M99 79 L104 82 L99 85 Z" fill="#e11d48"/>' +
        '<circle cx="108" cy="82" r="6.5" fill="#e11d48" stroke="#fff" stroke-width="1.5"/>' +
        _chip(40, 134, "#ffffff", "단순 중심", "#9aa1ac") +
        _chip(122, 134, "#e11d48", "인구가중 중심", "#e11d48")
      );
    }
    // 9) 도로 최단거리 — 직선(점선) vs 도로 경로(꺾은선)
    if(type === "road"){
      return _svg(
        _t(20, 28, "도로 최단거리", null, "shape-title") +
        '<line x1="58" y1="98" x2="206" y2="58" stroke="#b9c0cb" stroke-width="1.8" stroke-dasharray="6 4"/>' +
        '<path d="M58 98 L132 98 L132 58 L206 58" fill="none" stroke="#0f9d6f" stroke-width="3.4" stroke-linejoin="round"/>' +
        '<circle cx="58" cy="98" r="7" fill="#2563eb" stroke="#fff" stroke-width="1.6"/>' +
        '<circle cx="206" cy="58" r="7" fill="#7c3aed" stroke="#fff" stroke-width="1.6"/>' +
        _t(40, 116, "기점", null, "shape-label") + _t(194, 50, "종점", null, "shape-label") +
        _chip(30, 136, "#b9c0cb", "직선거리", "#b9c0cb") + _chip(118, 136, "#0f9d6f", "도로경로(QNEAT3)", "#0f9d6f")
      );
    }
    // 10) 이동량 집계 — 평행 화살표 2개 (유입/유출)
    if(type === "mobility"){
      return _svg(
        _t(20, 28, "이동량 집계", null, "shape-title") +
        '<rect x="26" y="60" width="82" height="46" rx="12" fill="url(#gBlue)" stroke="#2563eb" stroke-width="2"/>' +
        '<rect x="152" y="60" width="82" height="46" rx="12" fill="url(#gPurple)" stroke="#7c3aed" stroke-width="2"/>' +
        _t(40, 87, "하위생활권", null, "shape-label") + _t(166, 87, "상위중심지", null, "shape-label") +
        _t(118, 52, "유입", "#0f9d6f") +
        _arrow(110, 150, 72, "#0f9d6f", "r") +
        _arrow(150, 110, 94, "#c2780a", "l") +
        _t(118, 130, "유출", "#c2780a")
      );
    }
    // 12) 연도별 격자 인구 (인구 밀도 heat)
    if(type === "popgrid"){
      var H1 = "#eef4ff", H2 = "#cdddff", H3 = "#9dbdff", H4 = "#6f9bff";
      return _svg(
        _t(20, 28, "연도별 격자 인구", null, "shape-title") +
        _grid(64, 44, 6, 3, 23, 19, [
          H1,H2,H3,H4,H3,H2,
          H2,H3,H4,H4,H3,H2,
          H1,H2,H3,H3,H2,H1
        ]) +
        _chip(56, 134, H4, "인구 많음", "#2563eb") + _chip(150, 134, H1, "인구 적음", "#d6dbe2")
      );
    }
    // 13) 연도별 집계 표 (CSV·추계)
    if(type === "yeartable"){
      return _svg(
        _t(20, 28, "연도별 집계 표", null, "shape-title") +
        '<g transform="translate(24 42)">' +
          '<rect x="0" y="0" width="212" height="22" rx="6" fill="#eef0f3"/>' +
          _t(8, 15, "구분") + _t(66, 15, "2025") + _t(116, 15, "2030") + _t(166, 15, "2035") +
          '<rect x="0" y="27" width="212" height="20" rx="5" fill="#fff" stroke="#eef0f3"/>' +
          _t(8, 41, "43111") + _t(66, 41, "142") + _t(116, 41, "138") + _t(166, 41, "135") +
          '<rect x="0" y="51" width="212" height="20" rx="5" fill="#eef4ff" stroke="#cfe0ff"/>' +
          _t(8, 65, "43112") + _t(66, 65, "210") + _t(116, 65, "205") + _t(166, 65, "198") +
        '</g>' +
        _t(24, 132, "시군구·연도별 값 (인구 / 호수)")
      );
    }
    // 14) POI 서비스권역 — 반경 버퍼 + 배후인구
    if(type === "poibuffer"){
      return _svg(
        _t(20, 28, "POI 서비스권역", null, "shape-title") +
        '<circle cx="96" cy="82" r="44" fill="#eff4ff" fill-opacity="0.55" stroke="#2563eb" stroke-width="1.8" stroke-dasharray="6 4"/>' +
        '<g fill="#0f9d6f"><circle cx="78" cy="70" r="4"/><circle cx="112" cy="72" r="4"/><circle cx="82" cy="98" r="4"/><circle cx="110" cy="96" r="4"/></g>' +
        '<circle cx="152" cy="56" r="4" fill="#c2c7d0"/>' +
        '<circle cx="96" cy="82" r="7" fill="#e11d48" stroke="#fff" stroke-width="1.6"/>' +
        _t(150, 88, "반경 내", null, "shape-label") + _t(150, 104, "배후인구 합산", null, "shape-label") +
        _chip(40, 134, "#e11d48", "POI 시설", "#e11d48") + _chip(120, 134, "#0f9d6f", "권역 내 인구", "#0f9d6f")
      );
    }
    // 15) 관리대상 시설 판정 — 관리대상(1)/유지(0)
    if(type === "facflag"){
      return _svg(
        _t(20, 28, "관리대상 시설 판정", null, "shape-title") +
        '<circle cx="60" cy="58" r="9" fill="#e11d48" stroke="#fff" stroke-width="1.6"/>' + _t(57, 62, "1", "#fff") +
        '<circle cx="120" cy="70" r="9" fill="#0f9d6f" stroke="#fff" stroke-width="1.6"/>' + _t(117, 74, "0", "#fff") +
        '<circle cx="174" cy="56" r="9" fill="#0f9d6f" stroke="#fff" stroke-width="1.6"/>' + _t(171, 60, "0", "#fff") +
        '<circle cx="90" cy="100" r="9" fill="#e11d48" stroke="#fff" stroke-width="1.6"/>' + _t(87, 104, "1", "#fff") +
        '<circle cx="158" cy="102" r="9" fill="#0f9d6f" stroke="#fff" stroke-width="1.6"/>' + _t(155, 106, "0", "#fff") +
        _chip(40, 134, "#e11d48", "관리대상 (1)", "#e11d48") + _chip(140, 134, "#0f9d6f", "유지 (0)", "#0f9d6f")
      );
    }
    // 11) 상위생활권 합역 (default) — 분리된 권역 2개 + 중심
    return _svg(
      _t(20, 28, "상위생활권 합역", null, "shape-title") +
      '<ellipse cx="74" cy="80" rx="40" ry="30" fill="url(#gGreen)" stroke="#0f9d6f" stroke-width="2.4"/>' +
      _star(74, 80, "#0f9d6f") +
      _t(54, 124, "상위권역 A", null, "shape-label") +
      '<ellipse cx="188" cy="80" rx="40" ry="30" fill="url(#gPurple)" stroke="#7c3aed" stroke-width="2.4"/>' +
      _star(188, 80, "#7c3aed") +
      _t(168, 124, "상위권역 B", null, "shape-label")
    );
  }

  function rowsHtml(rows){
    return '<table><tbody>' + rows.map(function(row){
      return '<tr><th>' + escapeHtml(row[0]) + '</th><td>' + escapeHtml(row[1]) + '</td></tr>';
    }).join("") + '</tbody></table>';
  }

  function sampleCard(kind, title, shape, rows){
    return '<section class="sample-card ' + kind + '">' +
      '<div class="sample-head"><span class="sample-kicker">' + (kind === "input" ? "Input Data Sample" : "Output Data Sample") + '</span><h2>' + escapeHtml(title) + '</h2></div>' +
      '<div class="shape-box">' + shapeSvg(shape) + '</div>' +
      '<div class="sample-table">' + rowsHtml(rows) + '</div>' +
      '<div class="sample-note">샘플 값은 구조 설명용 가상 예시입니다.</div>' +
    '</section>';
  }

  // 단계 연산 종류별 아이콘. viewBox 120x70.
  function iconSvg(key){
    var o = '<svg viewBox="0 0 120 70" preserveAspectRatio="xMidYMid meet" aria-hidden="true">';
    var c = '</svg>';
    if(key === "load"){          // 데이터 읽기/로드
      return o +
        '<path d="M60 8 L60 22" stroke="#2563eb" stroke-width="2.4"/><path d="M54 16 L60 23 L66 16 Z" fill="#2563eb"/>' +
        '<rect x="40" y="26" width="40" height="32" rx="4" fill="#eff4ff" stroke="#2563eb" stroke-width="1.6"/>' +
        '<line x1="46" y1="36" x2="74" y2="36" stroke="#9dbdff" stroke-width="2"/><line x1="46" y1="44" x2="74" y2="44" stroke="#9dbdff" stroke-width="2"/><line x1="46" y1="52" x2="66" y2="52" stroke="#9dbdff" stroke-width="2"/>' + c;
    }
    if(key === "index"){         // 공간 인덱스/중심점
      return o +
        [[0,0],[1,0],[2,0],[0,1],[1,1],[2,1],[0,2],[1,2],[2,2]].map(function(p){
          return '<rect x="' + (42+p[0]*16) + '" y="' + (16+p[1]*16) + '" width="14" height="14" rx="2" fill="#e6eaf1" stroke="#fff" stroke-width="2"/>';
        }).join("") +
        '<circle cx="49" cy="23" r="3.5" fill="#0f9d6f"/><circle cx="81" cy="39" r="3.5" fill="#0f9d6f"/><circle cx="65" cy="55" r="3.5" fill="#0f9d6f"/>' + c;
    }
    if(key === "filter"){        // 필터/조건/선별
      return o + '<path d="M40 18 L80 18 L64 40 L64 54 L56 54 L56 40 Z" fill="#e8f7f1" stroke="#0f9d6f" stroke-width="2" stroke-linejoin="round"/>' + c;
    }
    if(key === "buffer"){        // 버퍼/서비스권역
      return o + '<circle cx="60" cy="36" r="22" fill="#eff4ff" fill-opacity="0.6" stroke="#2563eb" stroke-width="1.8" stroke-dasharray="5 4"/><circle cx="60" cy="36" r="5" fill="#e11d48"/>' + c;
    }
    if(key === "overlap"){       // 교차/중첩/포함
      return o + '<circle cx="52" cy="36" r="20" fill="#cdddff" fill-opacity="0.65" stroke="#2563eb" stroke-width="1.6"/><circle cx="74" cy="36" r="20" fill="#c3ecdc" fill-opacity="0.65" stroke="#0f9d6f" stroke-width="1.6"/>' + c;
    }
    if(key === "bars"){          // 합산/집계/통계
      return o + '<line x1="42" y1="54" x2="82" y2="54" stroke="#9aa1ac" stroke-width="1.6"/><rect x="46" y="36" width="9" height="18" rx="2" fill="#0f9d6f"/><rect x="58" y="24" width="9" height="30" rx="2" fill="#0f9d6f"/><rect x="70" y="30" width="9" height="24" rx="2" fill="#0f9d6f"/>' + c;
    }
    if(key === "compute"){       // 계산/배분 (기어)
      return o + '<g transform="translate(60 36)" fill="#c2780a">' +
        '<rect x="-3" y="-23" width="6" height="8" rx="1"/><rect x="-3" y="15" width="6" height="8" rx="1"/><rect x="-23" y="-3" width="8" height="6" rx="1"/><rect x="15" y="-3" width="8" height="6" rx="1"/>' +
        '<rect x="-3" y="-23" width="6" height="8" rx="1" transform="rotate(45)"/><rect x="-3" y="15" width="6" height="8" rx="1" transform="rotate(45)"/><rect x="-23" y="-3" width="8" height="6" rx="1" transform="rotate(45)"/><rect x="15" y="-3" width="8" height="6" rx="1" transform="rotate(45)"/>' +
        '<circle r="15" fill="#fdf3e3" stroke="#c2780a" stroke-width="2"/><circle r="6" fill="#fff" stroke="#c2780a" stroke-width="1.6"/></g>' + c;
    }
    if(key === "tag"){           // 분류/판정/라벨
      return o + '<path d="M40 24 L66 24 L84 36 L66 48 L40 48 Z" fill="#f3edff" stroke="#7c3aed" stroke-width="1.8" stroke-linejoin="round"/><circle cx="50" cy="36" r="3.2" fill="#7c3aed"/>' + c;
    }
    if(key === "point"){         // 대표점/포인트
      return o + '<path d="M60 16 C49 16 41 25 41 35 C41 48 60 58 60 58 C60 58 79 48 79 35 C79 25 71 16 60 16 Z" fill="#e8f1ff" stroke="#2563eb" stroke-width="1.8"/><circle cx="60" cy="34" r="6" fill="#2563eb"/>' + c;
    }
    if(key === "merge"){         // 합역/dissolve
      return o + '<rect x="44" y="24" width="32" height="28" rx="8" fill="#e8f7f1"/><rect x="62" y="24" width="32" height="28" rx="8" fill="#e8f7f1"/><path d="M52 24 L86 24 Q94 24 94 32 L94 44 Q94 52 86 52 L52 52 Q44 52 44 44 L44 32 Q44 24 52 24 Z" fill="none" stroke="#0f9d6f" stroke-width="2.4"/>' + c;
    }
    if(key === "route"){         // 도로/OD 경로
      return o + '<path d="M40 50 L62 50 L62 26 L84 26" fill="none" stroke="#0f9d6f" stroke-width="3" stroke-linejoin="round"/><circle cx="40" cy="50" r="6" fill="#2563eb" stroke="#fff" stroke-width="1.4"/><circle cx="84" cy="26" r="6" fill="#7c3aed" stroke="#fff" stroke-width="1.4"/>' + c;
    }
    if(key === "link"){          // 조인/매핑/결합
      return o + '<rect x="36" y="28" width="20" height="16" rx="5" fill="#eef4ff" stroke="#2563eb" stroke-width="1.6"/><rect x="64" y="28" width="20" height="16" rx="5" fill="#e8f7f1" stroke="#0f9d6f" stroke-width="1.6"/><line x1="56" y1="36" x2="64" y2="36" stroke="#9aa1ac" stroke-width="2.6"/>' + c;
    }
    // save (출력/저장) — 기본값
    return o + '<path d="M60 16 L60 38" stroke="#0f9d6f" stroke-width="2.6"/><path d="M53 31 L60 39 L67 31 Z" fill="#0f9d6f"/><path d="M40 42 L40 54 L80 54 L80 42" fill="none" stroke="#0f9d6f" stroke-width="2.2" stroke-linejoin="round"/>' + c;
  }

  // 도구·단계별 아이콘 (단계 의미에 맞춤)
  var STEP_ICONS = {
    extract_candidates:        ["filter","buffer","filter","tag"],
    extract_center_attributes: ["index","overlap","bars","bars"],
    classify_centers:          ["filter","filter","filter","tag"],
    od_matrix_region_assign:   ["load","compute","filter","link"],
    region_smoothing:          ["load","index","bars","link"],
    pop_weighted_centroid:     ["overlap","bars","compute","point"],
    od_matrix_road_distance:   ["route","filter","filter","route"],
    mobility_matrix:           ["link","overlap","load","bars"],
    attractiveness_upper_zone: ["bars","link","compute","merge"],
    policy_interest_area:      ["filter","filter","merge","tag"],
    pop_grid_allocate:         ["link","compute","compute","save"],
    living_condition:          ["index","bars","buffer","compute"],
    infra_mgmt:                ["index","save","buffer","save"],
    pop_plan_step1:            ["overlap","compute","load","bars"],
    pop_plan_step2:            ["load","load","compute","save"],
    pop_plan_step3:            ["compute","filter","compute","save"],
    pop_plan_step4:            ["index","buffer","bars","tag"]
  };

  function processStageSvg(tool, i){
    var keys = STEP_ICONS[tool.id] || ["load","filter","compute","save"];
    return iconSvg(keys[i] || "save");
  }
  function diagramHtml(tool){
    return '<section class="process-card"><div class="process-head"><h2>Process Diagram</h2><span>단계별 중간 산출 예시</span></div><div class="diagram"><div class="diagram-track">' +
      tool.steps.map(function(step, i){
        return '<article class="diagram-step"><span class="step-no">' + pad(i + 1) + '</span><div class="step-viz">' + processStageSvg(tool, i) + '</div><h3 class="step-title">' + escapeHtml(step.title) + '</h3><p class="step-action">' + escapeHtml(step.action) + '</p><div class="artifact"><b>intermediate</b><span>' + escapeHtml(step.artifact) + '</span></div></article>';
      }).join("") +
    '</div></div></section>';
  }

  function go(nextIndex){
    if(nextIndex < 0) nextIndex = tools.length - 1;
    if(nextIndex >= tools.length) nextIndex = 0;
    index = nextIndex;
    render();
    if(history.replaceState){ history.replaceState(null,"","#" + tools[index].id); }
  }

  function render(){
    var tool = tools[index];
    toolWindow.innerHTML = [
      '<div class="slide-head"><div><span class="kicker ' + escapeHtml(tool.group) + '">' + escapeHtml(groupLabel(tool)) + '</span><h1 class="tool-title">' + escapeHtml(tool.name) + '</h1><p class="tool-summary">' + escapeHtml(tool.summary) + '</p></div><span class="alg-id">' + escapeHtml(tool.alg) + '</span></div>',
      '<div class="story-grid">',
        sampleCard("input", tool.inputTitle, tool.inputShape, tool.inputRows),
        diagramHtml(tool),
        sampleCard("output", tool.outputTitle, tool.outputShape, tool.outputRows),
      '</div>',
      '<div class="footer-row"><section class="note-card check"><h3>확인할 점</h3><p>' + escapeHtml(tool.note) + '</p></section><section class="note-card next"><h3>다음 단계</h3><p>' + escapeHtml(tool.next) + '</p></section></div>'
    ].join("");
    counter.textContent = pad(index + 1) + " / " + pad(tools.length);
    crumb.textContent = groupLabel(tool);
    progress.style.width = tools.length > 1 ? (index / (tools.length - 1) * 100) + "%" : "100%";
    renderDots();
  }

  function renderDots(){
    dots.innerHTML = tools.map(function(tool, i){
      return '<button type="button" class="dot-btn' + (i === index ? ' active' : '') + '" aria-label="' + escapeHtml(tool.name) + '" data-index="' + i + '"></button>';
    }).join("");
    Array.prototype.forEach.call(dots.querySelectorAll(".dot-btn"), function(btn){
      btn.addEventListener("click", function(){ go(Number(btn.getAttribute("data-index"))); });
    });
  }

  prevBtn.addEventListener("click", function(){ go(index - 1); });
  nextBtn.addEventListener("click", function(){ go(index + 1); });
  document.addEventListener("keydown", function(event){
    if(anyModalOpen()) return;
    if(event.key === "ArrowRight" || event.key === "PageDown" || event.key === " "){
      event.preventDefault(); go(index + 1);
    }else if(event.key === "ArrowLeft" || event.key === "PageUp"){
      event.preventDefault(); go(index - 1);
    }else if(event.key === "Home"){
      event.preventDefault(); go(0);
    }else if(event.key === "End"){
      event.preventDefault(); go(tools.length - 1);
    }
  });

  // ── 중복·결합 분석 모달 (2종) ────────────────────────────────────
  // Airflow 스타일 DAG 헬퍼
  var DAG_NODE_H = 34;
  var DAG_COLORS = {
    center: {fill:"#eff4ff", stroke:"#2563eb", ink:"#1d4ed8"},
    region: {fill:"#e8f7f1", stroke:"#0f9d6f", ink:"#0b7a55"},
    sim:    {fill:"#f3edff", stroke:"#7c3aed", ink:"#6d28d9"},
    popplan:{fill:"#fdf3e3", stroke:"#c2780a", ink:"#9a5b00"},
    data:   {fill:"#eef0f3", stroke:"#9aa1ac", ink:"#485060"},
    result: {fill:"#15181d", stroke:"#15181d", ink:"#ffffff"}
  };
  function dagNode(x, y, w, label, key){
    var col = DAG_COLORS[key] || DAG_COLORS.data;
    return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + DAG_NODE_H + '" rx="9" fill="' + col.fill + '" stroke="' + col.stroke + '" stroke-width="1.6"/>' +
           '<text x="' + (x + w/2) + '" y="' + (y + DAG_NODE_H/2 + 4) + '" text-anchor="middle" class="dag-t" style="fill:' + col.ink + '">' + label + '</text>';
  }
  function dagEdge(x1, y1, x2, y2, dashed){
    var ang = Math.atan2(y2 - y1, x2 - x1), s = 7;
    var hx1 = (x2 + s*Math.cos(ang + 2.6)).toFixed(1), hy1 = (y2 + s*Math.sin(ang + 2.6)).toFixed(1);
    var hx2 = (x2 + s*Math.cos(ang - 2.6)).toFixed(1), hy2 = (y2 + s*Math.sin(ang - 2.6)).toFixed(1);
    return '<path d="M' + x1 + ' ' + y1 + ' L' + x2 + ' ' + y2 + '" fill="none" stroke="#9aa1ac" stroke-width="1.7"' + (dashed ? ' stroke-dasharray="5 4"' : '') + '/>' +
           '<path d="M' + x2 + ' ' + y2 + ' L' + hx1 + ' ' + hy1 + ' L' + hx2 + ' ' + hy2 + ' Z" fill="#9aa1ac"/>';
  }
  function dagCap(x, y, txt){ return '<text x="' + x + '" y="' + y + '" text-anchor="middle" class="dag-cap">' + txt + '</text>'; }
  function dagWrap(w, h, inner){
    return '<svg class="dag" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMidYMid meet" role="img" aria-label="결합 흐름도">' + inner + '</svg>';
  }

  // ── 모형 적용 유즈케이스(결합 방식) 카드 헬퍼 ──
  function ucModels(arr){
    return '<div class="uc-models">' + arr.map(function(m){
      return '<span class="uc-model ' + m.y + '"><span class="yr">' + m.yr + '</span>' + m.t + '</span>';
    }).join("") + '</div>';
  }
  function ucItems(cls, arr){
    return '<ul class="' + cls + '">' + arr.map(function(s){ return '<li>' + s + '</li>'; }).join("") + '</ul>';
  }
  function ucBlock(c){
    return '<section class="uc-card">' +
      '<div class="uc-title"><span class="uc-num">' + c.n + '</span>' + c.title + '</div>' +
      '<div class="uc-crumb">적용대상 · ' + c.crumb + '</div>' +
      (c.warn ? '<div class="uc-warn">' + c.warn + '</div>' : '') +
      '<div class="uc-sec"><div class="uc-label">행위자 질문 (활동 목적)</div>' + ucItems("uc-q", c.q) + '</div>' +
      '<div class="uc-sec"><div class="uc-label">결합 모형 기능</div>' + ucModels(c.models) + '</div>' +
      '<div class="uc-sec"><div class="uc-label">결합 흐름</div>' + c.dag + '</div>' +
      '<div class="uc-sec"><div class="uc-label">주요 산출물</div>' + ucItems("uc-out", c.out) + '</div>' +
      '<div class="uc-sec"><div class="uc-label">적용 조건 · 한계</div>' + ucItems("uc-cond", c.cond) + '</div>' +
    '</section>';
  }

  // 유즈케이스 1 · 중심지 기반 생활권 도출 + KPI/진단 결합
  var ucDagA = dagWrap(760, 188,
    dagEdge(104,89,130,89) + dagEdge(258,89,284,89) + dagEdge(432,89,458,89) + dagEdge(584,89,618,89) +
    dagEdge(298,142,358,106,true) + dagEdge(494,142,521,106,true) +
    dagNode(14,72,90,"거점지도","data") +
    dagNode(130,72,128,"중심지 추출·위계","center") +
    dagNode(284,72,148,"중심지-생활권 경계","region") +
    dagNode(458,72,126,"KPI·진단 10지표","region") +
    dagNode(618,72,128,"생활권 현황·진단","result") +
    dagNode(246,142,104,"통행행렬","data") +
    dagNode(430,142,128,"격자 인구·시설","data"));

  // 유즈케이스 2 · 현재 생활권 경계 + 장래인구/시설 융합 → 변화 전망
  var ucDagB = dagWrap(760, 178,
    dagEdge(156,41,300,95) + dagEdge(156,95,300,95) + dagEdge(156,149,300,95) +
    dagEdge(470,95,560,95) +
    dagNode(16,24,140,"생활권 경계(현재)","region") +
    dagNode(16,78,140,"장래인구 배분","sim") +
    dagNode(16,132,140,"장래 시설 위치","data") +
    dagNode(300,78,170,"KPI·진단 재산정","region") +
    dagNode(560,78,170,"현재 → 장래 비교","result"));

  // 유즈케이스 3 · 계획반영 장래인구 배분 → 시설 시뮬 → 계획지표
  var ucDagC = dagWrap(760, 166,
    dagEdge(166,41,210,89) + dagEdge(166,137,210,89) +
    dagEdge(370,89,406,89) + dagEdge(556,89,590,89) +
    dagNode(16,24,150,"시군구 장래인구추계","data") +
    dagNode(16,120,150,"개발계획 사업지구","popplan") +
    dagNode(210,72,160,"계획반영 격자배분","popplan") +
    dagNode(406,72,150,"시설 신설·폐지","sim") +
    dagNode(590,72,150,"시설 계획지표","result"));

  // 유즈케이스 4 · 계획반영 장래 사회경제지표 → 중심지 추출 → 장래 중심지
  var ucDagD = dagWrap(760, 100,
    dagEdge(176,57,210,57) + dagEdge(340,57,374,57) + dagEdge(524,57,560,57) +
    dagNode(16,40,160,"장래 사회경제지표","data") +
    dagNode(210,40,130,"계획반영 격자배분","popplan") +
    dagNode(374,40,150,"중심지 추출·위계","center") +
    dagNode(560,40,150,"장래 중심지 분포","result") +
    dagCap(635,90,"현재 대비 차이 비교"));

  var COMB_HTML = [
    '<p class="muted">「모형적용 TF 2차회의 자료」가 정리한 <b>4개 결합 방식(모형 적용 유즈케이스)</b> — 1·2차년도 모형 기능을 결합해 공간계획 업무를 지원하는 시나리오입니다. 각 카드는 <b>적용 업무 ▸ 행위자 질문 → 결합 모형 → 결합 흐름 → 산출물 → 조건·한계</b> 순. DAG 노드 색 = 모형 그룹(파랑 중심지분석 · 초록 생활권 · 보라 시뮬레이션 · 주황 계획반영), 검정 = 최종 산출물.</p>',
    ucBlock({
      n:"1", title:"중심지 기반 생활권 도출 · 특성 진단",
      crumb:"공간 형성 방향 설정 ▸ 생활권 현황 및 진단",
      q:[
        "현 계획권역에서 중심지와의 일상 통행을 고려할 때 생활권은 어떻게 형성되어 있는가?",
        "생활권 간 계층 구조(기초·지역·광역)는 어떠한가?",
        "공간구조 측면에서 생활권들은 어떤 특성을 가지는가?"
      ],
      models:[
        {y:"y2", yr:"2차", t:"중심지-생활권 설정 모형"},
        {y:"y1", yr:"1차", t:"KPI 진단지표"},
        {y:"y2", yr:"2차", t:"생활권 공간구조 진단(10지표)"}
      ],
      dag:ucDagA,
      out:[
        "중심지 분포 지도<small>생활(충족도 마을+거점 20%↑) · 지역(거점 50%↑ &amp; 주거 5천명↑) · 광역(주거·근무 각 5만명↑ &amp; 유입+유출중심성 ≥ 2.0)</small>",
        "중심지-생활권 경계 지도 (기초 · 지역 · 광역 생활권)",
        "생활권별 공간구조 특성 지표 표 및 시각화 결과물"
      ],
      cond:[
        "거점지도 지표 기반 — 적용지역·목적에 맞게 중심지 기준·위계 구분을 사용자가 조정",
        "“정책관심구역 내 인구밀도” 등 일부 지표는 정책관심구역을 사용자가 설정 필요",
        "도로망 기반 이동성 분석 → 섬 지역 등은 바로 적용 어려워 대안적 분석 필요",
        "고밀 단일 중심지는 내부 하위 생활권 세분화 등 추가 분석 필요"
      ]
    }),
    ucBlock({
      n:"2", title:"생활권 공간구조 변화 전망",
      crumb:"지역 여건 진단 및 전망 ▸ 여건 변화 전망",
      q:[
        "장래 인구 변화를 고려할 때 계획권역 내부 생활권의 공간구조는 어떻게 될 것인가?",
        "인구 분산이 심화되고 서비스 이용이 어려워져 관심을 두어야 할 지역은 어디인가?"
      ],
      models:[
        {y:"y2", yr:"2차", t:"중심지-생활권 모형(현재 경계)"},
        {y:"y1", yr:"1차", t:"격자단위 장래인구 배분(현재 추세)"},
        {y:"y1", yr:"1차", t:"KPI 진단지표"},
        {y:"y2", yr:"2차", t:"생활권 공간구조 진단(10지표)"}
      ],
      dag:ucDagB,
      out:[
        "생활권별 공간구조 특성 지표 표 및 시각화 (현재 → 장래)",
        "인구과소지역 비율 지표 시각화 및 관련 변화 지도",
        "중심지 인구 집중도 지표(유형별 분해) 시각화 및 변화 지도"
      ],
      cond:[
        "생활권 경계를 분석으로 도출할 경우 유즈케이스 1의 조건과 동일",
        "사용자가 별도 생활권 경계를 쓸 경우 생활권별 중심지의 공간적 범위 데이터도 필요",
        "장래 데이터를 구득·생산하기 어려운 지표는 전망에 활용 불가"
      ]
    }),
    ucBlock({
      n:"3", title:"장래인구 기반 시설 계획지표 설정",
      crumb:"계획 방향 설정 ▸ 계획 목표지표 설정",
      q:[
        "공공도서관·초등학교 등 공공시설·생활인프라시설의 장래 목표치는 어떻게, 얼마로 설정해야 하는가?"
      ],
      models:[
        {y:"y1", yr:"1차", t:"공간정책 투입모형"},
        {y:"y1", yr:"1차", t:"격자단위 장래인구 배분모형"},
        {y:"y1", yr:"1차", t:"생활여건 변화모형"},
        {y:"y1", yr:"1차", t:"KPI 진단지표"},
        {y:"new", yr:"신규", t:"계획반영 장래인구 배분모형"}
      ],
      dag:ucDagC,
      out:[
        "시나리오별 장래인구 분포 및 변화 지도",
        "시나리오별 장래 시설 위치 및 변화 지도",
        "시나리오별 시설 공급 · 형평성(향유도) 지표 표 및 시각화"
      ],
      cond:[
        "시군구 단위 장래인구 추계치 확보 필요 (개발계획 별도 산출 시도 시군구 단위)",
        "계획반영 시나리오: 사업지구 데이터(경계·계획인구·건설호수)와 신규 시설 위치 데이터 필요",
        "정책관심구역을 사용자가 설정 — 신규 개발지구는 정책관심구역으로 간주",
        "장래 데이터 구득·생산이 어려운 지표는 활용 불가"
      ]
    }),
    ucBlock({
      n:"4", title:"장래 중심지 전망",
      crumb:"공간 형성 방향 설정 ▸ 공간구조 진단 및 전망 (중심지 구조)",
      warn:"※ 본 결합 방식은 실제 구현 가능성과 결과의 유의미성에 대해 추가 테스트가 필요한 것으로 PDF에 명시됨.",
      q:[
        "인구감소·개발계획 등을 고려할 때 장래 시점(목표년도 등)의 중심지는 어디일까?"
      ],
      models:[
        {y:"new", yr:"신규", t:"계획반영 장래 사회경제지표 격자배분"},
        {y:"y2", yr:"2차", t:"중심지 추출 및 위계 설정"}
      ],
      dag:ucDagD,
      out:[
        "장래 중심지 분포 지도",
        "현재 대비 장래 중심지 차이 지도"
      ],
      cond:[
        "개발계획이 반영된 장래 사회경제 지표(인구·종사자수·취업자수)를 미리 확보 필요",
        "거점지도 분석지표 중 근무인구를 종사자 수 지표로 대체 필요",
        "장래 도로망 데이터 확보가 어려워 생활인프라 충족도로 위계 설정 곤란 → 사용자가 격자 장래 지표·추가 정보로 위계 기준 설정"
      ]
    })
  ].join("");

  var DUP_HTML = [
    '<p class="muted">같은(또는 거의 같은) 연산인데 별도 도구로 나뉜 것들. 중복도가 높을수록 통합·재사용 후보입니다.</p>',
    '<table class="dup-table"><thead><tr><th>중복도</th><th>도구 (유사·중복)</th><th>공통 핵심</th><th>차이</th></tr></thead><tbody>',
    '<tr><td><span class="dots d3">●●●</span></td><td><b>장래인구 격자 배분</b> ⟷ <b>인구 격자 배분(3단계)</b></td><td>거점 가중 지수배분(ratio·a·b·c·d)</td><td>후자=개발/비개발 분리 + 사업지구 신규호수</td></tr>',
    '<tr><td><span class="dots d3">●●●</span></td><td><b>관리대상 시설 탐색</b> ⟷ <b>폐업 시뮬레이션</b></td><td>POI 버퍼→배후인구 합산→임계 미만(&lt;) 판정</td><td>시점 컬럼 수(8 vs 4)</td></tr>',
    '<tr><td><span class="dots d2">●●</span></td><td><b>향유도</b> · <b>관리대상</b> · <b>폐업</b></td><td>POI 버퍼 + 격자 중심점 배후인구 합산</td><td>산출물: 비율(향유도) vs 플래그(0/1)</td></tr>',
    '<tr><td><span class="dots d2">●●</span></td><td><b>이동량 행렬</b> → <b>매력도</b></td><td>하위-상위 통행량 집계</td><td>매력도가 출력을 안 쓰고 CSV 재집계</td></tr>',
    '<tr><td><span class="dots d2">●●</span></td><td><b>거리행렬 권역할당</b> ⟷ <b>매력도 상위생활권</b></td><td>최적 중심지 배정 후 dissolve</td><td>기준: 최소비용 vs 매력도</td></tr>',
    '<tr><td><span class="dots d1">●</span></td><td><b>중심지 후보·위계</b> ⟷ <b>정책관심구역</b></td><td>거점/중심지 식별</td><td>버퍼·위계규칙 vs 유형+인프라 충족도</td></tr>',
    '<tr><td><span class="dots d1">●</span></td><td>공간 인덱스 + 격자 중심점 포함 판정</td><td>다수 도구 공통 서브루틴</td><td>도구 중복 아님 — 모듈화 후보</td></tr>',
    '</tbody></table>',
    '<p class="muted" style="margin-top:10px;">● 약함 · ●● 메커니즘/패턴 공유 · ●●● 강한 중복(통합 권장)</p>'
  ].join("");

  function makeModal(title, bodyHtml){
    var m = document.createElement("div");
    m.className = "modal";
    m.setAttribute("hidden", "");
    m.innerHTML =
      '<div class="modal-backdrop" data-close></div>' +
      '<div class="modal-card" role="dialog" aria-modal="true" aria-label="' + title + '">' +
        '<header class="modal-head"><h2>' + title + '</h2>' +
        '<button class="modal-x" type="button" data-close aria-label="닫기">✕</button></header>' +
        '<div class="modal-body">' + bodyHtml + '</div>' +
      '</div>';
    document.body.appendChild(m);
    m.addEventListener("click", function(e){ if(e.target.hasAttribute("data-close")) closeM(m); });
    return m;
  }
  function openM(m){ m.removeAttribute("hidden"); document.body.classList.add("modal-open"); }
  function closeM(m){ m.setAttribute("hidden", ""); document.body.classList.remove("modal-open"); }
  function anyModalOpen(){ return !!document.querySelector(".modal:not([hidden])"); }

  var dupModal = makeModal("중복 · 유사 기능 점검", DUP_HTML);
  var combModal = makeModal("기능 결합 방식 · 모형 적용 유즈케이스", COMB_HTML);
  var dupBtn = document.getElementById("dupBtn");
  var combBtn = document.getElementById("combBtn");
  if(dupBtn) dupBtn.addEventListener("click", function(){ openM(dupModal); });
  if(combBtn) combBtn.addEventListener("click", function(){ openM(combModal); });
  // ── 전체 구조(폴더 트리) 모달 ──
  var KPI_ITEMS = [
    {t:"1. 공간구조 효율성(콤팩트성)", s:"1차년도 효율성 KPI + 2차년도 콤팩트성"},
    {t:"2. 생활서비스 편리성", s:"1차년도 형평성 KPI + 2차년도 생활편리성"},
    {t:"3. 생활서비스 운영 지속가능성", s:"1차년도 운영 지속가능성 KPI"},
    {t:"4. 중심지 연결성", s:"2차년도 네트워크성"}
  ];
  function buildTree(){
    var html = '<div class="tree"><div class="tree-root">KRIHS 공간구조 분석/시뮬레이션</div>';
    var cur = null;
    tools.forEach(function(t, i){
      if(t.group !== cur){
        if(cur !== null) html += '</div>';
        html += '<div class="tree-folder"><div class="tree-folder-label">' + escapeHtml(GROUP_LABELS[t.group] || t.group) + '</div>';
        cur = t.group;
      }
      html += '<button type="button" class="tree-leaf" data-index="' + i + '">' + escapeHtml(t.name) + '</button>';
    });
    if(cur !== null) html += '</div>';
    html += '<div class="tree-folder kpi"><div class="tree-folder-label">06. KPI 진단모형 <span class="tree-soon">구현 예정</span></div>';
    KPI_ITEMS.forEach(function(k){
      html += '<div class="tree-leaf disabled">' + escapeHtml(k.t) + '<small>' + escapeHtml(k.s) + '</small></div>';
    });
    html += '</div></div>';
    return html;
  }
  var treeModal = makeModal("전체 구조 (폴더 트리)", buildTree());
  treeModal.addEventListener("click", function(e){
    var el = e.target;
    while(el && el !== treeModal && !(el.classList && el.classList.contains("tree-leaf"))) el = el.parentNode;
    if(el && el.classList && el.classList.contains("tree-leaf") && el.hasAttribute("data-index")){
      go(Number(el.getAttribute("data-index")));
      closeM(treeModal);
    }
  });
  var treeBtn = document.getElementById("treeBtn");
  if(treeBtn) treeBtn.addEventListener("click", function(){ openM(treeModal); });

  document.addEventListener("keydown", function(e){
    if(e.key === "Escape"){
      Array.prototype.forEach.call(document.querySelectorAll(".modal:not([hidden])"), function(m){ closeM(m); });
    }
  });

  var hash = (location.hash || "").replace("#", "");
  var initialIndex = tools.findIndex(function(tool){ return tool.id === hash; });
  if(initialIndex >= 0) index = initialIndex;
  render();
})();




