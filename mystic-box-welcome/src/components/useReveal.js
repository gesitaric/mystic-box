import { useEffect } from "react";

// Mostra com uma leve subida os elementos com a classe .reveal ao entrarem na tela.
// Observa a página inteira (também o que aparece depois que a API responde).
export function useReveal() {
  useEffect(() => {
    if (!("IntersectionObserver" in window)) {
      document.documentElement.classList.add("no-reveal");
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );

    const watch = () => {
      document.querySelectorAll(".reveal:not(.is-visible):not([data-watched])").forEach((el) => {
        el.dataset.watched = "";
        observer.observe(el);
      });
    };
    watch();
    const mutations = new MutationObserver(watch);
    mutations.observe(document.body, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      mutations.disconnect();
    };
  }, []);
}
