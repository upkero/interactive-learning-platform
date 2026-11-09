// @vitest-environment node
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, describe, expect, it } from "vitest";
import stylelint from "stylelint";
import { designChecklist } from "./checklist";

const root = fileURLToPath(new URL("../..", import.meta.url));
const temp = mkdtempSync(join(tmpdir(), "grasp-design-test-"));
const nodeArgs = ["--experimental-strip-types"];
afterAll(() => rmSync(temp, { recursive: true, force: true }));

describe("design catalog", () => {
  it("has stable unique rule identifiers", () => {
    expect(designChecklist).toHaveLength(10);
    expect(new Set(designChecklist.map((rule) => rule.id)).size).toBe(
      designChecklist.length
    );
  });
  it("exports the actual runtime UI components deterministically without changing the working tree", () => {
    const target = join(temp, "catalog.json");
    const script = resolve(root, "scripts/export-catalog.ts");
    execFileSync(process.execPath, [...nodeArgs, script, target], {
      cwd: root,
    });
    const first = readFileSync(target, "utf8");
    execFileSync(process.execPath, [...nodeArgs, script, target], {
      cwd: root,
    });
    expect(readFileSync(target, "utf8")).toBe(first);
    const catalog = JSON.parse(first);
    expect(catalog.design.checklist).toHaveLength(10);
    expect(catalog.design.tokens).toContain("--g-color-accent");
    expect(catalog.design.uiExports).toEqual([
      "Button",
      "Slider",
      "StepControls",
      "Toggle",
    ]);
    expect(first).toBe(
      readFileSync(resolve(root, "dist/catalog.json"), "utf8")
    );
  });
  it("rejects a low-contrast visualization token", () => {
    const source = readFileSync(resolve(root, "src/tokens/tokens.css"), "utf8");
    const mutated = join(temp, "bad-tokens.css");
    writeFileSync(
      mutated,
      source.replace(/--g-viz-1:\s*#[\da-f]{6}/i, "--g-viz-1: #f0f0f0")
    );
    const result = spawnSync(
      process.execPath,
      [...nodeArgs, resolve(root, "scripts/check-contrast.ts"), mutated],
      { encoding: "utf8" }
    );
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("--g-viz-1");
  });
  it("rejects literal spacing, radius and motion duration outside token definitions", async () => {
    const result = await stylelint.lint({
      code: ".bad { padding: 13px; border-radius: 5px; transition: color 300ms; }",
      codeFilename: resolve(root, "src/Bad.module.css"),
      configFile: resolve(root, ".stylelintrc.json"),
    });
    expect(result.errored).toBe(true);
    expect(result.results[0].warnings).toHaveLength(3);
  });
});
