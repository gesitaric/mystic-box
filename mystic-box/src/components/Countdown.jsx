import { useEffect, useRef, useState } from "react";

function formatClock(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

// Contagem regressiva só de exibição. O prazo vem do servidor (`seconds`,
// medido no momento `since` em que a resposta chegou); o relógio só anda na
// tela. Ao zerar, chama onExpire para buscar de novo o estado no servidor.
function Countdown({ seconds, since, onExpire, prefix = "" }) {
  const deadline = since + seconds * 1000;
  const [now, setNow] = useState(() => Date.now());
  const remaining = Math.min(seconds, Math.max(0, Math.ceil((deadline - now) / 1000)));
  const expired = remaining === 0;

  useEffect(() => {
    if (expired) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [expired, deadline]);

  const expireRef = useRef(onExpire);
  useEffect(() => {
    expireRef.current = onExpire;
  }, [onExpire]);

  useEffect(() => {
    if (expired) expireRef.current?.();
  }, [expired]);

  return (
    <span role="timer" aria-live="off">
      {expired ? "Expired" : `${prefix}${formatClock(remaining)}`}
    </span>
  );
}

export default Countdown;
