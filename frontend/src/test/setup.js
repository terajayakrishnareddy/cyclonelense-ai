import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.restoreAllMocks();
  window.location.hash = '';
});

// Leaflet needs a real layout engine; the map is replaced by a light stub in unit tests.
vi.mock('react-leaflet', () => {
  const React = require('react');
  const Stub = ({ children }) => React.createElement('div', { 'data-testid': 'leaflet-stub' }, children);
  return { MapContainer: Stub, TileLayer: () => null, CircleMarker: Stub, Polyline: () => null, Popup: Stub, useMap: () => ({ fitBounds() {} }) };
});
// Recharts' ResponsiveContainer renders nothing without layout; stub it so chart wrappers/labels can be asserted.
vi.mock('recharts', async (orig) => {
  const mod = await orig();
  return { ...mod, ResponsiveContainer: ({ children }) => children };
});
