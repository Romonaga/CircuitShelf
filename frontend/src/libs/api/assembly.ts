import type {
  AssemblyLearningSession,
  AssemblyPhotoCheck,
  AssemblyPlan,
  AssemblyPlanExport,
  AssemblyPlanSummary,
  AssemblyStepEvidence,
  BuildAssemblyPlanResponse,
  ConversationBenchPlanResponse,
} from "../../types";
import { requestJson } from "./core";

export function getAssemblyPlans(): Promise<{ plans: AssemblyPlanSummary[] }> {
  return requestJson<{ plans: AssemblyPlanSummary[] }>("/api/assembly-plans");
}

export function getAssemblyPlan(planId: string): Promise<{ plan: AssemblyPlan }> {
  return requestJson<{ plan: AssemblyPlan }>(`/api/assembly-plans/${encodeURIComponent(planId)}`);
}

export function deleteAssemblyPlan(planId: string): Promise<{ ok: boolean; deleted?: { id: string; title: string } }> {
  return requestJson<{ ok: boolean; deleted?: { id: string; title: string } }>(`/api/assembly-plans/${encodeURIComponent(planId)}`, {
    method: "DELETE"
  });
}

export function buildAssemblyPlan(payload: {
  objective: string;
  model: string;
  topK: number;
  distanceThreshold: number;
  maxTokens: number;
  strategy: string;
}): Promise<BuildAssemblyPlanResponse> {
  return requestJson<BuildAssemblyPlanResponse>("/api/assembly-plans/build", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createAssemblyPlanFromConversation(payload: {
  conversationId: string;
  objective?: string;
}): Promise<ConversationBenchPlanResponse> {
  return requestJson<ConversationBenchPlanResponse>("/api/assembly-plans/from-conversation", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateAssemblyStep(planId: string, stepId: string, completed: boolean): Promise<{ plan: AssemblyPlan }> {
  return requestJson<{ plan: AssemblyPlan }>(
    `/api/assembly-plans/${encodeURIComponent(planId)}/steps/${encodeURIComponent(stepId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ completed })
    }
  );
}

export function askAssemblyAssistant(planId: string, message: string, model: string): Promise<{ plan: AssemblyPlan; answer: string }> {
  return requestJson<{ plan: AssemblyPlan; answer: string }>(
    `/api/assembly-plans/${encodeURIComponent(planId)}/assistant`,
    {
      method: "POST",
      body: JSON.stringify({ message, model })
    }
  );
}

export function getAssemblyStepEvidence(planId: string, stepId: string): Promise<AssemblyStepEvidence> {
  return requestJson<AssemblyStepEvidence>(
    `/api/assembly-plans/${encodeURIComponent(planId)}/steps/${encodeURIComponent(stepId)}/evidence`
  );
}

export function exportAssemblyPlan(planId: string, format: string): Promise<AssemblyPlanExport> {
  return requestJson<AssemblyPlanExport>(
    `/api/assembly-plans/${encodeURIComponent(planId)}/export?format=${encodeURIComponent(format)}`
  );
}

export function getAssemblyLearning(planId: string): Promise<{ learning: AssemblyLearningSession }> {
  return requestJson<{ learning: AssemblyLearningSession }>(`/api/assembly-plans/${encodeURIComponent(planId)}/learning`);
}

export function updateAssemblyLearning(planId: string, action: string): Promise<{ learning: AssemblyLearningSession }> {
  return requestJson<{ learning: AssemblyLearningSession }>(`/api/assembly-plans/${encodeURIComponent(planId)}/learning`, {
    method: "PATCH",
    body: JSON.stringify({ action })
  });
}

export function submitAssemblyPhotoCheck(
  planId: string,
  file: File,
  note: string,
  stepId?: string | null
): Promise<{ check: AssemblyPhotoCheck; checks: AssemblyPhotoCheck[] }> {
  const body = new FormData();
  body.append("file", file);
  body.append("note", note);
  if (stepId) {
    body.append("stepId", stepId);
  }
  return requestJson<{ check: AssemblyPhotoCheck; checks: AssemblyPhotoCheck[] }>(
    `/api/assembly-plans/${encodeURIComponent(planId)}/photo-check`,
    {
      method: "POST",
      body,
      headers: {}
    }
  );
}

export function getAssemblyPhotoChecks(planId: string, stepId?: string | null): Promise<{ checks: AssemblyPhotoCheck[] }> {
  const query = stepId ? `?stepId=${encodeURIComponent(stepId)}` : "";
  return requestJson<{ checks: AssemblyPhotoCheck[] }>(`/api/assembly-plans/${encodeURIComponent(planId)}/photo-checks${query}`);
}
