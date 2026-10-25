"""섹터 자금 흐름 설정: 폴더, 비교 기간, 판정 기준, ETF 19개 목록, 판정 이름."""
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "flow_cache"      # 받은 엑셀 (git 제외)
RECORD_DIR = ROOT / "flow_기록"       # 날짜별 판정 기록 (나중에 실제 흐름과 맞춰 보기용)
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
