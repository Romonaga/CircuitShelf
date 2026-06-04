import { formatBytes, formatDurationMs, formatInteger } from "../format";

export interface UploadSelectionFile {
  path: string;
  name: string;
  folder: string;
}

export interface UploadSelectionSummary {
  label: string;
  title: string;
  totalSize: string;
  files: UploadSelectionFile[];
}

export function summarizeSelection(files: File[]): UploadSelectionSummary {
  if (!files.length) {
    return { label: "No files selected.", title: "", totalSize: "", files: [] };
  }
  const selectedFiles = files.map((file) => {
    const path = file.webkitRelativePath || file.name;
    const parts = path.split("/");
    const name = parts.pop() || path;
    return {
      path,
      name,
      folder: parts.join("/")
    };
  });
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  return {
    label: `${formatInteger(files.length)} selected`,
    totalSize: formatBytes(totalBytes),
    files: selectedFiles,
    title: selectedFiles.map((file) => file.path).join("\n")
  };
}

export function formatUploadSpeed(bytesPerSecond: number | null | undefined) {
  if (!bytesPerSecond || !Number.isFinite(bytesPerSecond)) {
    return "calculating";
  }
  return `${formatBytes(bytesPerSecond)}/s`;
}

export function formatUploadEta(seconds: number | null | undefined, percent: number, completedLabel = "server processing") {
  if (percent >= 100) {
    return completedLabel;
  }
  if (!seconds || !Number.isFinite(seconds)) {
    return "calculating";
  }
  return formatDurationMs(seconds * 1000);
}

export function formatUploadEtaHeadline(seconds: number | null | undefined, percent: number) {
  if (percent >= 100) {
    return "Waiting for server";
  }
  if (!seconds || !Number.isFinite(seconds)) {
    return "Calculating ETA";
  }
  return `${formatDurationMs(seconds * 1000)} left`;
}
