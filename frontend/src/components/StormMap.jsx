import React, { useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, useMap } from 'react-leaflet';
import { fmtNum, fmtTime, projectionPositions, unwrapLongitudes, windColor, WIND_BINS, UNKNOWN_WIND } from '../utils';

const TILE_URL = import.meta.env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

function Fit({ positions }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length) map.fitBounds(positions, { padding: [30, 30], maxZoom: 7 });
  }, [map, positions]);
  return null;
}

/**
 * observed: points of an OBSERVED best track (solid line, wind-coloured dots)
 * projection: optional BASELINE projection points (dashed amber line) - visually distinct on purpose
 */
export default function StormMap({ observed = [], projection = [], height = 460, label = 'Map of storm track' }) {
  const obsPos = unwrapLongitudes(observed);
  const projPos = projectionPositions(observed, projection);
  const fit = [...obsPos, ...projPos];
  return (
    <div role="region" aria-label={label} className="mapWrap">
      <MapContainer center={[15, 70]} zoom={2} scrollWheelZoom style={{ height, width: '100%' }} worldCopyJump>
        <TileLayer attribution="&copy; OpenStreetMap contributors" url={TILE_URL} />
        {obsPos.length > 1 && <Polyline positions={obsPos} pathOptions={{ color: '#42d9e8', weight: 2, opacity: 0.8 }} />}
        {observed.map((p, i) => (
          <CircleMarker key={p.timestamp + i} center={obsPos[i]} radius={5}
            pathOptions={{ color: '#0b1e2d', weight: 1, fillColor: windColor(p.wind_speed_kt), fillOpacity: 0.95 }}>
            <Popup>
              <b>Observed (historical best track)</b><br />
              {fmtTime(p.timestamp)}<br />
              Wind: {fmtNum(p.wind_speed_kt)} kt{p.wind_source ? ` (${p.wind_source})` : ''}<br />
              Pressure: {fmtNum(p.pressure_hpa)} hPa{p.pressure_source ? ` (${p.pressure_source})` : ''}<br />
              {p.latitude}, {p.longitude}
            </Popup>
          </CircleMarker>
        ))}
        {projPos.length > 1 && <Polyline positions={projPos} pathOptions={{ color: '#f0b75a', weight: 3, dashArray: '6 8' }} />}
        {projection.map((p, i) => (
          <CircleMarker key={`p${p.hours_ahead}`} center={projPos[i + 1]} radius={5}
            pathOptions={{ color: '#f0b75a', weight: 2, fillColor: '#06131f', fillOpacity: 1 }}>
            <Popup><b>Baseline projection — not a forecast</b><br />+{p.hours_ahead} h<br />{p.latitude}, {p.longitude}</Popup>
          </CircleMarker>
        ))}
        <Fit positions={fit} />
      </MapContainer>
      <ul className="legend" aria-label="Map legend">
        {WIND_BINS.map((b) => <li key={b.label}><i style={{ background: b.color }} />{b.label}</li>)}
        <li><i style={{ background: UNKNOWN_WIND.color }} />{UNKNOWN_WIND.label}</li>
        <li><i className="dash" />baseline projection (not a forecast)</li>
      </ul>
    </div>
  );
}
