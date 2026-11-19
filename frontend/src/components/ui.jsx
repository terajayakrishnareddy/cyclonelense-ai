import React from 'react';
import { AlertTriangle, Info, LogIn } from 'lucide-react';
import { useAuth } from '../auth';
import { RESEARCH_DISCLAIMER } from '../utils';

export function Disclaimer({ compact = false }) {
  return (
    <div className="warning" role="note" aria-label="Research limitation">
      <AlertTriangle size={18} aria-hidden="true" />
      <span><b>Research limitation.</b> {compact ? 'Not an official forecast. Do not use for warnings or safety decisions.' : RESEARCH_DISCLAIMER}</span>
    </div>
  );
}

export function Panel({ title, sub, children, actions, className = '' }) {
  return (
    <section className={`panel ${className}`} aria-label={title}>
      <div className="panelHead">
        <div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function Kpi({ icon, label, value, sub }) {
  return (
    <div className="kpi">
      <div className="kpiTop"><span>{label}</span>{icon}</div>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}

export const Loading = ({ label = 'Loading…' }) => <div className="state" role="status" aria-live="polite">{label}</div>;

export function ErrorBox({ error, onRetry }) {
  return (
    <div className="error" role="alert">
      <span>{error?.message || 'Something went wrong.'}</span>
      {onRetry && <button type="button" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export const Empty = ({ title, children }) => (
  <div className="state empty"><Info size={20} aria-hidden="true" /><div><b>{title}</b>{children && <p>{children}</p>}</div></div>
);

/** Renders loading / error / empty / content for a useApi() result. */
export function Async({ state, isEmpty, emptyTitle, emptyText, children, loadingLabel }) {
  if (state.loading && state.data === null) return <Loading label={loadingLabel} />;
  if (state.error) return <ErrorBox error={state.error} onRetry={state.reload} />;
  if (state.data === null) return null;
  if (isEmpty?.(state.data)) return <Empty title={emptyTitle}>{emptyText}</Empty>;
  return children(state.data);
}

/** Gate for actions that need a login (and optionally the admin role). */
export function RequireAuth({ admin = false, what, children }) {
  const { user, isAdmin } = useAuth();
  if (!user) {
    return (
      <div className="state empty" data-testid="needs-login">
        <LogIn size={20} aria-hidden="true" />
        <div><b>Sign in required</b><p>You need to sign in to {what}. <a href="#/account">Go to sign in</a></p></div>
      </div>
    );
  }
  if (admin && !isAdmin) {
    return (
      <div className="state empty" data-testid="needs-admin">
        <Info size={20} aria-hidden="true" />
        <div><b>Administrator role required</b><p>You are signed in as {user.email} ({user.role}) and cannot {what}. Administrators are created on the server with the CLI (see the README).</p></div>
      </div>
    );
  }
  return children;
}
