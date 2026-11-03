// Chart colors for each theme.
// Severity is a fixed status-style scale; every bar is also labelled with its
// name, so color is never the only way to read it. Both sets were checked with
// the dataviz palette validator (colour-blind separation, normal-vision
// separation, and >= 3:1 contrast against the chart background):
//   dark  on #0f172a: CVD dE 12.5, normal dE 17.7
//   light on #f1f5f9: CVD dE 11.7, normal dE 19.9
const CHART_COLORS = {
  dark: {
    severity: { Low: "#38bdf8", Medium: "#fde047", High: "#fb923c", Critical: "#f43f5e" },
    accent: "#22d3ee", // single-series bars
    grid: "#1e293b", // recessive gridlines
    axis: "#334155",
    tick: "#94a3b8", // text uses text colors, never series colors
    label: "#cbd5e1",
    cursor: "rgba(148,163,184,0.08)",
  },
  light: {
    severity: { Low: "#0284c7", Medium: "#854d0e", High: "#ea580c", Critical: "#9f1239" },
    accent: "#0891b2",
    grid: "#e2e8f0",
    axis: "#cbd5e1",
    tick: "#475569",
    label: "#334155",
    cursor: "rgba(100,116,139,0.10)",
  },
};

export function getChartColors(theme) {
  return CHART_COLORS[theme] || CHART_COLORS.dark;
}
