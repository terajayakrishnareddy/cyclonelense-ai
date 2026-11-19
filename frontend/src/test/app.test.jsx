import React from 'react';
import { describe, expect, it } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import App, { ROUTES } from '../App';
import { mockFetch, signIn } from './helpers.jsx';

const quiet = [['/api/analytics/overview', { body: { observations: 0, storms: 0, basins: 0 } }], ['/api/analytics/', { body: [] }], ['/api/storms', { body: { total: 0, limit: 25, offset: 0, items: [] } }],
  ['/api/data/imports', { body: [] }], ['/api/ml/models', { body: [] }], ['/api/ml/capabilities', { body: {} }]];

describe('App shell', () => {
  it('every navigation item routes to a working page that carries the research disclaimer', async () => {
    mockFetch(quiet);
    render(<App />);
    const nav = screen.getByRole('navigation', { name: 'Main' });
    for (const r of ROUTES.filter((x) => !x.hidden)) {
      const link = nav.querySelector(`a[href="#${r.path}"]`);
      expect(link, r.label).not.toBeNull();
      act(() => { window.location.hash = `#${r.path}`; });
      expect(await screen.findByRole('heading', { level: 1, name: r.title })).toBeInTheDocument();
      expect(screen.getByRole('note', { name: 'Research limitation' })).toHaveTextContent(/not an official forecast/i);
      expect(link).toHaveAttribute('aria-current', 'page');
    }
  });

  it('unknown routes fall back to the overview and the sign-in entry is reachable', async () => {
    mockFetch(quiet);
    window.location.hash = '#/nope';
    render(<App />);
    expect(await screen.findByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '#/account');
    expect(screen.getByRole('link', { name: 'Skip to content' })).toBeInTheDocument();
  });

  it('an expired session signs the user out with an explanation', async () => {
    signIn('researcher', 'me@example.org');
    const spy = mockFetch([['/api/predictions', { status: 401, body: { detail: 'Invalid or expired access token' } }], ...quiet]);
    window.location.hash = '#/models';
    render(<App />);
    await waitFor(() => expect(screen.getByRole('link', { name: 'Sign in' })).toBeInTheDocument());
    expect(spy.mock.calls.find(([u]) => u.includes('/api/predictions'))[1].headers.Authorization).toBe('Bearer tok');  // token sent on the very first request after reload
    expect(sessionStorage.getItem('cyclonelens.session')).toBeNull();
  });
});
