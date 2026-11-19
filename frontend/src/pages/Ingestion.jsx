import React, { useEffect, useRef, useState } from 'react';
import { CloudDownload } from 'lucide-react';
import { api } from '../api';
import { useApi } from '../hooks';
import { Async, ErrorBox, Panel, RequireAuth } from '../components/ui';
import { fmtBytes, fmtNum, fmtTime } from '../utils';

export function RunSummary({ run }) {
  const reasons = Object.entries(run.invalid_reasons || {});
  const notes = Object.entries(run.notes || {});
  return (
    <div className={`result ${run.status}`} role="status" aria-live="polite">
      <b>{run.status === 'running' ? 'Import running…' : run.status === 'completed' ? 'Import completed' : 'Import failed'}</b>
      {run.error && <p role="alert">{run.error}</p>}
      <dl className="facts">
        <div><dt>Rows read</dt><dd>{fmtNum(run.rows_seen)}</dd></div>
        <div><dt>New observations added</dt><dd>{fmtNum(run.rows_added)}</dd></div>
        <div><dt>Duplicates skipped</dt><dd>{fmtNum(run.rows_duplicate)}</dd></div>
        <div><dt>Existing rows enriched</dt><dd>{fmtNum(run.rows_enriched)}</dd></div>
        <div><dt>Invalid rows</dt><dd>{fmtNum(run.rows_invalid)}</dd></div>
        <div><dt>Spur-track rows skipped</dt><dd>{fmtNum(run.rows_skipped_spur)}</dd></div>
      </dl>
      {reasons.length > 0 && <p className="muted">Invalid rows by reason: {reasons.map(([k, v]) => `${k.replaceAll('_', ' ')} (${fmtNum(v)})`).join(', ')}</p>}
      {notes.length > 0 && <p className="muted">Notes: {notes.map(([k, v]) => `${k.replaceAll('_', ' ')} (${fmtNum(v)})`).join(', ')}</p>}
      {run.status === 'failed' && <p className="muted">Counts cover only data that was committed before the failure.</p>}
      <p className="muted">File {run.filename} · {fmtBytes(run.size_bytes)} · SHA-256 <code>{run.sha256?.slice(0, 16)}…</code></p>
    </div>
  );
}

function Uploader({ onDone, pollMs }) {
  const [file, setFile] = useState(null);
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);

  const poll = (id) => {
    timer.current = setTimeout(async () => {
      try {
        const r = await api(`/api/data/imports/${id}`);
        setRun(r);
        if (r.status === 'running') poll(id);
        else { setBusy(false); onDone(); }
      } catch (e) { setError(e); setBusy(false); }
    }, pollMs);
  };

  async function submit(e) {
    e.preventDefault();
    if (!file) return;
    setError(null); setRun(null); setBusy(true);
    const form = new FormData();
    form.append('file', file);
    try {
      const r = await api('/api/data/import-ibtracs', { method: 'POST', form });
      setRun(r);
      if (r.status === 'running') poll(r.id); else { setBusy(false); onDone(); }
    } catch (err) { setError(err); setBusy(false); }
  }

  return (
    <form onSubmit={submit} className="ingest">
      <CloudDownload size={32} aria-hidden="true" />
      <label htmlFor="ibtracs-file"><b>Choose the IBTrACS v04r01 CSV</b></label>
      <p>Upload the official <code>ibtracs.ALL.list.v04r01.csv</code> (or a subset with the same columns). The full file is several hundred MB: it uploads first, then imports in the background. Re-importing is safe; duplicates are skipped.</p>
      <input id="ibtracs-file" type="file" accept=".csv,text/csv" onChange={(e) => { setFile(e.target.files?.[0] || null); setRun(null); setError(null); }} />
      {file && <small>{file.name} ({fmtBytes(file.size)})</small>}
      <button type="submit" disabled={!file || busy}>{busy ? 'Importing…' : 'Import historical records'}</button>
      {error && <ErrorBox error={error} />}
      {run && <RunSummary run={run} />}
    </form>
  );
}

export default function Ingestion({ pollMs = 1500 }) {
  const history = useApi(() => api('/api/data/imports'));
  return (
    <>
      <div className="two">
        <Panel title="NOAA IBTrACS CSV import" sub="Administrators only. Imports best-track observations from the official NCEI CSV">
          <RequireAuth admin what="import data">
            <Uploader onDone={history.reload} pollMs={pollMs} />
          </RequireAuth>
        </Panel>
        <Panel title="Download source" sub="Official historical best-track archive">
          <p>Download the versioned IBTrACS CSV from NOAA NCEI and keep a copy of the original file with its retrieval date in your research log.</p>
          <p><a className="external" href="https://www.ncei.noaa.gov/products/international-best-track-archive" target="_blank" rel="noreferrer">Open NOAA IBTrACS portal ↗</a></p>
          <p className="muted">Wind and pressure: the WMO agency value is used when present, otherwise the USA agency value (labelled “USA” in the data). Agencies use different averaging periods, so values are not strictly comparable across basins. Alternative “spur” track rows are skipped.</p>
        </Panel>
      </div>
      <Panel title="Import history" sub="Provenance of the data in this database">
        <Async state={history} isEmpty={(d) => d.length === 0} emptyTitle="No imports yet" emptyText="No IBTrACS file has been imported into this database.">
          {(d) => (
            <div className="tableWrap short">
              <table>
                <caption className="sr">Previous imports</caption>
                <thead><tr><th scope="col">#</th><th scope="col">File</th><th scope="col">Status</th><th scope="col">Finished</th><th scope="col" className="num">Added</th><th scope="col" className="num">Duplicates</th><th scope="col" className="num">Invalid</th><th scope="col">SHA-256</th></tr></thead>
                <tbody>{d.map((r) => (
                  <tr key={r.id}><td>{r.id}</td><th scope="row">{r.filename}</th><td>{r.status}</td><td>{fmtTime(r.finished_at)}</td><td className="num">{fmtNum(r.rows_added)}</td><td className="num">{fmtNum(r.rows_duplicate)}</td><td className="num">{fmtNum(r.rows_invalid)}</td><td><code>{r.sha256?.slice(0, 12)}…</code></td></tr>))}</tbody>
              </table>
            </div>
          )}
        </Async>
      </Panel>
    </>
  );
}
