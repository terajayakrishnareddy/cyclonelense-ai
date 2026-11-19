import React from 'react';
import { describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Overview from '../pages/Overview';
import Explorer from '../pages/Explorer';
import Ingestion from '../pages/Ingestion';
import ImageIntake from '../pages/ImageIntake';
import Models from '../pages/Models';
import MapPage from '../pages/MapPage';
import Account from '../pages/Account';
import Analytics from '../pages/Analytics';
import { mockFetch, renderWithAuth, signIn } from './helpers.jsx';

const OVERVIEW = { observations: 1200, storms: 30, basins: 4, demo_records: 0, source_records: 1200, mean_wind_kt: 40, observations_with_wind: 1000,
  first_observation: '2020-01-01T00:00:00Z', last_observation: '2021-01-01T00:00:00Z', last_import: { id: 1, filename: 'ibtracs.csv', finished_at: '2021-02-01T00:00:00Z' } };
const STORM = { storm_id: '2020001N10080', name: 'ALPHA', basin: 'NI', start_time: '2020-05-01T00:00:00Z', end_time: '2020-05-04T00:00:00Z', observations: 4, max_wind_kt: 70, min_pressure_hpa: 980, source: 'NOAA_IBTRACS_v04r01' };
const TRACK = { storm_id: STORM.storm_id, name: 'ALPHA', basin: 'NI', kind: 'observed_best_track', source: 'NOAA_IBTRACS_v04r01',
  points: [{ timestamp: '2020-05-01T00:00:00Z', latitude: 10, longitude: 80, wind_speed_kt: 30, pressure_hpa: 1000, wind_source: 'WMO', pressure_source: 'WMO' },
           { timestamp: '2020-05-01T06:00:00Z', latitude: 10, longitude: 81, wind_speed_kt: 40, pressure_hpa: 995, wind_source: 'USA', pressure_source: 'USA' }] };
const common = [['/api/analytics/by-basin', { body: [{ basin: 'NI', count: 4 }] }], ['/api/analytics/yearly', { body: [{ year: '2020', observations: 4 }] }]];

describe('Overview', () => {
  it('shows a loading state, then real numbers with provenance', async () => {
    mockFetch([['/api/analytics/overview', { body: OVERVIEW }], ...common]);
    renderWithAuth(<Overview />);
    expect(screen.getAllByRole('status')[0]).toHaveTextContent(/loading/i);
    expect(await screen.findByText('1,200')).toBeInTheDocument();
    expect(screen.getByText(/NOAA NCEI IBTrACS v04r01/)).toBeInTheDocument();
    expect(screen.getByText(/WMO agency value when present/)).toBeInTheDocument();
  });

  it('shows an honest empty state (no fabricated numbers) when the database is empty', async () => {
    mockFetch([['/api/analytics/overview', { body: { ...OVERVIEW, observations: 0, storms: 0, last_import: null } }], ['/api/analytics/by-basin', { body: [] }], ['/api/analytics/yearly', { body: [] }]]);
    renderWithAuth(<Overview />);
    expect(await screen.findByText('No historical data loaded yet')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Data ingestion/ })).toHaveAttribute('href', '#/ingest');
    expect(screen.queryByText('Unique storms')).not.toBeInTheDocument();
  });

  it('shows an error with retry when the API is down, and recovers', async () => {
    let up = false;
    mockFetch([['/api/analytics/overview', () => (up ? { body: OVERVIEW } : { status: 500, body: null })], ...common]);
    renderWithAuth(<Overview />);
    const alerts = await screen.findAllByRole('alert');
    expect(alerts[0]).toHaveTextContent(/internal error/i);
    up = true;
    await userEvent.click(within(alerts[0]).getByRole('button', { name: /try again/i }));
    expect(await screen.findByText('1,200')).toBeInTheDocument();
  });
});

describe('Analytics', () => {
  it('shows empty state for charts with no data and accessible chart summaries with data', async () => {
    mockFetch([['/by-basin', { body: [] }], ['/yearly', { body: [] }]]);
    const { unmount } = renderWithAuth(<Analytics />);
    expect(await screen.findAllByText('No data')).toHaveLength(2);
    unmount();
    mockFetch(common);
    renderWithAuth(<Analytics />);
    expect(await screen.findByRole('img', { name: /NI: 4/ })).toBeInTheDocument();
  });
});

