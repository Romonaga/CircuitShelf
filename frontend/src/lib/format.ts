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
