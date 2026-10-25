"""미국 섹터 자금 흐름 서버. 실행 후 http://127.0.0.1:8602 접속.

서버는 이 PC(127.0.0.1)에서만 열린다. 휴대폰 등 외부에서는 옆 프로젝트 '매매자료정리' 의 ngrok 주소 뒤에 /flow/ 를 붙여 들어온다.
화면은 web/flow/ 폴더(HTML·CSS·JS)이고, 그 안의 주소는 전부 상대 경로(api/data)여야 한다.
  python flow_web.py   서버 실행
"""
import math
import threading
import time
from datetime import datetime

import flow_data as fd
import webcommon

HOST, PORT = "127.0.0.1", 8602
# 설명서 PC용 사본. /guide 로 내보내 휴대폰에서도 같은 로그인으로 읽게 한다 (아티팩트 링크는 claude.ai 로그인이 필요)
GUIDE = fd.ROOT / "섹터자금흐름_설명" / "섹터자금흐름_설명_읽기.html"
# 가격은 1시간, 계산 결과는 10분마다 새로 만든다 (엑셀은 flow_data.download 가 6시간마다 다시 받는다)
TTL_PRICES, TTL_RESULT = 3600, 600

_lock = threading.Lock()
_state = {"prices": (None, None), "result": (None, None)}


def _clean(o):
    """JSON 에 NaN 이 들어가지 않게 바꾼다."""
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else o
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


def payload():
    with _lock:
        at, result = _state["result"]
        if at is not None and time.monotonic() - at < TTL_RESULT:
            return result
        p_at, prices = _state["prices"]
        if p_at is None or time.monotonic() - p_at > TTL_PRICES:
            try:
                prices = fd.fetch_prices()
                _state["prices"] = (time.monotonic(), prices)
            except Exception:
                if prices is None:
                    raise
        res = fd.build(*prices)
        try:
            fd.save_record(res)
        except OSError:
            pass
        res = _clean(res)
        res["time"] = datetime.now().strftime("%H:%M:%S")
        res["labels"] = fd.LABELS
        _state["result"] = (time.monotonic(), res)
        return res


if __name__ == "__main__":
    handler = webcommon.make_handler(fd.ROOT / "web" / "flow", {"/api/data": payload}, {"/guide": GUIDE})
    webcommon.serve(HOST, PORT, handler, "서버")
