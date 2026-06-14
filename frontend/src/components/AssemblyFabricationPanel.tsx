import { useState } from "react";
import { getFabricationPackage } from "../libs/api";
import { downloadBlob } from "../libs/download";
import { errorMessage } from "../libs/errors";
import { formatBytes } from "../libs/format";
import type { AssemblyPlan, FabricationPackage } from "../types";
import { ErrorMessage } from "./ErrorMessage";

export function AssemblyFabricationPanel({ plan }: { plan: AssemblyPlan }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [fabPackage, setFabPackage] = useState<FabricationPackage | null>(null);

  async function reviewFabrication() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await getFabricationPackage(plan.id);
      setFabPackage(response.package ?? null);
      if (response.package?.generated) {
        setNotice("Fabrication package generated and ready for review.");
      } else {
        setNotice(response.package?.manifest.requiredNextStep || response.error || "Fabrication package is not ready.");
      }
    } catch (err) {
      setError(errorMessage(err, "Could not review fabrication package"));
    } finally {
      setBusy(false);
    }
  }

  function downloadFabricationPackage() {
    if (!fabPackage?.generated || !fabPackage.manifest.downloadAllowed || !fabPackage.zipBase64) {
      setError("Fabrication package download is blocked until preflight passes.");
      return;
    }
    const bytes = bytesFromBase64(fabPackage.zipBase64);
    downloadBlob(new Blob([bytes], { type: "application/zip" }), `${fabPackage.manifest.projectName}-fabrication.zip`);
  }

  const checks = fabPackage?.manifest.checks ?? [];
  const files = fabPackage?.manifest.files ?? [];

  return (
    <section className="assembly-tool-panel fabrication-review-panel">
      <h3>PCB fabrication review</h3>
      <div className="assembly-export-controls">
        <button className="ghost-button" type="button" disabled={busy} onClick={() => void reviewFabrication()}>
          {busy ? "Reviewing..." : "Review fabrication"}
        </button>
        <button
          className="ghost-button"
          type="button"
          disabled={!fabPackage?.generated || !fabPackage.manifest.downloadAllowed}
          onClick={downloadFabricationPackage}
        >
          Download package
        </button>
      </div>

      {fabPackage ? (
        <div className="fabrication-review-body">
          <div className={`fabrication-status ${fabPackage.generated ? "ready" : "blocked"}`}>
            <strong>{statusLabel(fabPackage.status)}</strong>
            <span>{fabPackage.manifest.requiredNextStep || "Review generated fabrication files before ordering."}</span>
          </div>
          <div className="fabrication-check-list">
            {checks.map((check) => (
              <div key={`${check.code}-${check.message}`} className={`fabrication-check ${check.status}`}>
                <strong>{check.code}</strong>
                <span>{check.message}</span>
              </div>
            ))}
          </div>
          {files.length ? (
            <div className="fabrication-file-list">
              {files.map((file) => (
                <span key={`${file.kind}-${file.path}`}>
                  {file.kind}: {file.path}
                  {file.bytes !== undefined ? ` (${formatBytes(file.bytes)})` : ""}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <ErrorMessage message={notice} className={fabPackage?.generated ? "success-message" : "error"} />
      <ErrorMessage message={error} />
    </section>
  );
}

function statusLabel(status: string) {
  return status.replace(/_/g, " ");
}

function bytesFromBase64(value: string) {
  const raw = window.atob(value);
  const bytes = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) {
    bytes[index] = raw.charCodeAt(index);
  }
  return bytes;
}
