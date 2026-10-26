import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const tokensPath = fileURLToPath(
  new URL("../src/tokens/tokens.css", import.meta.url),
);
const css = readFileSync(tokensPath, "utf8");

const themes = ["light", "dark"];
const requiredTokens = [
  "--g-color-bg",
  "--g-color-surface",
  "--g-color-text",
  "--g-color-text-muted",
  "--g-color-accent",
  "--g-color-success",
  "--g-color-danger",
  "--g-viz-1",
  "--g-viz-2",
  "--g-viz-3",
  "--g-viz-4",
  "--g-viz-5",
  "--g-viz-6",
];

function relativeLuminance(hex) {
  const channels = hex
    .slice(1)
    .match(/.{2}/g)
    .map((part) => Number.parseInt(part, 16) / 255)
    .map((channel) =>
      channel <= 0.04045
        ? channel / 12.92
        : ((channel + 0.055) / 1.055) ** 2.4,
    );

  return (
    0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
  );
}

function contrastRatio(foreground, background) {
  const [lighter, darker] = [
    relativeLuminance(foreground),
    relativeLuminance(background),
  ].sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
}

function tokensFor(theme) {
  const selector = theme === "light" ? ":root," : '[data-theme="dark"]';
  const start = css.indexOf(selector);
  const end = css.indexOf("}\n", start);
  if (start === -1 || end === -1) {
    throw new Error(`Could not find ${theme} theme in ${tokensPath}`);
  }

  const declarations = css.slice(start, end);
  return Object.fromEntries(
    [...declarations.matchAll(/(--g-[\w-]+):\s*(#[\da-fA-F]{6})/g)].map(
      ([, name, value]) => [name, value],
    ),
  );
}

const failures = [];

for (const theme of themes) {
  const tokens = tokensFor(theme);
  for (const token of requiredTokens) {
    if (!tokens[token]) failures.push(`${theme}: missing ${token}`);
  }

  const textPairs = [
    ["--g-color-text", "--g-color-bg"],
    ["--g-color-text", "--g-color-surface"],
    ["--g-color-text-muted", "--g-color-bg"],
    ["--g-color-text-muted", "--g-color-surface"],
  ];
  const controlPairs = [
    ["--g-color-accent", "--g-color-bg"],
    ["--g-color-success", "--g-color-bg"],
    ["--g-color-danger", "--g-color-bg"],
  ];
  const visualizationPairs = ["--g-viz-1", "--g-viz-2", "--g-viz-3", "--g-viz-4", "--g-viz-5", "--g-viz-6"].map(
    (token) => [token, "--g-color-bg"],
  );

  for (const [foreground, background] of textPairs) {
    const ratio = contrastRatio(tokens[foreground], tokens[background]);
    if (ratio < 4.5) {
      failures.push(`${theme}: ${foreground}/${background} is ${ratio.toFixed(2)}:1; expected 4.5:1`);
    }
  }
  for (const [foreground, background] of [...controlPairs, ...visualizationPairs]) {
    const ratio = contrastRatio(tokens[foreground], tokens[background]);
    if (ratio < 3) {
      failures.push(`${theme}: ${foreground}/${background} is ${ratio.toFixed(2)}:1; expected 3:1`);
    }
  }
}

if (failures.length > 0) {
  console.error("Contrast check failed:\n- " + failures.join("\n- "));
  process.exitCode = 1;
} else {
  console.log("Contrast check passed for light and dark themes.");
}
