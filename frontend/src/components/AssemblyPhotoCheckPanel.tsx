import { FormEvent, useEffect, useState } from "react";
import { getAssemblyPhotoChecks, submitAssemblyPhotoCheck } from "../api";
import { errorMessage } from "../libs/errors";
import type { AssemblyPhotoCheck, AssemblyPlan } from "../types";
import { ErrorMessage } from "./ErrorMessage";

export function AssemblyPhotoCheckPanel({ plan }: { plan: AssemblyPlan }) {
  const [checks, setChecks] = useState<AssemblyPhotoCheck[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const response = await getAssemblyPhotoChecks(plan.id);
        if (!cancelled) {
          setChecks(response.checks);
        }
      } catch {
        if (!cancelled) {
          setChecks([]);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [plan.id]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || busy) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await submitAssemblyPhotoCheck(plan.id, file, note);
      setChecks(response.checks);
      setFile(null);
      setNote("");
    } catch (err) {
      setError(errorMessage(err, "Could not save photo check"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="assembly-tool-panel">
      <h3>Photo bench check</h3>
      <form className="assembly-photo-form" onSubmit={submit}>
        <input type="file" accept="image/*" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <textarea value={note} rows={2} onChange={(event) => setNote(event.target.value)} placeholder="What did you wire or what looks suspicious?" />
        <button className="primary-button compact-button" disabled={!file || busy}>
          {busy ? "Saving..." : "Save photo check"}
        </button>
      </form>
      <ErrorMessage message={error} />
      <div className="assembly-photo-checks">
        {checks.map((check) => (
          <article key={check.id} className="assembly-note assistant">
            <strong>{check.createdAt ? new Date(check.createdAt).toLocaleString() : "Photo check"}</strong>
            <PhotoDiagnostics diagnostics={check.diagnostics} />
            <pre>{check.checklist}</pre>
          </article>
        ))}
      </div>
    </section>
  );
}

function PhotoDiagnostics({ diagnostics }: { diagnostics: AssemblyPhotoCheck["diagnostics"] }) {
  if (!diagnostics || !Object.keys(diagnostics).length) {
    return null;
  }
  return (
    <div className="photo-diagnostics">
      <span>{diagnostics.width} x {diagnostics.height}</span>
      <span>brightness {diagnostics.brightness}</span>
      <span>contrast {diagnostics.contrast}</span>
      <span>edges {diagnostics.edgeDensity}</span>
      <span>blur {diagnostics.blurScore}</span>
      {diagnostics.warnings?.map((warning) => (
        <small key={warning}>{warning}</small>
      ))}
      {diagnostics.dominantColors?.length ? (
        <div className="photo-color-strip">
          {diagnostics.dominantColors.map((color) => (
            <span key={color.hex} title={`${color.hex} ${color.percent}%`} style={{ background: color.hex }} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
