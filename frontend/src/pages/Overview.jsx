import React from 'react';
import { Activity, Database, MapPin, Wind } from 'lucide-react';
import { api } from '../api';
import { useApi } from '../hooks';
import { Async, Kpi, Panel } from '../components/ui';
import { fmtNum, fmtTime } from '../utils';
import { BasinChart, YearlyChart } from './Analytics';

export default function Overview() {
  const overview = useApi(() => api('/api/analytics/overview'));
  const basins = useApi(() => api('/api/analytics/by-basin'));
  const yearly = useApi(() => api('/api/analytics/yearly'));
  return (
    <>
      <Async state={overview} loadingLabel="Loading overview…" isEmpty={(d) => d.observations === 0}
        emptyTitle="No historical data loaded yet"
        emptyText={<>This database is empty. An administrator can import the NOAA IBTrACS CSV on the <a href="#/ingest">Data ingestion</a> page. Nothing is shown until real data is imported.</>}>
        {(o) => (
          <>
            <div className="kpis">
              <Kpi icon={<Database aria-hidden="true" />} label="Observations" value={fmtNum(o.observations)} sub="Stored best-track points" />
              <Kpi icon={<Activity aria-hidden="true" />} label="Unique storms" value={fmtNum(o.storms)} sub="Distinct storm IDs" />
              <Kpi icon={<MapPin aria-hidden="true" />} label="Basins" value={fmtNum(o.basins)} sub="Represented in database" />
              <Kpi icon={<Wind aria-hidden="true" />} label="With wind value" value={fmtNum(o.observations_with_wind)} sub="Observations reporting wind" />
            </div>
            <Panel title="Data provenance" sub="Where the observations in this database come from">
              <dl className="facts">
                <div><dt>Source</dt><dd>NOAA NCEI IBTrACS v04r01 ({fmtNum(o.source_records)} observations){o.demo_records > 0 && `, plus ${fmtNum(o.demo_records)} demo records`}</dd></div>
                <div><dt>Covers</dt><dd>{fmtTime(o.first_observation)} → {fmtTime(o.last_observation)}</dd></div>
                <div><dt>Last import</dt><dd>{o.last_import ? `${o.last_import.filename} (${fmtTime(o.last_import.finished_at)})` : '—'}</dd></div>
              </dl>
              <p className="muted">Historical best-track observations only. Wind and pressure use the WMO agency value when present and otherwise the USA agency value; each observation records which.</p>
            </Panel>
          </>
        )}
      </Async>
      <div className="two">
        <Panel title="Observations by basin" sub="Database distribution"><BasinChart state={basins} /></Panel>
        <Panel title="Observation volume by year" sub="Counts by observation year"><YearlyChart state={yearly} /></Panel>
      </div>
    </>
  );
}
