import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function Pre({ children }) {
  const ref = useRef(null);
  const [copied, setCopied] = useState(false);
  const lang = (children?.props?.className || "").replace("language-", "");

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(ref.current?.innerText ?? "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  };

  return (
    <div className="codeblock">
      <div className="codebar">
        <span>{lang || "code"}</span>
        <button onClick={copy}>{copied ? "Copied" : "Copy"}</button>
      </div>
      <pre ref={ref}>{children}</pre>
    </div>
  );
}

const components = {
  pre: Pre,
  a: ({ children, ...props }) => (
    <a {...props} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

export default function Markdown({ children }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  );
}
