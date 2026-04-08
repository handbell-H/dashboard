# 생활인프라 종합 모니터링 대시보드 v3

v2 대비 종합지수 산출 방식 및 세부지수 표준화 방법을 개선한 버전입니다.

🔗 **[대시보드 바로 보기](https://handbell-h.github.io/dashboard/monitoring_living_infra_total_dashboard_v3/dashboard.html)**

---

## 프로젝트 구조

```
monitoring_living_infra_total_dashboard_v3/
├── dashboard.html        # 메인 대시보드 (데이터 내장 단일 파일)
├── build.py              # 데이터 → 대시보드 빌드 스크립트
└── README.md
```

데이터는 상위 폴더의 `../data/`를 참조합니다.  
`dashboard.html`은 모든 데이터가 내장된 독립 실행 파일입니다.

---

## v2 대비 변경사항

| 항목 | 내용 |
|------|------|
| 종합지수 산출 방식 | 0~100 리스케일 → **부문별 T점수 편리성 지수의 가중 평균** (전국 평균 ≈ 50, 실제 범위 39~74) |
| 세부지수 표준화 | minmax (0~1) → **T점수** (mean ≈ 50 기준, 상대적 위치 직관적 해석 가능) |
| 종합지수 색상 범위 | 고정 0~100 → **데이터 실제 범위 기반 동적 색상** |
| 소수점 표기 통일 | 지수별 혼용 → **전 항목 소수점 1자리** 통일 |

### 종합지수 산출 방식 변경 배경

기존 0~100 리스케일은 전국 최저/최고 지역에 의존하는 수치로, 중간 지역의 차이가 희석되어 해석이 어려웠습니다.  
T점수 기반 평균은 전국 평균을 50으로 고정해 **각 지역이 전국 대비 어느 위치인지 직관적으로 파악**할 수 있습니다.

---

## 빌드 방법

```bash
cd monitoring_living_infra_total_dashboard_v3
python build.py
```

출력: `dashboard.html` (브라우저에서 바로 열 수 있는 단일 파일)
