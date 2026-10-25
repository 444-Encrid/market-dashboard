"""동반 하락 신호 (2026-10-25): 오늘의 판, 유가 추이, 다음 연준 회의, 주식·금 상관계수.

영상(2026-10-22 하락 해설)의 관점: 주식과 피난처(금·비트코인)가 같이 빠지면 "다 팔고 현금으로" 신호.
검증된 규칙이 아니라서 위험 지표의 안정/주의/위험 개수에는 넣지 않고 따로 보여 준다."""
import pandas as pd

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
