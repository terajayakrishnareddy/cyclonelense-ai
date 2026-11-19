import { describe, expect, it } from 'vitest';
import { fmtBytes, fmtNum, fmtTime, motionFromTrack, projectionPositions, unwrapLongitudes, windColor } from '../utils';

const pt = (timestamp, latitude, longitude) => ({ timestamp, latitude, longitude });

describe('utils', () => {
  it('derives motion from the last two observations', () => {
    const m = motionFromTrack([pt('2020-01-01T00:00:00Z', 10, 80), pt('2020-01-01T06:00:00Z', 10, 81)]);
    expect(m.direction_degrees).toBeCloseTo(90, 0);
    expect(m.speed_kmh).toBeCloseTo(18.5, 0);  // ~109.5 km in 6 h
  });
  it('returns null when motion cannot be derived', () => {
    expect(motionFromTrack([pt('2020-01-01T00:00:00Z', 1, 1)])).toBeNull();
    expect(motionFromTrack([pt('2020-01-01T00:00:00Z', 1, 1), pt('2020-01-01T00:00:00Z', 2, 2)])).toBeNull();
  });
  it('caps speed at the API maximum and keeps direction < 360', () => {
    const m = motionFromTrack([pt('2020-01-01T00:00:00Z', 0, 0), pt('2020-01-01T01:00:00Z', 5, 0)]);
    expect(m.speed_kmh).toBe(150);
    expect(m.direction_degrees).toBeLessThan(360);
  });
  it('unwraps longitudes across the antimeridian', () => {
    expect(unwrapLongitudes([pt('a', 0, 178), pt('b', 0, -179), pt('c', 0, -176)]).map((p) => p[1])).toEqual([178, 181, 184]);
    expect(unwrapLongitudes([pt('a', 0, -178), pt('b', 0, 179)]).map((p) => p[1])).toEqual([-178, -181]);
  });
  it('continues a projection from the last observed point', () => {
    const obs = [pt('a', 0, 178), pt('b', 0, 179)];
    const pos = projectionPositions(obs, [{ latitude: 0, longitude: -179 }]);
    expect(pos).toEqual([[0, 179], [0, 181]]);
    expect(projectionPositions([], [{ latitude: 0, longitude: 0 }])).toEqual([]);
  });
  it('formats values without inventing data', () => {
    expect(fmtNum(null)).toBe('—');
    expect(fmtNum(1234567)).toBe('1,234,567');
    expect(fmtTime('2020-05-01T06:00:00Z')).toBe('2020-05-01 06:00 UTC');
    expect(fmtTime(null)).toBe('—');
    expect(fmtTime('garbage')).toBe('—');
    expect(fmtBytes(1536)).toBe('1.5 KB');
  });
  it('colours unknown wind distinctly', () => {
    expect(windColor(null)).not.toBe(windColor(10));
    expect(windColor(120)).not.toBe(windColor(40));
  });
});
