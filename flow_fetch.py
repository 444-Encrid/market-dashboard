"""자료 받기: State Street NAV 기록 엑셀(주식 수·NAV)과 야후 가격·거래대금. 하루 유입 계산과 분할 보정."""
import time

import pandas as pd
import requests
import yfinance as yf

from flow_config import BENCH, CACHE_DIR, ETFS

URL = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-{}.xlsx"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


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
