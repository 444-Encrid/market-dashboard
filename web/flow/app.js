// 화면 배치, 업종 고르기, 그리기, 자료 받기, 기간 버튼
let win = 5, data = null, selected = "XLK";

const wide = () => window.innerWidth >= 1100;
// 넓으면 요약과 카드를 오른쪽 판에, 좁으면 요약은 맨 위, 카드는 표 아래에 둔다
function place() {
  const side = $("side");
  if (wide()) { side.append($("summary"), $("card")); }
  else { $("summary-slot").append($("summary")); $("card-slot").append($("card")); }
}
function select(t) {
  selected = t; renderTable(); drawDetail(); $("card").innerHTML = cardHtml();
  if (!wide()) $("card").scrollIntoView({behavior: "smooth", block: "start"});
}

function render() {
  if (!data) return;
  place();
  $("summary").innerHTML = summaryHtml();
  drawScatter(); renderTable(); drawDetail();
  $("card").innerHTML = cardHtml();
}

async function load() {
  try {
    const res = await fetch("api/data", {cache: "no-store"});
    if (res.status === 401) { location.reload(); return; }
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
    $("asof").textContent = `자금 기준일 ${data.asof} (미국)`;
    $("stamp").textContent = `마지막 갱신 ${data.time} · 10분마다 자동 갱신 · 자금: State Street (하루 늦음) · 가격: 야후`;
    render();
  } catch (e) {
    $("stamp").textContent = "PC의 서버에 연결하지 못했습니다. 10분 뒤 다시 시도합니다.";
  }
}

$("windows").innerHTML = WINDOWS.map(w => `<button data-w="${w}">${w}일</button>`).join("");
function markWin() { document.querySelectorAll("#windows button").forEach(b => b.classList.toggle("on", +b.dataset.w === win)); }
$("windows").addEventListener("click", e => { if (e.target.dataset.w) { win = +e.target.dataset.w; markWin(); render(); } });
window.addEventListener("resize", () => { if (data) { place(); renderTable(); } });
$("table").addEventListener("click", e => { const tr = e.target.closest("[data-t]"); if (tr) select(tr.dataset.t); });
markWin();
load();
setInterval(load, REFRESH_MS);
