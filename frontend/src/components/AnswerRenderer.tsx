import { ReactNode, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const ALLOWED_TAGS = new Set(["DETAILS", "SUMMARY", "DIV", "P", "PRE", "CODE", "IMG"]);

function renderAllowedNode(node: Node, key: string): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.textContent;
  }

  if (node.nodeType !== Node.ELEMENT_NODE) {
    return null;
  }

  const element = node as Element;
  const children = Array.from(element.childNodes).map((child, index) => renderAllowedNode(child, `${key}-${index}`));

  if (!ALLOWED_TAGS.has(element.tagName)) {
    return <span key={key}>{children}</span>;
  }

  switch (element.tagName) {
    case "DETAILS":
      return (
        <details key={key} className="answer-details">
          {children}
        </details>
      );
    case "SUMMARY":
      return (
        <summary key={key} className="answer-summary">
          {children}
        </summary>
      );
    case "DIV":
      return (
        <div key={key} className="answer-image-group">
          {children}
        </div>
      );
    case "P":
      return <p key={key}>{children}</p>;
    case "PRE":
      return (
        <pre key={key} className="answer-ocr">
          {children}
        </pre>
      );
    case "CODE":
      return <code key={key}>{children}</code>;
    case "IMG": {
      const src = element.getAttribute("src") ?? "";
      if (!src.startsWith("data:image/")) {
        return null;
      }
      return <img key={key} className="answer-image" src={src} alt={element.getAttribute("alt") ?? "Related source"} />;
    }
    default:
      return null;
  }
}

function renderGeneratedImageHtml(html: string): ReactNode[] {
  if (!html.trim() || typeof window === "undefined") {
    return [];
  }

  const parsed = new DOMParser().parseFromString(`<div>${html}</div>`, "text/html");
  return Array.from(parsed.body.firstElementChild?.childNodes ?? []).map((node, index) => renderAllowedNode(node, `html-${index}`));
}

export function AnswerRenderer({ content }: { content: string }) {
  const splitAt = content.indexOf("<details");
  const answerText = splitAt >= 0 ? content.slice(0, splitAt).trimEnd() : content;
  const generatedImageHtml = splitAt >= 0 ? content.slice(splitAt) : "";
  const imageNodes = useMemo(() => renderGeneratedImageHtml(generatedImageHtml), [generatedImageHtml]);

  return (
    <div className="answer-rich">
      {answerText ? (
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: ({ children }) => <span>{children}</span> }}>
          {answerText}
        </ReactMarkdown>
      ) : null}
      {imageNodes.length ? <div className="answer-generated-images">{imageNodes}</div> : null}
    </div>
  );
}
