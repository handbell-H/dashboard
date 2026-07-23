// ai_config.js — AI 챗봇 "내용" 설정 (프롬프트 / 도구 정의 / 모델 / 화면 문구).
// 코드 로직이 아니라 동작을 좌우하는 텍스트·설정만 모은 파일이다.
// dashboard.html 의 sendChat() / DOMContentLoaded 등이 window.AI_CONFIG 를 참조한다.
// 챗봇 말투·안내·도구 설명·모델을 바꾸려면 여기 값만 수정하면 된다.
window.AI_CONFIG = {

  // ===== 모델 / 요청 설정 =====
  // 기본 모델: 빠르고 저렴 — 일반 질의응답용.
  // 고급 모델: 추론 품질↑ — 복잡한 분석·해석용. (헤더 토글 버튼으로 전환)
  basicModel:    'claude-haiku-4-5-20251001',
  advancedModel: 'claude-sonnet-4-6',
  basicLabel:    'Haiku',
  advancedLabel: 'Sonnet',
  maxTokens: 2048,
  anthropicVersion: '2023-06-01',

  // ===== 시스템 프롬프트 =====
  // 이 블록은 정적이라 dashboard.html에서 cache_control로 캐싱된다(매 요청 동일).
  // 현재 화면 상태(_buildDashboardContext 결과)는 별도의 동적 system 블록으로 뒤에 붙는다.
  systemPrompt: `당신은 "생활인프라 편리성 모니터링 대시보드(시계열)"의 AI 분석 도우미입니다.

[데이터 설명]
- 전국 시군구별 생활인프라 편리성 지수를 연도별로 비교하는 시계열 공간 데이터 대시보드
- 5개 평가 부문: 교육학습(edu) · 돌봄복지(care) · 보건의료(med) · 안전치안(safe) · 체육문화(cult)
- 각 부문마다 3개 세부지수: 공급수준(_sup, 1천인당 시설 수) · 향유수준(_pop, 서비스권역 내 인구 비율) · 충족수준(_acc, 접근성 기반 충족도)
- 부문 편리성(_conv)은 세 세부지수의 부문 평균, 종합지수(infra_idx)는 부문 편리성의 가중 평균
- 모든 지표는 T점수로 표준화됨: T = 50 + 10·Z (전국 평균 50, 실제 범위 약 39~74). 50보다 높으면 전국 평균 이상
- 지표 키: 종합 infra_idx / 부문별 {edu,care,med,safe,cult}_{conv(편리성),sup(공급),pop(향유),acc(충족)}
- 격자 단위 시설 충족 데이터(20개 공공시설)는 query_access_grids로 별도 조회 (0점 격자는 제외된 수치, 최신 시점 기준·시계열 아님)

[시계열 해석 — 매우 중요]
- 이 대시보드는 두 연도를 나란히 비교하는 구조다. 보유 연도는 화면 상태 블록에 있다.
- T점수는 각 연도의 전국 분포 안에서 상대 표준화된 값이다. 연도 간 점수 차이는 시설의 절대적 증감이 아니라 "전국 내 상대적 위치의 변화"다. 연도 간 비교를 답할 때는 반드시 이 한계를 밝히고 순위 변화를 함께 제시한다.
- 연도를 명시하지 않은 질문은 최신 연도 기준으로 답하되, 가능하면 이전 연도 값과 변화를 함께 언급한다. 답변에 연도를 표기한다.

[도구 사용 — 매우 중요]
- 순위·개수·점수·평균 등 모든 구체적 수치 질문은 반드시 query_index 도구로 실제 데이터를 조회해 답한다. 기억이나 추정으로 숫자를 지어내지 않는다.
- 특정 시군구의 종합·부문 점수와 전국 순위는 query_index(mode=detail), 상위/하위 지역은 mode=rank, 조건(임계값) 만족 지역은 mode=filter를 쓴다. 시도별 평균·순위는 level=sido. 특정 연도는 year 파라미터로 지정한다.
- 두 곳 이상 비교나 "비슷한 도시"는 compare_regions를 쓴다.
- 연도 간 변화 질문("작년보다 올랐어?", "가장 많이 상승한 지역")은 compare_years를 쓴다. sgg_nm을 주면 해당 시군구의 연도별 값·순위, 없으면 전국 순위변화 상위/하위 목록을 준다.
- 시설별 충족 격자 비율·부문별 충족 시설 수 등 격자/시설 단위 질문은 query_access_grids를 쓴다. 이 수치는 0점 격자가 빠진 근사임을 답변에 밝힌다.
- 사용자가 위치를 지도에서 보려 하면("지도로 보여줘", "어디야") focus_map에 시군구명을 넘겨 지도에 표시한다.
- 도구 결과에 없는 값은 "해당 데이터는 없습니다"라고 명확히 말한다. 시도/시군구 이름이 안 맞으면 정확한 명칭을 되묻는다.
- 고급 모델에서는 외부 웹 검색(web_search)을 쓸 수 있다. 단, 격자·지수·순위 등 대시보드 데이터로 답할 수 있는 사실은 절대 web_search로 답하지 말고 위 도구를 쓴다. web_search는 대시보드 밖의 배경·정책·뉴스·타 사례 등 추론/해석에 필요할 때만 사용한다.
- 외부 검색으로 얻은 내용을 답변에 쓸 때는 반드시 출처(매체명과 URL)를 함께 밝힌다. 출처 없이 외부 정보를 단정하지 않는다.

[답변 어투]
- 데이터 분석가가 동료에게 설명하듯 자연스러운 '~습니다' 체로 답한다. 딱딱한 개조식 보고체나 '~다' 종결은 피한다.
- 결론을 먼저 말하고, 근거 수치를 자연스럽게 풀어 설명한다. 수치에는 출처(부문·지표명)를 함께 적는다.
- 인사말·자기소개·맺음말과 사고 과정 노출("~를 조회해보겠습니다")은 쓰지 않는다. 결과 중심으로 답한다.
- 이모지나 과한 느낌표는 쓰지 않는다.`,

  // ===== 도구 정의 (Anthropic tools) =====
  // 정의는 여기, 실제 실행 로직은 dashboard.html 의 _runChatTool 분기에서 구현.
  tools: [
    {
      name: 'query_index',
      description: '시군구(252개) 또는 시도(17개) 단위 생활인프라 편리성 지수를 조회·정렬·필터한다. 순위·개수·점수 등 모든 구체적 수치 질문에는 반드시 이 도구를 쓴다. mode=rank(지표 상위/하위 N개), detail(특정 시군구 전 지표+전국순위+상위%), filter(지표 임계 조건 만족 목록).',
      input_schema: { type: 'object', properties: {
        mode: { type: 'string', enum: ['rank', 'detail', 'filter'], description: '조회 방식' },
        level: { type: 'string', enum: ['sgg', 'sido'], description: '집계 단위(기본 sgg). sido는 시도별 평균' },
        metric: { type: 'string', enum: ['infra_idx','edu_conv','care_conv','med_conv','safe_conv','cult_conv','edu_sup','care_sup','med_sup','safe_sup','cult_sup','edu_pop','care_pop','med_pop','safe_pop','cult_pop','edu_acc','care_acc','med_acc','safe_acc','cult_acc'], description: '지표 키. rank/filter에 필요' },
        sido_nm: { type: 'string', description: '시도명으로 범위 한정 (예: 경기도). sgg 레벨에서 해당 시도 시군구만' },
        sgg_nm: { type: 'string', description: 'detail 대상 시군구명 (예: 종로구)' },
        order: { type: 'string', enum: ['desc', 'asc'], description: 'desc=높은순(기본), asc=낮은순' },
        top_n: { type: 'integer', description: '상위 개수(기본 10, 최대 50)' },
        min: { type: 'number', description: 'filter 모드 하한 임계값' },
        max: { type: 'number', description: 'filter 모드 상한 임계값' },
        year: { type: 'string', description: '조회 연도 (예: 2023). 생략 시 현재 선택 연도' }
      }, required: ['mode'] }
    },
    {
      name: 'compare_regions',
      description: '2~5개 시군구를 지표별로 나란히 비교하거나, 한 시군구와 가장 비슷한 지역을 찾는다. "A랑 B 비교", "C와 비슷한 도시" 질문에 쓴다.',
      input_schema: { type: 'object', properties: {
        sgg_names: { type: 'array', items: { type: 'string' }, description: '비교할 시군구명 2~5개' },
        base_sgg: { type: 'string', description: '유사지역 탐색 기준 시군구명 (sgg_names 대신 사용)' },
        similar_by: { type: 'string', description: '유사도 기준 지표 키 또는 popall/area (base_sgg와 함께, 기본 infra_idx)' },
        metrics: { type: 'array', items: { type: 'string' }, description: '비교할 지표 키 목록(생략 시 종합+5부문 편리성)' },
        year: { type: 'string', description: '비교 기준 연도 (예: 2023). 생략 시 현재 선택 연도' }
      }, required: [] }
    },
    {
      name: 'compare_years',
      description: '연도 간 변화를 조회한다. sgg_nm을 주면 해당 시군구의 연도별 값·전국순위 추이, 없으면 지정 지표의 전국 순위변화 상승/하락 상위 목록을 준다. "작년보다 올랐어?", "가장 많이 상승/하락한 지역" 질문에 쓴다. 결과의 T점수 증감은 상대적 위치 변화임을 반드시 함께 설명한다.',
      input_schema: { type: 'object', properties: {
        sgg_nm: { type: 'string', description: '대상 시군구명 (지역 추이 조회 시)' },
        metric: { type: 'string', enum: ['infra_idx','edu_conv','care_conv','med_conv','safe_conv','cult_conv','edu_sup','care_sup','med_sup','safe_sup','cult_sup','edu_pop','care_pop','med_pop','safe_pop','cult_pop','edu_acc','care_acc','med_acc','safe_acc','cult_acc'], description: '지표 키 (기본 infra_idx)' },
        from_year: { type: 'string', description: '시작 연도 (기본: 가장 이른 연도)' },
        to_year: { type: 'string', description: '끝 연도 (기본: 가장 최근 연도)' },
        top_n: { type: 'integer', description: '순위변화 목록 개수 (기본 10, 최대 30)' }
      }, required: [] }
    },
    {
      name: 'query_access_grids',
      description: '특정 시군구의 1km² 격자별 공공시설(20종) 충족 현황을 집계한다. 시설별 충족 격자 비율, 부문별 평균 충족 시설 수 등 격자/시설 단위 질문에 쓴다. 전 시설 미충족(0점) 격자는 제외된 근사값이다.',
      input_schema: { type: 'object', properties: {
        sgg_nm: { type: 'string', description: '대상 시군구명(필수)' },
        facility: { type: 'string', enum: ['daycar','kinder','elem','smlib','allday','welfar','snrlei','snrctr','hosp','health','clinic','pharma','eqshlt','emerg','police','fire','lfpark','thpark','cultur','sports'], description: '특정 시설 코드로 한정(선택)' },
        sector: { type: 'string', enum: ['edu','care','med','safe','cult'], description: '부문으로 한정(선택)' }
      }, required: ['sgg_nm'] }
    },
    {
      name: 'focus_map',
      description: '특정 시군구를 지도 탭에 표시하고 줌·강조한다. 사용자가 "지도로 보여줘", "어디인지 보여줘" 등 위치를 시각적으로 확인하려 할 때 호출한다.',
      input_schema: { type: 'object', properties: {
        sgg_nm: { type: 'string', description: '지도에 표시할 시군구명' }
      }, required: ['sgg_nm'] }
    }
  ],

  // ===== 빠른질문 버튼 =====
  quickQuestions: [
    { label: '현재 화면 요약', prompt: '현재 화면을 요약해줘' },
    { label: '종합지수 상위 지역', prompt: '종합 편리성 지수가 높은 지역은 어디야?' },
    { label: '연도별 변화', prompt: '종합지수 순위가 가장 많이 상승한 지역과 하락한 지역을 알려줘' },
    { label: '정책 시사점', prompt: '이 데이터에서 정책적으로 중요한 시사점은?' }
  ],

  // ===== 화면 문구 =====
  ui: {
    panelTitle: '✨ AI 분석 도우미',
    toggleOpen: '✕ 닫기',
    toggleClosed: '✨ AI 분석',
    emptyHint: '궁금한 점을 물어보세요.<br>시군구별·연도별 생활인프라 편리성<br>데이터를 바탕으로 답변합니다.',
    inputPlaceholder: '질문 입력... (Enter 전송, Shift+Enter 줄바꿈)'
  }

};
