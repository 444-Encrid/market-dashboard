"""위험 지표 대시보드 서버. 실행 후 http://127.0.0.1:8601 접속.

서버는 이 PC(127.0.0.1)에서만 열리고 자체 로그인이 없다. 휴대폰 등 외부에서는 옆 프로젝트
'매매자료정리' 의 ngrok 주소 뒤에 /risk/ 를 붙여 들어온다 (그쪽 app.py 가 로그인 검사 후 전달).
화면은 web/risk/ 폴더(HTML·CSS·JS)이고, 그 안의 주소는 전부 상대 경로(api/data)여야 한다.
  python risk_web.py   서버 실행
"""
import threading
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

import risk_data as rd
import webcommon

HOST, PORT = "127.0.0.1", 8601
WEB = Path(__file__).resolve().parent / "web" / "risk"
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


if __name__ == "__main__":
    webcommon.serve(HOST, PORT, webcommon.make_handler(WEB, {"/api/data": payload}), "대시보드")
