"""PC가 꺼져 있어도 휴대폰에서 볼 수 있게, 대시보드 두 개를 정적 웹페이지로 만든다.

GitHub Actions 가 30분마다 이 파일을 돌리고 결과(site 폴더)를 GitHub Pages 에 올린다.
화면 파일(web/<이름>/ 의 HTML·CSS·JS)은 PC 서버와 똑같은 것을 쓴다. 화면이 읽는 상대 주소 api/data 에 JSON 파일을 둔다.
원본 코드는 무한질문정리봇 폴더에 있고, 그쪽 `클라우드_올리기.bat` 이 이 폴더로 복사한다.
    python build_site.py site
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import flow_web
import risk_web

ROOT = Path(__file__).parent
GUIDE = ROOT / "섹터자금흐름_설명_읽기.html"


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cloud_page(page: str, stamp: str) -> str:
    """PC 서버 화면 맨 위에 '클라우드 사본' 안내 한 줄을 넣는다."""
    note = ('<div style="background:#1a1a19;border:1px solid #2c2c2a;border-radius:8px;padding:8px 12px;'
            'margin:0 0 12px;color:#c3c2b7;font-size:.82rem">클라우드 사본 · 30분마다 새로 만듦 · '
            f'자료 만든 시각 {stamp} (한국) · <a href="../" style="color:#6aa8f0">처음 화면</a></div>')
    return page.replace("<main>", "<main>" + note, 1)


def main(out: Path):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    errors = []
    for name, web in (("risk", risk_web), ("flow", flow_web)):
        try:
            data = web.payload()
        except Exception as e:  # 한쪽이 실패해도 다른 쪽은 올린다
            errors.append(f"{name}: {type(e).__name__}: {e}")
            continue
        write(out / name / "api" / "data", json.dumps(data, ensure_ascii=False))
        for f in (ROOT / "web" / name).iterdir():   # 화면 파일 (HTML·CSS·JS)
            text = f.read_text(encoding="utf-8")
            write(out / name / f.name, cloud_page(text, stamp) if f.name == "index.html" else text)
    write(out / "flow" / "guide" / "index.html", GUIDE.read_text(encoding="utf-8"))
    write(out / ".nojekyll", "")
    write(out / "index.html", f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>시장 대시보드</title>
<style>body{{margin:0;background:#0d0d0d;color:#f0efec;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:560px;margin:0 auto;padding:28px 16px}}h1{{font-size:1.6rem}}
a.big{{display:block;border:1px solid #2c2c2a;background:#1a1a19;border-radius:10px;padding:16px;margin:12px 0;
color:#f0efec;text-decoration:none;font-size:1.15rem;font-weight:600}}a.big span{{display:block;color:#898781;font-size:.85rem;font-weight:400;margin-top:4px}}
p{{color:#898781;font-size:.85rem}}</style></head>
<body><main><h1>시장 대시보드</h1>
<a class="big" href="risk/">위험 지표 대시보드<span>VIX · 금리 · 환율 · 동반 하락 신호</span></a>
<a class="big" href="flow/">미국 섹터 자금 흐름<span>State Street ETF 19개 자금 유입</span></a>
<p>클라우드 사본 · 30분마다 새로 만듦 · 자료 만든 시각 {stamp} (한국)<br>
PC가 켜져 있을 때는 기존 주소가 더 빠릅니다 (60초 갱신).</p>
{"<p>이번에 못 만든 화면: " + " / ".join(errors) + "</p>" if errors else ""}
</main></body></html>
""")
    print("만든 시각", stamp, "실패", errors or "없음")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "site"))
