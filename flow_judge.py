"""판정: 평소 대비 순위, 다섯 가지 판정 이름, 판정을 의심할 반대 근거."""
from flow_config import HIGH, LOW, RANK_DAYS, WINDOWS


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
