"""미국 섹터 자금 흐름: State Street ETF 19개의 주식 수 변화로 섹터별 실제 자금 유입을 계산한다.

미국은 투자자별 순매수를 매일 공개하지 않으므로 ETF 자금 유입으로 대신한다.
  하루 유입 = (오늘 주식 수 − 어제 주식 수) × 오늘 NAV
ETF 는 돈이 들어오면 주식을 새로 찍고 나가면 없애므로, 이 값이 그날 실제로 오간 돈이다.

데이터: State Street 가 공개하는 NAV 기록 엑셀 (키 불필요, 하루 늦게 올라옴).
가격: 야후 파이낸스 (S&P500 대비 초과수익, 거래대금 관심도).
  python flow_data.py   계산 결과를 표로 출력 (확인용)

나눠 둔 부분: 설정·ETF 목록 flow_config, 자료 받기 flow_fetch, 판정 flow_judge. 여기는 ETF별 분석·합계·기록 저장.
flow_web 과 설명서 만들기는 이 모듈(fd)만 불러 쓰므로, 나눠 놓은 이름도 여기서 다시 내보낸다.
"""
import json

import numpy as np
import pandas as pd

from flow_config import (BENCH, CACHE_DIR, CHART_DAYS, ETFS, HIGH, LABELS, LOW, RANK_DAYS,  # noqa: F401
                         RECORD_DIR, ROOT, SECTORS, WINDOWS, Etf)
from flow_fetch import daily_flow, download, fetch_prices, load_nav  # noqa: F401
from flow_judge import BIG_DAY, INFLOW, OUTFLOW, _rank, against, judge  # noqa: F401


def analyze(etf, nav, close, dollar):
    flow, splits = daily_flow(nav)
    year = flow.iloc[-252:].abs()
    big = BIG_DAY * float(year[year > 0].median())
    asof = flow.index[-1]
    # 가격도 자금 기록의 마지막 날에 맞춰 같은 기간으로 비교한다
    c = close.loc[:asof]
    out = {"ticker": etf.ticker, "name": etf.name, "parent": etf.parent, "asof": asof.strftime("%Y-%m-%d"),
           "tna": float(nav["tna"].iloc[-1]), "splits": [d.strftime("%Y-%m-%d") for d in splits if d > asof - pd.Timedelta(days=400)],
           "windows": {}}
    tna = nav["tna"].reindex(flow.index)
    for w in WINDOWS:
        if len(flow) < w + 1:
            out["windows"][w] = None
            continue
        roll = flow.rolling(w).sum()
        base = tna.shift(w)
        pct_series = roll / base * 100
        f, pct = float(roll.iloc[-1]), float(pct_series.iloc[-1])
        rank = _rank(pct_series, pct)
        excess = ret = None
        if etf.ticker in c and len(c) > w and not np.isnan(c[etf.ticker].iloc[-w - 1]):
            ret = float(c[etf.ticker].iloc[-1] / c[etf.ticker].iloc[-w - 1] - 1) * 100
            bench = float(c[BENCH].iloc[-1] / c[BENCH].iloc[-w - 1] - 1) * 100
            excess = ret - bench
        seg = flow.iloc[-w:]
        top = seg.idxmax() if f >= 0 else seg.idxmin()   # 순유입과 같은 방향으로 가장 큰 하루
        out["windows"][w] = {
            "flow": f, "pct": pct, "rank": rank, "in_days": int((seg > 0).sum()), "out_days": int((seg < 0).sum()),
            "ret": ret, "excess": excess, "label": judge(rank, f, excess),
            "top_date": top.strftime("%Y-%m-%d"), "top_flow": float(seg[top]),
            # 순유입이 0에 가까우면 비율이 의미 없으므로 순자산의 0.5% 이상일 때만 센다
            "top_share": float(seg[top] / f * 100) if abs(pct) >= 0.5 else None,
            "round_trip": bool((seg > big).any() and (seg < -big).any()),
        }
    # 거래 관심: 최근 5일 평균 거래대금 ÷ 직전 15일 평균
    d = dollar[etf.ticker].loc[:asof].dropna() if etf.ticker in dollar else pd.Series(dtype=float)
    out["interest"] = float(d.iloc[-5:].mean() / d.iloc[-20:-5].mean()) if len(d) >= 20 else None
    for w in WINDOWS:
        if out["windows"][w]:
            out["windows"][w]["against"] = against(out, w)
    # 차트: 1년 누적 유입(억 달러)과 S&P500 대비 상대 가격(시작=100)
    fl = flow.iloc[-CHART_DAYS:]
    rel = (c[etf.ticker] / c[BENCH]).dropna().iloc[-CHART_DAYS:] if etf.ticker in c else pd.Series(dtype=float)
    out["chart"] = {
        "dates": [x.strftime("%Y-%m-%d") for x in fl.index],
        "cum": [round(v / 1e8, 2) for v in fl.cumsum()],
        "daily": [round(v / 1e8, 2) for v in fl],
        "rel_dates": [x.strftime("%Y-%m-%d") for x in rel.index],
        "rel": [round(v, 2) for v in (rel / rel.iloc[0] * 100)] if len(rel) else [],
    }
    return out


def build(close, dollar):
    """ETF 19개 분석 결과와 시장 요약. 한 ETF가 실패하면 그 줄만 오류로 남긴다."""
    items = []
    for e in ETFS:
        try:
            items.append(analyze(e, load_nav(download(e.ticker)), close, dollar))
        except Exception as ex:
            items.append({"ticker": e.ticker, "name": e.name, "parent": e.parent, "error": f"{type(ex).__name__}: {ex}"})
    ok = [it for it in items if "error" not in it]
    asof = max((it["asof"] for it in ok), default=None)
    market = {}
    for w in WINDOWS:
        sec = [it["windows"][w] for it in ok if it["parent"] is None and it["windows"].get(w)]
        b = close[BENCH].loc[:asof].dropna() if asof else pd.Series(dtype=float)
        market[w] = {
            "total": sum(x["flow"] for x in sec),
            "in_count": sum(x["flow"] > 0 for x in sec), "count": len(sec),
            "spy": float(b.iloc[-1] / b.iloc[-w - 1] - 1) * 100 if len(b) > w else None,
        }
    return {"asof": asof, "items": items, "market": market}


def save_record(result):
    """그날 판정을 한 번만 저장한다 (같은 기준일 파일이 있으면 그대로 둔다)."""
    if not result["asof"]:
        return
    RECORD_DIR.mkdir(exist_ok=True)
    path = RECORD_DIR / f"{result['asof']}.json"
    if path.exists():
        return
    rows = {it["ticker"]: {str(w): ({k: v[k] for k in ("flow", "pct", "rank", "excess", "label")} if v else None)
                           for w, v in it["windows"].items()}
            for it in result["items"] if "error" not in it}
    path.write_text(json.dumps({"asof": result["asof"], "etfs": rows}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    res = build(*fetch_prices())
    print("기준일", res["asof"])
    for it in res["items"]:
        if "error" in it:
            print(it["ticker"], "오류", it["error"])
            continue
        w = it["windows"][20]
        print(f'{it["ticker"]:5} {it["name"]:14} 20일 {w["flow"] / 1e8:+8.1f}억$ {w["pct"]:+6.1f}% '
              f'평소대비 {w["rank"] * 100:3.0f}% 초과 {w["excess"]:+6.1f}% {w["label"]} 관심 {it["interest"]:.2f} 분할 {it["splits"]}')
    print(res["market"])
