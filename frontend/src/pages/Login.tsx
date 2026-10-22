import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { homeFor } from "../components/Layout";
import { ErrorBox, Field } from "../components/ui";
import { post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAction } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

export default function Login() {
  const { user, login } = useAuth();
  const { setLang } = useI18n();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"password" | "pin">("pin");
  const [username, setUsername] = useState("");
  const [secret, setSecret] = useState("");
  const { busy, error, run } = useAction();

  if (user) return <Navigate to={homeFor(user.role, user.is_manager)} replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      const tokens = await post(mode === "pin" ? "/auth/pin/" : "/auth/login/", {
        username,
        [mode === "pin" ? "pin" : "password"]: secret,
      });
      login(tokens);
      setLang(tokens.user.preferred_language);
      navigate(homeFor(tokens.user.role, tokens.user.is_manager));
    });
  };

  return (
    <div className="login">
      <form className="card login-card" onSubmit={submit}>
        <div className="brand big">
          <span className="logo">V</span>
          <div>
            <strong>Vora Addis Hotel</strong>
            <small>Staff sign-in</small>
          </div>
        </div>
        <div className="tabs">
          <button type="button" className={mode === "pin" ? "active" : ""} onClick={() => setMode("pin")}>PIN</button>
          <button type="button" className={mode === "password" ? "active" : ""} onClick={() => setMode("password")}>Password</button>
        </div>
        <Field label="Username">
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
        </Field>
        <Field label={mode === "pin" ? "PIN" : "Password"}>
          <input
            type="password"
            inputMode={mode === "pin" ? "numeric" : undefined}
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            autoComplete={mode === "pin" ? "off" : "current-password"}
            required
          />
        </Field>
        <ErrorBox error={error} />
        <button className="primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </div>
  );
}
