"""위험 지표 대시보드 서버. 실행 후 http://127.0.0.1:8601 접속.

서버는 이 PC(127.0.0.1)에서만 열리고 자체 로그인이 없다. 휴대폰 등 외부에서는 옆 프로젝트
'매매자료정리' 의 ngrok 주소 뒤에 /risk/ 를 붙여 들어온다 (그쪽 app.py 가 로그인 검사 후 전달).
그래서 화면(PAGE)의 주소는 전부 상대 경로(api/data)여야 한다.
  python risk_web.py   서버 실행
"""
import json
import os
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pandas as pd

import risk_data as rd

HOST, PORT = "127.0.0.1", 8601
CHART_DAYS = 252
# 데이터를 다시 받아오는 간격(초)
TTL_MARKET, TTL_FNG, TTL_FRED = 60, 300, 6 * 3600

_cache = {}  # 이름 -> (받은 시각, 값)
_cache_lock = threading.Lock()


def cached(name, ttl, fetch):
    """ttl 안이면 저장된 값, 아니면 새로 받는다. 실패하면 직전 값을 그대로 쓴다."""
    with _cache_lock:
        at, value = _cache.get(name, (None, None))
        if at is not None and time.monotonic() - at < ttl:
            return value
        try:
            value = fetch()
        except Exception:
            # 실패하면 1분 뒤에 다시 시도한다 (화면 요청마다 15초씩 멈추는 것 방지)
            _cache[name] = (time.monotonic() - ttl + 60, value)
            return value
        _cache[name] = (time.monotonic(), value)
        return value


def load_results():
    closes = cached("market", TTL_MARKET, rd.fetch_market)
    extra = {rd.FNG_ID: cached("fng", TTL_FNG, rd.fetch_fng)}
    for series_id in rd.FRED_IDS:
        extra[series_id] = cached(series_id, TTL_FRED, lambda s=series_id: rd.fetch_fred(s))
    return rd.build(closes, {k: v for k, v in extra.items() if v is not None})


def payload():
    results = load_results()
    items = []
    for r in results:
        spec = r["spec"]
        item = {
            "key": spec.key, "name": spec.name, "unit": spec.unit, "decimals": spec.decimals,
            "desc": spec.desc, "warn": spec.warn, "danger": spec.danger,
            "higher_is_worse": spec.higher_is_worse, "judge_name": spec.judge_name,
            "judge_unit": spec.judge_unit,
            "guide": rd.GUIDE[spec.key], "status": r["status"], "error": r["error"],
            "bands": spec.bands, "label": r.get("label"),
            # 가운데 구간(중립)은 안정으로 세되 화면에서는 회색으로 그린다
            "neutral": bool(spec.bands) and r.get("label") == spec.bands[1][0],
        }
        if not r["error"]:
            s = r["display"].iloc[-CHART_DAYS:]
            item.update(
                value=r["value"], prev=r["prev"], judge_value=r["judge_value"],
                asof=r["asof"].strftime("%Y-%m-%d"),
                dates=[d.strftime("%Y-%m-%d") for d in s.index],
                values=[round(float(v), 4) for v in s.values],
            )
        items.append(item)
    return {"time": datetime.now().strftime("%H:%M:%S"), "items": items, "co": co_payload()}


def co_payload():
    """동반 하락 신호. 못 받으면 error 만 담는다 (나머지 카드는 그대로 보이게)."""
    try:
        c = rd.cosignal(cached("market", TTL_MARKET, rd.fetch_market))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    oil = c["oil"].iloc[-63:]                      # 유가는 최근 3개월
    corr = c["corr_series"].iloc[-126:]            # 상관계수는 최근 6개월
    day = lambda idx: [d.strftime("%Y-%m-%d") for d in idx]
    r = lambda s, n: [round(float(v), n) for v in s.values]
    return {
        "error": None, "asof": c["asof"].strftime("%Y-%m-%d"), "session": c["session"],
        "nasdaq": c["nasdaq"], "gold": c["gold"], "btc": c["btc"],
        "tnx": c["tnx"], "tnx_diff": c["tnx_diff"], "verdict": c["verdict"],
        "corr": c["corr"], "corr_label": c["corr_label"], "corr_high": rd.CORR_HIGH, "corr_low": rd.CORR_LOW,
        "corr_dates": day(corr.index), "corr_values": r(corr, 3),
        "oil_dates": day(oil.index), "oil_values": r(oil, 2),
        "oil_ma": r(c["oil_ma"].reindex(oil.index), 2), "oil_down": c["oil_down"],
        "oil_asof": c["oil_asof"].strftime("%Y-%m-%d"),
        # 성명 발표는 미국 동부 오후 2시. 한국 시간은 서머타임에 따라 새벽 3시 또는 4시.
        "fomc": [{"date": d, "kst": (pd.Timestamp(f"{d} 14:00").tz_localize("America/New_York")
                                     .tz_convert("Asia/Seoul").strftime("%m/%d %H시"))} for d in c["fomc"]],
        "fedwatch": c["fedwatch"],
    }


