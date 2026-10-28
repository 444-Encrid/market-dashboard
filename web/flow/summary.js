// 오른쪽 판: 기간×판정 개수표, 요약, 좌표 그림
// 기간 4개 × 판정 5개 개수. 고른 기간 열을 밝게
function matrixHtml() {
  const ok = data.items.filter(it => !it.error);
  const head = WINDOWS.map(w => `<th class="${w === win ? "cur" : ""}">${w}일</th>`).join("");
  const rows = Object.keys(COLORS).map(l => `<tr><td><i class="dot" style="background:${COLORS[l]}"></i> ${l}</td>` +
    WINDOWS.map(w => { const n = ok.filter(it => it.windows[w] && it.windows[w].label === l).length;
      return `<td class="${w === win ? "cur" : ""}${n ? "" : " dim"}">${n}</td>`; }).join("") + "</tr>").join("");
  return `<div class="matrix"><div class="matrix-title">기간별 판정 개수 (19개)</div>` +
    `<table><thead><tr><th></th>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function summaryHtml() {
  const m = data.market[win];
  const items = data.items.filter(ok);
  const by = {};
  Object.keys(COLORS).forEach(l => by[l] = items.filter(it => it.windows[win].label === l));
  const failed = data.items.filter(it => it.error).length;
  const tiles = Object.keys(COLORS).map(l => `<div class="tile" style="--c:${COLORS[l]}">` +
    `<div class="tile-label">${l}</div><div class="tile-num">${by[l].length}</div>` +
    `<div class="tile-names">${by[l].map(it => it.ticker).join(" · ") || "&nbsp;"}</div></div>`).join("") +
    (failed ? `<div class="tile" style="--c:${MUTED}"><div class="tile-label">불러오기 실패</div><div class="tile-num">${failed}</div></div>` : "");
  return `<div class="banner"><div class="banner-title">${win}거래일 동안 11개 섹터 합계 ` +
    `<span class="${cls(m.total)}">${eok(m.total)}</span> · 유입 섹터 ${m.in_count}/${m.count}</div>` +
    `<div class="banner-sub">같은 기간 S&P500(SPY) <span class="${cls(m.spy)}">${signed(m.spy, 1, "%")}</span> · ` +
    `자금 기준일 ${data.asof} (미국 날짜)</div></div><div class="tiles">${tiles}</div>` + matrixHtml();
}

function drawScatter() {
  const items = data.items.filter(ok);
  const traces = [false, true].map(isSub => {
    const g = items.filter(it => !!it.parent === isSub);
    return {
      x: g.map(it => it.windows[win].pct), y: g.map(it => it.windows[win].excess),
      text: g.map(it => it.ticker), customdata: g.map(it => [it.name, eok(it.windows[win].flow), it.windows[win].label || "–", rankText(it.windows[win].rank)]),
      mode: "markers+text", textposition: "top center", textfont: {color: INK, size: 11},
      marker: {size: g.map(it => Math.max(10, Math.sqrt(it.tna / 1e9) * 4.2)),
               color: isSub ? "rgba(0,0,0,0)" : g.map(it => rgba(COLORS[it.windows[win].label] || MUTED, 0.75)),
               line: {color: g.map(it => COLORS[it.windows[win].label] || MUTED), width: isSub ? 2.5 : 1}},
      hovertemplate: "<b>%{text} %{customdata[0]}</b><br>유입 %{customdata[1]} (순자산 대비 %{x:+.1f}%)<br>" +
        "평소 대비 %{customdata[3]}<br>S&P500 대비 %{y:+.1f}%<br>%{customdata[2]}<extra></extra>",
      name: isSub ? "세부 업종" : "섹터",
    };
  });
  const layout = {
    margin: {l: 50, r: 16, t: 10, b: 44}, showlegend: false, dragmode: false,
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    hoverlabel: {bgcolor: SURFACE, bordercolor: GRID, font: {color: INK}},
    font: {family: FONT, color: MUTED, size: 11},
    xaxis: {title: {text: "← 유출 · 순자산 대비 유입 % · 유입 →"}, gridcolor: GRID, zerolinecolor: MUTED, ticksuffix: "%", fixedrange: true},
    yaxis: {title: {text: "S&P500 대비 %"}, gridcolor: GRID, zerolinecolor: MUTED, ticksuffix: "%", fixedrange: true},
  };
  Plotly.react("scatter", traces, layout, {displayModeBar: false, responsive: true}).then(plainMinus);
  $("scatter").removeAllListeners?.("plotly_click");
  $("scatter").on("plotly_click", e => select(e.points[0].text));
}
