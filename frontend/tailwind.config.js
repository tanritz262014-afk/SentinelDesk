import colors from "tailwindcss/colors";

/*
 * Dark / light theme
 * ------------------
 * Every color used by the app (slate, cyan, rose, ...) points to a CSS variable
 * instead of a fixed value. The dark theme uses Tailwind's normal palette.
 * The light theme MIRRORS each scale (50<->950, 100<->900, ... 500 stays), so
 * dark backgrounds become light, light text becomes dark, and pale accent text
 * (e.g. cyan-300) becomes a darker, readable shade (cyan-700).
 * The theme is switched by setting data-theme="light" on the <html> element.
 */
const THEMED = ["slate", "cyan", "rose", "amber", "emerald", "yellow", "orange", "sky", "indigo"];
const STEPS = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"];
const mirror = (step) => STEPS[STEPS.length - 1 - STEPS.indexOf(step)];

// "#0ea5e9" -> "14 165 233" (the format Tailwind needs for opacity like bg-cyan-500/10)
function toRgb(hex) {
  const value = parseInt(hex.slice(1), 16);
  return `${(value >> 16) & 255} ${(value >> 8) & 255} ${value & 255}`;
}

function themeVariables(useMirror) {
  const vars = {};
  for (const name of THEMED) {
    for (const step of STEPS) {
      vars[`--c-${name}-${step}`] = toRgb(colors[name][useMirror ? mirror(step) : step]);
    }
  }
  return vars;
}

const themedColors = Object.fromEntries(
  THEMED.map((name) => [name, Object.fromEntries(STEPS.map((step) => [step, `rgb(var(--c-${name}-${step}) / <alpha-value>)`]))]),
);

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ...themedColors,
        // Not mirrored: solid buttons with white text need a dark fill in both themes.
        brand: colors.cyan,
        danger: colors.rose,
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Consolas", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [
    function themeVariablesPlugin({ addBase }) {
      addBase({
        ":root": { ...themeVariables(false), colorScheme: "dark" },
        ':root[data-theme="light"]': { ...themeVariables(true), colorScheme: "light" },
      });
    },
  ],
};
