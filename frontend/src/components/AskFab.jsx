export default function AskFab({ sel, onAsk }) {
  if (!sel) return null;
  return (
    <button
      className="ask-fab"
      style={{ left: sel.x, top: sel.y }}
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => onAsk(sel)}
    >
      Ask doubt
    </button>
  );
}
