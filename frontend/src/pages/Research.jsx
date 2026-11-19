import React from 'react';
import { Panel } from '../components/ui';

export default function Research() {
  return (
    <>
      <div className="two">
        <Panel title="What this platform does">
          <ul className="plain">
            <li>Imports the NOAA NCEI IBTrACS v04r01 historical best-track archive and lets you explore, filter, map and chart it.</li>
            <li>Offers a transparent constant-motion track baseline for comparison with future models.</li>
            <li>Validates uploaded satellite image files (no analysis).</li>
          </ul>
        </Panel>
        <Panel title="What it does not do">
          <ul className="plain">
            <li>It is not an operational forecast, watch or warning system, and must not be used for public warnings, evacuation, navigation or other safety decisions. Follow your national meteorological service.</li>
            <li>No trained machine-learning model is installed; none is claimed.</li>
            <li>No live satellite or weather feed is connected. All storm data is historical.</li>
            <li>Images are not classified; no intensity, structure or location is inferred from images.</li>
          </ul>
        </Panel>
      </div>
      <div className="two">
        <Panel title="Scientific workflow (future work)">
          <ol>
            <li>Acquire versioned IBTrACS best-track data (implemented).</li>
            <li>Acquire matching satellite imagery and quality metadata (not implemented).</li>
            <li>Match image patches to storm IDs and observation times.</li>
            <li>Split train/test by storm identity to prevent leakage.</li>
            <li>Train image and temporal models separately.</li>
            <li>Evaluate against persistence/climatology and official guidance, by lead time and basin, with uncertainty.</li>
          </ol>
        </Panel>
        <Panel title="Data portals">
          <ul className="plain">
            <li><a className="external" href="https://www.ncei.noaa.gov/products/international-best-track-archive" target="_blank" rel="noreferrer">NOAA NCEI IBTrACS ↗</a></li>
            <li><a className="external" href="https://www.goes.noaa.gov/" target="_blank" rel="noreferrer">NOAA GOES ↗</a></li>
            <li><a className="external" href="https://www.earthdata.nasa.gov/" target="_blank" rel="noreferrer">NASA Earthdata ↗</a></li>
            <li><a className="external" href="https://cds.climate.copernicus.eu/" target="_blank" rel="noreferrer">Copernicus Climate Data Store ↗</a></li>
          </ul>
          <p className="muted">Cite IBTrACS per NOAA's guidance when publishing results. Map tiles © OpenStreetMap contributors.</p>
        </Panel>
      </div>
    </>
  );
}
