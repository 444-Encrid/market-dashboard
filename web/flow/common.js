// 공통: 판정 색, 숫자·글자 도우미
const REFRESH_MS = 600000;
const WINDOWS = [5, 20, 60, 120];
const COLORS = {"자금·가격 동반": "#0ca30c", "자금만 유입": "#3987e5", "뚜렷하지 않음": "#898781",
                "가격만 강세": "#fab219", "자금·가격 이탈": "#d03b3b"};
const FG = {"자금·가격 동반": "#0b0b0b", "자금만 유입": "#fff", "뚜렷하지 않음": "#0b0b0b", "가격만 강세": "#0b0b0b", "자금·가격 이탈": "#fff"};
const FONT = '"Pretendard Variable", Pretendard, Tossface, sans-serif';
const INK = "#f0efec", MUTED = "#898781", GRID = "#2c2c2a", SURFACE = "#1a1a19";
const $ = id => document.getElementById(id);
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])); }
function rgba(hex, a) { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; }
function num(v, d) { return Math.abs(v).toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d}); }
function signed(v, d, unit = "") { return v == null ? "–" : (v > 0 ? "+" : v < 0 ? "-" : "") + num(v, d) + unit; }
function cls(v) { return v == null ? "dim" : v > 0 ? "pos" : v < 0 ? "neg" : "dim"; }
// 억 달러: 1e8 달러 단위
function eok(usd) { return usd == null ? "–" : signed(usd / 1e8, Math.abs(usd) >= 1e10 ? 0 : 1, "억$"); }
function rankText(r) { if (r == null) return "–"; return r >= 0.5 ? `상위 ${Math.max(1, Math.round((1 - r) * 100))}%` : `하위 ${Math.max(1, Math.round(r * 100))}%`; }
function badge(label) { return label ? `<span class="badge" style="background:${COLORS[label]};color:${FG[label]}">${label}</span>` : "–"; }
function ok(it) { return !it.error && it.windows[win]; }

// 프리텐다드에는 수학 빼기 기호(−)가 없다. Plotly 는 음수 눈금·값에 그 기호를 쓰므로 그린 뒤 보통 빼기(-)로 바꾼다.
function plainMinus(gd) {
  if (typeof gd === "string") gd = document.getElementById(gd);
  const fix = () => gd.querySelectorAll("text, tspan").forEach(t => {
    for (const c of t.childNodes) if (c.nodeType === 3 && c.data.includes("−")) c.data = c.data.replaceAll("−", "-");
  });
  fix();
  if (!gd._plainMinus) { gd._plainMinus = true; gd.on("plotly_afterplot", fix); gd.on("plotly_hover", fix); }
}
