"""위험 지표를 안정/주의/위험으로 판정한다. 목록은 risk_specs, 자료 받기는 risk_fetch, 동반 하락 신호는 cosignal.

risk_web 은 이 모듈 하나(rd)만 불러 쓰므로, 나눠 놓은 이름도 여기서 다시 내보낸다.
"""
import pandas as pd

from cosignal import CORR_HIGH, CORR_LOW, cosignal  # noqa: F401
from risk_fetch import FNG_ID, FRED_IDS, fetch_fng, fetch_fred, fetch_market  # noqa: F401
from risk_specs import DANGER, GUIDE, MONTH, OK, SPECS, WARN, YEAR, Spec  # noqa: F401


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
