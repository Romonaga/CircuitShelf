export interface ChartTheme {
  accent: string;
  line: string;
  muted: string;
  panelSoft: string;
  text: string;
  splitLine: string;
}

export function readChartTheme(): ChartTheme {
  if (typeof window === "undefined") {
    return {
      accent: "#41c7b2",
      line: "#35516a",
      muted: "#9fb3c8",
      panelSoft: "#13293a",
      text: "#e6f0f8",
      splitLine: "rgba(148, 163, 184, 0.28)"
    };
  }
  const styles = getComputedStyle(document.documentElement);
  const read = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback;
  return {
    accent: read("--accent", "#41c7b2"),
    line: read("--line", "#35516a"),
    muted: read("--muted", "#9fb3c8"),
    panelSoft: read("--panel-soft", "#13293a"),
    text: read("--text", "#e6f0f8"),
    splitLine: "rgba(148, 163, 184, 0.28)"
  };
}
