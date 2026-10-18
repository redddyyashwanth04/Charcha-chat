import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function AuthPage({ mode }) {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isLogin = mode === "login";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={location.state?.from || "/"} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!isLogin && password.length < 8) return setError("Password must be at least 8 characters.");
    setBusy(true);
    try {
      await (isLogin ? login : register)(email.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand big">
          <span className="logo">D</span>
          <span>DoubtChat</span>
        </div>
        <h1>{isLogin ? "Welcome back" : "Create your account"}</h1>
        <p className="muted">
          Chat without losing your place. Ask doubts in a side window as you read.
        </p>
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete={isLogin ? "current-password" : "new-password"}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && (
          <div className="inline-error" role="alert">
            {error}
          </div>
        )}
        <button className="btn primary wide-btn" disabled={busy}>
          {busy ? "Please wait…" : isLogin ? "Log in" : "Sign up"}
        </button>
        <p className="muted small center">
          {isLogin ? (
            <>
              New here? <Link to="/register">Create an account</Link>
            </>
          ) : (
            <>
              Already have an account? <Link to="/login">Log in</Link>
            </>
          )}
        </p>
      </form>
    </main>
  );
}
