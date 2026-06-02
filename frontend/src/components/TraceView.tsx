import { useEffect, useState } from "react";
import { getTrace } from "../api";
import { errorMessage } from "../lib/errors";
import { formatObject } from "../lib/format";
import { useLogTail } from "../hooks/useLogTail";
import { ErrorMessage } from "./ErrorMessage";
import { LogTailPanel } from "./LogTailPanel";
import { SectionHeader } from "./SectionHeader";

export function TraceView({ isActive, isAdmin }: { isActive: boolean; isAdmin: boolean }) {
  const [trace, setTrace] = useState<Record<string, unknown>>({});
  const [error, setError] = useState("");
  const logTail = useLogTail(isActive && isAdmin);

  async function refresh() {
    setError("");
    try {
      setTrace(await getTrace());
    } catch (err) {
      setError(errorMessage(err, "Could not load trace"));
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <section className="single-panel">
      <SectionHeader
        title="Last trace"
        description="Most recent retrieval and generation diagnostics."
        actions={
        <button className="ghost-button" onClick={refresh}>
          Refresh
        </button>
        }
      />
      <ErrorMessage message={error} />
      <pre className="json-view">{formatObject(trace)}</pre>
      {isAdmin ? <LogTailPanel tail={logTail.tail} loading={logTail.loading} error={logTail.error} onRefresh={logTail.refresh} /> : null}
    </section>
  );
}
