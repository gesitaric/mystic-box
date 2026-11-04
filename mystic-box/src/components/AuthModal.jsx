import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import {
  confirmSignUp,
  describeAuthError,
  resendConfirmationCode,
  signIn,
  signUp,
} from "../auth/cognito";

// Email da conta criada que ainda espera o código. Fica no navegador para que
// recarregar a página não tire o usuário da tela de confirmação.
const PENDING_CONFIRM_KEY = "mysticbox.pendingConfirmEmail";

function readPendingEmail() {
  try {
    return localStorage.getItem(PENDING_CONFIRM_KEY) ?? "";
  } catch {
    return "";
  }
}

function savePendingEmail(email) {
  try {
    if (email) localStorage.setItem(PENDING_CONFIRM_KEY, email);
    else localStorage.removeItem(PENDING_CONFIRM_KEY);
  } catch {
    // Sem acesso ao storage: o fluxo segue, só não sobrevive ao reload.
  }
}

const COPY = {
  signin: {
    title: "SIGN IN",
    subtitle: "Sign in to your account to keep your cards.",
    submit: "Sign in",
  },
  signup: {
    title: "CREATE ACCOUNT",
    subtitle: "Create an account to keep the cards you summon.",
    submit: "Create account",
  },
  confirm: {
    title: "CONFIRM EMAIL",
    subtitle: "Enter the code we sent to your email.",
    submit: "Confirm",
  },
};

function AuthModal({ open, onClose, onAuthenticated }) {
  const [mode, setMode] = useState(() =>
    readPendingEmail() ? "confirm" : "signin"
  );
  const [email, setEmail] = useState(readPendingEmail);
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

  function goToConfirm(confirmEmail, message) {
    savePendingEmail(confirmEmail);
    setMode("confirm");
    setCode("");
    setInfo(message);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);

    try {
      if (mode === "signin") {
        try {
          const auth = await signIn(email.trim(), password);
          onAuthenticated(auth);
        } catch (signInError) {
          const errorCode = signInError?.code ?? signInError?.name;
          if (errorCode !== "UserNotConfirmedException") throw signInError;
          goToConfirm(
            email.trim(),
            "Your email isn't confirmed yet. Enter the code we sent you."
          );
        }
        return;
      }

      if (mode === "signup") {
        const result = await signUp(email.trim(), password);

        if (result.userConfirmed) {
          const auth = await signIn(email.trim(), password);
          onAuthenticated(auth);
          return;
        }

        goToConfirm(email.trim(), "We sent a confirmation code to your email.");
        return;
      }

      await confirmSignUp(email.trim(), code.trim());
      savePendingEmail("");

      // Depois de recarregar a página a senha não está mais em memória.
      if (!password) {
        setMode("signin");
        setInfo("Account confirmed! Sign in with your email and password.");
        return;
      }

      try {
        const auth = await signIn(email.trim(), password);
        onAuthenticated(auth);
      } catch {
        setMode("signin");
        setPassword("");
        setInfo("Account confirmed! Sign in with your email and password.");
      }
    } catch (authError) {
      setError(describeAuthError(authError));
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setError("");
    setInfo("");
    setLoading(true);

    try {
      await resendConfirmationCode(email.trim());
      setInfo("We sent a new code to your email.");
    } catch (authError) {
      setError(describeAuthError(authError));
    } finally {
      setLoading(false);
    }
  }

  function switchMode(nextMode) {
    if (mode === "confirm") savePendingEmail("");
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
          aria-label="Close"
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
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "signup"}
              className={`auth-tab ${mode === "signup" ? "active" : ""}`}
              onClick={() => switchMode("signup")}
            >
              Create account
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
            <span>Email</span>
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
              <span>Password</span>
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
              Password must be at least 8 characters long and include an uppercase letter, a lowercase letter and a number.
            </p>
          )}

          {mode === "confirm" && (
            <label className="auth-field">
              <span>Confirmation code</span>
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
            {loading ? "Please wait..." : copy.submit}
          </button>
        </form>

        {mode === "confirm" && (
          <>
            <button
              type="button"
              className="auth-link"
              onClick={handleResend}
              disabled={loading}
            >
              Resend code
            </button>
            <button
              type="button"
              className="auth-link"
              onClick={() => switchMode("signin")}
            >
              Back to sign in
            </button>
          </>
        )}
      </div>
    </div>,
    document.body
  );
}

export default AuthModal;
