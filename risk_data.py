# 위험 지표 데이터를 무료 출처(야후 파이낸스, FRED)에서 가져와 안정/주의/위험으로 판정합니다.
from dataclasses import dataclass
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

MONTH = 21  # 1개월 = 약 21거래일
YEAR = 252  # 1년 = 약 252거래일

OK, WARN, DANGER = "안정", "주의", "위험"


@dataclass
class Spec:
    key: str
    name: str
    unit: str
    decimals: int
    desc: str
    # 판정 기준. 숫자만 바꾸면 기준이 바뀝니다.
    warn: float
    danger: float
    higher_is_worse: bool
    # 판정에 쓰는 값이 화면에 보이는 값과 다를 때의 이름 (예: 1개월 변화)
    judge_name: str = ""
    judge_unit: str = ""
    # 안정/주의/위험 대신 구간 이름으로 보여줄 지표용. (이름, 이 값 미만까지, 요약에 셀 상태) 순서대로 3개.
    # 가운데 구간은 화면에서 회색(중립)으로 그립니다. bands 가 있으면 warn, danger 는 쓰지 않습니다.
    bands: tuple = ()


SPECS = [
    Spec("vix", "VIX (공포지수)", "", 2,
         "S&P500 옵션으로 본 향후 변동성. 20 이상이면 불안, 30 이상이면 공포 구간.",
         warn=20, danger=30, higher_is_worse=True),
    Spec("vix_term", "VIX 기간구조 (VIX ÷ VIX3M)", "", 3,
         "단기 공포가 3개월 공포보다 커지면(1 이상) 시장이 급하게 겁먹은 상태.",
         warn=0.9, danger=1.0, higher_is_worse=True),
    Spec("fng", "공포탐욕지수 (CNN)", "", 0,
         "0은 극단적 공포, 100은 극단적 탐욕. 44 이하는 공포, 45~54는 중립, 55 이상은 탐욕.",
         warn=45, danger=45, higher_is_worse=False,
         bands=(("공포", 45, DANGER), ("중립", 55, OK), ("탐욕", 100, OK))),
    Spec("ndx_dd", "나스닥100 고점 대비 낙폭", "%", 1,
         "최근 1년 최고가에서 얼마나 내려왔는지. -10%는 조정, -20%는 약세장.",
         warn=-10, danger=-20, higher_is_worse=False),
    Spec("spx_ma200", "S&P500 200일선 이격", "%", 1,
         "200일 평균가보다 얼마나 위/아래인지. 아래로 내려가면 장기 추세 약화.",
         warn=0, danger=-5, higher_is_worse=False),
    Spec("t10y2y", "장단기 금리차 (10년 − 2년)", "%p", 2,
         "0 아래(역전)는 대표적인 경기침체 선행 신호.",
         warn=0.25, danger=0, higher_is_worse=False),
    Spec("hy", "하이일드 스프레드", "%p", 2,
         "부실 기업 채권의 가산금리. 벌어질수록 신용 불안이 커진다는 뜻.",
         warn=4, danger=6, higher_is_worse=True),
    Spec("tnx", "미국 10년물 금리", "%", 2,
         "금리가 한 달 새 급등하면 성장주에 부담. 최근 1개월 상승폭으로 판정.",
         warn=0.3, danger=0.5, higher_is_worse=True,
         judge_name="1개월 변화", judge_unit="%p"),
    Spec("dxy", "달러인덱스", "", 2,
         "달러가 한 달 새 급등하면 위험자산 회피 신호. 최근 1개월 상승률로 판정.",
         warn=2, danger=4, higher_is_worse=True,
         judge_name="1개월 변화", judge_unit="%"),
    Spec("krw", "원/달러 환율", "원", 1,
         "환율 급등은 해외주식 신규 매수 부담. 최근 1개월 상승률로 판정.",
         warn=2, danger=4, higher_is_worse=True,
         judge_name="1개월 변화", judge_unit="%"),
]


