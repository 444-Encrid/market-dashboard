// 표(PC)와 두 줄 목록(휴대폰), 기간 일치 점, 반대 근거 표시
// 5·20·60·120일 판정을 색 점 4개로. 고른 기간은 테두리
function dots(it) {
  return `<span class="dots">${WINDOWS.map(w => {
    const x = it.windows[w], l = x && x.label;
    return `<i class="dot${w === win ? " cur" : ""}" style="background:${l ? COLORS[l] : GRID}" title="${w}일: ${l || "자료 부족"}"></i>`;
  }).join("")}</span>`;
}
function warnMark(w) { return w.against && w.against.length ? `<span class="warn" title="${esc(w.against.join(" / "))}"><span class="ico">⚠️</span> ${w.against.length}</span>` : `<span class="dim">–</span>`; }

function flowBar(pct, max) {
  const w = Math.min(Math.abs(pct) / max, 1) * 100, c = pct >= 0 ? "#4cc94c" : "#ef6a6a";
  const bar = `<i style="width:${w.toFixed(0)}%;background:${c}"></i>`;
  return `<span class="flowbar"><span>${pct < 0 ? bar : ""}</span><span>${pct >= 0 ? bar : ""}</span></span>`;
}

const narrow = () => window.innerWidth < 700;

// 휴대폰: 표 대신 줄마다 두 줄짜리 목록
function mobileList(order, max) {
  return order.map(it => {
    const sub = it.parent ? " sub" : "", sel = it.ticker === selected ? " sel" : "";
    const head = `<div class="m-head"><span>${esc(it.name)}<span class="tk">${it.ticker}</span></span>`;
    const w = !it.error && it.windows[win];
    if (!w) return `<div class="m-row${sub}">${head}<span class="dim">${it.error ? "불러오기 실패" : "자료 부족"}</span></div></div>`;
    const intr = it.interest == null ? "" : ` · 관심 <span class="${it.interest >= 1.2 ? "pos" : it.interest <= 0.8 ? "neg" : ""}">${it.interest.toFixed(2)}배</span>`;
    return `<div class="m-row${sub}${sel}" data-t="${it.ticker}">${head}${badge(w.label)}</div>` +
      `<div class="m-line"><span class="${cls(w.flow)}">${eok(w.flow)}</span> (<span class="${cls(w.pct)}">${signed(w.pct, 1, "%")}</span>)${flowBar(w.pct, max)}` +
      ` &nbsp;${dots(it)}${w.against && w.against.length ? " &nbsp;" + warnMark(w) : ""}</div>` +
      `<div class="m-line">평소 ${rankText(w.rank)} · S&P 대비 <span class="${cls(w.excess)}">${signed(w.excess, 1, "%")}</span>${intr}</div></div>`;
  }).join("");
}

function renderTable() {
  const max = Math.max(1, ...data.items.filter(ok).map(it => Math.abs(it.windows[win].pct)));
  const order = [];
  data.items.filter(it => !it.parent).forEach(s => { order.push(s); data.items.filter(it => it.parent === s.ticker).forEach(c => order.push(c)); });
  const rows = order.map(it => {
    const sub = it.parent ? " sub" : "", sel = it.ticker === selected ? " sel" : "";
    if (it.error) return `<tr class="row${sub}"><td>${esc(it.name)}<span class="tk">${it.ticker}</span></td><td colspan="9" class="dim">불러오기 실패</td></tr>`;
    const w = it.windows[win];
    if (!w) return `<tr class="row${sub}"><td>${esc(it.name)}<span class="tk">${it.ticker}</span></td><td colspan="9" class="dim">자료 부족</td></tr>`;
    const intr = it.interest == null ? "–" : `<span class="${it.interest >= 1.2 ? "pos" : it.interest <= 0.8 ? "neg" : ""}">${it.interest.toFixed(2)}배</span>`;
    return `<tr class="row${sub}${sel}" data-t="${it.ticker}"><td>${esc(it.name)}<span class="tk">${it.ticker}</span></td>` +
      `<td>${badge(w.label)}</td><td style="text-align:center">${dots(it)}</td><td style="text-align:center">${warnMark(w)}</td>` +
      `<td><span class="${cls(w.flow)}">${eok(w.flow)}</span>${flowBar(w.pct, max)}</td>` +
      `<td class="${cls(w.pct)}">${signed(w.pct, 1, "%")}</td><td>${rankText(w.rank)}</td>` +
      `<td>${w.in_days}/${win}일</td><td class="${cls(w.excess)}">${signed(w.excess, 1, "%")}</td>` +
      `<td>${intr}</td></tr>`;
  }).join("");
  if (narrow()) { $("table").innerHTML = mobileList(order, max); return; }
  $("table").innerHTML = `<table><thead><tr><th>섹터</th><th>판정</th><th style="text-align:center">기간 일치</th><th style="text-align:center">반대</th><th>유입액</th><th>순자산 대비</th><th>평소 대비</th>` +
    `<th>유입한 날</th><th>S&P500 대비</th><th>거래 관심</th></tr></thead><tbody>${rows}</tbody></table>`;
}
