import React, { useState } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';
import { useApi } from '../hooks';
import { Async, ErrorBox, Panel } from '../components/ui';
import StormMap from '../components/StormMap';
import { StormFilters, useStorms } from './Explorer';
import { fmtNum, fmtTime, motionFromTrack } from '../utils';

export default function MapPage({ params }) {
  const { user } = useAuth();
  const [f, setF] = useState({ search: '', basin: 'All', minWind: '' });
  const [selected, setSelected] = useState(params.storm || '');
  const basins = useApi(() => api('/api/analytics/by-basin'));
  const storms = useStorms(f, 0, 12);
  const track = useApi(() => (selected ? api(`/api/cyclones/${encodeURIComponent(selected)}/track`) : Promise.resolve(null)), [selected]);
  const [proj, setProj] = useState({ hours: 48, data: null, error: null, busy: false });

  const points = track.data?.points || [];
  const motion = motionFromTrack(points);
  const choose = (id) => { setSelected(id); setProj({ hours: proj.hours, data: null, error: null, busy: false }); };

  async function project() {
    setProj((p) => ({ ...p, busy: true, error: null }));
    const last = points[points.length - 1];
    try {
      const data = await api('/api/ml/predict-track', { method: 'POST', json: { latitude: last.latitude, longitude: last.longitude, ...motion, hours: Number(proj.hours) } });
      setProj((p) => ({ ...p, data, busy: false }));
    } catch (error) {
      setProj((p) => ({ ...p, error, busy: false, data: null }));
    }
  }

  return (
    <div className="mapLayout">
      <Panel title="Choose a storm" sub="Observed historical tracks">
        <StormFilters f={f} setF={setF} basins={basins.data} />
        <Async state={storms} loadingLabel="Loading storms…" isEmpty={(d) => d.total === 0} emptyTitle="No storms" emptyText="Nothing matches, or no data has been imported yet.">
          {(d) => (
            <ul className="stormList">
              {d.items.map((s) => (
                <li key={s.storm_id}>
                  <button type="button" className={selected === s.storm_id ? 'selected' : ''} aria-pressed={selected === s.storm_id} onClick={() => choose(s.storm_id)}>
                    <b>{s.name}</b> <span>{s.storm_id}</span><small>{s.basin} · {s.start_time?.slice(0, 10)} · peak {fmtNum(s.max_wind_kt)} kt</small>
                  </button>
                </li>
              ))}
              {d.total > d.items.length && <li className="muted">Showing {d.items.length} of {fmtNum(d.total)}. Narrow the search or use the Storm explorer.</li>}
            </ul>
          )}
        </Async>
      </Panel>

      <div>
        <Panel title={track.data ? `${track.data.name} · ${track.data.storm_id}` : 'Storm track map'}
          sub={track.data ? `Observed best track (${track.data.source}). ${points.length} observations, ${fmtTime(points[0]?.timestamp)} → ${fmtTime(points[points.length - 1]?.timestamp)}` : 'Select a storm to draw its observed track'}>
          {selected && track.loading && !track.data && <div className="state" role="status">Loading track…</div>}
          {selected && track.error && <ErrorBox error={track.error} onRetry={track.reload} />}
          {!selected && <div className="state empty"><b>No storm selected.</b><p>Pick a storm from the list. Markers are historical observations, not real-time positions.</p></div>}
          <StormMap observed={points} projection={proj.data?.points || []} height={470} label={track.data ? `Observed track of ${track.data.name}` : 'Storm map'} />
        </Panel>

        {track.data && points.length > 0 && (
          <Panel title="Baseline projection (optional)" sub="Extends the last observed motion in a straight line. This is NOT a forecast and NOT machine learning.">
            {!user ? (
              <p className="muted">Sign in to compute a baseline projection. <a href="#/account">Go to sign in</a></p>
            ) : !motion ? (
              <p className="muted">At least two observations at different times are needed to derive a motion.</p>
            ) : (
              <>
                <p className="muted">Derived from the last two observations: moving toward {fmtNum(motion.direction_degrees, 1)}° at {fmtNum(motion.speed_kmh, 1)} km/h.</p>
                <div className="inline">
                  <label>Hours ahead
                    <select value={proj.hours} onChange={(e) => setProj({ ...proj, hours: e.target.value })}>{[24, 48, 72, 96, 120].map((h) => <option key={h} value={h}>{h}</option>)}</select>
                  </label>
                  <button type="button" onClick={project} disabled={proj.busy}>{proj.busy ? 'Calculating…' : 'Show baseline projection'}</button>
                </div>
              </>
            )}
            {proj.error && <ErrorBox error={proj.error} />}
            {proj.data && <p className="warning inlineWarning" role="note"><b>Baseline projection (dashed). </b>{proj.data.warning}</p>}
          </Panel>
        )}

        {points.length > 0 && (
          <Panel title="Observations in this track" sub="Text alternative to the map">
            <div className="tableWrap short">
              <table>
                <caption className="sr">Observed best-track points</caption>
                <thead><tr><th scope="col">Time (UTC)</th><th scope="col" className="num">Lat</th><th scope="col" className="num">Lon</th><th scope="col" className="num">Wind (kt)</th><th scope="col" className="num">Pressure (hPa)</th></tr></thead>
                <tbody>{points.slice(0, 300).map((p) => (
                  <tr key={p.timestamp}><th scope="row">{fmtTime(p.timestamp)}</th><td className="num">{p.latitude}</td><td className="num">{p.longitude}</td>
                    <td className="num">{fmtNum(p.wind_speed_kt)}{p.wind_source ? ` ${p.wind_source}` : ''}</td><td className="num">{fmtNum(p.pressure_hpa)}{p.pressure_source ? ` ${p.pressure_source}` : ''}</td></tr>))}</tbody>
              </table>
            </div>
            {points.length > 300 && <p className="muted">Showing the first 300 of {points.length} observations.</p>}
          </Panel>
        )}
      </div>
    </div>
  );
}
