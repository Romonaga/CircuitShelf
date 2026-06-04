import { formatNumber } from "./format";

export function money(value: number | null | undefined): string {
  return `$${formatNumber(value ?? 0)}`;
}
