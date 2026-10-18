import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";

/** Small accessible modal: Esc / backdrop closes, focus moves inside. */
export function Modal({ title, onClose, children, wide = false }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div className="backdrop" onMouseDown={onClose}>
      <div
        className={"modal" + (wide ? " wide" : "")}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>,
    document.body
  );
}

export function ConfirmDialog({ title, body, confirmLabel = "Delete", onConfirm, onCancel }) {
  return (
    <Modal title={title} onClose={onCancel}>
      <h3>{title}</h3>
      <p className="muted">{body}</p>
      <div className="modal-actions">
        <button className="btn" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn danger" onClick={onConfirm} autoFocus>
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

/** Tiny toast hook for transient errors. */
export function useToast() {
  const [toast, setToast] = useState("");
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 5000);
    return () => clearTimeout(t);
  }, [toast]);
  const show = useCallback((msg) => setToast(msg), []);
  const node = toast ? (
    <div className="toast" role="alert">
      {toast}
    </div>
  ) : null;
  return [show, node];
}
