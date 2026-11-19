import React from 'react';
import { ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { api } from '../api';
import { useApi } from '../hooks';
import { Async, Panel } from '../components/ui';
import { fmtNum } from '../utils';

const tick = { fill: '#a9bfcf', fontSize: 11 };
const tip = { contentStyle: { background: '#0b1b2a', border: '1px solid #27445b', color: '#eaf3fb' } };

export function BasinChart({ state, height = 300 }) {
  return (
    <Async state={state} isEmpty={(d) => d.length === 0} emptyTitle="No data" emptyText="Import IBTrACS data to see basin counts.">
      {(d) => (
        <div role="img" aria-label={`Bar chart of observation counts by basin. ${d.map((x) => `${x.basin}: ${fmtNum(x.count)}`).join(', ')}.`}>
          <ResponsiveContainer width="100%" height={height}>
            <BarChart data={d}><CartesianGrid stroke="#1d3446" strokeDasharray="3 3" /><XAxis dataKey="basin" tick={tick} /><YAxis tick={tick} /><Tooltip {...tip} /><Bar dataKey="count" fill="#38c9d7" radius={[5, 5, 0, 0]} /></BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Async>
  );
}

export function YearlyChart({ state, height = 300 }) {
  return (
    <Async state={state} isEmpty={(d) => d.length === 0} emptyTitle="No data" emptyText="Import IBTrACS data to see yearly counts.">
      {(d) => (
        <div role="img" aria-label={`Area chart of observation counts per year, from ${d[0].year} to ${d[d.length - 1].year}.`}>
          <ResponsiveContainer width="100%" height={height}>
            <AreaChart data={d}><CartesianGrid stroke="#1d3446" strokeDasharray="3 3" /><XAxis dataKey="year" tick={tick} /><YAxis tick={tick} /><Tooltip {...tip} /><Area dataKey="observations" stroke="#35d1dc" fill="#35d1dc" fillOpacity={0.14} /></AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Async>
  );
}

export default function Analytics() {
  const basins = useApi(() => api('/api/analytics/by-basin'));
  const yearly = useApi(() => api('/api/analytics/yearly'));
  return (
    <>
      <div className="two">
        <Panel title="Basin comparison" sub="Observation count per basin (all stored data)"><BasinChart state={basins} height={340} /></Panel>
        <Panel title="Yearly records" sub="Observation count per calendar year"><YearlyChart state={yearly} height={340} /></Panel>
      </div>
      <Panel title="How to read these charts">
        <p className="muted">Counts are numbers of stored 3- or 6-hourly best-track observations, not numbers of storms, and they depend on which IBTrACS file was imported and when. Reporting practices and observing technology changed over the decades, so year-to-year differences are not evidence of climate trends without careful analysis.</p>
      </Panel>
    </>
  );
}
