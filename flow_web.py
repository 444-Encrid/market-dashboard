"""미국 섹터 자금 흐름 서버. 실행 후 http://127.0.0.1:8602 접속.

위험 지표 대시보드(risk_web.py)와 같은 방식이다. 이 PC(127.0.0.1)에서만 열리고 자체 로그인이 없다.
휴대폰 등 외부에서는 옆 프로젝트 '매매자료정리' 의 ngrok 주소 뒤에 /flow/ 를 붙여 들어온다.
그래서 화면(PAGE)의 주소는 전부 상대 경로(api/data)여야 한다.
  python flow_web.py   서버 실행
"""
import json
import math
import os
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import flow_data as fd

HOST, PORT = "127.0.0.1", 8602
# 설명서 PC용 사본. /guide 로 내보내 휴대폰에서도 같은 로그인으로 읽게 한다 (아티팩트 링크는 claude.ai 로그인이 필요)
GUIDE = fd.ROOT / "섹터자금흐름_설명" / "섹터자금흐름_설명_읽기.html"
# 가격은 1시간, 계산 결과는 10분마다 새로 만든다 (엑셀은 flow_data.download 가 6시간마다 다시 받는다)
TTL_PRICES, TTL_RESULT = 3600, 600

_lock = threading.Lock()
_state = {"prices": (None, None), "result": (None, None)}


def _clean(o):
    """JSON 에 NaN 이 들어가지 않게 바꾼다."""
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else o
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


def payload():
    with _lock:
        at, result = _state["result"]
        if at is not None and time.monotonic() - at < TTL_RESULT:
            return result
        p_at, prices = _state["prices"]
        if p_at is None or time.monotonic() - p_at > TTL_PRICES:
            try:
                prices = fd.fetch_prices()
                _state["prices"] = (time.monotonic(), prices)
            except Exception:
                if prices is None:
                    raise
        res = fd.build(*prices)
        try:
            fd.save_record(res)
        except OSError:
            pass
        res = _clean(res)
        res["time"] = datetime.now().strftime("%H:%M:%S")
        res["labels"] = fd.LABELS
        _state["result"] = (time.monotonic(), res)
        return res


