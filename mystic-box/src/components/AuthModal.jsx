import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import {
  confirmSignUp,
  describeAuthError,
  signIn,
  signUp,
} from "../auth/cognito";

const COPY = {
  signin: {
    title: "ENTRAR",
    subtitle: "Acesse sua conta para guardar suas cartas.",
    submit: "Entrar",
  },
  signup: {
    title: "CRIAR CONTA",
    subtitle: "Crie sua conta para manter as cartas que puxar.",
    submit: "Criar conta",
  },
  confirm: {
    title: "CONFIRMAR E-MAIL",
    subtitle: "Informe o código que enviamos para seu e-mail.",
    submit: "Confirmar",
  },
};

function AuthModal({ open, onClose, onAuthenticated }) {
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;

    function handleKeyDown(event) {
      if (event.key === "Escape") onClose();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const copy = COPY[mode];

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);

    try {
      if (mode === "signin") {
        const auth = await signIn(email.trim(), password);
        onAuthenticated(auth);
        return;
      }

      if (mode === "signup") {
        const result = await signUp(email.trim(), password);

        if (result.userConfirmed) {
          const auth = await signIn(email.trim(), password);
          onAuthenticated(auth);
          return;
        }

        setMode("confirm");
        setCode("");
        setInfo("Enviamos um código de confirmação para seu e-mail.");
        return;
      }

      await confirmSignUp(email.trim(), code.trim());

      try {
        const auth = await signIn(email.trim(), password);
        onAuthenticated(auth);
      } catch {
        setMode("signin");
        setPassword("");
        setInfo("Conta confirmada! Entre com seu e-mail e senha.");
      }
    } catch (authError) {
      setError(describeAuthError(authError));
    } finally {
      setLoading(false);
    }
  }

  function switchMode(nextMode) {
    setMode(nextMode);
    setError("");
    setInfo("");
    setCode("");
  }

  return createPortal(
    <div className="auth-overlay" onClick={onClose}>
      <div
        className="auth-modal"
        role="dialog"
        aria-modal="true"
        aria-label={copy.title}
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="auth-close"
          onClick={onClose}
          aria-label="Fechar"
        >
          ×
        </button>

        <header className="auth-header">
          <span className="auth-ornament">✦ ✧ ✦</span>
          <h2>{copy.title}</h2>
          <p>{copy.subtitle}</p>
        </header>

        {mode !== "confirm" && (
          <div className="auth-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "signin"}
              className={`auth-tab ${mode === "signin" ? "active" : ""}`}
              onClick={() => switchMode("signin")}
            >
              Entrar
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "signup"}
              className={`auth-tab ${mode === "signup" ? "active" : ""}`}
              onClick={() => switchMode("signup")}
            >
              Criar conta
            </button>
          </div>
        )}

        {info && <p className="auth-info">{info}</p>}
        {error && (
          <p className="auth-error" role="alert">
            {error}
          </p>
        )}

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="auth-field">
            <span>E-mail</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
              disabled={loading || mode === "confirm"}
            />
          </label>

          {mode !== "confirm" && (
            <label className="auth-field">
              <span>Senha</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                minLength={8}
                required
                disabled={loading}
              />
            </label>
          )}

          {mode === "signup" && (
            <p className="auth-hint">
              A senha deve ter ao menos 8 caracteres, com maiúscula, minúscula e número.
            </p>
          )}

          {mode === "confirm" && (
            <label className="auth-field">
              <span>Código de confirmação</span>
              <input
                type="text"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                disabled={loading}
              />
            </label>
          )}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? "Aguarde..." : copy.submit}
          </button>
        </form>

        {mode === "confirm" && (
          <button
            type="button"
            className="auth-link"
            onClick={() => switchMode("signin")}
          >
            Voltar para o login
          </button>
        )}
      </div>
    </div>,
    document.body
  );
}

export default AuthModal;
