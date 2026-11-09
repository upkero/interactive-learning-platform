import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import postcss from "postcss";

const tokensPath = process.argv[2] ?? fileURLToPath(new URL("../src/tokens/tokens.css", import.meta.url));
const css = postcss.parse(readFileSync(tokensPath, "utf8"), { from: tokensPath });
const themes: Record<string, Record<string, string>> = { light: {}, dark: {} };

css.walkRules((rule) => {
  // Reduced-motion overrides are not theme color declarations.
  if (rule.parent?.type !== "root") return;
  const selectors = rule.selectors.map((selector) => selector.trim());
  for (const theme of ["light", "dark"] as const) {
    if (!selectors.includes(`[data-theme="${theme}"]`) && !(theme === "light" && selectors.includes(":root"))) continue;
    rule.walkDecls(/^--g-/, (decl) => { themes[theme][decl.prop] = decl.value.trim(); });
  }
});

function luminance(hex: string): number {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) throw new Error(`Expected a six-digit hex color: ${hex}`);
  const channels = hex.slice(1).match(/.{2}/g)!.map((part) => parseInt(part, 16) / 255).map((c) => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
function ratio(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

const pairs: [string, string, number][] = [
  ["--g-color-text", "--g-color-bg", 4.5], ["--g-color-text", "--g-color-surface", 4.5],
  ["--g-color-text-muted", "--g-color-bg", 4.5], ["--g-color-text-muted", "--g-color-surface", 4.5],
  ["--g-color-accent", "--g-color-bg", 4.5], ["--g-color-accent", "--g-color-surface", 4.5],
  ["--g-color-accent-contrast", "--g-color-accent", 4.5],
  ["--g-color-border", "--g-color-bg", 3], ["--g-color-border", "--g-color-surface", 3],
  ["--g-color-success", "--g-color-bg", 4.5], ["--g-color-danger", "--g-color-bg", 4.5],
  ...Array.from({ length: 6 }, (_, index): [string, string, number] => [`--g-viz-${index + 1}`, "--g-color-bg", 3]),
];
const failures: string[] = [];
for (const [theme, values] of Object.entries(themes)) for (const [foreground, background, minimum] of pairs) {
  if (!values[foreground] || !values[background]) {
    failures.push(`${theme}: missing ${!values[foreground] ? foreground : background}`);
    continue;
  }
  try {
    const value = ratio(values[foreground], values[background]);
    if (value < minimum) failures.push(`${theme}: ${foreground}/${background} = ${value.toFixed(2)}:1; expected ${minimum}:1`);
  } catch (error) { failures.push(`${theme}: ${String(error)}`); }
}
if (failures.length) {
  console.error(`Contrast check failed:\n- ${failures.join("\n- ")}`);
  process.exitCode = 1;
} else console.log("Contrast check passed for light and dark themes.");
