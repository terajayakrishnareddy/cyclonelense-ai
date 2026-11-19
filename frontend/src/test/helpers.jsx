import React from 'react';
import { render } from '@testing-library/react';
import { vi } from 'vitest';
import { AuthProvider } from '../auth';

/** handlers: array of [matcher, (url, init) => ({status?, body})]; first match wins. Returns the fetch spy. */
export function mockFetch(handlers) {
  const spy = vi.fn(async (url, init = {}) => {
    const path = String(url);
    for (const [m, h] of handlers) {
      const hit = typeof m === 'string' ? path.includes(m) : m.test(path);
      if (!hit) continue;
      const r = await (typeof h === 'function' ? h(path, init) : h);
      const status = r.status ?? 200;
      return { ok: status < 400, status, json: async () => r.body };
    }
    return { ok: false, status: 404, json: async () => ({ detail: `no mock for ${path}` }) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

export function signIn(role = 'researcher', email = 'someone@example.org') {
  sessionStorage.setItem('cyclonelens.session', JSON.stringify({ token: 'tok', user: { id: 1, email, role } }));
}

export const renderWithAuth = (ui) => render(<AuthProvider>{ui}</AuthProvider>);
