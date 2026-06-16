const CSV_PATH = "./nec_0020260603_local_vccp08_long.csv";
const CSV_GZ_PATH = `${CSV_PATH}.gz`;
const REQUIRED_COLUMNS = [
  "election_id",
  "election_code",
  "election_name",
  "city_code",
  "city_name",
  "sgg_city_code",
  "sgg_city_name",
  "town_code",
  "town_name",
  "sgg_town_code",
  "sgg_town_name",
  "statement_id",
  "table_row_index",
  "읍면동명",
  "투표구명",
  "선거인수",
  "투표수",
  "후보순번",
  "정당명",
  "후보자명",
  "후보자표기",
  "득표수",
  "후보자별 득표수_계",
  "무효 투표수",
  "기권자수",
];

const initialParams = new URLSearchParams(window.location.search);

const state = {
  rawRows: 0,
  records: [],
  headers: [],
  sourceName: "",
  includeExcluded: initialParams.get("includeExcluded") === "1",
  lastAnalysis: null,
};

const els = {
  loadStatus: document.getElementById("loadStatus"),
  rowCount: document.getElementById("rowCount"),
  regionCount: document.getElementById("regionCount"),
  candidateStatus: document.getElementById("candidateStatus"),
  csvFile: document.getElementById("csvFile"),
  reloadBtn: document.getElementById("reloadBtn"),
  typeSelect: document.getElementById("typeSelect"),
  voteCategorySelect: document.getElementById("voteCategorySelect"),
  turnoutLevelSelect: document.getElementById("turnoutLevelSelect"),
  minVotes: document.getElementById("minVotes"),
  includeExcludedBtn: document.getElementById("includeExcludedBtn"),
  sameVotesBtn: document.getElementById("sameVotesBtn"),
  sameRatioBtn: document.getElementById("sameRatioBtn"),
  benfordBtn: document.getElementById("benfordBtn"),
  earlyTurnoutBtn: document.getElementById("earlyTurnoutBtn"),
  summaryPanel: document.getElementById("summaryPanel"),
  resultPanel: document.getElementById("resultPanel"),
  emptyTemplate: document.getElementById("emptyTemplate"),
};

const numberFormatter = new Intl.NumberFormat("ko-KR");
const percentFormatter = new Intl.NumberFormat("ko-KR", {
  style: "percent",
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
});

function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = "";
  let quoted = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (quoted) {
      if (char === '"' && next === '"') {
        value += '"';
        i += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        value += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(value);
      value = "";
    } else if (char === "\n") {
      row.push(value);
      rows.push(row);
      row = [];
      value = "";
    } else if (char !== "\r") {
      value += char;
    }
  }

  if (value.length || row.length) {
    row.push(value);
    rows.push(row);
  }

  return rows.filter((items) => items.some((item) => item.trim() !== ""));
}

function toNumber(value) {
  if (value === undefined || value === null || value === "") return 0;
  const numeric = Number(String(value).replaceAll(",", "").trim());
  return Number.isFinite(numeric) ? numeric : 0;
}

function validateHeaders(headers) {
  const missing = REQUIRED_COLUMNS.filter((column) => !headers.includes(column));
  if (missing.length) {
    throw new Error(`필수 컬럼이 없습니다: ${missing.join(", ")}`);
  }
}

