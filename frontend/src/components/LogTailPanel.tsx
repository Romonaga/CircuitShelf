import { useEffect, useRef } from "react";
import { formatInteger } from "../lib/format";
import type { LogTailPayload } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { LoadingSpinner } from "./LoadingSpinner";

export function LogTailPanel({
  tail,
  loading,
  error,
  onRefresh
}: {
  tail: LogTailPayload | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
}) {
  const logRef = useRef<HTMLPreElement | null>(null);

  useEffect(() => {
    const logWindow = logRef.current;
    if (logWindow) {
      logWindow.scrollTop = logWindow.scrollHeight;
    }
  }, [tail?.updatedAt]);

  const lineText = tail?.lines.length ? tail.lines.join("\n") : tail?.exists === false ? "Log file does not exist yet." : "No log lines available.";

  return (
    <section className="log-tail-panel">
      <div className="log-tail-toolbar">
        <div>
          <h3>Trace log</h3>
          <p>
            {tail?.path ?? "Loading log path..."}
            {tail ? ` | ${formatInteger(tail.lineCount)} lines | ${formatInteger(tail.sizeBytes)} bytes` : ""}
            {tail?.truncated ? " | tail truncated" : ""}
          </p>
        </div>
        <button className="ghost-button" type="button" onClick={onRefresh} disabled={loading}>
          {loading ? (
            <>
              <LoadingSpinner className="button-spinner" />
              Loading
            </>
          ) : (
            "Refresh log"
          )}
        </button>
      </div>
      <ErrorMessage message={error || tail?.error || ""} />
      <pre ref={logRef} className="log-tail-window">
        {lineText}
      </pre>
    </section>
  );
}
