"""미국 섹터 자금 흐름: State Street ETF 19개의 주식 수 변화로 섹터별 실제 자금 유입을 계산한다.

미국은 투자자별 순매수를 매일 공개하지 않으므로 ETF 자금 유입으로 대신한다.
  하루 유입 = (오늘 주식 수 − 어제 주식 수) × 오늘 NAV
ETF 는 돈이 들어오면 주식을 새로 찍고 나가면 없애므로, 이 값이 그날 실제로 오간 돈이다.

데이터: State Street 가 공개하는 NAV 기록 엑셀 (키 불필요, 하루 늦게 올라옴).
가격: 야후 파이낸스 (S&P500 대비 초과수익, 거래대금 관심도).
  python flow_data.py   계산 결과를 표로 출력 (확인용)
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "flow_cache"      # 받은 엑셀 (git 제외)
RECORD_DIR = ROOT / "flow_기록"       # 날짜별 판정 기록 (나중에 실제 흐름과 맞춰 보기용)
URL = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-{}.xlsx"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
BENCH = "SPY"
WINDOWS = (5, 20, 60, 120)
RANK_DAYS = 756       # 평소와 비교할 기간 (약 3년)
CHART_DAYS = 252
HIGH, LOW = 0.7, 0.3  # 평소 대비 상위 30% 이상이면 유입이 많은 편, 하위 30% 이하면 유출이 많은 편


@dataclass(frozen=True)
class Etf:
    ticker: str
    name: str
    parent: str | None = None   # 세부 업종이면 속한 섹터 ETF


ETFS = [
    Etf("XLK", "기술"), Etf("XLC", "통신서비스"), Etf("XLY", "경기소비재"), Etf("XLP", "필수소비재"),
    Etf("XLE", "에너지"), Etf("XLF", "금융"), Etf("XLV", "헬스케어"), Etf("XLI", "산업재"),
    Etf("XLB", "소재"), Etf("XLRE", "부동산"), Etf("XLU", "유틸리티"),
    Etf("XSD", "반도체 (동일가중)", "XLK"), Etf("XSW", "소프트웨어 (동일가중)", "XLK"),
    Etf("XHB", "주택건설", "XLY"), Etf("XOP", "석유가스 개발", "XLE"), Etf("KRE", "지역은행", "XLF"),
    Etf("XBI", "바이오 (동일가중)", "XLV"), Etf("XAR", "항공우주·방산", "XLI"), Etf("XME", "금속·광업", "XLB"),
]
SECTORS = [e.ticker for e in ETFS if e.parent is None]

# 판정 이름 -> (색 이름, 설명). 화면이 같은 순서로 그린다.
LABELS = {
    "자금·가격 동반": "평소보다 돈이 많이 들어오고 S&P500보다도 올랐다",
    "자금만 유입": "돈은 많이 들어오는데 가격은 S&P500보다 약하다",
    "뚜렷하지 않음": "자금 흐름이 평소 수준이다",
    "가격만 강세": "가격은 S&P500보다 강한데 돈은 빠져나간다",
    "자금·가격 이탈": "평소보다 돈이 많이 빠지고 가격도 S&P500보다 약하다",
}


def download(ticker, max_age=6 * 3600):
    """엑셀을 받아 저장한다. max_age 안에 받은 파일이 있으면 다시 받지 않는다. 실패하면 이전 파일을 쓴다."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{ticker.lower()}.xlsx"
    if path.exists() and time.time() - path.stat().st_mtime < max_age:
        return path
    try:
        r = requests.get(URL.format(ticker.lower()), headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        if not r.content.startswith(b"PK") or len(r.content) < 5000:   # 엑셀이 아닌 안내 화면이 온 경우
            raise ValueError("엑셀 파일이 아님")
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(r.content)
        tmp.replace(path)
    except Exception:
        if not path.exists():
            raise
    return path


def load_nav(path):
    """날짜, NAV, 주식 수, 순자산. 값이 '-' 인 옛날 날짜는 버린다."""
    d = pd.read_excel(path, header=3).iloc[:, :4]
    d.columns = ["date", "nav", "shares", "tna"]
    d["date"] = pd.to_datetime(d["date"], format="%d-%b-%Y", errors="coerce")
    for c in ("nav", "shares", "tna"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna().drop_duplicates("date").set_index("date").sort_index()
    return d[d["shares"] > 0]


def daily_flow(nav):
    """하루 유입(달러). 주식 분할일은 주식 수가 배로 바뀌고 NAV가 같은 비율로 줄어드므로 그만큼 빼고 센다."""
    prev = nav["shares"].shift()
    ratio = nav["shares"] / prev
    nav_ratio = nav["nav"] / nav["nav"].shift()
    split = ((ratio > 1.3) | (ratio < 0.77)) & ((ratio * nav_ratio - 1).abs() < 0.15)
    k = pd.Series(1.0, index=nav.index)
    k[split & (ratio > 1)] = ratio[split & (ratio > 1)].round()
    k[split & (ratio < 1)] = 1 / (1 / ratio[split & (ratio < 1)]).round()
    return ((nav["shares"] - prev * k) * nav["nav"]).iloc[1:], nav.index[split].tolist()


def fetch_prices():
    """배당 포함 종가와 거래대금(달러). S&P500 비교용 SPY 포함."""
    tickers = [e.ticker for e in ETFS] + [BENCH]
    raw = yf.download(tickers, period="2y", auto_adjust=True, progress=False, threads=True)
    close = raw["Close"].dropna(how="all")
    dollar = (raw["Close"] * raw["Volume"]).reindex(close.index)
    close.index = close.index.tz_localize(None)
    dollar.index = close.index
    return close, dollar


def _rank(series, value):
    """value 가 지난 RANK_DAYS 동안의 series 중 몇 % 위치인지 (0~1)."""
    s = series.dropna().iloc[-RANK_DAYS:]
    return float((s < value).mean()) if len(s) >= 60 else None


def judge(rank, flow, excess):
    if rank is None or excess is None:
        return None
    if rank >= HIGH and flow > 0:
        return "자금·가격 동반" if excess > 0 else "자금만 유입"
    if rank <= LOW and flow < 0:
        return "가격만 강세" if excess > 0 else "자금·가격 이탈"
    return "뚜렷하지 않음"


INFLOW = ("자금·가격 동반", "자금만 유입")
OUTFLOW = ("가격만 강세", "자금·가격 이탈")
BIG_DAY = 5           # 1년 하루 유입 크기(중앙값)의 5배를 넘으면 "큰 날"
ONE_DAY_SHARE = 60    # 20일 이상 기간에서 순유입의 60% 이상이 하루에 몰리면 반대 근거로 본다


def against(out, w):
    """판정과 어긋나는 근거. 유입 쪽·유출 쪽 판정에만 붙인다."""
    x = out["windows"].get(w)
    if not x or x["label"] not in INFLOW + OUTFLOW:
        return []
    inflow = x["label"] in INFLOW
    word = "유입" if inflow else "유출"
    res = []
    if x["round_trip"]:
        res.append("같은 기간에 큰 유입과 큰 유출이 함께 있다 (리밸런싱 왕복 의심)")
    if w >= 20 and x["top_share"] is not None and x["top_share"] >= ONE_DAY_SHARE:
        day = x["top_date"][5:].replace("-", "/")
        if x["top_share"] > 100:
            res.append(f"하루({day}) {word}이 기간 전체 순{word}보다 크다 ({x['top_share']:.0f}%)")
        else:
            res.append(f"순{word}의 {x['top_share']:.0f}%가 하루({day})에 몰렸다")
    same = x["in_days"] if inflow else x["out_days"]
    if same < w / 2:
        res.append(f"{word}한 날이 {same}/{w}일로 절반이 안 된다")
    for o in WINDOWS:
        y = out["windows"].get(o)
        if o != w and y and y["label"] in (OUTFLOW if inflow else INFLOW):
            res.append(f"{o}일 판정은 반대쪽인 {y['label']}")
    if inflow and out["interest"] is not None and out["interest"] < 0.8:
        res.append(f"거래 관심이 줄고 있다 ({out['interest']:.2f}배)")
    return res


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
