import { useEffect } from "react";
import { createPortal } from "react-dom";

// Janela modal usada pela coleção e pela loja.
function Modal({ label, className = "", onClose, children }) {
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") onClose();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return createPortal(
    <div
      className="auth-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={label}
      onClick={onClose}
    >
      <div
        className={`auth-modal ${className}`.trim()}
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="auth-close"
          aria-label="Fechar"
          onClick={onClose}
        >
          ×
        </button>

        {children}
      </div>
    </div>,
    document.body
  );
}

export default Modal;