PAGE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>위험 지표 대시보드</title>
<script src="https://cdn.plot.ly/plotly-basic-2.35.2.min.js"></script>
<style>
:root{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;
--grid:#2c2c2a;--ok:#0ca30c;--warn:#fab219;--danger:#d03b3b}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1400px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:1.9rem;margin:0 0 12px}
h2{font-size:1.3rem;margin:26px 0 10px}
.bar{display:flex;gap:10px 20px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
.seg{display:inline-flex;border:1px solid var(--grid);border-radius:8px;overflow:hidden}
.seg button{background:none;border:0;color:var(--ink2);font:inherit;font-size:.9rem;padding:7px 14px;cursor:pointer}
.seg button.on{background:#3987e5;color:#fff;font-weight:600}
.note{color:var(--muted);font-size:.8rem;margin:6px 0}
.banner{border-left:6px solid;border-radius:8px;padding:12px 16px;margin:8px 0 10px}
.banner-title{font-size:1.25rem;font-weight:700}
.banner-sub{color:var(--ink2);font-size:.9rem;margin-top:2px}
.tiles{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.tile{flex:1 1 90px;border:1px solid var(--grid);border-top:4px solid;border-radius:8px;padding:8px 14px;background:var(--surface)}
.tile-label{color:var(--ink2);font-size:.85rem}
.tile-num{font-size:1.9rem;font-weight:700;line-height:1.15}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.card{border:1px solid var(--grid);border-left:5px solid var(--grid);border-radius:10px;padding:14px 14px 8px;min-width:0}
.name{color:var(--ink2);font-size:.9rem}
.value{font-size:1.9rem;font-weight:600;line-height:1.2}
.unit{color:var(--muted);font-size:1rem;font-weight:400;margin-left:2px}
.sub{color:var(--ink2);font-size:.82rem}
.desc{color:var(--muted);font-size:.78rem;margin-top:4px;min-height:2.4em}
.badge{float:right;font-size:.85rem;font-weight:700;border-radius:999px;padding:2px 12px}
.gauge{position:relative;display:flex;gap:2px;height:8px;margin:12px 0 2px}
.gauge>span{flex:1;border-radius:4px}
.pin{position:absolute;top:-5px;width:6px;height:18px;margin-left:-5px;background:var(--ink);border:2px solid var(--page);border-radius:3px;box-sizing:content-box}
.gauge-labels{display:flex;color:var(--muted);font-size:.7rem}
.gauge-labels>span{flex:1;text-align:center}
.chart{height:190px;margin-top:6px}
details{border:1px solid var(--grid);border-radius:8px;padding:10px 14px;margin-top:14px}
summary{cursor:pointer;color:var(--ink2)}
.tablewrap{overflow-x:auto;margin-top:10px}
table{border-collapse:collapse;font-size:.84rem;white-space:nowrap;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 12px;border-bottom:1px solid var(--grid)}
th{color:var(--muted);font-weight:500}
.guide{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px}
.guide-item{border:1px solid var(--grid);border-radius:8px;padding:10px 14px;background:var(--surface)}
.guide-name{font-weight:700;margin-bottom:4px}
.guide-row{color:var(--ink2);font-size:.84rem;margin-top:3px;line-height:1.5}
.tag{display:inline-block;font-size:.72rem;font-weight:700;border-radius:4px;padding:0 6px;margin-right:6px}
.co{border:1px solid var(--grid);border-left:5px solid;border-radius:10px;padding:14px 16px;margin-bottom:14px}
.co-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.moves{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0 6px}
.move{background:var(--surface);border:1px solid var(--grid);border-radius:8px;padding:8px 12px}
.move-num{font-size:1.6rem;font-weight:700;line-height:1.2;font-variant-numeric:tabular-nums}
.cards.co-cards{margin-bottom:6px}
.card a{color:#6aa8f0}
@media (max-width:600px){.moves{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style></head>
<body><main>
<h1>위험 지표 대시보드</h1>
<div class="bar">
  <div class="seg" id="periods"></div>
</div>
<div class="note" id="stamp">불러오는 중…</div>
<div id="summary"></div>
<h2>동반 하락 신호</h2>
<div id="co"></div>
<h2>위험 지표</h2>
<div class="cards" id="cards"></div>
<details><summary>표로 보기 (판정 기준 포함)</summary><div class="tablewrap" id="table"></div></details>
<h2>지표 설명</h2>
<div class="guide" id="guide"></div>
<p class="note">판정 기준은 널리 쓰이는 경험칙이며 투자 권유가 아닙니다. 시세는 무료 출처라 15분가량 늦을 수 있고,
금리차와 하이일드 스프레드는 하루 한 번, 공포탐욕지수는 5분마다 갱신됩니다.</p>
</main>
<script>
const REFRESH_MS = 60000;
const PERIODS = {"1개월": 21, "3개월": 63, "6개월": 126, "1년": 252};
const STATUS = {
  "안정": {color: "#0ca30c", icon: "✓", fg: "#0b0b0b", tint: 0.05},
  "주의": {color: "#fab219", icon: "!", fg: "#0b0b0b", tint: 0.09},
  "위험": {color: "#d03b3b", icon: "✕", fg: "#ffffff", tint: 0.16},
};
const ORDER = ["안정", "주의", "위험"];
const NEUTRAL = {color: "#898781", icon: "–", fg: "#0b0b0b", tint: 0.07};
const look = it => it.neutral ? NEUTRAL : STATUS[it.status];
const INK = "#f0efec", MUTED = "#898781", GRID = "#2c2c2a", SURFACE = "#1a1a19", LINE = "#3987e5";
let period = "6개월", data = null;
const $ = id => document.getElementById(id);

function rgba(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
}
function fmt(v, d, unit = "", sign = false) {
  const s = Math.abs(v).toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d});
  return (v < 0 ? "-" : sign ? "+" : "") + s + unit;
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])); }

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
    font: {family: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: MUTED, size: 11},
    xaxis: {showgrid: false, linecolor: GRID, tickformat: "%m/%d", nticks: 5, fixedrange: true,
            showspikes: true, spikemode: "across", spikethickness: 1, spikecolor: MUTED, spikedash: "solid"},
    yaxis: {gridcolor: GRID, zeroline: false, side: "right", nticks: 4, fixedrange: true, range: [lo - pad, hi + pad]},
  };
  Plotly.react("chart_" + it.key, traces, layout, {displayModeBar: false, responsive: true});
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

function render() {
  if (!data) return;
  $("summary").innerHTML = summaryHtml(data.items);
  $("co").innerHTML = coHtml(data.co);
  drawCo(data.co);
  $("cards").innerHTML = data.items.map(cardHtml).join("");
  data.items.filter(it => !it.error).forEach(drawChart);
  $("table").innerHTML = tableHtml(data.items);
  $("guide").innerHTML = guideHtml(data.items);
}

async function load() {
  try {
    const res = await fetch("api/data", {cache: "no-store"});
    if (res.status === 401) { location.reload(); return; }   // 로그인이 풀림 → 로그인 화면으로
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
    $("stamp").textContent = `마지막 갱신 ${data.time} · 60초마다 자동 갱신`;
    render();
  } catch (e) {
    $("stamp").textContent = "PC의 대시보드 서버에 연결하지 못했습니다. 60초 뒤 다시 시도합니다.";
  }
}

$("periods").innerHTML = Object.keys(PERIODS).map(p => `<button data-p="${p}">${p}</button>`).join("");
function markPeriod() { document.querySelectorAll("#periods button").forEach(b => b.classList.toggle("on", b.dataset.p === period)); }
$("periods").addEventListener("click", e => { if (e.target.dataset.p) { period = e.target.dataset.p; markPeriod(); render(); } });
markPeriod();
load();
setInterval(load, REFRESH_MS);
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self.reply(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
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
        sys.exit(f"{PORT} 포트가 이미 사용 중입니다. 대시보드가 이미 켜져 있을 수 있습니다.")
    server.serve_forever()
