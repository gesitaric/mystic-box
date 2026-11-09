import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { useBackHandler } from "../router";

// Modais abertos, do mais antigo ao mais recente. Com um modal aberto sobre
// outro (ex.: formulário de venda dentro da loja), o Esc fecha só o de cima.
const openModals = [];

// Janela modal usada pela coleção e pela loja.
// `routed`: o modal tem endereço próprio (ex.: /shop) e o Voltar do navegador
// já o fecha pela mudança de endereço. Sem endereço, o Voltar fecha o modal
// como o Esc (camada no histórico, ver router.js).
function Modal({ label, className = "", routed = false, onClose, children }) {
  const id = useRef(Symbol("modal"));
  const onCloseRef = useRef(onClose);
  useBackHandler(() => onCloseRef.current(), { active: !routed });

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
