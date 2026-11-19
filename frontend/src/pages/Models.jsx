import React, { useState } from 'react';
import { BrainCircuit } from 'lucide-react';
import { api } from '../api';
import { useApi } from '../hooks';
import { Async, ErrorBox, Panel, RequireAuth } from '../components/ui';
import { fmtNum, fmtTime } from '../utils';

const FIELDS = [
  { key: 'latitude', label: 'Latitude (°, −90 to 90)', min: -90, max: 90, step: 'any' },
  { key: 'longitude', label: 'Longitude (°, −180 to 180)', min: -180, max: 180, step: 'any' },
  { key: 'direction_degrees', label: 'Direction of motion (°, clockwise from north)', min: 0, max: 359.9, step: 'any' },
  { key: 'speed_kmh', label: 'Speed (km/h, 0 to 150)', min: 0, max: 150, step: 'any' },
  { key: 'hours', label: 'Hours ahead (1 to 120)', min: 1, max: 120, step: 1 },
];

function Calculator({ onSaved }) {
  const [form, setForm] = useState({ latitude: '15', longitude: '80', direction_degrees: '45', speed_kmh: '15', hours: '24' });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, Number(v)]));
      setResult(await api('/api/ml/predict-track', { method: 'POST', json: body }));
      onSaved();
    } catch (err) { setError(err); setResult(null); } finally { setBusy(false); }
  }

  return (
    <>
      <form onSubmit={submit} className="formgrid">
        {FIELDS.map((f) => (
          <label key={f.key}>{f.label}
            <input type="number" required min={f.min} max={f.max} step={f.step} value={form[f.key]} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
          </label>
        ))}
        <div className="formActions"><button type="submit" disabled={busy}>{busy ? 'Calculating…' : 'Calculate baseline projection'}</button></div>
      </form>
      {error && <ErrorBox error={error} />}
      {result && (
        <div className="result" role="status" aria-live="polite">
          <p className="warning inlineWarning" role="note"><b>Baseline projection, not a forecast. </b>{result.warning}</p>
          <p className="muted">Method: {result.method} · model status: {result.model_status} · observed: no</p>
          <div className="tableWrap short">
            <table>
              <caption className="sr">Projected positions</caption>
              <thead><tr><th scope="col">Hours ahead</th><th scope="col" className="num">Latitude</th><th scope="col" className="num">Longitude</th></tr></thead>
              <tbody>
                <tr><th scope="row">0 (start)</th><td className="num">{result.start.latitude}</td><td className="num">{result.start.longitude}</td></tr>
                {result.points.map((p) => <tr key={p.hours_ahead}><th scope="row">+{p.hours_ahead}</th><td className="num">{p.latitude}</td><td className="num">{p.longitude}</td></tr>)}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

export default function Models() {
  const models = useApi(() => api('/api/ml/models'));
  const caps = useApi(() => api('/api/ml/capabilities'));
  const history = useApi(() => api('/api/predictions?limit=20').catch((e) => (e.status === 401 ? [] : Promise.reject(e))));
  return (
    <>
      <div className="two">
        <Panel title="Track baseline calculator" sub="Constant-motion great-circle extrapolation. Not machine learning. Not a forecast.">
          <RequireAuth what="run the baseline calculator"><Calculator onSaved={history.reload} /></RequireAuth>
        </Panel>
        <Panel title="Model registry" sub="Trained models registered with this installation">
          <Async state={models} isEmpty={(d) => d.length === 0} emptyTitle="No trained models are registered"
            emptyText="No ML model artifact or evaluation report is installed, so no ML predictions are available. Only the baseline calculator works.">
            {(d) => (
              <ul className="plain">{d.map((m) => <li key={m.id}><b>{m.name}</b> v{m.version} · {m.task} · <span className="tag">{m.status}</span> <small>{fmtTime(m.created_at)}</small></li>)}</ul>
            )}
          </Async>
          <h3><BrainCircuit size={16} aria-hidden="true" /> Capability status</h3>
          <Async state={caps}>
            {(c) => (
              <ul className="plain">{Object.entries(c).map(([k, v]) => (
                <li key={k}><b>{k.replaceAll('_', ' ')}</b>: <span className={`tag ${v.status}`}>{v.status.replaceAll('_', ' ')}</span><br /><small>{v.description}</small></li>))}</ul>
            )}
          </Async>
        </Panel>
      </div>
      <Panel title="Your baseline calculation history" sub="Saved baseline projections (administrators see everyone's)">
        <RequireAuth what="see your calculation history">
          <Async state={history} isEmpty={(d) => d.length === 0} emptyTitle="No calculations yet" emptyText="Run the calculator above to create one.">
            {(d) => (
              <div className="tableWrap short">
                <table>
                  <caption className="sr">Baseline calculation history</caption>
                  <thead><tr><th scope="col">When (UTC)</th><th scope="col">Type</th><th scope="col">Start</th><th scope="col" className="num">Hours</th><th scope="col">Endpoint</th></tr></thead>
                  <tbody>{d.map((p) => (
                    <tr key={p.id}><th scope="row">{fmtTime(p.created_at)}</th><td>{p.is_baseline ? 'Baseline (not a forecast)' : p.task}</td>
                      <td>{p.input.latitude}, {p.input.longitude}</td><td className="num">{fmtNum(p.input.hours)}</td><td>{p.output.endpoint?.latitude}, {p.output.endpoint?.longitude}</td></tr>))}</tbody>
                </table>
              </div>
            )}
          </Async>
        </RequireAuth>
      </Panel>
    </>
  );
}
