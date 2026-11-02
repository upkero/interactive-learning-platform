import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";

import { describe, expect, it } from "vitest";

import { findObviousDesignIssues } from "./code-check";
import { designChecklist } from "./checklist";
import { getPrimitives } from "../registry";

const root = process.cwd();
const catalogPath = `${root}/dist/catalog.json`;

describe("design checklist", () => {
  it("has stable, unique rule identifiers", () => {
    expect(designChecklist).toHaveLength(10);
    expect(new Set(designChecklist.map((rule) => rule.id)).size).toBe(
      designChecklist.length,
    );
  });

  it("flags two intentionally non-compliant widgets by checklist id", () => {
    const hardcodedWidget = `
      export function Widget() {
        return <button style={{ color: "#ffffff" }}>Next</button>;
      }
    `;
    const inaccessibleAnimatedWidget = `
      const styles = { animation: "pulse 1s ease" };
      export function Widget() {
        return <svg><circle /></svg>;
      }
    `;

    expect(findObviousDesignIssues(hardcodedWidget).map((issue) => issue.id)).toEqual([
      "DS-01",
      "DS-03",
      "DS-04",
    ]);
    expect(
      findObviousDesignIssues(inaccessibleAnimatedWidget).map((issue) => issue.id),
    ).toEqual(["DS-08", "DS-09"]);
  });

  it("exports a deterministic design catalog", () => {
    execFileSync(process.execPath, ["--experimental-strip-types", "scripts/export-catalog.ts"], {
      cwd: root,
    });
    const first = readFileSync(catalogPath, "utf8");
    execFileSync(process.execPath, ["--experimental-strip-types", "scripts/export-catalog.ts"], {
      cwd: root,
    });
    const catalog = JSON.parse(readFileSync(catalogPath, "utf8")) as {
      catalogVersion: number;
      design: { checklist: unknown[]; tokens: string[]; uiExports: string[] };
      primitives: { id: string }[];
    };

    expect(readFileSync(catalogPath, "utf8")).toBe(first);
    expect(catalog.catalogVersion).toBe(1);
    expect(catalog.design.checklist).toHaveLength(10);
    expect(catalog.design.tokens).toContain("--g-color-accent");
    expect(catalog.design.uiExports).toEqual([
      "Button",
      "ModeTabs",
      "Slider",
      "StepControls",
      "Toggle",
    ]);
    expect(catalog.primitives.map((primitive) => primitive.id)).toEqual(
      getPrimitives().map((primitive) => primitive.id),
    );
  });
});
