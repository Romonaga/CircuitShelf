import type { ResponseValidation } from "./query";
import type { SourceSummary } from "./documents";

export interface AssemblyPlanSummary {
  id: string;
  userId?: number | null;
  createdBy?: string | null;
  title: string;
  objective: string;
  componentName: string;
  componentType: string;
  confidence?: number | null;
  status: string;
  stepCount: number;
  completedStepCount: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface AssemblyPlanPart {
  id: string;
  name: string;
  detail: string;
}

export interface AssemblyPlanPowerNote {
  id: string;
  note: string;
}

export interface AssemblyPlanStep {
  id: string;
  ordinal: number;
  type: "wiring" | "check" | "warning" | string;
  title: string;
  instruction: string;
  note: string;
  sourcePath?: string | null;
  page?: number | null;
  completed: boolean;
  completedAt?: string | null;
}

export interface AssemblyStepEvidenceChunk {
  sourcePath: string;
  displayName: string;
  chunkIndex: number;
  page?: number | null;
  section: string;
  category: string;
  quality?: number | null;
  preview: string;
}

export interface AssemblyStepEvidenceImage {
  sourcePath: string;
  displayName: string;
  imageKey: string;
  caption: string;
  page?: number | null;
  width: number;
  height: number;
  imageMimeType: string;
  imageBase64: string;
}

export interface AssemblyStepEvidence {
  chunks: AssemblyStepEvidenceChunk[];
  images: AssemblyStepEvidenceImage[];
}

export interface AssemblyPlanSource {
  id: string;
  sourcePath: string;
  displayName: string;
  pages: number[];
  chunkCount: number;
}

export interface AssemblyPlanNote {
  id: string;
  role: "user" | "assistant" | string;
  message: string;
  createdAt?: string | null;
}

export interface AssemblyPlan extends AssemblyPlanSummary {
  summary: string;
  parts: AssemblyPlanPart[];
  power: AssemblyPlanPowerNote[];
  steps: AssemblyPlanStep[];
  sources: AssemblyPlanSource[];
  notes: AssemblyPlanNote[];
}

export interface AssemblyPlanExport {
  filename: string;
  mimeType: string;
  content: string;
}

export interface AssemblyLearningSession {
  planId: string;
  currentOrdinal: number;
  modeEnabled: boolean;
  stepCount: number;
  currentStep?: AssemblyPlanStep | null;
  prompt: string;
}

export interface AssemblyPhotoCheck {
  id: string;
  planId: string;
  stepId?: string | null;
  userId: number;
  imageMimeType: string;
  note: string;
  checklist: string;
  diagnostics?: BenchPhotoDiagnostics;
  verification?: BenchPhotoVerification;
  createdAt?: string | null;
}

export interface BenchPhotoVerification {
  status: "looks_consistent" | "needs_attention" | "cannot_verify" | string;
  confidence?: number | null;
  summary: string;
  findings: string[];
  requestedEvidence: string[];
  provider: string;
  model?: string | null;
}

export interface BenchPhotoDiagnostics {
  width?: number;
  height?: number;
  brightness?: number;
  contrast?: number;
  edgeDensity?: number;
  blurScore?: number;
  dominantColors?: Array<{ hex: string; percent: number }>;
  wireColorPixels?: Record<string, number>;
  warnings?: string[];
}

export interface BuildAssemblyPlanResponse {
  plan?: AssemblyPlan;
  answer?: string;
  sources?: SourceSummary[];
  validation?: ResponseValidation | null;
  confidence?: number | null;
  averageQueryTime?: number | null;
  error?: string;
}