PAGE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>미국 섹터 자금 흐름</title>
<script src="https://cdn.plot.ly/plotly-basic-2.35.2.min.js"></script>
<style>
:root{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1400px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:1.5rem;margin:0}
/* 맨 위 고정 바: 제목, 기간 버튼, 자금 기준일 */
.topbar{position:sticky;top:env(safe-area-inset-top,0px);z-index:20;background:var(--page);display:flex;flex-wrap:wrap;align-items:center;gap:8px 18px;padding:10px 0;margin:-10px 0 4px;border-bottom:1px solid var(--grid)}
.topbar .asof{color:var(--ink2);font-size:.85rem;margin-left:auto}
.guide-link{color:#3987e5;font-size:.85rem;text-decoration:none;border:1px solid var(--grid);border-radius:8px;padding:5px 10px}
@media (max-width:699px){h1{font-size:1.15rem}.topbar .seg button{padding:6px 11px}.topbar .asof{margin-left:0;font-size:.78rem}}
#card,#detail-title{scroll-margin-top:110px}
h2{font-size:1.3rem;margin:26px 0 6px}
.bar{display:flex;gap:10px 20px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
.seg{display:inline-flex;border:1px solid var(--grid);border-radius:8px;overflow:hidden}
.seg button{background:none;border:0;color:var(--ink2);font:inherit;font-size:.9rem;padding:7px 14px;cursor:pointer}
.seg button.on{background:#3987e5;color:#fff;font-weight:600}
.note{color:var(--muted);font-size:.8rem;margin:6px 0}
.banner{border-left:6px solid #3987e5;background:rgba(57,135,229,.12);border-radius:8px;padding:12px 16px;margin:8px 0 10px}
.banner-title{font-size:1.2rem;font-weight:700}
.banner-sub{color:var(--ink2);font-size:.9rem;margin-top:3px}
.tiles{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.tile{flex:1 1 120px;border:1px solid var(--grid);border-top:4px solid var(--c);border-radius:8px;padding:8px 14px;background:var(--surface)}
/* PC: 왼쪽 그림·표, 오른쪽 고정 요약 판. 1100px 미만은 한 단 (요약은 위, 카드는 표 아래로 옮긴다) */
.layout{display:grid;grid-template-columns:minmax(0,1fr) 350px;gap:20px;align-items:start}
.mainc{min-width:0}
.side{position:sticky;top:72px;max-height:calc(100vh - 84px);overflow-y:auto;display:flex;flex-direction:column;gap:12px;margin-top:26px}
.side:empty{display:none}
@media (max-width:1099px){.layout{grid-template-columns:minmax(0,1fr)}.side{display:none}}
.side .banner{margin:0}
.side .tiles{flex-direction:column;gap:6px;margin:0}
.side .tile{flex:none;display:grid;grid-template-columns:1fr auto;align-items:center;column-gap:10px;border-top:1px solid var(--grid);border-left:4px solid var(--c);padding:6px 12px}
.side .tile-num{font-size:1.25rem;grid-row:span 2}
.card{border:1px solid var(--grid);border-radius:10px;background:var(--surface);padding:12px 14px}
.card-head{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.card-head b{font-size:1.1rem}
.wins{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:10px 0 4px}
.wins div{text-align:center;font-size:.7rem;color:var(--muted);line-height:1.3;word-break:keep-all}
.wins .dot{width:14px;height:14px;margin:0 auto 3px;display:block}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:8px 14px;font-size:.88rem;margin:10px 0;font-variant-numeric:tabular-nums}
.kv div{white-space:nowrap}
.kv .k{color:var(--muted);display:block;font-size:.72rem}
.against-title{font-size:.82rem;font-weight:700;color:#fab219;margin-top:10px}
.against{margin:4px 0 0;padding-left:18px;font-size:.84rem;color:var(--ink2);line-height:1.5}
.calm{font-size:.82rem;color:var(--muted);margin-top:10px}
.dots{display:inline-flex;gap:4px;vertical-align:middle}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.dot.cur{box-shadow:0 0 0 2px var(--surface),0 0 0 3.5px var(--ink)}
.warn{color:#fab219;font-weight:600}
.matrix{border:1px solid var(--grid);border-radius:10px;background:var(--surface);padding:10px 12px;margin-bottom:6px}
.matrix-title{font-size:.8rem;color:var(--muted);margin-bottom:4px}
.matrix table{width:100%;font-size:.82rem}
.matrix th,.matrix td{padding:5px 6px;text-align:center}
.matrix td:first-child{text-align:left;white-space:nowrap}
.matrix .cur{background:#26303d;color:var(--ink);font-weight:700}
.say{font-size:.9rem;line-height:1.6;color:var(--ink);margin:10px 0 2px;padding:9px 11px;background:#22252b;border-radius:8px}
#card-slot .card{margin-top:24px}
.tile-label{color:var(--ink2);font-size:.85rem}
.tile-num{font-size:1.7rem;font-weight:700;line-height:1.15}
.tile-names{color:var(--muted);font-size:.75rem;margin-top:2px}
.panel{border:1px solid var(--grid);border-radius:10px;padding:10px 12px;background:var(--surface)}
#scatter{height:440px}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;font-size:.83rem;white-space:nowrap;font-variant-numeric:tabular-nums;width:100%}
th,td{text-align:right;padding:7px 8px;border-bottom:1px solid var(--grid)}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}
th{color:var(--muted);font-weight:500;font-size:.78rem}
tr.row{cursor:pointer}
tr.row:hover{background:#222220}
tr.row.sel{background:#26303d}
tr.sub td:first-child{padding-left:28px;color:var(--ink2)}
.tk{color:var(--muted);font-size:.75rem;margin-left:6px}
.badge{display:inline-block;font-size:.76rem;font-weight:700;border-radius:999px;padding:2px 10px}
.flowbar{display:inline-flex;width:64px;height:8px;vertical-align:middle;margin-left:8px}
.flowbar>span{flex:1;display:flex}
.flowbar>span:first-child{justify-content:flex-end;border-right:1px solid var(--muted)}
.flowbar i{display:block;height:100%;border-radius:2px}
.m-row{padding:9px 6px;border-bottom:1px solid var(--grid);cursor:pointer}
.m-row.sub{padding-left:22px}
.m-row.sel{background:#26303d}
.m-head{display:flex;justify-content:space-between;align-items:center;gap:8px;font-weight:600}
.m-row.sub .m-head{font-weight:500;color:var(--ink2)}
.m-line{font-size:.82rem;color:var(--ink2);margin-top:3px;font-variant-numeric:tabular-nums}
.pos{color:#4cc94c}.neg{color:#ef6a6a}.dim{color:var(--muted)}
#detail-title{font-size:1.15rem;font-weight:700;margin:2px 0}
#detail-chart{height:420px}
.guide{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px}
.guide-item{border:1px solid var(--grid);border-radius:8px;padding:10px 14px;background:var(--surface);color:var(--ink2);font-size:.86rem;line-height:1.6}
.guide-item b{color:var(--ink)}
</style></head>
<body><main>
<div class="topbar"><h1>미국 섹터 자금 흐름</h1><div class="seg" id="windows"></div><span class="asof" id="asof"></span><a class="guide-link" href="guide">설명서</a></div>
<div class="note" id="stamp">불러오는 중… 처음에는 자료를 받느라 30초쯤 걸립니다.</div>
<div id="summary-slot"></div>
<div class="layout">
<div class="mainc">
<h2>자금 좌표</h2>
<div class="note">가로: 기간 동안 들어온 돈 ÷ 순자산 · 세로: S&P500 대비 초과수익 · 원 크기: 순자산 · 속이 빈 원은 세부 업종 · 원을 누르면 상세</div>
<div class="panel"><div id="scatter"></div></div>

<h2>섹터별 표</h2>
<div class="note">줄을 누르면 상세와 1년 흐름이 나옵니다. 점 4개는 왼쪽부터 5·20·60·120일 판정, 테두리가 고른 기간입니다. ⚠ 는 반대 근거 개수입니다.</div>
<div class="panel tablewrap" id="table"></div>

<div id="card-slot"></div>
<h2 id="detail-title"></h2>
<div class="note" id="detail-sub"></div>
<div class="panel"><div id="detail-chart"></div></div>
</div>
<aside class="side" id="side"></aside>
</div>
<div hidden><div id="summary"></div><div class="card" id="card"></div></div>

<h2>읽는 법</h2>
<div class="guide">
<div class="guide-item"><b>유입액</b>: 주식 수 변화 × NAV 입니다. ETF는 돈이 들어오면 주식을 새로 찍고 나가면 없애므로 실제로 오간 돈입니다.
분할일(2025-12-05 등)은 자동으로 빼고 셉니다. 막대는 오른쪽이 유입, 왼쪽이 유출입니다.</div>
<div class="guide-item"><b>평소 대비</b>: 같은 길이 기간의 유입(순자산 대비 %)을 지난 3년과 비교한 위치입니다.
상위 30% 이내 + 유입이면 "돈이 많이 들어옴", 하위 30% 이내 + 유출이면 "돈이 많이 빠짐"으로 봅니다.</div>
<div class="guide-item"><b>판정</b>: 위 자금 판정에 S&P500 대비 초과수익(+/−)을 겹친 것입니다.
<span style="color:#0ca30c">자금·가격 동반</span>은 돈과 가격이 같은 방향, <span style="color:#3987e5">자금만 유입</span>은 돈이 먼저 움직이는 중,
<span style="color:#fab219">가격만 강세</span>는 돈이 빠지는데 가격만 버티는 중입니다.</div>
<div class="guide-item"><b>기간 일치</b>: 표의 점 4개는 5·20·60·120일 판정 색입니다. 여러 기간이 같은 색이면 흐름이 오래 이어지는 중이고,
짧은 기간과 긴 기간 색이 반대면 방향이 바뀌는 중일 수 있습니다.</div>
<div class="guide-item"><b>반대 근거</b>: 판정과 어긋나는 점입니다. 큰 유입과 큰 유출이 같이 있음(리밸런싱 왕복 의심), 순유입의 60% 이상이 하루에 몰림(20일 이상),
돈이 들어온 날이 절반이 안 됨, 다른 기간 판정이 반대, 거래 관심 감소. 큰 날은 1년 하루 유입 크기(중앙값)의 5배 넘는 날입니다.</div>
<div class="guide-item"><b>거래 관심</b>: 최근 5일 평균 거래대금 ÷ 직전 15일 평균입니다. 1.2배 이상이면 관심이 커지는 중입니다.
거래대금은 사고판 금액이라 유입액과 다릅니다.</div>
<div class="guide-item"><b>주의</b>: 이 ETF들은 섹터 전체 돈의 일부만 보여 줍니다. 분기 리밸런싱 때 큰돈이 들어왔다 며칠 만에 나가기도 해서
(XLK 2026-06-17 +89억, 06-22 −93억) 5일 값이 튈 수 있습니다. 동일가중 ETF(반도체·소프트웨어·바이오)는 대형주 몇 개가 아니라 업종 전체 분위기에 가깝습니다.</div>
<div class="guide-item"><b>한계</b>: 관측용이며 매매 신호가 아닙니다. 판정 기준이 앞으로도 맞는지는 아직 검증되지 않았습니다.
매일 판정을 flow_기록 폴더에 남겨 나중에 맞춰 볼 수 있게 했습니다. 자금 자료는 State Street가 하루 늦게 올립니다.</div>
</div>
</main>
<script>
const REFRESH_MS = 600000;
const WINDOWS = [5, 20, 60, 120];
const COLORS = {"자금·가격 동반": "#0ca30c", "자금만 유입": "#3987e5", "뚜렷하지 않음": "#898781",
                "가격만 강세": "#fab219", "자금·가격 이탈": "#d03b3b"};
const FG = {"자금·가격 동반": "#0b0b0b", "자금만 유입": "#fff", "뚜렷하지 않음": "#0b0b0b", "가격만 강세": "#0b0b0b", "자금·가격 이탈": "#fff"};
const INK = "#f0efec", MUTED = "#898781", GRID = "#2c2c2a", SURFACE = "#1a1a19";
let win = 20, data = null, selected = "XLK";
const $ = id => document.getElementById(id);
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])); }
function rgba(hex, a) { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; }
function num(v, d) { return Math.abs(v).toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d}); }
function signed(v, d, unit = "") { return v == null ? "–" : (v > 0 ? "+" : v < 0 ? "−" : "") + num(v, d) + unit; }
function cls(v) { return v == null ? "dim" : v > 0 ? "pos" : v < 0 ? "neg" : "dim"; }
// 억 달러: 1e8 달러 단위
function eok(usd) { return usd == null ? "–" : signed(usd / 1e8, Math.abs(usd) >= 1e10 ? 0 : 1, "억$"); }
function rankText(r) { if (r == null) return "–"; return r >= 0.5 ? `상위 ${Math.max(1, Math.round((1 - r) * 100))}%` : `하위 ${Math.max(1, Math.round(r * 100))}%`; }
function badge(label) { return label ? `<span class="badge" style="background:${COLORS[label]};color:${FG[label]}">${label}</span>` : "–"; }
function ok(it) { return !it.error && it.windows[win]; }

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
    font: {family: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: MUTED, size: 11},
    xaxis: {title: {text: "← 유출 · 순자산 대비 유입 % · 유입 →"}, gridcolor: GRID, zerolinecolor: MUTED, ticksuffix: "%", fixedrange: true},
    yaxis: {title: {text: "S&P500 대비 %"}, gridcolor: GRID, zerolinecolor: MUTED, ticksuffix: "%", fixedrange: true},
  };
  Plotly.react("scatter", traces, layout, {displayModeBar: false, responsive: true});
  $("scatter").removeAllListeners?.("plotly_click");
  $("scatter").on("plotly_click", e => select(e.points[0].text));
}

// 5·20·60·120일 판정을 색 점 4개로. 고른 기간은 테두리
function dots(it) {
  return `<span class="dots">${WINDOWS.map(w => {
    const x = it.windows[w], l = x && x.label;
    return `<i class="dot${w === win ? " cur" : ""}" style="background:${l ? COLORS[l] : GRID}" title="${w}일: ${l || "자료 부족"}"></i>`;
  }).join("")}</span>`;
}
function warnMark(w) { return w.against && w.against.length ? `<span class="warn" title="${esc(w.against.join(" / "))}">⚠ ${w.against.length}</span>` : `<span class="dim">–</span>`; }

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
    ? `<div class="against-title">⚠ 반대 근거 ${w.against.length}개</div><ul class="against">${w.against.map(s => `<li>${esc(s)}</li>`).join("")}</ul>`
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

const wide = () => window.innerWidth >= 1100;
// 넓으면 요약과 카드를 오른쪽 판에, 좁으면 요약은 맨 위, 카드는 표 아래에 둔다
function place() {
  const side = $("side");
  if (wide()) { side.append($("summary"), $("card")); }
  else { $("summary-slot").append($("summary")); $("card-slot").append($("card")); }
}
function select(t) {
  selected = t; renderTable(); drawDetail(); $("card").innerHTML = cardHtml();
  if (!wide()) $("card").scrollIntoView({behavior: "smooth", block: "start"});
}

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
    font: {family: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: MUTED, size: 11},
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
  Plotly.react("detail-chart", traces, layout, {displayModeBar: false, responsive: true});
}

function render() {
  if (!data) return;
  place();
  $("summary").innerHTML = summaryHtml();
  drawScatter(); renderTable(); drawDetail();
  $("card").innerHTML = cardHtml();
}

async function load() {
  try {
    const res = await fetch("api/data", {cache: "no-store"});
    if (res.status === 401) { location.reload(); return; }
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
    $("asof").textContent = `자금 기준일 ${data.asof} (미국)`;
    $("stamp").textContent = `마지막 갱신 ${data.time} · 10분마다 자동 갱신 · 자금: State Street (하루 늦음) · 가격: 야후`;
    render();
  } catch (e) {
    $("stamp").textContent = "PC의 서버에 연결하지 못했습니다. 10분 뒤 다시 시도합니다.";
  }
}

$("windows").innerHTML = WINDOWS.map(w => `<button data-w="${w}">${w}일</button>`).join("");
function markWin() { document.querySelectorAll("#windows button").forEach(b => b.classList.toggle("on", +b.dataset.w === win)); }
$("windows").addEventListener("click", e => { if (e.target.dataset.w) { win = +e.target.dataset.w; markWin(); render(); } });
window.addEventListener("resize", () => { if (data) { place(); renderTable(); } });
$("table").addEventListener("click", e => { const tr = e.target.closest("[data-t]"); if (tr) select(tr.dataset.t); });
markWin();
load();
setInterval(load, REFRESH_MS);
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self.reply(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
        elif url.path == "/guide":
            try:
                self.reply(200, "text/html; charset=utf-8", GUIDE.read_bytes())
            except OSError:
                self.reply(404, "text/plain; charset=utf-8", "설명서 파일이 없습니다".encode("utf-8"))
        elif url.path == "/api/data":
            try:
                body = json.dumps(payload(), ensure_ascii=False).encode("utf-8")
            except Exception as e:
                self.reply(500, "text/plain; charset=utf-8", f"{type(e).__name__}: {e}".encode("utf-8"))
                return
            self.reply(200, "application/json; charset=utf-8", body)
        else:
            self.reply(404, "text/plain; charset=utf-8", b"not found")

    def reply(self, status, ctype, body):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # pythonw 로 창 없이 돌 때 stderr 가 없어서 기록하지 않는다
        pass


if __name__ == "__main__":
    if sys.stderr is None:  # pythonw 는 출력 창이 없다
        sys.stdout = sys.stderr = open(os.devnull, "w")
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        sys.exit(f"{PORT} 포트가 이미 사용 중입니다. 서버가 이미 켜져 있을 수 있습니다.")
    server.serve_forever()