# 대시보드 맨 아래 설명란에 나오는 글. key: (의미, 위험한 상황)
GUIDE = {
    "vix": ("S&P500 옵션 가격으로 계산한, 앞으로 30일간 예상되는 주가 출렁임의 크기입니다.",
            "20을 넘으면 불안이 커지는 구간이고, 30을 넘으면 급락장에서 나타나는 공포 구간입니다."),
    "vix_term": ("1개월 공포(VIX)를 3개월 공포(VIX3M)로 나눈 값입니다. 평소에는 1보다 작습니다.",
                 "1을 넘으면 먼 미래보다 당장이 더 무섭다는 뜻으로, 급락이 진행 중일 때 주로 나타납니다."),
    "fng": ("CNN이 주가 흐름, 풋/콜 비율, 안전자산 수요 등 7가지를 합쳐 만든 투자 심리 점수(0~100)입니다.",
            "44 이하(공포)는 투자자들이 겁먹고 주식을 파는 구간이고, 25 이하는 시장이 크게 흔들리는 극단적 공포입니다. 55 이상(탐욕)은 낙관이 우세한 구간입니다."),
    "ndx_dd": ("나스닥100이 최근 1년 최고가에서 몇 % 내려와 있는지 보여줍니다.",
               "-10% 아래는 조정장, -20% 아래는 약세장으로 봅니다. 레버리지 ETF는 낙폭이 이보다 훨씬 커집니다."),
    "spx_ma200": ("S&P500이 200일 평균 가격보다 몇 % 위나 아래에 있는지로, 장기 추세를 보는 기준입니다.",
                  "0% 아래로 내려가면 장기 상승 추세가 꺾였다는 신호이고, -5% 아래면 하락 추세가 굳어진 상태로 봅니다."),
    "t10y2y": ("미국 10년 국채 금리에서 2년 국채 금리를 뺀 값입니다. 보통은 플러스입니다.",
               "0 아래(역전)로 내려가면 과거에 경기침체가 뒤따른 경우가 많았습니다."),
    "hy": ("신용등급이 낮은 기업의 채권 금리가 국채보다 얼마나 더 높은지로, 부도 걱정의 크기를 보여줍니다.",
           "4%p를 넘으면 신용 불안이 번지는 중이고, 6%p를 넘으면 금융 스트레스가 큰 상태입니다."),
    "tnx": ("미국 정부가 10년간 돈을 빌릴 때의 금리로, 주식 가치를 매기는 기준이 됩니다.",
            "한 달 사이 0.3%p 이상 오르면 성장주와 기술주에 부담이 되고, 0.5%p 이상이면 충격 수준입니다."),
    "dxy": ("유로, 엔 등 주요 6개 통화와 비교한 달러의 가치입니다.",
            "한 달 사이 2% 이상 오르면 돈이 안전자산으로 몰린다는 신호이고, 4% 이상이면 위험자산 회피가 강한 상태입니다."),
    "krw": ("1달러를 사는 데 필요한 원화입니다.",
            "한 달 사이 2% 이상 오르면 해외주식 매수 비용이 눈에 띄게 늘고, 4% 이상이면 금융시장 불안 신호로 봅니다."),
}


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


def _band(spec: Spec, value: float) -> tuple:
    for band in spec.bands[:-1]:
        if value < band[1]:
            return band
    return spec.bands[-1]


def label(spec: Spec, value: float, status: str) -> str:
    """배지에 쓸 이름. bands 가 있으면 구간 이름(공포/중립/탐욕), 없으면 상태 그대로."""
    return _band(spec, value)[0] if spec.bands else status


def judge(spec: Spec, value: float) -> str:
    if spec.bands:
        return _band(spec, value)[2]
    if spec.higher_is_worse:
        if value >= spec.danger:
            return DANGER
        return WARN if value >= spec.warn else OK
    if value <= spec.danger:
        return DANGER
    return WARN if value <= spec.warn else OK


def _series(spec: Spec, closes: pd.DataFrame, fred: dict) -> tuple[pd.Series, pd.Series]:
    """(화면에 그릴 값, 판정에 쓸 값)"""
    def col(ticker):
        return closes[ticker].dropna()

    if spec.key == "vix":
        s = col("^VIX")
    elif spec.key == "vix_term":
        s = (closes["^VIX"] / closes["^VIX3M"]).dropna()
    elif spec.key == "fng":
        s = fred[FNG_ID]
    elif spec.key == "ndx_dd":
        ndx = col("^NDX")
        s = ((ndx / ndx.rolling(YEAR, min_periods=MONTH).max() - 1) * 100).dropna()
    elif spec.key == "spx_ma200":
        spx = col("^GSPC")
        s = ((spx / spx.rolling(200).mean() - 1) * 100).dropna()
    elif spec.key == "t10y2y":
        s = fred["T10Y2Y"]
    elif spec.key == "hy":
        s = fred["BAMLH0A0HYM2"]
    elif spec.key == "tnx":
        s = col("^TNX")
        return s, (s - s.shift(MONTH)).dropna()
    elif spec.key == "dxy":
        s = col("DX-Y.NYB")
        return s, ((s / s.shift(MONTH) - 1) * 100).dropna()
    elif spec.key == "krw":
        s = col("KRW=X")
        return s, ((s / s.shift(MONTH) - 1) * 100).dropna()
    else:
        raise KeyError(spec.key)
    return s, s


