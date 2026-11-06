import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

// Modais abertos, do mais antigo ao mais recente. Com um modal aberto sobre
// outro (ex.: formulário de venda dentro da loja), o Esc fecha só o de cima.
const openModals = [];

// Janela modal usada pela coleção e pela loja.
function Modal({ label, className = "", onClose, children }) {
  const id = useRef(Symbol("modal"));
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const modalId = id.current;
    openModals.push(modalId);

    function handleKeyDown(event) {
      if (event.key === "Escape" && openModals[openModals.length - 1] === modalId) {
        onCloseRef.current();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      openModals.splice(openModals.indexOf(modalId), 1);
    };
  }, []);

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
          aria-label="Close"
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
