// ---------- 동반 하락 신호 ----------
const UP = "#0ca30c", DOWN = "#d03b3b";   // 등락 색: 상승 초록, 하락 빨강 (2026-10-25 사용자 선택)
const VERDICT = {"강한 동반 하락": STATUS["위험"], "동반 하락": STATUS["주의"], "동반 하락 아님": NEUTRAL};
const md = s => s.slice(5).replace("-", "/");
const WEEK = "일월화수목금토";

function badge(text, st) {
  return `<span class="badge" style="background:${st.color};color:${st.fg}">${esc(text)}</span>`;
}
function move(name, v, sub = "") {
  const color = v > 0 ? UP : v < 0 ? DOWN : INK;
  return `<div class="move"><div class="tile-label">${name}</div>` +
         `<div class="move-num" style="color:${color}">${fmt(v, 2, "%", true)}</div>${sub}</div>`;
}

function coHtml(co) {
  if (co.error) return `<div class="co"><div class="sub">동반 하락 신호를 불러오지 못했습니다. 잠시 뒤 자동으로 다시 시도합니다.</div></div>`;
  const v = VERDICT[co.verdict];
  const tnx = `<div class="move"><div class="tile-label">미국 10년 금리</div>` +
    `<div class="move-num">${fmt(co.tnx, 2, "%")}</div><div class="sub">전일 대비 ${fmt(co.tnx_diff, 2, "%p", true)}</div></div>`;
  const panel = `<div class="co" style="border-left-color:${v.color};background:${rgba(v.color, v.tint)}">` +
    `<div class="co-head"><div class="name">오늘의 동반 하락 판 · 기준일 ${md(co.asof)} ${co.session}</div>${badge(co.verdict, v)}</div>` +
    `<div class="moves">${move("나스닥", co.nasdaq)}${move("금", co.gold)}${move("비트코인", co.btc)}${tnx}</div>` +
    `<div class="desc">나스닥과 금이 같은 날 둘 다 떨어지면 동반 하락, 둘 다 -1% 이하면 강한 동반 하락. ` +
    `비트코인은 주말에도 거래되므로 나스닥 거래일 값에 맞춰 비교합니다.</div></div>`;

  const oilSt = co.oil_down ? STATUS["안정"] : STATUS["주의"];
  const oilV = co.oil_values[co.oil_values.length - 1], oilMa = co.oil_ma[co.oil_ma.length - 1];
  const oil = `<div class="card" style="border-left-color:${oilSt.color}">` +
    badge(co.oil_down ? "꺾이는 중" : "오르는 흐름", oilSt) +
    `<div class="name">① 브렌트유 (최근 3개월)</div>` +
    `<div class="value">${fmt(oilV, 2)}<span class="unit">달러</span></div>` +
    `<div class="sub">20일 평균 ${fmt(oilMa, 2)} · 평균선 ${co.oil_down ? "아래" : "위"} · 기준일 ${md(co.oil_asof)}</div>` +
    `<div class="desc">가격이 20일 평균선 아래로 내려가면 "꺾이는 중". 파란 선이 가격, 점선이 20일 평균.</div>` +
    `<div class="chart" id="chart_oil"></div></div>`;

  let fed;
  if (co.fomc.length) {
    const [next, ...rest] = co.fomc;
    const d = new Date(next.date + "T00:00:00");
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const left = Math.round((d - today) / 86400000);
    fed = `<div class="value">${md(next.date)} (${WEEK[d.getDay()]})<span class="unit">미국 시간</span></div>` +
      `<div class="sub">${left > 0 ? "D-" + left : "오늘"} · 한국 시간 ${next.kst} 발표` +
      `${rest.length ? " · 그다음 " + rest.map(f => md(f.date)).join(", ") : ""}</div>`;
  } else {
    fed = `<div class="sub">등록된 회의 일정이 없습니다. 새 일정을 넣어야 합니다.</div>`;
  }
  const fedCard = `<div class="card"><div class="name">② 다음 연준 회의</div>${fed}` +
    `<div class="desc">금리를 또 올릴지는 회의 전 시장 예상 확률로 봅니다. 확률은 자동으로 가져오지 않고 링크로 확인합니다.</div>` +
    `<p><a href="${co.fedwatch}" target="_blank" rel="noopener">CME FedWatch에서 금리 확률 보기 ↗</a></p></div>`;

  const cSt = co.corr >= co.corr_high ? STATUS["주의"] : co.corr < co.corr_low ? STATUS["안정"] : NEUTRAL;
  const corr = `<div class="card" style="border-left-color:${cSt.color}">` +
    badge(co.corr_label.split(" (")[0], cSt) +
    `<div class="name">③ 주식·금 상관계수 (최근 6개월)</div>` +
    `<div class="value">${fmt(co.corr, 2)}</div>` +
    `<div class="sub">${esc(co.corr_label)} · 기준일 ${md(co.asof)}</div>` +
    `<div class="desc">나스닥과 금의 하루 변화율로 잰 최근 20거래일 상관계수(-1~+1). ` +
    `${co.corr_high} 이상 같이 움직임, ${co.corr_low} 미만 따로 움직임.</div>` +
    `<div class="chart" id="chart_corr"></div></div>`;

  return panel + `<div class="cards co-cards">${oil}${fedCard}${corr}</div>` +
    `<p class="note">영상 작성자의 관점으로 만든 참고 신호입니다. 검증된 매매 규칙이 아니어서 위 안정·주의·위험 개수에는 넣지 않습니다.</p>`;
}

function coChart(id, traces, shapes = [], annotations = [], range) {
  Plotly.react(id, traces, {
    margin: {l: 4, r: 40, t: 8, b: 26}, showlegend: false, shapes, annotations,
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", hovermode: "x unified", dragmode: false,
    hoverlabel: {bgcolor: SURFACE, bordercolor: GRID, font: {color: INK}},
    font: {family: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: MUTED, size: 11},
    xaxis: {showgrid: false, linecolor: GRID, tickformat: "%m/%d", nticks: 5, fixedrange: true},
    yaxis: {gridcolor: GRID, zeroline: false, side: "right", nticks: 4, fixedrange: true, range},
  }, {displayModeBar: false, responsive: true});
}

function drawCo(co) {
  if (co.error) return;
  coChart("chart_oil", [
    {x: co.oil_dates, y: co.oil_values, mode: "lines", line: {color: LINE, width: 2}, name: "가격",
     hovertemplate: "%{y:,.2f}달러<extra>가격</extra>"},
    {x: co.oil_dates, y: co.oil_ma, mode: "lines", line: {color: MUTED, width: 1.5, dash: "dot"}, name: "20일 평균",
     hovertemplate: "%{y:,.2f}달러<extra>20일 평균</extra>"},
  ]);
  const lines = [[co.corr_high, STATUS["주의"].color, `같이 ${co.corr_high}`], [co.corr_low, STATUS["안정"].color, `따로 ${co.corr_low}`]];
  coChart("chart_corr", [
    {x: co.corr_dates, y: co.corr_values, mode: "lines", line: {color: LINE, width: 2},
     hovertemplate: "%{y:.2f}<extra></extra>"},
  ], lines.map(([y, color]) => ({type: "line", xref: "paper", x0: 0, x1: 1, y0: y, y1: y, line: {color, width: 1, dash: "dot"}})),
     lines.map(([y, , text]) => ({xref: "paper", x: 0, xanchor: "left", y, yanchor: "bottom", text, showarrow: false, font: {color: MUTED, size: 11}})),
     [Math.min(-0.2, ...co.corr_values) - 0.05, Math.max(0.8, ...co.corr_values) + 0.05]);
}
