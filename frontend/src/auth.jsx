import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { api, configureAuth } from './api';

const KEY = 'cyclonelens.session';
const AuthContext = createContext(null);

function readSession() {
  try {
    const s = JSON.parse(sessionStorage.getItem(KEY) || 'null');
    return s?.token && s?.user ? s : null;
  } catch {
    return null;
  }
}
function writeSession(s) {
  try {
    if (s) sessionStorage.setItem(KEY, JSON.stringify(s));
    else sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: session lives in memory only */
  }
}

// Token lives in sessionStorage (cleared when the tab closes), never localStorage.
export function AuthProvider({ children }) {
  const [session, setSession] = useState(readSession);
  const [notice, setNotice] = useState('');

  // Wire the API client synchronously (before any child effect can fire a request) and read the
  // latest session through a ref, so requests made right after a page reload still carry the token.
  const sessionRef = useRef(session);
  sessionRef.current = session;
  useState(() => {
    configureAuth({
      getToken: () => sessionRef.current?.token ?? null,
      onUnauthorized: () => {
        writeSession(null);
        sessionRef.current = null;
        setSession(null);
        setNotice('Your session expired. Please sign in again.');
      },
    });
    return null;
  });

  const login = useCallback(async (email, password) => {
    const d = await api('/api/auth/login', { method: 'POST', json: { email, password } });
    const s = { token: d.access_token, user: d.user };
    writeSession(s);
    setSession(s);
    setNotice('');
    return d.user;
  }, []);

  const register = useCallback(async (email, password) => {
    await api('/api/auth/register', { method: 'POST', json: { email, password } });
    return login(email, password);
  }, [login]);

  const logout = useCallback(() => {
    writeSession(null);
    setSession(null);
    setNotice('');
  }, []);

  const value = useMemo(() => ({
    user: session?.user ?? null, token: session?.token ?? null, notice, login, register, logout,
    isAdmin: session?.user?.role === 'admin',
  }), [session, notice, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
