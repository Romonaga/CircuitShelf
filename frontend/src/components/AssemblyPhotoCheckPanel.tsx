import { FormEvent, useEffect, useState } from "react";
import { getAssemblyPhotoChecks, submitAssemblyPhotoCheck } from "../libs/api";
import { errorMessage } from "../libs/errors";
import { formatNumber } from "../libs/format";
import type { AssemblyPhotoCheck, AssemblyPlan, AssemblyPlanStep } from "../types";
import { ErrorMessage } from "./ErrorMessage";

export function AssemblyPhotoCheckPanel({
  plan,
  step,
  compact = false
}: {
  plan: AssemblyPlan;
  step?: AssemblyPlanStep | null;
  compact?: boolean;
}) {
  const [checks, setChecks] = useState<AssemblyPhotoCheck[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const response = await getAssemblyPhotoChecks(plan.id, step?.id);
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
  }, [plan.id, step?.id]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || busy) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await submitAssemblyPhotoCheck(plan.id, file, note, step?.id);
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
    <section className={compact ? "assembly-photo-step-panel" : "assembly-tool-panel"}>
      <h3>{step ? "Step photo inspection" : "Photo bench check"}</h3>
      <form className="assembly-photo-form" onSubmit={submit}>
        <input type="file" accept="image/*" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <textarea
          value={note}
          rows={compact ? 1 : 2}
          onChange={(event) => setNote(event.target.value)}
          placeholder={step ? "What changed or what should be checked?" : "What did you wire or what looks suspicious?"}
        />
        <button className="primary-button compact-button" disabled={!file || busy}>
          {busy ? "Inspecting..." : step ? "Inspect step photo" : "Save photo check"}
        </button>
      </form>
      <ErrorMessage message={error} />
      <div className="assembly-photo-checks">
        {checks.map((check) => (
          <article key={check.id} className="assembly-note assistant">
            <div className="photo-check-heading">
              <strong>{check.createdAt ? new Date(check.createdAt).toLocaleString() : "Photo check"}</strong>
              <PhotoVerificationBadge check={check} />
            </div>
            <PhotoVerification verification={check.verification} />
            <PhotoDiagnostics diagnostics={check.diagnostics} />
            {!compact ? <pre>{check.checklist}</pre> : null}
          </article>
        ))}
        {compact && !checks.length ? <small className="muted">No step photos yet.</small> : null}
      </div>
    </section>
  );
}

function PhotoVerificationBadge({ check }: { check: AssemblyPhotoCheck }) {
  const status = check.verification?.status || "cannot_verify";
  const label = status === "looks_consistent" ? "Looks consistent" : status === "needs_attention" ? "Needs attention" : "Cannot verify";
  return <span className={`photo-verification-badge ${status}`}>{label}</span>;
}

function PhotoVerification({ verification }: { verification: AssemblyPhotoCheck["verification"] }) {
  if (!verification) {
    return null;
  }
  const findings = verification.findings ?? [];
  const requestedEvidence = verification.requestedEvidence ?? [];
  return (
    <div className="photo-verification">
      {verification.summary ? <p>{verification.summary}</p> : null}
      <small>
        {verification.provider}
        {verification.model ? ` | ${verification.model}` : ""}
        {verification.confidence != null ? ` | confidence ${formatNumber(verification.confidence)}` : ""}
      </small>
      {findings.length ? (
        <ul>
          {findings.slice(0, 4).map((finding) => (
            <li key={finding}>{finding}</li>
          ))}
        </ul>
      ) : null}
      {requestedEvidence.length ? (
        <ul>
          {requestedEvidence.slice(0, 3).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </div>
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
