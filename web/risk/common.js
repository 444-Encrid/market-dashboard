// 공통: 색, 상태, 숫자·글자 도우미
const REFRESH_MS = 60000;
const PERIODS = {"1개월": 21, "3개월": 63, "6개월": 126, "1년": 252};
const STATUS = {
  "안정": {color: "#0ca30c", icon: '<span class="ico">✅️</span>', fg: "#0b0b0b", tint: 0.05},
  "주의": {color: "#fab219", icon: '<span class="ico">⚠️</span>', fg: "#0b0b0b", tint: 0.09},
  "위험": {color: "#d03b3b", icon: '<span class="ico">🚨️</span>', fg: "#ffffff", tint: 0.16},
};
const ORDER = ["안정", "주의", "위험"];
const NEUTRAL = {color: "#898781", icon: '<span class="ico">➖️</span>', fg: "#0b0b0b", tint: 0.07};
const look = it => it.neutral ? NEUTRAL : STATUS[it.status];
const FONT = '"Pretendard Variable", Pretendard, Tossface, sans-serif';
const INK = "#f0efec", MUTED = "#898781", GRID = "#2c2c2a", SURFACE = "#1a1a19", LINE = "#3987e5";
const $ = id => document.getElementById(id);

function rgba(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
}
function fmt(v, d, unit = "", sign = false) {
  const s = Math.abs(v).toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d});
  return (v < 0 ? "-" : sign ? "+" : "") + s + unit;
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])); }

// 프리텐다드에는 수학 빼기 기호(−)가 없다. Plotly 는 음수 눈금·값에 그 기호를 쓰므로 그린 뒤 보통 빼기(-)로 바꾼다.
function plainMinus(gd) {
  if (typeof gd === "string") gd = document.getElementById(gd);
  const fix = () => gd.querySelectorAll("text, tspan").forEach(t => {
    for (const c of t.childNodes) if (c.nodeType === 3 && c.data.includes("−")) c.data = c.data.replaceAll("−", "-");
  });
  fix();
  if (!gd._plainMinus) { gd._plainMinus = true; gd.on("plotly_afterplot", fix); gd.on("plotly_hover", fix); }
}
