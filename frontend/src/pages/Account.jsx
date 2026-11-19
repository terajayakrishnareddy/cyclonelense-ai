import React, { useState } from 'react';
import { useAuth } from '../auth';
import { ErrorBox, Panel } from '../components/ui';

export default function Account() {
  const { user, login, register, logout, notice } = useAuth();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  if (user) {
    return (
      <Panel title="Your account">
        <p>Signed in as <b>{user.email}</b> ({user.role}).</p>
        <button type="button" onClick={logout}>Sign out</button>
      </Panel>
    );
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await (mode === 'login' ? login(email, password) : register(email, password));
      window.location.hash = '#/overview';
    } catch (err) { setError(err); } finally { setBusy(false); }
  }

  return (
    <Panel title={mode === 'login' ? 'Sign in' : 'Create a researcher account'} sub="Reading historical data needs no account. Baseline calculations and image checks need a login; imports need an administrator.">
      {notice && <div className="error" role="alert">{notice}</div>}
      <form onSubmit={submit} className="authForm">
        <label>Email<input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Password{mode === 'register' && ' (at least 10 characters)'}
          <input type="password" required minLength={mode === 'register' ? 10 : 1} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <ErrorBox error={error} />}
        <button type="submit" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
      </form>
      <p className="muted">
        {mode === 'login' ? 'No account? ' : 'Already registered? '}
        <button type="button" className="linkbtn" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null); }}>
          {mode === 'login' ? 'Create one' : 'Sign in instead'}
        </button>
      </p>
    </Panel>
  );
}