function rowsFromCsv(text) {
  const table = parseCsv(text.replace(/^\ufeff/, ""));
  if (table.length < 2) throw new Error("CSV 데이터 행이 없습니다.");

  const headers = table[0].map((header) => header.trim());
  validateHeaders(headers);

  const headerIndex = new Map(headers.map((header, index) => [header, index]));
  const read = (cells, column) => cells[headerIndex.get(column)] ?? "";
  const grouped = new Map();

  for (let index = 1; index < table.length; index += 1) {
    const cells = table[index];
    const keyParts = [
      read(cells, "election_code"),
      read(cells, "city_code"),
      read(cells, "sgg_city_code"),
      read(cells, "town_code"),
      read(cells, "sgg_town_code"),
      read(cells, "statement_id"),
      read(cells, "table_row_index"),
      read(cells, "읍면동명"),
      read(cells, "투표구명"),
    ];
    const key = keyParts.join("|");
    let record = grouped.get(key);

    if (!record) {
      record = {
        key,
        electionId: read(cells, "election_id"),
        electionCode: read(cells, "election_code"),
        electionName: read(cells, "election_name"),
        cityCode: read(cells, "city_code"),
        cityName: read(cells, "city_name"),
        sggCityCode: read(cells, "sgg_city_code"),
        sggCityName: read(cells, "sgg_city_name"),
        townCode: read(cells, "town_code"),
        townName: read(cells, "town_name"),
        sggTownCode: read(cells, "sgg_town_code"),
        sggTownName: read(cells, "sgg_town_name"),
        statementId: read(cells, "statement_id"),
        tableRowIndex: read(cells, "table_row_index"),
        dongName: read(cells, "읍면동명"),
        precinctName: read(cells, "투표구명"),
        electors: toNumber(read(cells, "선거인수")),
        turnoutVotes: toNumber(read(cells, "투표수")),
        validVotes: toNumber(read(cells, "후보자별 득표수_계")),
        invalidVotes: toNumber(read(cells, "무효 투표수")),
        abstentions: toNumber(read(cells, "기권자수")),
        candidates: [],
      };
      grouped.set(key, record);
    }

    record.candidates.push({
      order: toNumber(read(cells, "후보순번")),
      party: read(cells, "정당명"),
      name: read(cells, "후보자명"),
      label: read(cells, "후보자표기") || read(cells, "정당명") || read(cells, "후보자명"),
      votes: toNumber(read(cells, "득표수")),
    });
  }

  const records = [...grouped.values()].map((record) => finalizeRecord(record));
  return { headers, rawRows: table.length - 1, records };
}

function finalizeRecord(record) {
  record.candidates.sort((a, b) => a.order - b.order || a.label.localeCompare(b.label, "ko"));
  record.first = record.candidates[0] || null;
  record.second = record.candidates[1] || null;
  record.contestKey = contestKey(record);
  record.contestLabel = districtLabel(record);
  record.regionLabel = regionLabel(record);
  record.candidatePair = record.first && record.second ? `${record.first.label} / ${record.second.label}` : "후보 2명 미만";
  record.firstRatio = record.validVotes > 0 && record.first ? (record.first.votes / record.validVotes) * 100 : null;
  record.secondRatio = record.validVotes > 0 && record.second ? (record.second.votes / record.validVotes) * 100 : null;
  record.voteCategory = voteCategory(record);
  return record;
}

const CITYWIDE_CONTESTS = new Set(["시·도지사선거", "교육감선거", "광역의원비례대표선거"]);
const DISTRICT_CONTESTS = new Set(["시·도의회의원선거", "구·시·군의회의원선거", "국회의원선거"]);

function contestKey(record) {
  if (CITYWIDE_CONTESTS.has(record.electionName)) {
    // 선거구가 시·도 전체인 선거: 자치구로 쪼개지 않는다.
    return [record.electionCode, record.cityCode].join("|");
  }
  if (DISTRICT_CONTESTS.has(record.electionName)) {
    // 지역구 의원: 선거구코드(sgg)까지로 식별한다.
    return [record.electionCode, record.cityCode, record.townCode, record.sggCityCode, record.sggTownCode].join("|");
  }
  // 구·시·군의 장, 기초의원 비례: 시·군·구 단위.
  return [record.electionCode, record.cityCode, record.townCode].join("|");
}

function voteCategory(record) {
  if (record.dongName === "합계") return "최종결과";
  if (record.dongName === "관외사전투표" || record.dongName === "거소투표" || record.precinctName === "관내사전투표") {
    return "사전투표";
  }
  return "본투표";
}

function compactParts(parts) {
  const result = [];
  for (const part of parts) {
    if (!part || part === "-1") continue;
    if (result[result.length - 1] !== part) result.push(part);
  }
  return result;
}

function districtLabel(record) {
  return compactParts([
    record.cityName,
    record.sggCityName,
    record.townName,
    record.sggTownName,
  ]).join(" ");
}

function regionLabel(record) {
  return compactParts([
    districtLabel(record),
    record.dongName,
    record.precinctName,
  ]).join(" ");
}

async function loadDefaultCsv() {
  setStatus("2026 지방선거 데이터 로드 중...");
  const text = await fetchDefaultCsvText();
  loadCsvText(text, "기본 CSV");
}

