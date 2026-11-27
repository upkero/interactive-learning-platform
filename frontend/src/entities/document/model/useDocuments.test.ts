import { describe, expect, it } from "vitest";
import { getMaterialRoute, type MaterialOut } from "./useDocuments";

const material: MaterialOut = {
  document_id: "123",
  parts_failed: 0,
  parts_published: 1,
  parts_total: 1,
  role: "owner",
  shared_by_email: null,
  source_type: "pdf",
  status: "done",
  title: "Example",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("getMaterialRoute", () => {
  it("opens completed materials in the document viewer", () => {
    expect(getMaterialRoute(material)).toBe("/documents/123");
  });

  it("opens generating materials in the progress view", () => {
    expect(getMaterialRoute({ ...material, status: "generating" })).toBe(
      "/documents/123/progress"
    );
  });
});
