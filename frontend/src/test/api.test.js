import { describe, expect, it, vi } from 'vitest';
import { api, ApiError, configureAuth, qs } from '../api';
import { mockFetch } from './helpers.jsx';

describe('api client', () => {
  it('returns JSON and uses same-origin relative paths by default', async () => {
    const spy = mockFetch([['/api/health', { body: { status: 'ok' } }]]);
    expect(await api('/api/health')).toEqual({ status: 'ok' });
    expect(spy.mock.calls[0][0]).toBe('/api/health');
  });

  it('turns string and validation-array details into readable messages', async () => {
    mockFetch([['/a', { status: 409, body: { detail: 'Email already registered' } }], ['/b', { status: 422, body: { detail: [{ loc: ['body', 'password'], msg: 'too short' }] } }]]);
    await expect(api('/a')).rejects.toMatchObject({ status: 409, message: 'Email already registered' });
    await expect(api('/b')).rejects.toMatchObject({ status: 422, message: 'password: too short' });
  });

  it('reports an unreachable API plainly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    const err = await api('/api/health').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(err.message).toMatch(/Cannot reach the API/);
  });

  it('hides server internals on 5xx without a JSON body', async () => {
    mockFetch([['/x', { status: 502, body: null }]]);
    await expect(api('/x')).rejects.toMatchObject({ message: expect.stringMatching(/internal error/i) });
  });

  it('sends the bearer token and signals 401 only when a token was sent', async () => {
    const onUnauthorized = vi.fn();
    configureAuth({ getToken: () => 'abc', onUnauthorized });
    const spy = mockFetch([['/p', { status: 401, body: { detail: 'Invalid or expired access token' } }]]);
    await expect(api('/p')).rejects.toBeInstanceOf(ApiError);
    expect(spy.mock.calls[0][1].headers.Authorization).toBe('Bearer abc');
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    configureAuth({ getToken: () => null });
    await expect(api('/p')).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('builds query strings without empty/"All" values', () => {
    expect(qs({ a: 'x', b: '', c: 'All', d: 0, e: undefined })).toBe('?a=x&d=0');
    expect(qs({})).toBe('');
  });
});
