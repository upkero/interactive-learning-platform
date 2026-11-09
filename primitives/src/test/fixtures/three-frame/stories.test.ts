import { describe, expect, it } from "vitest";
import { threeFrame } from "./index";
import { AddOne, AddTwo, AddZero } from "./ThreeFramePrimitive.stories";

describe("demo stories", () => {
  it("covers every example in the fixture definition", () => {
    const names = [AddOne, AddTwo, AddZero].map(
      (story) => story.args?.example ?? "add-two"
    );
    expect(names.sort()).toEqual(
      threeFrame.examples.map((example) => example.name).sort()
    );
  });
});