# ---------- 동반 하락 신호 (2026-10-25) ----------
# 영상(2026-10-22 하락 해설)의 관점: 주식과 피난처(금·비트코인)가 같이 빠지면 "다 팔고 현금으로" 신호.
# 검증된 규칙이 아니라서 위 안정/주의/위험 개수에는 넣지 않고 따로 보여 준다.
STRONG_DROP = -1.0             # 나스닥과 금이 둘 다 이 값(%) 이하면 강한 동반 하락
CORR_DAYS = 20                 # 주식·금 상관계수를 재는 거래일 수
CORR_HIGH, CORR_LOW = 0.5, 0.2  # 이상이면 같이 움직임, 미만이면 따로 움직임 (사이는 약간 같이)
OIL_MA = 20
# FOMC 둘째 날(성명 발표일, 미국 시간). 한국 시간으로는 다음 날 새벽 3시(서머타임) 또는 4시.
FOMC_DATES = ["2026-10-28", "2026-12-09"]
FEDWATCH_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"


def _session(asof: pd.Timestamp) -> str:
    """기준일 값이 장 마감 값인지, 아직 장중 값인지 (뉴욕 시간 기준)."""
    now = pd.Timestamp.now(tz="America/New_York")
    if asof.date() == now.date() and now.hour < 16:
        return "장중 (약 15분 지연)"
    return "마감"


def cosignal(closes: pd.DataFrame) -> dict:
    """오늘의 동반 하락 판, 유가 추이, 다음 연준 회의, 주식·금 상관계수."""
    nas = closes["^IXIC"].dropna()
    # 비트코인·금은 주말·휴일에도 값이 있어서 나스닥 거래일에 맞춘다 (빈 날은 직전 값)
    a = closes[["^IXIC", "GC=F", "BTC-USD", "^TNX"]].ffill().reindex(nas.index)
    pct = a.pct_change() * 100
    last = nas.index[-1]
    n, g = float(pct["^IXIC"].iloc[-1]), float(pct["GC=F"].iloc[-1])
    if n <= STRONG_DROP and g <= STRONG_DROP:
        verdict = "강한 동반 하락"
    elif n < 0 and g < 0:
        verdict = "동반 하락"
    else:
        verdict = "동반 하락 아님"

    corr = pct["^IXIC"].rolling(CORR_DAYS).corr(pct["GC=F"]).dropna()
    c = float(corr.iloc[-1])
    corr_label = ("같이 움직임 (위험 회피 매도 가능성)" if c >= CORR_HIGH
                  else "따로 움직임 (평소 모습)" if c < CORR_LOW else "약간 같이 움직임")

    oil = closes["BZ=F"].dropna()
    ma = oil.rolling(OIL_MA).mean()
    oil_down = bool(oil.iloc[-1] < ma.iloc[-1])

    today = pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None)
    upcoming = [d for d in FOMC_DATES if pd.Timestamp(d) >= today]

    return {
        "asof": last, "session": _session(last),
        "nasdaq": n, "gold": g, "btc": float(pct["BTC-USD"].iloc[-1]),
        "tnx": float(a["^TNX"].iloc[-1]), "tnx_diff": float(a["^TNX"].diff().iloc[-1]),
        "verdict": verdict,
        "corr": c, "corr_label": corr_label, "corr_series": corr,
        "oil": oil, "oil_ma": ma, "oil_down": oil_down, "oil_asof": oil.index[-1],
        "fomc": upcoming, "fedwatch": FEDWATCH_URL,
    }


def build(closes: pd.DataFrame | None, fred: dict) -> list[dict]:
    """지표별 결과. 데이터를 못 받은 지표는 error 에 이유가 들어갑니다."""
    results = []
    for spec in SPECS:
        try:
            display, judged = _series(spec, closes, fred)
            if len(display) < 2 or judged.empty:
                raise ValueError("데이터가 비어 있습니다")
            results.append({
                "spec": spec,
                "display": display,
                "judged": judged,
                "value": float(display.iloc[-1]),
                "prev": float(display.iloc[-2]),
                "judge_value": float(judged.iloc[-1]),
                "status": judge(spec, float(judged.iloc[-1])),
                "label": label(spec, float(judged.iloc[-1]), judge(spec, float(judged.iloc[-1]))),
                "asof": display.index[-1],
                "error": None,
            })
        except Exception as e:
            results.append({"spec": spec, "status": None, "error": f"{type(e).__name__}: {e}"})
    return results
