import { useState } from "react";
import { exportAssemblyPlan } from "../libs/api";
import { downloadBlob } from "../libs/download";
import { errorMessage } from "../libs/errors";
import type { AssemblyPlan } from "../types";
import { ErrorMessage } from "./ErrorMessage";

export function AssemblyExportPanel({ plan }: { plan: AssemblyPlan }) {
  const [format, setFormat] = useState("markdown");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function exportPlan() {
    setBusy(true);
    setError("");
    try {
      const payload = await exportAssemblyPlan(plan.id, format);
      const blob = new Blob([payload.content], { type: payload.mimeType });
      downloadBlob(blob, payload.filename);
    } catch (err) {
      setError(errorMessage(err, "Could not export plan"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="assembly-tool-panel">
      <h3>Simulator export</h3>
      <div className="assembly-export-controls">
        <select value={format} onChange={(event) => setFormat(event.target.value)}>
          <option value="markdown">Bench markdown</option>
          <option value="ltspice">LTspice starter</option>
          <option value="falstad">Falstad notes</option>
        </select>
        <button className="ghost-button" type="button" disabled={busy} onClick={() => void exportPlan()}>
          {busy ? "Exporting..." : "Export"}
        </button>
      </div>
      <ErrorMessage message={error} />
    </section>
  );
}
