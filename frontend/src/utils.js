export const RESEARCH_DISCLAIMER =
  'Research platform. Shows historical observations, not live storm alerts. Track projections here are an untrained constant-motion baseline, not an official forecast. Do not use for warnings, evacuation, navigation or other safety decisions.';

export const fmtNum = (v, digits = 0) =>
  v === null || v === undefined ? '—' : Number(v).toLocaleString('en-US', { maximumFractionDigits: digits });

export function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return `${d.toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}

export function fmtBytes(n) {
  if (n === null || n === undefined) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}

const toRad = (d) => (d * Math.PI) / 180;
const toDeg = (r) => (r * 180) / Math.PI;

export function haversineKm(a, b) {
  const dLat = toRad(b.latitude - a.latitude);
  const dLon = toRad(b.longitude - a.longitude);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.latitude)) * Math.cos(toRad(b.latitude)) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function bearingDeg(a, b) {
  const p1 = toRad(a.latitude), p2 = toRad(b.latitude), dl = toRad(b.longitude - a.longitude);
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return (toDeg(Math.atan2(y, x)) + 360) % 360;
}

/** Motion implied by the last two observed positions: {direction_degrees, speed_kmh} or null. */
export function motionFromTrack(points) {
  if (!points || points.length < 2) return null;
  const a = points[points.length - 2], b = points[points.length - 1];
  const hours = (new Date(b.timestamp) - new Date(a.timestamp)) / 36e5;
  if (!(hours > 0)) return null;
  const speed = Math.min(150, haversineKm(a, b) / hours);  // API accepts at most 150 km/h
  const dir = bearingDeg(a, b);
  return { direction_degrees: Math.round((dir >= 359.95 ? 0 : dir) * 10) / 10, speed_kmh: Math.round(speed * 10) / 10 };
}

/** Make longitudes continuous across the antimeridian so lines do not streak across the whole map. */
export function unwrapLongitudes(points) {
  let offset = 0, prev = null;
  return points.map((p) => {
    if (prev !== null) {
      const d = p.longitude - prev;
      if (d > 180) offset -= 360;
      else if (d < -180) offset += 360;
    }
    prev = p.longitude;
    return [p.latitude, p.longitude + offset];
  });
}

/** Projection points continuing from the last observed point, with longitudes made continuous with unwrapLongitudes(). */
export function projectionPositions(observed, projection) {
  if (!observed.length || !projection.length) return [];
  const unwrapped = unwrapLongitudes(observed);
  const [lastLat, lastLon] = unwrapped[unwrapped.length - 1];
  const rawLast = observed[observed.length - 1].longitude;
  return [[lastLat, lastLon], ...projection.map((p) => [p.latitude, lastLon + ((p.longitude - rawLast + 540) % 360) - 180])];
}

// Wind-speed bins used only to colour map markers (knots).
export const WIND_BINS = [
  { max: 34, color: '#5dade2', label: '< 34 kt' },
  { max: 64, color: '#58d68d', label: '34–63 kt' },
  { max: 96, color: '#f5b041', label: '64–95 kt' },
  { max: Infinity, color: '#ec7063', label: '≥ 96 kt' },
];
export const UNKNOWN_WIND = { color: '#95a5a6', label: 'wind not reported' };
export const windColor = (kt) => (kt === null || kt === undefined ? UNKNOWN_WIND.color : WIND_BINS.find((b) => kt < b.max).color);
