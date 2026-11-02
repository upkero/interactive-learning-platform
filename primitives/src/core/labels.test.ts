import { describe, expect, it, vi } from "vitest";

import en from "../i18n/en.json";
import ru from "../i18n/ru.json";
import { t } from "./labels";

describe("primitive labels", () => {
  it("keeps the ru and en key sets identical", () => {
    expect(Object.keys(ru).sort()).toEqual(Object.keys(en).sort());
  });

  it("resolves a label and interpolates named variables", () => {
    expect(t(en, "common.next")).toBe("Next");
    expect(t({ greeting: "Hello, {name}! You have {count} tasks." }, "greeting", {
      name: "Ada",
      count: 2,
    })).toBe("Hello, Ada! You have 2 tasks.");
  });

  it("keeps missing keys and variables visible to authors", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(t(en, "common.unknown")).toBe("common.unknown");
    expect(t({ greeting: "Hello, {name}!" }, "greeting")).toBe("Hello, {name}!");
    expect(warn).toHaveBeenCalledWith("Missing translation: common.unknown");
    warn.mockRestore();
  });
});