async function fetchDefaultCsvText() {
  // 용량이 작은 압축본(.gz)을 우선 시도하고, 없으면 원본 CSV로 폴백한다.
  if (typeof DecompressionStream === "function") {
    const gz = await fetch(`${CSV_GZ_PATH}?t=${Date.now()}`, { cache: "no-store" });
    if (gz.ok && gz.body) {
      const stream = gz.body.pipeThrough(new DecompressionStream("gzip"));
      return new Response(stream).text();
    }
  }
  const response = await fetch(`${CSV_PATH}?t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`데이터를 불러오지 못했습니다. HTTP ${response.status}`);
  return response.text();
}

function loadCsvText(text, sourceName) {
  const parsed = rowsFromCsv(text);
  state.rawRows = parsed.rawRows;
  state.records = parsed.records;
  state.headers = parsed.headers;
  state.sourceName = sourceName;
  fillTypeOptions();
  updateStatus();
  renderIntro();
  runFromUrl();
}

function fillTypeOptions() {
  const counts = new Map();
  for (const row of state.records) {
    counts.set(row.electionName, (counts.get(row.electionName) || 0) + 1);
  }

  const options = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"));
  els.typeSelect.innerHTML = `<option value="__ALL__">전체 선거유형</option>`;
  for (const [type, count] of options) {
    const option = document.createElement("option");
    option.value = type;
    option.textContent = `${type} (${numberFormatter.format(count)})`;
    els.typeSelect.appendChild(option);
  }
}

function setStatus(text) {
  els.loadStatus.textContent = text;
}

function updateStatus() {
  const candidatePairs = new Set(state.records.map((row) => `${row.electionName}|${row.candidatePair}`)).size;
  els.loadStatus.textContent = `${state.sourceName} 로드 완료`;
  els.rowCount.textContent = numberFormatter.format(state.rawRows);
  els.regionCount.textContent = numberFormatter.format(state.records.length);
  els.candidateStatus.textContent = numberFormatter.format(candidatePairs);
}

function setBusy(isBusy) {
  [els.sameVotesBtn, els.sameRatioBtn, els.benfordBtn, els.earlyTurnoutBtn, els.reloadBtn, els.includeExcludedBtn].forEach((button) => {
    button.disabled = isBusy;
  });
}

function filteredRows() {
  const selectedType = els.typeSelect.value;
  const selectedCategory = els.voteCategorySelect.value;
  const minVotes = Math.max(0, toNumber(els.minVotes.value));

  return state.records.filter((row) => {
    if (!row.first || !row.second) return false;
    if (!state.includeExcluded && isDefaultExcluded(row)) return false;
    if (row.turnoutVotes < minVotes) return false;
    if (selectedType !== "__ALL__" && row.electionName !== selectedType) return false;
    if (selectedCategory !== "__ALL__" && row.voteCategory !== selectedCategory) return false;
    return true;
  });
}

function isDefaultExcluded(row) {
  return (
    row.dongName === "잘못 투입·구분된 투표지" ||
    row.precinctName === "계" ||
    row.precinctName === "선거일투표"
  );
}

function excludedModeLabel() {
  return state.includeExcluded ? "해제·포함" : "적용";
}

function updateExcludedButton() {
  els.includeExcludedBtn.setAttribute("aria-pressed", String(state.includeExcluded));
  els.includeExcludedBtn.textContent = state.includeExcluded ? "제외 항목 보기: 켜짐" : "제외 항목 보기: 꺼짐";
  els.includeExcludedBtn.classList.toggle("active", state.includeExcluded);
}

function maxDisplayRows() {
  return Number.MAX_SAFE_INTEGER;
}

function sameVotesAnalysis() {
  const rows = filteredRows();
  const groups = groupDuplicates(rows, (row) =>
    [
      row.electionName,
      row.contestKey,
      row.voteCategory,
      row.first.label,
      row.second.label,
      row.first.votes,
      row.second.votes,
    ].join("|"),
  );

  renderSummary([
    { label: "분석 개표단위", value: numberFormatter.format(rows.length) },
    { label: "같은 결과 묶음", value: numberFormatter.format(groups.length) },
    { label: "묶인 지역", value: numberFormatter.format(groups.reduce((sum, item) => sum + item.rows.length, 0)) },
    { label: "기본 제외", value: excludedModeLabel() },
  ]);

  if (!groups.length) {
    renderEmpty("동일 투표수 지역 추출", rows.length);
    return;
  }

  renderSameVotesCards(groups);
}

function sameRatioAnalysis() {
  const rows = filteredRows().filter((row) => row.validVotes > 0 && row.firstRatio !== null && row.secondRatio !== null);
  const groups = groupDuplicates(rows, (row) =>
    [
      row.electionName,
      row.contestKey,
      row.voteCategory,
      row.first.label,
      row.second.label,
      row.firstRatio.toFixed(3),
      row.secondRatio.toFixed(3),
    ].join("|"),
  );

  renderSummary([
    { label: "분석 개표단위", value: numberFormatter.format(rows.length) },
    { label: "같은 비율 묶음", value: numberFormatter.format(groups.length) },
    { label: "묶인 지역", value: numberFormatter.format(groups.reduce((sum, item) => sum + item.rows.length, 0)) },
    { label: "기본 제외", value: excludedModeLabel() },
  ]);

  if (!groups.length) {
    renderEmpty("동일 비율 지역 추출", rows.length);
    return;
  }

  renderSameRatioCards(groups);
}

function groupDuplicates(rows, keyFn) {
  const grouped = groupBy(rows, keyFn);
  return [...grouped.values()]
    .filter((group) => group.length >= 2)
    .map((group) => ({ rows: group, sample: group[0] }))
    .sort((a, b) => b.rows.length - a.rows.length || b.sample.turnoutVotes - a.sample.turnoutVotes);
}

function groupBy(values, keyFn) {
  const grouped = new Map();
  for (const value of values) {
    const key = keyFn(value);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(value);
  }
  return grouped;
}

function renderSameVotesCards(groups) {
  const display = groups.slice(0, maxDisplayRows());
  els.resultPanel.innerHTML = `
    <div class="panelHead">
      <div>
        <h2>동일 투표수 지역 추출</h2>
        <p>각 카드는 같은 선거구·같은 투표 구분·같은 1후보와 2후보에서 두 후보 득표수가 모두 똑같이 나온 지역 묶음입니다.</p>
      </div>
      <span class="badge">${numberFormatter.format(groups.length)}묶음</span>
    </div>
    <div class="readGuide">
      <b>읽는 순서</b>
      <span>1. 반복 지역 수가 큰 카드부터 봅니다.</span>
      <span>2. 가운데의 같은 결과가 여러 지역에서 그대로 반복됐다는 뜻입니다.</span>
      <span>3. v2는 서로 다른 선거구의 같은 숫자를 한 묶음으로 합치지 않습니다.</span>
      <span>4. 아래 지역 목록은 그 득표쌍이 나온 실제 개표단위입니다.</span>
      <span>5. 기본값은 잘못 투입·구분된 투표지, 계, 선거일투표를 제외합니다.</span>
      <span>6. 제외 항목 보기 버튼을 켜면 숨긴 목록까지 다시 계산합니다.</span>
    </div>
    <div class="sameVoteList">
      ${display.map((item, index) => renderSameVoteCard(item, index)).join("")}
    </div>
  `;
}

function renderSameVoteCard(item, index) {
  const sample = item.sample;
  return `
    <article class="sameVoteCard">
      <div class="sameVoteCardHead">
        <div>
          <span class="cardIndex">같은 결과 ${numberFormatter.format(index + 1)}</span>
          <h3>${escapeHtml(sample.electionName)} · ${escapeHtml(sample.contestLabel)} · ${escapeHtml(sample.voteCategory)}</h3>
        </div>
        <strong>${numberFormatter.format(item.rows.length)}곳</strong>
      </div>
      <div class="sameResult">
        <div>
          <span>1후보</span>
          <b>${escapeHtml(sample.first.label)}</b>
          <strong>${numberFormatter.format(sample.first.votes)}표</strong>
        </div>
        <div>
          <span>2후보</span>
          <b>${escapeHtml(sample.second.label)}</b>
          <strong>${numberFormatter.format(sample.second.votes)}표</strong>
        </div>
      </div>
      <p class="plainMeaning">
        아래 ${numberFormatter.format(item.rows.length)}곳에서 1후보는 ${numberFormatter.format(sample.first.votes)}표,
        2후보는 ${numberFormatter.format(sample.second.votes)}표로 똑같이 나왔습니다.
      </p>
      <div class="regionList">
        ${item.rows
          .slice(0, 16)
          .map((row) => `<span>${escapeHtml(row.regionLabel)}</span>`)
          .join("")}
        ${item.rows.length > 16 ? `<em>외 ${numberFormatter.format(item.rows.length - 16)}곳</em>` : ""}
      </div>
    </article>
  `;
}

function renderSameRatioCards(groups) {
  const display = groups.slice(0, maxDisplayRows());
  els.resultPanel.innerHTML = `
    <div class="panelHead">
      <div>
        <h2>동일 비율 지역 추출</h2>
        <p>각 카드는 같은 선거구·같은 투표 구분·같은 1후보와 2후보에서 두 후보 득표율이 소수점 3자리까지 똑같이 나온 지역 묶음입니다.</p>
      </div>
      <span class="badge">${numberFormatter.format(groups.length)}묶음</span>
    </div>
    <div class="readGuide">
      <b>읽는 순서</b>
      <span>1. 반복 지역 수가 큰 카드부터 봅니다.</span>
      <span>2. 가운데의 같은 비율이 여러 지역에서 반복됐다는 뜻입니다.</span>
      <span>3. v2는 서로 다른 선거구의 같은 비율을 한 묶음으로 합치지 않습니다.</span>
      <span>4. 비율은 유효표 대비 득표율을 소수점 3자리까지 비교합니다.</span>
      <span>5. 기본값은 잘못 투입·구분된 투표지, 계, 선거일투표를 제외합니다.</span>
    </div>
    <div class="sameVoteList">
      ${display.map((item, index) => renderSameRatioCard(item, index)).join("")}
    </div>
  `;
}

function renderSameRatioCard(item, index) {
  const sample = item.sample;
  return `
    <article class="sameVoteCard">
      <div class="sameVoteCardHead">
        <div>
          <span class="cardIndex">같은 비율 ${numberFormatter.format(index + 1)}</span>
          <h3>${escapeHtml(sample.electionName)} · ${escapeHtml(sample.contestLabel)} · ${escapeHtml(sample.voteCategory)}</h3>
        </div>
        <strong>${numberFormatter.format(item.rows.length)}곳</strong>
      </div>
      <div class="sameResult">
        <div>
          <span>1후보</span>
          <b>${escapeHtml(sample.first.label)}</b>
          <strong>${sample.firstRatio.toFixed(3)}%</strong>
        </div>
        <div>
          <span>2후보</span>
          <b>${escapeHtml(sample.second.label)}</b>
          <strong>${sample.secondRatio.toFixed(3)}%</strong>
        </div>
      </div>
      <p class="plainMeaning">
        아래 ${numberFormatter.format(item.rows.length)}곳에서 1후보 비율은 ${sample.firstRatio.toFixed(3)}%,
        2후보 비율은 ${sample.secondRatio.toFixed(3)}%로 똑같이 나왔습니다.
      </p>
      <div class="regionList">
        ${item.rows
          .slice(0, 16)
          .map((row) => `<span>${escapeHtml(row.regionLabel)} · 유효표 ${numberFormatter.format(row.validVotes)}</span>`)
          .join("")}
        ${item.rows.length > 16 ? `<em>외 ${numberFormatter.format(item.rows.length - 16)}곳</em>` : ""}
      </div>
    </article>
  `;
}

function sampleRegions(rows) {
  const visible = rows.slice(0, 10).map((row) => row.regionLabel);
  const suffix = rows.length > visible.length ? ` 외 ${numberFormatter.format(rows.length - visible.length)}곳` : "";
  return `${visible.join(" / ")}${suffix}`;
}

function benfordAnalysis() {
  const rows = filteredRows();
  // 전체 선거유형은 규모가 다른 선거를 섞으면 분포가 무너지므로 유형별로 나눠 계산한다.
  const series = els.typeSelect.value === "__ALL__" ? benfordSeriesByType(rows) : benfordSeriesByRole(rows);

  const sampleTotal = series.reduce((sum, item) => sum + item.result.total, 0);
  const worst = series.length ? Math.max(...series.map((item) => item.result.chiSquare)) : 0;
  const status = worst > 20.09 ? "검토 필요" : worst > 15.51 ? "주의" : "기준 내";

  renderSummary([
    { label: "분석 개표단위", value: numberFormatter.format(rows.length) },
    { label: "전체 표본", value: numberFormatter.format(sampleTotal) },
    { label: "최대 카이제곱", value: worst.toFixed(2) },
    { label: "기본 제외", value: excludedModeLabel() },
  ]);
  renderBenford(series, status);
}

function benfordSeriesByRole(rows) {
  const allCandidateVotes = [];
  const firstVotes = [];
  const secondVotes = [];

  for (const row of rows) {
    for (const candidate of row.candidates) {
      if (candidate.votes > 0) allCandidateVotes.push(candidate.votes);
    }
    if (row.first?.votes > 0) firstVotes.push(row.first.votes);
    if (row.second?.votes > 0) secondVotes.push(row.second.votes);
  }

  return [
    { label: "전체 후보·정당 득표수", result: benfordResult(allCandidateVotes) },
    { label: "1후보 득표수", result: benfordResult(firstVotes) },
    { label: "2후보 득표수", result: benfordResult(secondVotes) },
  ];
}

function benfordSeriesByType(rows) {
  return [...groupBy(rows, (row) => row.electionName).entries()]
    .map(([name, typeRows]) => {
      const votes = [];
      for (const row of typeRows) {
        for (const candidate of row.candidates) {
          if (candidate.votes > 0) votes.push(candidate.votes);
        }
      }
      return { label: name, result: benfordResult(votes) };
    })
    .sort((a, b) => b.result.chiSquare - a.result.chiSquare);
}

function benfordResult(values) {
  const counts = Object.fromEntries(Array.from({ length: 9 }, (_, i) => [String(i + 1), 0]));
  for (const value of values) {
    const firstDigit = String(Math.abs(value)).replace(/^0+/, "")[0];
    if (counts[firstDigit] !== undefined) counts[firstDigit] += 1;
  }

  const total = values.length;
  const expected = {};
  let chiSquare = 0;
  for (let digit = 1; digit <= 9; digit += 1) {
    expected[digit] = Math.log10(1 + 1 / digit);
    const expectedCount = expected[digit] * total;
    if (expectedCount > 0) {
      chiSquare += (counts[digit] - expectedCount) ** 2 / expectedCount;
    }
  }
  return { counts, expected, total, chiSquare };
}

function renderBenford(series, status) {
  const badgeClass = status === "기준 내" ? "" : status === "주의" ? "warn" : "bad";
  els.resultPanel.innerHTML = `
    <div class="panelHead">
      <div>
        <h2>벤포드 법칙 점검</h2>
        <p>첫 자리 숫자 분포를 벤포드 기대분포와 비교했습니다. 선거 데이터는 행정구역 규모와 후보 수의 영향을 받기 때문에 편차는 추가 검토 신호로만 보아야 합니다.</p>
      </div>
      <span class="badge ${badgeClass}">${escapeHtml(status)}</span>
    </div>
    <div class="benfordGrid">
      ${series.map(renderBenfordCard).join("")}
    </div>
  `;
}

function renderBenfordCard(item) {
  const { counts, expected, total, chiSquare } = item.result;
  const verdict = chiSquare > 20.09 ? "검토 필요" : chiSquare > 15.51 ? "주의" : "기준 내";
  return `
    <div class="miniCard">
      <h3>${escapeHtml(item.label)} · ${escapeHtml(verdict)} · χ² ${chiSquare.toFixed(2)}</h3>
      ${Array.from({ length: 9 }, (_, i) => i + 1)
        .map((digit) => {
          const observed = total ? counts[digit] / total : 0;
          const expectedRate = expected[digit];
          const width = Math.max(2, Math.min(100, observed * 260));
          return `
            <div class="barRow">
              <b>${digit}</b>
              <div class="barTrack" title="관측 ${percentFormatter.format(observed)} / 기대 ${percentFormatter.format(expectedRate)}">
                <div class="barFill" style="width:${width}%"></div>
              </div>
              <span class="barMeta">${percentFormatter.format(observed)}</span>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function earlyTurnoutAnalysis() {
  const selectedElection = turnoutElectionName();
  const level = els.turnoutLevelSelect.value;
  const rows = state.records.filter((row) => row.electionName === selectedElection);
  const groups = new Map();

  for (const row of rows) {
    const groupKey = turnoutRegionKey(row, level);
    if (!groupKey) continue;
    const item = ensureTurnoutGroup(groups, groupKey, row, level);

    if (row.voteCategory === "최종결과") {
      item.electors += row.electors;
      item.totalVotes += row.turnoutVotes;
    } else if (row.voteCategory === "사전투표") {
      item.earlyVotes += row.turnoutVotes;
      item.earlyElectors += row.electors;
    }
  }

  const results = [...groups.values()]
    .filter((item) => item.electors > 0 || item.earlyVotes > 0)
    .map((item) => ({
      ...item,
      earlyRate: item.electors > 0 ? item.earlyVotes / item.electors : 0,
      turnoutRate: item.electors > 0 ? item.totalVotes / item.electors : 0,
    }))
    .sort((a, b) => b.earlyRate - a.earlyRate || b.earlyVotes - a.earlyVotes || a.label.localeCompare(b.label, "ko"));

  const totals = results.reduce(
    (sum, item) => {
      sum.electors += item.electors;
      sum.earlyVotes += item.earlyVotes;
      sum.totalVotes += item.totalVotes;
      return sum;
    },
    { electors: 0, earlyVotes: 0, totalVotes: 0 },
  );
  const totalRate = totals.electors > 0 ? totals.earlyVotes / totals.electors : 0;

  renderSummary([
    { label: "기준 선거유형", value: selectedElection },
    { label: "지역 단위", value: level === "province" ? "도단위" : "시단위" },
    { label: "전체 사전투표율", value: percentFormatter.format(totalRate) },
    { label: "지역 수", value: numberFormatter.format(results.length) },
  ]);
  renderEarlyTurnout(results, totals, selectedElection, level);
}

function turnoutElectionName() {
  const selectedType = els.typeSelect.value;
  if (selectedType !== "__ALL__") return selectedType;
  return state.records.some((row) => row.electionName === "시·도지사선거") ? "시·도지사선거" : state.records[0]?.electionName || "";
}

function turnoutRegionKey(row, level) {
  if (level === "province") return row.cityCode ? `province|${row.cityCode}` : "";
  return row.cityCode && row.townCode ? `city|${row.cityCode}|${row.townCode}` : "";
}

function turnoutRegionLabel(row, level) {
  if (level === "province") return row.cityName;
  return compactParts([row.cityName, row.townName]).join(" ");
}

function ensureTurnoutGroup(groups, key, row, level) {
  if (!groups.has(key)) {
    groups.set(key, {
      key,
      label: turnoutRegionLabel(row, level),
      electors: 0,
      earlyElectors: 0,
      earlyVotes: 0,
      totalVotes: 0,
    });
  }
  return groups.get(key);
}

function renderEarlyTurnout(results, totals, selectedElection, level) {
  const totalRate = totals.electors > 0 ? totals.earlyVotes / totals.electors : 0;
  els.resultPanel.innerHTML = `
    <div class="panelHead">
      <div>
        <h2>지역별 사전투표율</h2>
        <p>${escapeHtml(selectedElection)} 기준으로 최종 선거인수 대비 관내사전투표·관외사전투표·거소투표 투표수를 합산했습니다. 전체 선거유형을 선택하면 중복을 피하기 위해 시·도지사선거 기준으로 계산합니다.</p>
      </div>
      <span class="badge">${escapeHtml(level === "province" ? "도단위" : "시단위")}</span>
    </div>
    <div class="readGuide">
      <b>계산식</b>
      <span>사전투표율 = 사전투표수 / 최종 선거인수</span>
      <span>사전투표수 = 관내사전투표 + 관외사전투표 + 거소투표</span>
      <span>전체 기준 사전투표율은 ${percentFormatter.format(totalRate)}입니다.</span>
    </div>
    <div class="tableWrap">
      <table>
        <thead>
          <tr>
            <th class="number">순위</th>
            <th>지역</th>
            <th class="number">선거인수</th>
            <th class="number">사전투표수</th>
            <th class="number">사전투표율</th>
            <th class="number">전체 투표수</th>
            <th class="number">전체 투표율</th>
          </tr>
        </thead>
        <tbody>
          ${results
            .map(
              (item, index) => `
                <tr>
                  <td class="number">${numberFormatter.format(index + 1)}</td>
                  <td>${escapeHtml(item.label)}</td>
                  <td class="number">${numberFormatter.format(item.electors)}</td>
                  <td class="number">${numberFormatter.format(item.earlyVotes)}</td>
                  <td class="number"><strong>${percentFormatter.format(item.earlyRate)}</strong></td>
                  <td class="number">${numberFormatter.format(item.totalVotes)}</td>
                  <td class="number">${percentFormatter.format(item.turnoutRate)}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderSummary(items) {
  els.summaryPanel.innerHTML = items
    .map(
      (item) => `
        <div class="summaryItem">
          <span class="label">${escapeHtml(item.label)}</span>
          <b>${escapeHtml(item.value)}</b>
        </div>
      `,
    )
    .join("");
}

function renderIntro() {
  const byElection = [...groupBy(state.records, (row) => row.electionName).entries()]
    .sort((a, b) => b[1].length - a[1].length);
  renderSummary([
    { label: "CSV 원본 행", value: numberFormatter.format(state.rawRows) },
    { label: "개표단위", value: numberFormatter.format(state.records.length) },
    { label: "선거유형", value: numberFormatter.format(byElection.length) },
    { label: "파일", value: CSV_PATH.replace("./", "") },
  ]);
  els.resultPanel.innerHTML = `
    <div class="panelHead">
      <div>
        <h2>전체 CSV 로드 완료</h2>
        <p>원본 후보별 행을 개표단위로 묶어 분석합니다. 위 버튼을 눌러 동일 투표수, 동일 비율, 벤포드 점검, 지역별 사전투표율을 실행하세요.</p>
      </div>
      <span class="badge">준비 완료</span>
    </div>
    <div class="tableWrap">
      <table>
        <thead>
          <tr>
            <th>선거유형</th>
            <th class="number">개표단위</th>
          </tr>
        </thead>
        <tbody>
          ${byElection
            .map(([name, rows]) => `
              <tr>
                <td>${escapeHtml(name)}</td>
                <td class="number">${numberFormatter.format(rows.length)}</td>
              </tr>
            `)
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderEmpty(title, analyzedRows) {
  renderSummary([
    { label: "분석 개표단위", value: numberFormatter.format(analyzedRows) },
    { label: "결과", value: "0" },
    { label: "선거유형", value: els.typeSelect.options[els.typeSelect.selectedIndex].textContent },
    { label: "투표 구분", value: els.voteCategorySelect.options[els.voteCategorySelect.selectedIndex].textContent },
  ]);
  els.resultPanel.innerHTML = `
    <div class="panelHead">
      <div>
        <h2>${escapeHtml(title)}</h2>
        <p>현재 필터 조건에서 발견된 항목이 없습니다.</p>
      </div>
      <span class="badge">0건</span>
    </div>
    ${els.emptyTemplate.innerHTML}
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function runAnalysis(callback) {
  if (!state.records.length) {
    setStatus("먼저 CSV를 불러오세요.");
    return;
  }
  state.lastAnalysis = callback;
  setBusy(true);
  setStatus("계산 중...");
  await new Promise((resolve) => setTimeout(resolve, 20));
  try {
    callback();
    setStatus("계산 완료");
  } catch (error) {
    els.resultPanel.innerHTML = `
      <div class="empty">
        <h2>계산 중 오류</h2>
        <p>${escapeHtml(error.message)}</p>
      </div>
    `;
    setStatus("계산 오류");
  } finally {
    setBusy(false);
  }
}

function runFromUrl() {
  const run = initialParams.get("run");
  const actions = {
    sameVotes: sameVotesAnalysis,
    sameRatio: sameRatioAnalysis,
    benford: benfordAnalysis,
    earlyTurnout: earlyTurnoutAnalysis,
  };
  if (actions[run]) {
    setTimeout(() => runAnalysis(actions[run]), 60);
  }
}

els.reloadBtn.addEventListener("click", () => {
  loadDefaultCsv().catch((error) => {
    setStatus("자동 로드 실패");
    els.resultPanel.innerHTML = `
      <div class="empty">
        <h2>CSV 자동 로드 실패</h2>
        <p>${escapeHtml(error.message)} 파일 선택 버튼으로 CSV를 직접 지정할 수 있습니다.</p>
      </div>
    `;
  });
});

els.csvFile.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  setStatus("선택한 CSV 전체 로드 중...");
  const text = await file.text();
  loadCsvText(text, file.name);
});

els.includeExcludedBtn.addEventListener("click", () => {
  state.includeExcluded = !state.includeExcluded;
  updateExcludedButton();
  if (state.lastAnalysis) {
    runAnalysis(state.lastAnalysis);
  } else {
    renderIntro();
  }
});

els.sameVotesBtn.addEventListener("click", () => runAnalysis(sameVotesAnalysis));
els.sameRatioBtn.addEventListener("click", () => runAnalysis(sameRatioAnalysis));
els.benfordBtn.addEventListener("click", () => runAnalysis(benfordAnalysis));
els.earlyTurnoutBtn.addEventListener("click", () => runAnalysis(earlyTurnoutAnalysis));

updateExcludedButton();

loadDefaultCsv().catch((error) => {
  setStatus("자동 로드 실패");
  els.resultPanel.innerHTML = `
    <div class="empty">
      <h2>CSV 자동 로드 실패</h2>
      <p>${escapeHtml(error.message)} 파일 선택 버튼으로 CSV를 직접 지정해 주세요.</p>
    </div>
  `;
});
