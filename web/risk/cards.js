// 위험 지표 카드·차트·요약·표·설명
function gauge(it) {
  if (it.bands.length) {   // 공포/중립/탐욕처럼 이름이 따로 있는 지표: 실제 눈금 비율대로 그린다
    const [low, mid, high] = it.bands, max = high[1];
    const parts = [[low[0], low[1], STATUS[low[2]].color], [mid[0], mid[1] - low[1], NEUTRAL.color],
                   [high[0], max - mid[1], STATUS[high[2]].color]];
    const pos = Math.min(Math.max(it.judge_value / max, 0.03), 0.97);
    const segs = parts.map(([n, w, c]) => `<span style="flex:${w};background:${c};opacity:${n === it.label ? 1 : 0.3}"></span>`).join("");
    return `<div class="gauge">${segs}<div class="pin" style="left:${(pos * 100).toFixed(1)}%"></div></div>` +
           `<div class="gauge-labels">${parts.map(([n, w]) => `<span style="flex:${w}">${n}</span>`).join("")}</div>`;
  }
  const step = it.danger - it.warn;
  let pos = (it.judge_value - (it.warn - step)) / (3 * step);
  pos = Math.min(Math.max(pos, 0.03), 0.97);
  const segs = ORDER.map(s => `<span style="background:${STATUS[s].color};opacity:${s === it.status ? 1 : 0.3}"></span>`).join("");
  return `<div class="gauge">${segs}<div class="pin" style="left:${(pos * 100).toFixed(1)}%"></div></div>` +
         `<div class="gauge-labels">${ORDER.map(s => `<span>${s}</span>`).join("")}</div>`;
}

function cardHtml(it) {
  if (it.error) {
    return `<div class="card"><div class="name">${esc(it.name)}</div>` +
           `<div class="sub">데이터를 불러오지 못했습니다. 잠시 뒤 자동으로 다시 시도합니다.</div></div>`;
  }
  const st = look(it), diff = it.value - it.prev;
  const arrow = diff > 0 ? "▲" : diff < 0 ? "▼" : "–";
  let sub = `전일 대비 ${arrow} ${fmt(Math.abs(diff), it.decimals)}`;
  if (it.judge_name) sub += ` · ${it.judge_name} ${fmt(it.judge_value, 2, it.judge_unit, true)}`;
  sub += ` · 기준일 ${it.asof.slice(5).replace("-", "/")}`;
  return `<div class="card" style="border-left-color:${st.color};background:${rgba(st.color, st.tint)}">` +
    `<span class="badge" style="background:${st.color};color:${st.fg}">${st.icon} ${it.label}</span>` +
    `<div class="name">${esc(it.name)}</div>` +
    `<div class="value">${fmt(it.value, it.decimals)}<span class="unit">${esc(it.unit)}</span></div>` +
    `<div class="sub">${sub}</div>${gauge(it)}<div class="desc">${esc(it.desc)}</div>` +
    `<div class="chart" id="chart_${it.key}"></div></div>`;
}

function drawChart(it) {
  const days = PERIODS[period];
  const x = it.dates.slice(-days), y = it.values.slice(-days);
  let lo = Math.min(...y), hi = Math.max(...y);
  const pad = (hi - lo) * 0.15 || Math.abs(hi) * 0.01 || 1;
  const shapes = [], annotations = [];
  // 기준선과 색 구간은 화면에 보이는 값으로 판정하는 지표에만, 근처에 있을 때만 그린다.
  if (!it.judge_name) {
    const c = s => STATUS[s].color;
    let levels, zones;   // levels: [값, 색, 글자], zones: [아래, 위, 색, 진하기]
    if (it.bands.length) {
      const [low, mid, high] = it.bands;
      levels = [[low[1], c(low[2]), `${low[0]} ${low[1]} 미만`], [mid[1], c(high[2]), `${high[0]} ${mid[1]} 이상`]];
      zones = [[-Infinity, low[1], c(low[2]), 0.16], [mid[1], Infinity, c(high[2]), 0.10]];
    } else {
      levels = [[it.warn, c("주의"), `주의 ${it.warn}`], [it.danger, c("위험"), `위험 ${it.danger}`]];
      zones = it.higher_is_worse
        ? [[it.warn, it.danger, c("주의"), 0.10], [it.danger, Infinity, c("위험"), 0.16]]
        : [[it.danger, it.warn, c("주의"), 0.10], [-Infinity, it.danger, c("위험"), 0.16]];
    }
    for (const [level, color, text] of levels) {
      if (level >= lo - pad * 3 && level <= hi + pad * 3) {
        lo = Math.min(lo, level); hi = Math.max(hi, level);
        shapes.push({type: "line", xref: "paper", x0: 0, x1: 1, y0: level, y1: level,
                     line: {color, width: 1, dash: "dot"}});
        annotations.push({xref: "paper", x: 0, xanchor: "left", y: level, yanchor: "bottom",
                          text, showarrow: false, font: {color: MUTED, size: 11}});
      }
    }
    const y0 = lo - pad, y1 = hi + pad;
    for (const [a, b, color, alpha] of zones) {
      const z0 = Math.max(a, y0), z1 = Math.min(b, y1);
      if (z0 < z1) shapes.push({type: "rect", xref: "paper", x0: 0, x1: 1, y0: z0, y1: z1, layer: "below",
                                line: {width: 0}, fillcolor: rgba(color, alpha)});
    }
  }
  const traces = [
    {x, y, mode: "lines", line: {color: LINE, width: 2},
     hovertemplate: `%{y:,.${it.decimals}f}${it.unit}<extra></extra>`},
    {x: [x[x.length - 1]], y: [y[y.length - 1]], mode: "markers", hoverinfo: "skip",
     marker: {color: look(it).color, size: 11, line: {color: SURFACE, width: 2}}},
  ];
  const layout = {
    margin: {l: 4, r: 40, t: 8, b: 26}, showlegend: false, shapes, annotations,
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", hovermode: "x unified", dragmode: false,
    hoverlabel: {bgcolor: SURFACE, bordercolor: GRID, font: {color: INK}},
    font: {family: FONT, color: MUTED, size: 11},
    xaxis: {showgrid: false, linecolor: GRID, tickformat: "%m/%d", nticks: 5, fixedrange: true,
            showspikes: true, spikemode: "across", spikethickness: 1, spikecolor: MUTED, spikedash: "solid"},
    yaxis: {gridcolor: GRID, zeroline: false, side: "right", nticks: 4, fixedrange: true, range: [lo - pad, hi + pad]},
  };
  Plotly.react("chart_" + it.key, traces, layout, {displayModeBar: false, responsive: true}).then(plainMinus);
}

