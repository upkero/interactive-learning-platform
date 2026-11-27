import { describe, expect, it } from "vitest";
import { sanitizeNextUrl } from "./sanitizeNext";

describe("sanitizeNextUrl", () => {
  it.each([
    ["/en/materials?scope=shared#top", "/en/materials?scope=shared#top"],
    ["/documents/example?step=2", "/ru/documents/example?step=2"],
    [null, "/ru/materials"],
  ])("keeps an internal return destination %s", (input, expected) => {
    expect(sanitizeNextUrl(input, "ru")).toBe(expected);
  });

  it.each([
    "https://example.test",
    "//example.test",
    "/\\example.test",
    "/\t/example.test",
    "/temporary/..//example.test",
  ])("falls back to local materials for %j", (input) => {
    expect(sanitizeNextUrl(input, "en")).toBe("/en/materials");
  });
});
