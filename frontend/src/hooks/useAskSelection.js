import { useEffect, useState } from "react";

/** Floating "Ask doubt" button state: appears when the user selects text inside a bound element. */
export function useAskSelection() {
  const [sel, setSel] = useState(null);

  const capture =
    (extra = {}) =>
    () => {
      const s = window.getSelection();
      const text = s?.toString().trim();
      if (!text || !s.rangeCount) return setSel(null);
      const r = s.getRangeAt(0).getBoundingClientRect();
      setSel({ text: text.slice(0, 500), x: r.left + r.width / 2, y: r.top, ...extra });
    };

  const clear = () => {
    setSel(null);
    window.getSelection()?.removeAllRanges();
  };

  useEffect(() => {
    const onDown = (e) => {
      if (!e.target.closest?.(".ask-fab")) setSel(null);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  return { sel, capture, clear };
}
