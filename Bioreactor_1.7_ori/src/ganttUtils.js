// Date helpers — no external library needed
const DAY_MS = 86_400_000;

export function today() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

export function parseDate(str) {
  // 'YYYY-MM-DD' → local midnight Date
  const [y, m, d] = str.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function formatDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function addDays(d, n) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

// Days from a to b (b - a, may be negative)
export function daysBetween(a, b) {
  return Math.round((parseDate(b) - parseDate(a)) / DAY_MS);
}

export function isWeekend(d) {
  return d.getDay() === 0 || d.getDay() === 6;
}

// Reactor label — strip floor prefix for bioreactors, show vessel/station number for Ambr
export function reactorLabel(id) {
  if (id.startsWith('Ambr')) {
    return id.split('-').slice(2).join('-'); // vessel or station part
  }
  if (id.startsWith('6층-')) return id.slice(3);
  if (id.startsWith('5층-')) return '[5F] ' + id.slice(3);
  if (id.startsWith('7층-')) return '[7F] ' + id.slice(3);
  return id;
}

// Sort key for bioreactors only — Ambr reactors use API order (see App.jsx visibleReactors)
export function reactorSortKey(id) {
  const parts = id.split('-');
  if (parts.length < 3) return [99, 99, 99, 99];
  const room = parts[0], scale = parts[1], num = parts[parts.length - 1];
  const roomPrio  = { '6층': 1, '5층': 2, '7층': 3 }[room]  ?? 99;
  const scalePrio = { '5L': 1, '2L': 2, '10L': 3, '50L': 4, '200L': 5, 'Wave': 6 }[scale] ?? 99;
  const isPilot = num.includes('P') ? 1 : 0;
  const numVal  = parseInt(num.replace('P', '').replace('S', '')) || 0;
  return [roomPrio, scalePrio, isPilot, numVal];
}

export function compareReactors(a, b) {
  const ka = reactorSortKey(a), kb = reactorSortKey(b);
  for (let i = 0; i < ka.length; i++) {
    if (ka[i] !== kb[i]) return ka[i] - kb[i];
  }
  return 0;
}

// Project name normalisation matching the Plotly chart in Home.py
export function normalizeProject(raw) {
  const m = raw.match(/SB[\s._-]*(\d+)/i);
  return m ? `SB${parseInt(m[1])}` : raw.trim();
}
