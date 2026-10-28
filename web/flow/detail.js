// 업종 카드: 한 줄 문장, 숫자, 누적 유입·상대 강도 차트
// 숫자를 문장으로: 돈 → 가격 → 판정 → 반대 근거
function sayText(w) {
  const amount = `${num(Math.abs(w.flow) / 1e8, 1)}억 달러`;
  let s = `${win}거래일 동안 ${amount}가 ${w.flow >= 0 ? "들어왔고" : "빠져나갔고"} (순자산의 ${signed(w.pct, 1, "%")}, 3년 중 ${rankText(w.rank)}), `;
  s += w.excess == null ? "가격 비교 자료는 없다." : `가격은 S&P500보다 ${num(Math.abs(w.excess), 1)}% ${w.excess >= 0 ? "강했다" : "약했다"}.`;
  if (w.label && data.labels[w.label]) s += ` 그래서 <b>${w.label}</b>: ${esc(data.labels[w.label])}.`;
  if (w.against && w.against.length) s += ` 다만 반대 근거가 ${w.against.length}개 있다. 먼저 볼 것은 "${esc(w.against[0])}".`;
  return s;
}

function cardHtml() {
  const it = data.items.find(x => x.ticker === selected && !x.error);
  if (!it) return "";
  const w = it.windows[win];
  const wins = WINDOWS.map(o => { const x = it.windows[o], l = x && x.label;
    return `<div><i class="dot${o === win ? " cur" : ""}" style="background:${l ? COLORS[l] : GRID}"></i>${o}일<br>${l || "자료 부족"}</div>`; }).join("");
  if (!w) return `<div class="card-head"><b>${esc(it.name)} <span class="tk">${it.ticker}</span></b></div><div class="wins">${wins}</div><div class="calm">${win}일 자료가 부족합니다.</div>`;
  const intr = it.interest == null ? "–" : `<span class="${it.interest >= 1.2 ? "pos" : it.interest <= 0.8 ? "neg" : ""}">${it.interest.toFixed(2)}배</span>`;
  const top = `${w.top_date.slice(5).replace("-", "/")} <span class="${cls(w.top_flow)}">${eok(w.top_flow)}</span>`;
  const against = w.against && w.against.length
    ? `<div class="against-title"><span class="ico">⚠️</span> 반대 근거 ${w.against.length}개</div><ul class="against">${w.against.map(s => `<li>${esc(s)}</li>`).join("")}</ul>`
    : (["뚜렷하지 않음", null].includes(w.label) ? `<div class="calm">자금 흐름이 평소 수준이라 따로 볼 근거가 없습니다.</div>`
                                                  : `<div class="calm">눈에 띄는 반대 근거가 없습니다.</div>`);
  return `<div class="card-head"><b>${esc(it.name)} <span class="tk">${it.ticker}</span></b>${badge(w.label)}</div>` +
    `<div class="say">${sayText(w)}</div><div class="wins">${wins}</div>` +
    `<div class="kv"><div><span class="k">${win}일 유입액</span><b class="${cls(w.flow)}">${eok(w.flow)}</b></div>` +
    `<div><span class="k">순자산 대비</span><b class="${cls(w.pct)}">${signed(w.pct, 1, "%")}</b></div>` +
    `<div><span class="k">평소 대비 (3년)</span>${rankText(w.rank)}</div><div><span class="k">유입한 날</span>${w.in_days}/${win}일</div>` +
    `<div><span class="k">S&P500 대비</span><b class="${cls(w.excess)}">${signed(w.excess, 1, "%")}</b></div><div><span class="k">거래 관심 (5일/15일)</span>${intr}</div>` +
    `<div><span class="k">가장 큰 하루</span>${top}</div><div><span class="k">순자산</span>${num(it.tna / 1e8, 0)}억$</div></div>` + against;
}

function drawDetail() {
  const it = data.items.find(x => x.ticker === selected && !x.error) || data.items.find(x => !x.error);
  if (!it) return;
  selected = it.ticker;
  const w = it.windows[win];
  $("detail-title").textContent = `${it.name} (${it.ticker}) · 1년 흐름`;
  $("detail-sub").innerHTML = `밝은 띠가 고른 기간(${win}거래일)입니다` + (it.splits.length ? ` · 분할일 ${it.splits.join(", ")} 보정함` : "");
  const c = it.chart, n = c.dates.length;
  const start = c.dates[Math.max(0, n - win)];
  const traces = [
    {x: c.dates, y: c.cum, customdata: c.daily, mode: "lines", line: {color: "#3987e5", width: 2}, fill: "tozeroy", fillcolor: "rgba(57,135,229,.15)",
     hovertemplate: "누적 %{y:+,.1f}억$ · 그날 %{customdata:+,.1f}억$<extra></extra>", xaxis: "x", yaxis: "y"},
    {x: c.rel_dates, y: c.rel, mode: "lines", line: {color: "#fab219", width: 2}, hovertemplate: "S&P500 대비 %{y:.1f}<extra></extra>", xaxis: "x", yaxis: "y3"},
  ];
  const layout = {
    margin: {l: 8, r: 54, t: 22, b: 26}, showlegend: false, dragmode: false, hovermode: "x unified",
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    hoverlabel: {bgcolor: SURFACE, bordercolor: GRID, font: {color: INK}},
    font: {family: FONT, color: MUTED, size: 11},
    xaxis: {showgrid: false, linecolor: GRID, tickformat: "%y/%m", fixedrange: true, showspikes: true, spikemode: "across", spikethickness: 1, spikecolor: MUTED},
    yaxis: {domain: [0.45, 1], gridcolor: GRID, zerolinecolor: MUTED, side: "right", ticksuffix: "억", fixedrange: true, nticks: 5},
    yaxis3: {domain: [0, 0.36], gridcolor: GRID, zeroline: false, side: "right", fixedrange: true, nticks: 4},
    shapes: [
      {type: "rect", xref: "x", yref: "paper", x0: start, x1: c.dates[n - 1], y0: 0, y1: 1, fillcolor: "rgba(240,239,236,.07)", line: {width: 0}, layer: "below"},
      {type: "line", xref: "paper", yref: "y3", x0: 0, x1: 1, y0: 100, y1: 100, line: {color: MUTED, width: 1, dash: "dot"}},
    ],
    annotations: [
      {xref: "paper", yref: "paper", x: 0, y: 1.04, xanchor: "left", showarrow: false, text: "파란 선: 1년 전부터 쌓인 유입 (억 달러, 위로 가면 돈이 들어옴)", font: {color: MUTED, size: 11}},
      {xref: "paper", yref: "paper", x: 0, y: 0.38, xanchor: "left", showarrow: false, text: "노란 선: S&P500 대비 가격 (1년 전 = 100, 위로 가면 더 강함)", font: {color: MUTED, size: 11}},
    ],
  };
  Plotly.react("detail-chart", traces, layout, {displayModeBar: false, responsive: true}).then(plainMinus);
}