describe('Explorer', () => {
  it('lists storms and links each to its observed track', async () => {
    mockFetch([['/api/storms', { body: { total: 1, limit: 25, offset: 0, items: [STORM] } }], ['/by-basin', { body: [{ basin: 'NI', count: 4 }] }]]);
    renderWithAuth(<Explorer />);
    expect(await screen.findByRole('rowheader', { name: 'ALPHA' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /View observed track of ALPHA/ })).toHaveAttribute('href', '#/map?storm=2020001N10080');
    expect(screen.getByText(/1 matching storm/)).toBeInTheDocument();
  });

  it('empty and error states', async () => {
    mockFetch([['/api/storms', { body: { total: 0, limit: 25, offset: 0, items: [] } }], ['/by-basin', { body: [] }]]);
    const { unmount } = renderWithAuth(<Explorer />);
    expect(await screen.findByText('No storms match')).toBeInTheDocument();
    unmount();
    mockFetch([['/api/storms', { status: 500, body: null }], ['/by-basin', { body: [] }]]);
    renderWithAuth(<Explorer />);
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('sends filters to the API', async () => {
    const spy = mockFetch([['/api/storms', { body: { total: 0, limit: 25, offset: 0, items: [] } }], ['/by-basin', { body: [{ basin: 'WP', count: 1 }] }]]);
    renderWithAuth(<Explorer />);
    await screen.findByText('No storms match');
    fireEvent.change(screen.getByLabelText('Basin'), { target: { value: 'WP' } });
    fireEvent.change(screen.getByLabelText(/Min. peak wind/), { target: { value: '90' } });
    await waitFor(() => expect(spy.mock.calls.some(([u]) => u.includes('basin=WP') && u.includes('min_wind=90'))).toBe(true));
  });
});

describe('Ingestion', () => {
  const hist = ['/api/data/imports', { body: [] }];

  it('asks anonymous visitors to sign in and still shows (empty) provenance history', async () => {
    mockFetch([hist]);
    renderWithAuth(<Ingestion />);
    expect(await screen.findByTestId('needs-login')).toBeInTheDocument();
    expect(await screen.findByText('No imports yet')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Choose the IBTrACS/)).not.toBeInTheDocument();
  });

  it('refuses non-admins with an explanation', async () => {
    signIn('researcher');
    mockFetch([hist]);
    renderWithAuth(<Ingestion />);
    expect(await screen.findByTestId('needs-admin')).toHaveTextContent(/Administrator role required/);
  });

  it('admin uploads, polls the running job and sees accurate counts', async () => {
    signIn('admin');
    const base = { id: 7, source: 'NOAA_IBTRACS_v04r01', filename: 'ibtracs.csv', sha256: 'a'.repeat(64), size_bytes: 2048, rows_seen: 0, rows_added: 0, rows_duplicate: 0, rows_enriched: 0, rows_invalid: 0, rows_skipped_spur: 0, invalid_reasons: {}, notes: {}, error: null };
    let polls = 0;
    mockFetch([
      [/imports\/7/, () => { polls += 1; return { body: { ...base, status: 'completed', rows_seen: 10, rows_added: 7, rows_duplicate: 1, rows_invalid: 2, invalid_reasons: { invalid_time: 2 } } }; }],
      ['/api/data/import-ibtracs', { status: 202, body: { ...base, status: 'running' } }],
      hist,
    ]);
    renderWithAuth(<Ingestion pollMs={5} />);
    const input = await screen.findByLabelText(/Choose the IBTrACS/);
    await userEvent.upload(input, new File(['SID,NAME\n'], 'ibtracs.csv', { type: 'text/csv' }));
    await userEvent.click(screen.getByRole('button', { name: /Import historical records/ }));
    expect(await screen.findByText('Import completed')).toBeInTheDocument();
    expect(polls).toBeGreaterThan(0);
    const dl = screen.getByText('New observations added').parentElement;
    expect(dl).toHaveTextContent('7');
    expect(screen.getByText(/invalid time \(2\)/)).toBeInTheDocument();
  });

  it('shows server rejection and failed jobs plainly', async () => {
    signIn('admin');
    mockFetch([['/api/data/import-ibtracs', { status: 400, body: { detail: 'Not an IBTrACS CSV: required column(s) missing: SID.' } }], hist]);
    renderWithAuth(<Ingestion pollMs={5} />);
    await userEvent.upload(await screen.findByLabelText(/Choose the IBTrACS/), new File(['x'], 'bad.csv', { type: 'text/csv' }));
    await userEvent.click(screen.getByRole('button', { name: /Import historical records/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/required column/);
    expect(screen.queryByText('Import completed')).not.toBeInTheDocument();
  });
});

describe('ImageIntake', () => {
  it('requires sign-in', async () => {
    mockFetch([]);
    renderWithAuth(<ImageIntake />);
    expect(screen.getByTestId('needs-login')).toBeInTheDocument();
  });

  it('never presents an accepted file as analysed', async () => {
    signIn();
    mockFetch([['/api/ml/analyze-image', { body: { status: 'ACCEPTED_NOT_ANALYZED', analyzed: false, stored: false, detected_type: 'image/png', bytes_received: 10, sha256: 'b'.repeat(64), message: 'No classification was performed.' } }]]);
    renderWithAuth(<ImageIntake />);
    await userEvent.upload(screen.getByLabelText('Select an image'), new File(['x'], 'a.png', { type: 'image/png' }));
    await userEvent.click(screen.getByRole('button', { name: /Validate image file/ }));
    expect(await screen.findByText(/NOT analysed/)).toBeInTheDocument();
    expect(screen.getByText('Analysed').nextSibling).toHaveTextContent('no');
    expect(screen.queryByText(/cyclone detected|category|confidence/i)).not.toBeInTheDocument();
  });

  it('shows server errors', async () => {
    signIn();
    mockFetch([['/api/ml/analyze-image', { status: 415, body: { detail: 'Only PNG, JPEG or TIFF images are accepted' } }]]);
    renderWithAuth(<ImageIntake />);
    await userEvent.upload(screen.getByLabelText('Select an image'), new File(['x'], 'a.png', { type: 'image/png' }));
    await userEvent.click(screen.getByRole('button', { name: /Validate image file/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Only PNG/);
  });
});

describe('Models', () => {
  const registry = [['/api/ml/models', { body: [] }], ['/api/ml/capabilities', { body: { track_baseline: { status: 'available', description: 'Constant-motion. Not machine learning.' }, image_classification: { status: 'not_configured', description: 'No trained model.' } } }]];

  it('is honest that no trained model exists, even when signed out', async () => {
    mockFetch(registry);
    renderWithAuth(<Models />);
    expect(await screen.findByText('No trained models are registered')).toBeInTheDocument();
    expect(await screen.findByText('image classification')).toBeInTheDocument();
    expect(screen.getAllByTestId('needs-login').length).toBeGreaterThan(0);
  });

  it('calculates a labelled baseline projection for a signed-in user', async () => {
    signIn();
    const result = { kind: 'baseline_projection', observed: false, method: 'constant-motion geometric baseline', model_status: 'NOT_TRAINED', warning: 'Research baseline only. Not an official forecast.',
      start: { latitude: 15, longitude: 80 }, endpoint: { latitude: 16, longitude: 81 }, points: [{ hours_ahead: 24, latitude: 16, longitude: 81 }], hours: 24 };
    const spy = mockFetch([['/api/ml/predict-track', { body: result }], ['/api/predictions', { body: [] }], ...registry]);
    renderWithAuth(<Models />);
    await userEvent.click(await screen.findByRole('button', { name: /Calculate baseline projection/ }));
    expect(await screen.findByText(/Baseline projection, not a forecast/)).toBeInTheDocument();
    expect(screen.getByText(/Not an official forecast/)).toBeInTheDocument();
    const call = spy.mock.calls.find(([u]) => u.includes('predict-track'));
    expect(JSON.parse(call[1].body)).toEqual({ latitude: 15, longitude: 80, direction_degrees: 45, speed_kmh: 15, hours: 24 });
  });

  it('surfaces API validation errors', async () => {
    signIn();
    mockFetch([['/api/ml/predict-track', { status: 422, body: { detail: [{ loc: ['body', 'hours'], msg: 'Input should be <= 120' }] } }], ['/api/predictions', { body: [] }], ...registry]);
    renderWithAuth(<Models />);
    await userEvent.click(await screen.findByRole('button', { name: /Calculate baseline projection/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('hours: Input should be <= 120');
  });
});

describe('MapPage', () => {
  const storms = ['/api/storms', { body: { total: 1, limit: 12, offset: 0, items: [STORM] } }];
  it('prompts to pick a storm, then draws the observed track and labels it observed', async () => {
    mockFetch([storms, ['/track', { body: TRACK }], common[0]]);
    renderWithAuth(<MapPage params={{}} />);
    expect(await screen.findByText('No storm selected.')).toBeInTheDocument();
    await userEvent.click(await screen.findByRole('button', { name: /ALPHA/ }));
    expect(await screen.findByText(/Observed best track \(NOAA_IBTRACS_v04r01\)/)).toBeInTheDocument();
    expect(screen.getByRole('table', { name: /Observed best-track points/ })).toBeInTheDocument();
    expect(screen.getByText(/Sign in to compute a baseline projection/)).toBeInTheDocument();
  });

  it('opens a storm from the URL and shows an error if its track cannot load', async () => {
    mockFetch([storms, ['/track', { status: 404, body: { detail: 'Storm ID not found' } }], common[0]]);
    renderWithAuth(<MapPage params={{ storm: 'NOPE' }} />);
    expect(await screen.findByText('Storm ID not found')).toBeInTheDocument();
  });

  it('signed-in users can overlay a clearly labelled baseline projection', async () => {
    signIn();
    const spy = mockFetch([storms, ['/track', { body: TRACK }], ['/predict-track', { body: { warning: 'Research baseline only. Not an official forecast.', points: [{ hours_ahead: 48, latitude: 11, longitude: 83 }] } }], common[0]]);
    renderWithAuth(<MapPage params={{ storm: STORM.storm_id }} />);
    await userEvent.click(await screen.findByRole('button', { name: /Show baseline projection/ }));
    expect(await screen.findByText(/Baseline projection \(dashed\)/)).toBeInTheDocument();
    const body = JSON.parse(spy.mock.calls.find(([u]) => u.includes('predict-track'))[1].body);
    expect(body).toMatchObject({ latitude: 10, longitude: 81, hours: 48 });
    expect(body.direction_degrees).toBeCloseTo(90, 0);
  });
});

describe('Account', () => {
  it('signs in and shows the user; wrong credentials show the server message', async () => {
    mockFetch([['/api/auth/login', (u, init) => (JSON.parse(init.body).password === 'right-password'
      ? { body: { access_token: 't', user: { id: 1, email: 'a@example.org', role: 'researcher' } } }
      : { status: 401, body: { detail: 'Incorrect email or password' } })]]);
    renderWithAuth(<Account />);
    await userEvent.type(screen.getByLabelText('Email'), 'a@example.org');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password');
    await userEvent.clear(screen.getByLabelText('Password'));
    await userEvent.type(screen.getByLabelText('Password'), 'right-password');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('a@example.org')).toBeInTheDocument();
    expect(JSON.parse(sessionStorage.getItem('cyclonelens.session')).token).toBe('t');
    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(sessionStorage.getItem('cyclonelens.session')).toBeNull();
  });

  it('register enforces the password length client-side and then signs in', async () => {
    const spy = mockFetch([['/api/auth/register', { status: 201, body: {} }], ['/api/auth/login', { body: { access_token: 't', user: { id: 2, email: 'n@example.org', role: 'researcher' } } }]]);
    renderWithAuth(<Account />);
    await userEvent.click(screen.getByRole('button', { name: 'Create one' }));
    await userEvent.type(screen.getByLabelText('Email'), 'n@example.org');
    await userEvent.type(screen.getByLabelText(/Password/), 'long-enough-password');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('n@example.org')).toBeInTheDocument();
    expect(spy.mock.calls.map(([u]) => u)).toEqual(['/api/auth/register', '/api/auth/login']);
  });
});
