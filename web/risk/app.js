// 화면 그리기, 자료 받기, 기간 버튼
let period = "1개월", data = null;

function render() {
  if (!data) return;
  $("summary").innerHTML = summaryHtml(data.items);
  $("co").innerHTML = coHtml(data.co);
  drawCo(data.co);
  $("cards").innerHTML = data.items.map(cardHtml).join("");
  data.items.filter(it => !it.error).forEach(drawChart);
  $("table").innerHTML = tableHtml(data.items);
  $("guide").innerHTML = guideHtml(data.items);
}

async function load() {
  try {
    const res = await fetch("api/data", {cache: "no-store"});
    if (res.status === 401) { location.reload(); return; }   // 로그인이 풀림 → 로그인 화면으로
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
    $("stamp").textContent = `마지막 갱신 ${data.time} · 60초마다 자동 갱신`;
    render();
  } catch (e) {
    $("stamp").textContent = "PC의 대시보드 서버에 연결하지 못했습니다. 60초 뒤 다시 시도합니다.";
  }
}

$("periods").innerHTML = Object.keys(PERIODS).map(p => `<button data-p="${p}">${p}</button>`).join("");
function markPeriod() { document.querySelectorAll("#periods button").forEach(b => b.classList.toggle("on", b.dataset.p === period)); }
$("periods").addEventListener("click", e => { if (e.target.dataset.p) { period = e.target.dataset.p; markPeriod(); render(); } });
markPeriod();
load();
setInterval(load, REFRESH_MS);
