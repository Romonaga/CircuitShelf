import { askAssemblyAssistant, updateAssemblyStep } from "../libs/api";
import { errorMessage } from "../libs/errors";
import { formatNumber } from "../libs/format";
import type { AppConfig, AssemblyPlan } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { AssemblyExportPanel } from "./AssemblyExportPanel";
import { AssemblyFabricationPanel } from "./AssemblyFabricationPanel";
import { AssemblyLearningPanel } from "./AssemblyLearningPanel";
import { AssemblyPhotoCheckPanel } from "./AssemblyPhotoCheckPanel";
import { AssemblyStepEvidencePanel } from "./AssemblyStepEvidencePanel";
import { LoadingSpinner } from "./LoadingSpinner";
import { SectionHeader } from "./SectionHeader";
import { FormEvent, useEffect, useMemo, useState } from "react";

export function AssemblyPlanDetail({
  plan,
  loading,
  config,
  onPlanUpdated
}: {
  plan: AssemblyPlan | null;
  loading: boolean;
  config: AppConfig;
  onPlanUpdated: (plan: AssemblyPlan) => void;
}) {
  const [stepBusy, setStepBusy] = useState("");
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [assistantMessage, setAssistantMessage] = useState("");
  const [error, setError] = useState("");
  const [openStepIds, setOpenStepIds] = useState<Record<string, boolean>>({});

  const progress = useMemo(() => {
    if (!plan?.stepCount) {
      return 0;
    }
    return Math.round((plan.completedStepCount / plan.stepCount) * 100);
  }, [plan]);

  useEffect(() => {
    if (!plan) {
      setOpenStepIds({});
      return;
    }
    const defaultOpenStep = plan.steps.find((step) => !step.completed) ?? plan.steps[0];
    setOpenStepIds(Object.fromEntries(plan.steps.map((step) => [step.id, step.id === defaultOpenStep?.id])));
  }, [plan?.id, plan?.steps.length]);

  async function toggleStep(stepId: string, completed: boolean) {
    if (!plan) {
      return;
    }
    setStepBusy(stepId);
    setError("");
    try {
      const response = await updateAssemblyStep(plan.id, stepId, completed);
      onPlanUpdated(response.plan);
    } catch (err) {
      setError(errorMessage(err, "Could not update step"));
    } finally {
      setStepBusy("");
    }
  }

  function toggleStepDetails(stepId: string) {
    setOpenStepIds((current) => ({
      ...current,
      [stepId]: !current[stepId]
    }));
  }

  async function submitAssistant(event: FormEvent) {
    event.preventDefault();
    if (!plan || !assistantMessage.trim() || assistantBusy) {
      return;
    }
    setAssistantBusy(true);
    setError("");
    try {
      const response = await askAssemblyAssistant(plan.id, assistantMessage, config.defaultModel);
      setAssistantMessage("");
      onPlanUpdated(response.plan);
    } catch (err) {
      setError(errorMessage(err, "Bench assistant failed"));
    } finally {
      setAssistantBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="document-loading">
        <LoadingSpinner />
        <span>Loading assembly plan...</span>
      </div>
    );
  }

  if (!plan) {
    return <div className="empty-state">Create or select an assembly plan.</div>;
  }

  return (
    <div className="assembly-detail">
      <SectionHeader
        title={plan.title}
        description={`${plan.componentName || "Circuit"} | Confidence ${formatNumber(plan.confidence)} | ${progress}% complete`}
      />
      <ErrorMessage message={error} />
      <p className="assembly-summary">{plan.summary || plan.objective}</p>

      <div className="assembly-section-grid">
        <section>
          <h3>Parts</h3>
          <ul className="assembly-list">
            {plan.parts.map((part) => (
              <li key={part.id}>
                <strong>{part.name}</strong>
                <span>{part.detail}</span>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h3>Power</h3>
          <ul className="assembly-list">
            {plan.power.map((item) => (
              <li key={item.id}>{item.note}</li>
            ))}
          </ul>
        </section>
      </div>

      <section>
        <h3>Assembly checklist</h3>
        <div className="assembly-step-list">
          {plan.steps.map((step) => {
            const detailsOpen = Boolean(openStepIds[step.id]);
            return (
              <article key={step.id} className={step.completed ? "assembly-step complete" : `assembly-step ${step.type}`}>
                <header className="assembly-step-header">
                  <input
                    type="checkbox"
                    aria-label={`Mark step ${step.ordinal} complete`}
                    checked={step.completed}
                    disabled={stepBusy === step.id}
                    onChange={(event) => void toggleStep(step.id, event.target.checked)}
                  />
                  <button
                    type="button"
                    className="assembly-step-toggle"
                    aria-expanded={detailsOpen}
                    aria-controls={`assembly-step-details-${step.id}`}
                    onClick={() => toggleStepDetails(step.id)}
                  >
                    <span className="collapse-caret" aria-hidden="true">{detailsOpen ? "v" : ">"}</span>
                    <span className="assembly-step-heading">
                      <strong>
                        {step.ordinal}. {step.title}
                      </strong>
                      <small>{step.instruction}</small>
                    </span>
                  </button>
                </header>
                {detailsOpen ? (
                  <div className="assembly-step-body" id={`assembly-step-details-${step.id}`}>
                    {step.note ? <small>{step.note}</small> : null}
                    {step.sourcePath || step.page ? (
                      <small>
                        Evidence: {step.sourcePath || "source"} {step.page ? `page ${step.page}` : ""}
                      </small>
                    ) : null}
                    <AssemblyStepEvidencePanel planId={plan.id} step={step} />
                    <AssemblyPhotoCheckPanel plan={plan} step={step} compact />
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>

      <div className="assembly-tool-grid">
        <AssemblyLearningPanel plan={plan} />
        <AssemblyExportPanel plan={plan} />
        <AssemblyFabricationPanel plan={plan} />
        <AssemblyPhotoCheckPanel plan={plan} />
      </div>

      <section>
        <h3>Sources</h3>
        <div className="assembly-source-list">
          {plan.sources.map((source) => (
            <div key={source.id} className="assembly-source-row">
              <strong>{source.displayName}</strong>
              <span>{source.pages.length ? `Pages ${source.pages.join(", ")}` : "No page refs"}</span>
              <small>{source.chunkCount} chunks</small>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3>Bench assistant</h3>
        <div className="assembly-notes">
          {plan.notes.map((note) => (
            <article key={note.id} className={`assembly-note ${note.role}`}>
              <strong>{note.role === "assistant" ? "Assistant" : "You"}</strong>
              <p>{note.message}</p>
            </article>
          ))}
          {!plan.notes.length ? <div className="empty-state compact">No bench conversation yet.</div> : null}
        </div>
        <form className="assembly-assistant-form" onSubmit={submitAssistant}>
          <textarea
            value={assistantMessage}
            onChange={(event) => setAssistantMessage(event.target.value)}
            placeholder="Example: I wired step 4. What should I test next?"
            rows={3}
          />
          <button className="primary-button" disabled={!assistantMessage.trim() || assistantBusy}>
            {assistantBusy ? "Thinking..." : "Ask bench assistant"}
          </button>
        </form>
      </section>
    </div>
  );
}
