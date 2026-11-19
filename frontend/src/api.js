// Single place that talks to the backend. Empty VITE_API_URL => same-origin "/api" (Vite proxy in dev, nginx in Docker).
export const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

let getToken = () => null;
let onUnauthorized = () => {};
export function configureAuth(opts) {
  getToken = opts.getToken ?? getToken;
  onUnauthorized = opts.onUnauthorized ?? onUnauthorized;
}

function detailMessage(body, status) {
  const d = body?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) {
    return d.map((e) => `${(e.loc || []).filter((x) => x !== 'body').join('.') || 'input'}: ${e.msg}`).join('; ');
  }
  if (status === 413) return 'The file is too large for this server.';
  if (status >= 500) return 'The server reported an internal error. Please try again later.';
  return `Request failed (HTTP ${status}).`;
}

export async function api(path, { method = 'GET', json, form, signal } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body;
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  let res;
  try {
    res = await fetch(API_BASE + path, { method, headers, body, signal });
  } catch (e) {
    if (e?.name === 'AbortError') throw e;
    throw new ApiError(0, `Cannot reach the API${API_BASE ? ` at ${API_BASE}` : ''}. Check that the backend is running and reachable.`);
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized();
    throw new ApiError(res.status, detailMessage(data, res.status));
  }
  return data;
}

export const qs = (params) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined && v !== 'All') p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : '';
};