function summaryHtml(items) {
  const by = {};
  ORDER.forEach(s => by[s] = items.filter(it => it.status === s).map(it => it.name));
  const failed = items.filter(it => !it.status).length;
  let top = "안정", title = "모든 지표가 안정입니다";
  if (by["위험"].length) { top = "위험"; title = `위험 신호 ${by["위험"].length}개`; }
  else if (by["주의"].length) { top = "주의"; title = `주의 신호 ${by["주의"].length}개`; }
  const st = STATUS[top];
  const lines = ["위험", "주의"].filter(s => by[s].length)
    .map(s => `<div class="banner-sub">${s}: ${by[s].map(esc).join(" · ")}</div>`).join("");
  let tiles = ORDER.map(s => `<div class="tile" style="border-top-color:${STATUS[s].color}">` +
    `<div class="tile-label">${STATUS[s].icon} ${s}</div><div class="tile-num">${by[s].length}</div></div>`).join("");
  if (failed) tiles += `<div class="tile" style="border-top-color:${MUTED}"><div class="tile-label">불러오기 실패</div><div class="tile-num">${failed}</div></div>`;
  return `<div class="banner" style="border-color:${st.color};background:${rgba(st.color, 0.14)}">` +
         `<div class="banner-title">${st.icon} ${title}</div>${lines}</div><div class="tiles">${tiles}</div>`;
}

function tableHtml(items) {
  const rows = items.map(it => {
    if (it.error) return `<tr><td>${esc(it.name)}</td><td colspan="6">불러오기 실패</td></tr>`;
    const op = it.higher_is_worse ? "이상" : "이하";
    const target = it.judge_name || "현재 값", unit = it.judge_name ? it.judge_unit : it.unit;
    const rule = it.bands.length
      ? `<td>–</td><td>${target} ${it.bands[0][1]} 미만 (${it.bands[0][0]})</td>`
      : `<td>${target} ${it.warn}${unit} ${op}</td><td>${target} ${it.danger}${unit} ${op}</td>`;
    return `<tr><td>${esc(it.name)}</td><td>${look(it).icon} ${it.label}</td>` +
      `<td>${fmt(it.value, it.decimals, it.unit)}</td><td>${fmt(it.judge_value, 2, unit)}</td>` +
      `${rule}<td>${it.asof}</td></tr>`;
  }).join("");
  return `<table><thead><tr><th>지표</th><th>상태</th><th>현재 값</th><th>판정에 쓴 값</th><th>주의 기준</th><th>위험 기준</th><th>기준일</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function guideHtml(items) {
  return items.map(it => `<div class="guide-item"><div class="guide-name">${esc(it.name)}</div>` +
    `<div class="guide-row"><span class="tag" style="background:${rgba(STATUS["안정"].color, 0.25)}">의미</span>${esc(it.guide[0])}</div>` +
    `<div class="guide-row"><span class="tag" style="background:${STATUS["위험"].color};color:#fff">위험</span>${esc(it.guide[1])}</div></div>`).join("");
}
