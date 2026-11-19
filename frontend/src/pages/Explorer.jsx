import React, { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { api, qs } from '../api';
import { useApi, useDebounced } from '../hooks';
import { Async, Panel } from '../components/ui';
import { fmtNum, fmtTime } from '../utils';

const PAGE = 25;

export function StormFilters({ f, setF, basins }) {
  return (
    <div className="filters" role="search">
      <label className="searchBox"><Search size={16} aria-hidden="true" /><span className="sr">Search by storm name or ID</span>
        <input type="search" placeholder="Search storm name or ID" value={f.search} onChange={(e) => setF({ ...f, search: e.target.value })} />
      </label>
      <label>Basin
        <select value={f.basin} onChange={(e) => setF({ ...f, basin: e.target.value })}>
          <option value="All">All basins</option>
          {(basins || []).map((b) => <option key={b.basin} value={b.basin}>{b.basin}</option>)}
        </select>
      </label>
      <label>Min. peak wind (kt)
        <input type="number" min="0" inputMode="numeric" placeholder="any" value={f.minWind} onChange={(e) => setF({ ...f, minWind: e.target.value })} />
      </label>
    </div>
  );
}

export function useStorms(f, offset, limit = PAGE) {
  const search = useDebounced(f.search);
  return useApi(() => api('/api/storms' + qs({ search: search.trim(), basin: f.basin, min_wind: f.minWind, limit, offset })),
    [search, f.basin, f.minWind, offset, limit]);
}

export default function Explorer() {
  const [f, setF] = useState({ search: '', basin: 'All', minWind: '' });
  const [offset, setOffset] = useState(0);
  const basins = useApi(() => api('/api/analytics/by-basin'));
  const storms = useStorms(f, offset);
  useEffect(() => setOffset(0), [f.search, f.basin, f.minWind]);

  return (
    <>
      <StormFilters f={f} setF={setF} basins={basins.data} />
      <Panel title="Storms" sub="One row per storm, aggregated from stored historical observations">
        <Async state={storms} loadingLabel="Loading storms…" isEmpty={(d) => d.total === 0}
          emptyTitle="No storms match"
          emptyText="Adjust the filters, or import IBTrACS data on the Data ingestion page if the database is empty.">
          {(d) => (
            <>
              <p className="muted" aria-live="polite">{fmtNum(d.total)} matching storm{d.total === 1 ? '' : 's'} · showing {d.offset + 1}–{d.offset + d.items.length}</p>
              <div className="tableWrap">
                <table>
                  <caption className="sr">Historical storms (observed best-track data)</caption>
                  <thead><tr><th scope="col">Storm</th><th scope="col">Storm ID</th><th scope="col">Basin</th><th scope="col">First observation</th><th scope="col">Last observation</th><th scope="col" className="num">Obs.</th><th scope="col" className="num">Peak wind (kt)</th><th scope="col" className="num">Min. pressure (hPa)</th><th scope="col">Track</th></tr></thead>
                  <tbody>
                    {d.items.map((s) => (
                      <tr key={s.storm_id}>
                        <th scope="row">{s.name}</th><td>{s.storm_id}</td><td>{s.basin}</td><td>{fmtTime(s.start_time)}</td><td>{fmtTime(s.end_time)}</td>
                        <td className="num">{fmtNum(s.observations)}</td><td className="num">{fmtNum(s.max_wind_kt)}</td><td className="num">{fmtNum(s.min_pressure_hpa)}</td>
                        <td><a className="btnlink" href={`#/map?storm=${encodeURIComponent(s.storm_id)}`} aria-label={`View observed track of ${s.name} (${s.storm_id}) on the map`}>View on map</a></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="pager">
                <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
                <button type="button" disabled={offset + PAGE >= d.total} onClick={() => setOffset(offset + PAGE)}>Next</button>
              </div>
            </>
          )}
        </Async>
      </Panel>
    </>
  );
}
