import { useState } from "react";
import { getAssemblyStepEvidence } from "../libs/api";
import { errorMessage } from "../libs/errors";
import type { AssemblyPlanStep, AssemblyStepEvidence } from "../types";
import { ErrorMessage } from "./ErrorMessage";

export function AssemblyStepEvidencePanel({ planId, step }: { planId: string; step: AssemblyPlanStep }) {
  const [evidence, setEvidence] = useState<AssemblyStepEvidence | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function toggle() {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (!nextOpen || evidence || loading) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      setEvidence(await getAssemblyStepEvidence(planId, step.id));
    } catch (err) {
      setError(errorMessage(err, "Could not load source evidence"));
    } finally {
      setLoading(false);
    }
  }

  if (!step.sourcePath && !step.page) {
    return null;
  }

  return (
    <div className="assembly-evidence">
      <button className="ghost-button compact-button" type="button" onClick={() => void toggle()}>
        {open ? "Hide evidence" : "Show evidence"}
      </button>
      {open ? (
        <div className="assembly-evidence-body">
          <ErrorMessage message={error} />
          {loading ? <small>Loading source evidence...</small> : null}
          {evidence?.chunks.map((chunk) => (
            <article key={`${chunk.sourcePath}-${chunk.chunkIndex}`} className="assembly-evidence-chunk">
              <strong>
                {chunk.displayName} #{chunk.chunkIndex}
                {chunk.page ? ` | page ${chunk.page}` : ""}
              </strong>
              <small>
                {chunk.section} | {chunk.category}
              </small>
              <p>{chunk.preview}</p>
            </article>
          ))}
          {evidence?.images.length ? (
            <div className="assembly-evidence-images">
              {evidence.images.map((image) => (
                <figure key={image.imageKey}>
                  <img src={`data:${image.imageMimeType};base64,${image.imageBase64}`} alt={image.caption} />
                  <figcaption>{image.caption}</figcaption>
                </figure>
              ))}
            </div>
          ) : null}
          {evidence && !evidence.chunks.length && !evidence.images.length ? <small>No source evidence found for this step.</small> : null}
        </div>
      ) : null}
    </div>
  );
}
