"""위험 지표 자료 받기: 야후 파이낸스 종가, FRED CSV, CNN 공포탐욕지수."""
from io import StringIO

import pandas as pd
import requests
import yfinance as yf

YF_TICKERS = ["^VIX", "^VIX3M", "^NDX", "^GSPC", "^TNX", "DX-Y.NYB", "KRW=X",
              "^IXIC", "GC=F", "BTC-USD", "BZ=F"]  # 뒤의 4개는 동반 하락 신호용
FRED_IDS = ["T10Y2Y", "BAMLH0A0HYM2"]
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FNG_ID = "FNG"
FNG_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


def fetch_market() -> pd.DataFrame:
    """야후 파이낸스 종가(오늘은 지연된 현재가). 열 = 티커."""
    raw = yf.download(YF_TICKERS, period="3y", interval="1d",
                      auto_adjust=True, progress=False, threads=True)
    closes = raw["Close"]
    closes.index = pd.to_datetime(closes.index).tz_localize(None)
    return closes


def fetch_fred(series_id: str) -> pd.Series:
    """FRED 일별 데이터 (키 없이 받는 CSV). 보통 하루 늦게 올라옵니다."""
    start = (pd.Timestamp.today() - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
    res = requests.get(FRED_URL, params={"id": series_id, "cosd": start}, timeout=15)
    res.raise_for_status()
    df = pd.read_csv(StringIO(res.text))
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    return s.dropna()


def fetch_fng() -> pd.Series:
    """CNN 공포탐욕지수 (비공식 주소). 브라우저처럼 보여야 응답합니다."""
    start = (pd.Timestamp.today() - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    res = requests.get(f"{FNG_URL}/{start}", timeout=15,
                       headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                                              "Chrome/126.0 Safari/537.36"})
    res.raise_for_status()
    data = res.json()
    hist = data["fear_and_greed_historical"]["data"]
    s = pd.Series([p["y"] for p in hist],
                  index=pd.to_datetime([p["x"] for p in hist], unit="ms").normalize())
    s = s[~s.index.duplicated(keep="last")].sort_index()
    now = data["fear_and_greed"]
    s[pd.to_datetime(now["timestamp"]).tz_localize(None).normalize()] = now["score"]
    return s.dropna().round()  # CNN 화면처럼 정수로 맞춰야 표시 숫자와 구간 이름이 어긋나지 않는다
