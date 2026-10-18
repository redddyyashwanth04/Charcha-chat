import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as api from "../api";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(api.hasToken());

  const logout = useCallback(() => {
    api.setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    api.setUnauthorizedHandler(logout);
    if (!api.hasToken()) return;
    api
      .me()
      .then(setUser)
      .catch(() => api.setToken(null))
      .finally(() => setLoading(false));
  }, [logout]);

  const authenticate = useCallback(async (fn, email, password) => {
    const { access_token, user: u } = await fn(email, password);
    api.setToken(access_token);
    setUser(u);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      logout,
      login: (e, p) => authenticate(api.login, e, p),
      register: (e, p) => authenticate(api.register, e, p),
    }),
    [user, loading, logout, authenticate]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
