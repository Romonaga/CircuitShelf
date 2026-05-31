export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function formatInteger(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "0";
  }
  return value.toLocaleString();
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = Math.max(0, value);
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toLocaleString(undefined, { maximumFractionDigits: unit === 0 ? 0 : 1 })} ${units[unit]}`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
}

export function formatDurationMs(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  const ms = Math.max(0, value);
  if (ms < 1000) {
    return `${Math.round(ms)} ms`;
  }
  const seconds = ms / 1000;
  if (seconds < 60) {
    return `${seconds.toLocaleString(undefined, { maximumFractionDigits: 1 })} sec`;
  }
  const minutes = seconds / 60;
  return `${minutes.toLocaleString(undefined, { maximumFractionDigits: 1 })} min`;
}

export function formatObject(value: unknown): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}

export function sourceLabel(source: unknown, index: number): string {
  if (typeof source === "string") {
    return source;
  }
  if (source && typeof source === "object") {
    const record = source as Record<string, unknown>;
    return String(record.source ?? record.document ?? record.file ?? `Source ${index + 1}`);
  }
  return `Source ${index + 1}`;
}
