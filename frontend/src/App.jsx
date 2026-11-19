import React from 'react';
import { Activity, BookOpen, BrainCircuit, ChartNoAxesCombined, CloudDownload, LayoutDashboard, MapPin, Satellite, Search, UserRound } from 'lucide-react';
import { AuthProvider, useAuth } from './auth';
import { useHashRoute } from './hooks';
//import { Disclaimer } from './components/ui';
import Overview from './pages/Overview';
import MapPage from './pages/MapPage';
import Explorer from './pages/Explorer';
import Ingestion from './pages/Ingestion';
import ImageIntake from './pages/ImageIntake';
import Models from './pages/Models';
import Analytics from './pages/Analytics';
import Research from './pages/Research';
import Account from './pages/Account';

export const ROUTES = [
  { path: '/overview', label: 'Overview', icon: LayoutDashboard, title: 'Overview', Page: Overview },
  { path: '/map', label: 'Storm map', icon: MapPin, title: 'Storm map (observed tracks)', Page: MapPage },
  { path: '/storms', label: 'Storm explorer', icon: Search, title: 'Storm explorer', Page: Explorer },
  { path: '/ingest', label: 'Data ingestion', icon: CloudDownload, title: 'Data ingestion', Page: Ingestion },
  { path: '/images', label: 'Image intake', icon: Satellite, title: 'Image intake (validation only)', Page: ImageIntake },
  { path: '/models', label: 'Model center', icon: BrainCircuit, title: 'Model center', Page: Models },
  { path: '/analytics', label: 'Analytics', icon: ChartNoAxesCombined, title: 'Analytics', Page: Analytics },
  { path: '/notes', label: 'Research notes', icon: BookOpen, title: 'Research notes and limitations', Page: Research },
  { path: '/account', label: 'Account', icon: UserRound, title: 'Account', Page: Account, hidden: true },
];

function Shell() {
  const { path, params } = useHashRoute();
  const { user } = useAuth();
  const route = ROUTES.find((r) => r.path === path) || ROUTES[0];
  const Page = route.Page;
  React.useEffect(() => { document.title = `${route.title} | CycloneLens AI`; }, [route]);
  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <aside className="sidebar">
        <div className="brand"><div className="brandIcon" aria-hidden="true"><Activity size={22} /></div><div><b>CycloneLens <em>AI</em></b><small>TROPICAL CYCLONE RESEARCH</small></div></div>
        <nav aria-label="Main">
          <div className="sectionLabel">RESEARCH WORKSPACE</div>
          {ROUTES.filter((r) => !r.hidden).map(({ path: p, label, icon: I }) => (
            <a key={p} href={`#${p}`} className={`nav${route.path === p ? ' selected' : ''}`} aria-current={route.path === p ? 'page' : undefined}><I size={17} aria-hidden="true" />{label}</a>
          ))}
        </nav>
        <div className="sideFoot">
          <a href="#/account" className={`nav${route.path === '/account' ? ' selected' : ''}`} aria-current={route.path === '/account' ? 'page' : undefined}><UserRound size={17} aria-hidden="true" />{user ? user.email : 'Sign in'}</a>
          <small>Research prototype · not an alert service</small>
        </div>
      </aside>
      <main className="main" id="main" tabIndex={-1}>
        <header><div><div className="eyebrow">TROPICAL CYCLONE RESEARCH</div><h1>{route.title}</h1><p>Historical observation analysis and experimental modelling workspace.</p></div></header>
        <Page params={params} />
        <footer>CycloneLens AI · Scientific research platform · Data: NOAA NCEI IBTrACS · Not an operational warning service.</footer>
      </main>
    </div>
  );
}

export default function App() {
  return <AuthProvider><Shell /></AuthProvider>;
}
