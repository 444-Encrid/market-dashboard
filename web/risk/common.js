// 공통: 색, 상태, 숫자·글자 도우미
const REFRESH_MS = 60000;
const PERIODS = {"1개월": 21, "3개월": 63, "6개월": 126, "1년": 252};
const STATUS = {
  "안정": {color: "#0ca30c", icon: "✓", fg: "#0b0b0b", tint: 0.05},
  "주의": {color: "#fab219", icon: "!", fg: "#0b0b0b", tint: 0.09},
  "위험": {color: "#d03b3b", icon: "✕", fg: "#ffffff", tint: 0.16},
};
const ORDER = ["안정", "주의", "위험"];
const NEUTRAL = {color: "#898781", icon: "–", fg: "#0b0b0b", tint: 0.07};
const look = it => it.neutral ? NEUTRAL : STATUS[it.status];
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
